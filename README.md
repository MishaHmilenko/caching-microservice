# Payload cache

A small async FastAPI service that builds payloads from two lists of strings and avoids
repeating the expensive per-string "transformer" call. Postgres is the source of truth;
Redis is a read-through cache in front of it.

- `POST /payload` with `{"list_1": [...], "list_2": [...]}` → `201 {"id", "message"}`
  (`200` if the same payload already existed)
- `GET /payload/{id}` → `{"output": "A, X, B, Y, ..."}` (`404` if unknown)
- `GET /health`

The output is the transformed strings of both lists interleaved and joined with `", "`.
The stand-in transformer upper-cases (`src/cache_service/transformer.py`).

## How caching works

- **Per-string results**: every distinct string is transformed at most once, ever. A request
  sends only unseen strings to the transformer in a single batched call, and makes no call
  when everything is known.
- **Payload id** is the SHA-256 of the canonical JSON of both lists, so a repeated request
  gets the same id and is answered without any transformer work.
- **Two storage tiers**: lookups go Redis → Postgres. Misses are filled from Postgres, and
  writes go to Postgres first and then Redis, so the cache never holds data the database
  lacks. Cache entries expire (`CACHE_CACHE_TTL_SECONDS`); losing Redis costs latency only.

## Architecture

```
routes (api/)  →  PayloadService  →  interfaces (StringRepository, PayloadRepository, Transformer)
                                           ▲
                    Cached*Repository ─────┤  (decorator over a repository + Cache)
                    Sql*Repository ────────┘  (SQLAlchemy async, Postgres)
                    RedisCache, UppercaseTransformer
```

```
src/cache_service/
  api/             HTTP layer: routes, request/response schemas, FastAPI dependency
  services/        PayloadService: use cases, depends only on domain interfaces
  domain/          interfaces.py (contracts) and payload.py (pure rules: id, interleaving)
  repositories/    sql.py (Postgres) and cached.py (Redis decorator) implementations
  infrastructure/  database setup and ORM models, Redis cache, transformer client
  core/            configuration
  main.py          composition root: the only place that picks implementations
```

Dependencies point inward: `api → services → domain ← repositories/infrastructure`.

## Run

```bash
docker compose up --build        # service on http://localhost:8000 with Postgres and Redis
```

Locally (needs Postgres and Redis; defaults are in `config.py`, override with
`CACHE_DATABASE_URL` / `CACHE_REDIS_URL`):

```bash
uv sync
uv run cache-service
```

## CLI

```bash
uv run cache-cli -j '{"list_1": ["a", "b"], "list_2": ["c", "d"]}' -r 3
echo '{"list_1": ["a"], "list_2": ["b"]}' | uv run cache-cli -i - -o result.jsonl
```

| Option | Meaning |
| --- | --- |
| `-H, --host URL` | Server base URL (default `http://localhost:8000`) |
| `-r, --repeat N` | Number of iterations (default 1) |
| `-i, --input FILE\|-` | JSON request body from a file or stdin |
| `-j, --json JSON` | JSON request body inline |
| `-o, --output FILE\|-` | Where to write results (default stdout) |

Exactly one of `--input` / `--json` is required. Each iteration creates the payload, reads it
back, and writes one `{"id", "output"}` JSON line. Exit code is non-zero on any error.

## Tests

The suite is end-to-end: it runs the real app against a separate Postgres and Redis
(`docker-compose.test.yml`, ports 5433/6380, data in tmpfs). Only the external transformer is
replaced, so its calls can be counted.

```bash
make test        # starts the test backing services, runs pytest, tears them down
make lint
```

To iterate faster: `make test-up`, then `uv run pytest` as often as needed, then `make test-down`.
Override the targets with `TEST_DATABASE_URL` / `TEST_REDIS_URL`.

## Decisions and shortcuts

- **`-H` for host.** The task lists `-h` for both `--host` and `--help`, which cannot coexist
  in argparse; `-h` stays help and the host gets `-H`.
- **Redis next to Postgres.** The task asks for SQLite or PostgreSQL storage; Postgres holds
  all durable data, and Redis is an optional accelerator, not a requirement for correctness.
- **Table creation on startup** (`create_all`) instead of migrations — fine for two tables;
  adopt Alembic once the schema evolves.
- **No in-flight de-duplication.** Two simultaneous requests with the same unseen strings can
  both call the transformer. Inserts use `ON CONFLICT DO NOTHING`, so the outcome is still
  correct and exactly one request reports `201`; a per-key lock would save the wasted call.
- **Strings are keyed by SHA-256** in Postgres, since long multibyte text can exceed B-tree
  entry limits.
- **Input limits** (1000 items, 1000 chars each) bound one request's work and key sizes.
- The CLI imports the request model from the service package so both validate identically.
