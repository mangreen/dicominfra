.PHONY: sync fmt lint typecheck test test-int check up down audit

sync:
	uv sync

fmt:
	uv run ruff format .

lint:
	uv run ruff format --check .
	uv run ruff check .

typecheck:
	uv run mypy

test:
	uv run pytest -m "not integration"

# 需要先 `make up`，並設定好 TEST_DATABASE_URL / TEST_AMQP_URL（見 .env.example）
test-int:
	uv run pytest -m integration

check: lint typecheck test

up:
	docker compose up -d --wait

down:
	docker compose down

audit:
	uv run pip-audit
