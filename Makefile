TEST_COMPOSE = docker compose -f docker-compose.test.yml

.PHONY: test test-up test-down lint

test-up:
	$(TEST_COMPOSE) up -d --wait

test-down:
	$(TEST_COMPOSE) down -v

# Starts the isolated test database/cache, runs the suite, and always tears them down.
test: test-up
	uv run pytest; status=$$?; $(TEST_COMPOSE) down -v; exit $$status

lint:
	uv run ruff check . && uv run ruff format --check .
