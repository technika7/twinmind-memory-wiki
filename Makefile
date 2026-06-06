.PHONY: up down build test lint logs seed

# ── Docker ────────────────────────────────────────────────────
up:
	docker-compose up --build -d

down:
	docker-compose down -v

build:
	docker-compose build

logs:
	docker-compose logs -f

logs-api:
	docker-compose logs -f api

logs-worker:
	docker-compose logs -f worker

# ── Database ──────────────────────────────────────────────────
migrate:
	docker-compose exec api alembic upgrade head

migration:
	docker-compose exec api alembic revision --autogenerate -m "$(msg)"

# ── Testing ───────────────────────────────────────────────────
test:
	docker-compose exec api pytest tests/ -v --tb=short

test-unit:
	docker-compose exec api pytest tests/unit/ -v --tb=short

test-integration:
	docker-compose exec api pytest tests/integration/ -v --tb=short

test-e2e:
	docker-compose exec api pytest tests/e2e/ -v --tb=short

test-cov:
	docker-compose exec api pytest tests/ -v --cov=src --cov-report=term-missing

# ── Utilities ─────────────────────────────────────────────────
seed:
	docker-compose exec api python -m scripts.seed_data

shell:
	docker-compose exec api python -c "import IPython; IPython.start_ipython()" 2>/dev/null || docker-compose exec api python
