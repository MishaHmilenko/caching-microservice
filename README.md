# Payload cache

A small FastAPI service that builds payloads from two lists of strings and caches the
expensive per-string "transformer" call in a database.

- `POST /payload` with `{"list_1": [...], "list_2": [...]}` → `201 {"id", "message"}`
  (`200` if the same payload already existed)
- `GET /payload/{id}` → `{"output": "A, X, B, Y, ..."}` (`404` if unknown)
- `GET /health`

The output is the transformed strings of both lists interleaved and joined with `", "`.
The stand-in transformer upper-cases (see `src/cache_service/transformer.py`).

## How caching works

- **Per-string cache** (`TransformedString` table): every distinct string is transformed at
  most once, ever. A request only sends strings it has not seen to the transformer, in a
  single batched call, and makes no call at all when everything is cached.
- **Payload id** is the SHA-256 of the canonical JSON of both lists, so a repeated request
  gets the same id and is answered from the `Payload` table without any transformer work.

## Run

```bash
docker compose up --build        # service on http://localhost:8000, data in a named volume
```

Locally:

```bash
uv sync
uv run cache-service             # or: uv run uvicorn cache_service.main:create_app --factory
```

Configuration: `CACHE_DATABASE_URL` (SQLAlchemy URL, default `sqlite:///./data/cache.db`).

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

```bash
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

## Decisions and shortcuts

- **`-H` for host.** The task lists `-h` for both `--host` and `--help`, which cannot coexist
  in argparse; `-h` stays help and the host gets `-H`.
- **Table creation on startup** (`create_all`) instead of migrations — fine for two tables,
  use Alembic once the schema evolves.
- **No in-flight de-duplication.** Two simultaneous requests with the same unseen strings can
  both call the transformer; the second insert loses the race and is resolved by retrying
  against the first one's rows. A per-key lock or single-flight would close this gap.
- **Input limits** (1000 items, 1000 chars each) keep queries and index keys bounded.
- **SQLite concurrency** is adequate for a single instance; use `CACHE_DATABASE_URL` with
  PostgreSQL for multiple replicas (the code uses no SQLite-specific features).
- The CLI imports the request model from the service package so both validate identically.
