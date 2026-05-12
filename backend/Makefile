.PHONY: install run migrate migration test lint format shell clean

install:
	docker-compose build

up:
	docker-compose up -d

db:
	docker-compose exec -it db psql -U elevare -d elevare_db

down:
	docker-compose down $(if $(V),--volumes,)

logs:
	docker-compose logs -f api

migrate:
	docker-compose exec api alembic upgrade head

migration:
	docker-compose exec api alembic revision --autogenerate -m "$(message)"

status:
	docker-compose exec api alembic current

test:
	docker-compose exec api pytest tests/ -v --cov=app --cov-report=term-missing

lint:
	docker-compose exec api ruff check . && black --check . && isort --check-only .

format:
	docker-compose exec api black . && isort .

shell:
	docker-compose exec api python -c "import asyncio; from app.core.database import engine; print('DB connected')"

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -name "*.pyc" -delete
