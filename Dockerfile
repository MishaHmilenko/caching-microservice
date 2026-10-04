FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /usr/local/bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PATH="/app/.venv/bin:$PATH"

# Dependencies first so code changes don't invalidate the cached layer.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
RUN uv sync --frozen --no-dev

# Run unprivileged; /data holds the SQLite file and is meant to be a volume.
RUN useradd --system --create-home app && mkdir /data && chown app /data
USER app
ENV CACHE_DATABASE_URL=sqlite:////data/cache.db
VOLUME /data

EXPOSE 8000
HEALTHCHECK CMD python -c "import urllib.request as u; u.urlopen('http://localhost:8000/health')"
CMD ["cache-service"]
