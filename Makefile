.DEFAULT_GOAL := help

.PHONY: help up-ecs up-local down-local logs test run-pipeline run-pipeline-dry mongo-shell mongo-shell-root

DATE ?=
LOG_LEVEL ?= INFO

help:
	@printf "%s\n" \
		"Targets:" \
		"  up-ecs           Start stack (ECS/remote Mongo config) with build" \
		"  up-local         Start stack (local override) with build" \
		"  down-local       Stop local stack and remove volumes" \
		"  logs             Follow docker compose logs" \
		"  test             Run pytest" \
		"  run-pipeline     Run ETL pipeline (use DATE=YYYY-MM-DD LOG_LEVEL=INFO)" \
		"  run-pipeline-dry Run ETL pipeline in dry-run mode (no Mongo writes)" \
		"  mongo-shell      Open mongosh as app user (uses env vars/.env)" \
		"  mongo-shell-root Open mongosh as root user (uses env vars/.env)"

up-ecs:
	docker compose up --build

up-local:
	docker compose -f docker-compose.yml -f docker-compose.local.yml up --build

down-local:
	docker compose -f docker-compose.yml -f docker-compose.local.yml down -v

logs:
	docker compose logs -f --tail=200

test:
	poetry run pytest -vv src/tests

run-pipeline:
	poetry run forecast-pipeline $(if $(DATE),--date $(DATE),) --log-level $(LOG_LEVEL)

run-pipeline-dry:
	poetry run forecast-pipeline $(if $(DATE),--date $(DATE),) --dry-run --log-level $(LOG_LEVEL)

# App user (readWrite on $MONGO_DB). Override via .env if needed.
mongo-shell:
	docker exec -it forecast-mongo mongosh "mongodb://$${MONGO_APP_USERNAME:-forecast_app}:$${MONGO_APP_PASSWORD:-forecast_app_password}@127.0.0.1:27017/$${MONGO_DB:-forecast_2_0}?authSource=$${MONGO_DB:-forecast_2_0}"

# Root user (admin). Override via .env if needed.
mongo-shell-root:
	docker exec -it forecast-mongo mongosh "mongodb://$${MONGO_ROOT_USERNAME:-root}:$${MONGO_ROOT_PASSWORD:-rootpassword}@127.0.0.1:27017/admin"
