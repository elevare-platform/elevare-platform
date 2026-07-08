.PHONY: help deploy logs-api logs-worker logs-beat logs-db shell-db ps restart-api restart-worker restart-beat down up

help:
	@echo "Elevare Production Operations"
	@echo ""
	@echo "Deployment:"
	@echo "  make deploy          - Full deploy (pull, build, migrate, restart)"
	@echo ""
	@echo "Logs:"
	@echo "  make logs-api        - Tail API logs"
	@echo "  make logs-worker     - Tail Celery worker logs"
	@echo "  make logs-beat       - Tail Celery beat logs"
	@echo "  make logs-db         - Tail database logs"
	@echo ""
	@echo "Database:"
	@echo "  make shell-db        - Enter PostgreSQL shell"
	@echo ""
	@echo "Container Management:"
	@echo "  make ps              - List running containers"
	@echo "  make restart-api     - Restart API container"
	@echo "  make restart-worker  - Restart Celery worker"
	@echo "  make restart-beat    - Restart Celery beat"
	@echo "  make down            - Stop all containers"
	@echo "  make up              - Start all containers"

deploy:
	@bash deploy.sh

logs-api:
	@docker compose -f docker-compose.prod.yml logs -f api

logs-worker:
	@docker compose -f docker-compose.prod.yml logs -f celery_worker

logs-beat:
	@docker compose -f docker-compose.prod.yml logs -f celery_beat

logs-db:
	@docker compose -f docker-compose.prod.yml logs -f db

shell-db:
	@docker exec -it elevare-db psql -U elevare -d elevare_db

ps:
	@docker compose -f docker-compose.prod.yml ps

restart-api:
	@docker compose -f docker-compose.prod.yml restart api

restart-worker:
	@docker compose -f docker-compose.prod.yml restart celery_worker

restart-beat:
	@docker compose -f docker-compose.prod.yml restart celery_beat

down:
	@docker compose -f docker-compose.prod.yml down

up:
	@docker compose -f docker-compose.prod.yml up -d
