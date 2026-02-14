.DEFAULT_GOAL := help

.PHONY: help up-atlas up-local down-local logs test mongo-shell mongo-shell-root

help:
	@printf "%s\n" \
		"Targets:" \
		"  up-atlas         Start stack (Atlas config) with build" \
		"  up-local         Start stack (local override) with build" \
		"  down-local       Stop local stack and remove volumes" \
		"  logs             Follow docker compose logs" \
		"  test             Run pytest" \
		"  mongo-shell      Open mongosh as app user (uses env vars/.env)" \
		"  mongo-shell-root Open mongosh as root user (uses env vars/.env)"

up-atlas:
	docker compose up --build

up-local:
	docker compose -f docker-compose.yml -f docker-compose.local.yml up --build

down-local:
	docker compose -f docker-compose.yml -f docker-compose.local.yml down -v

logs:
	docker compose logs -f --tail=200

test:
	pytest -vv src/tests

# App user (readWrite on $MONGO_DB). Override via .env if needed.
mongo-shell:
	docker exec -it forecast-mongo mongosh "mongodb://$${MONGO_APP_USERNAME:-forecast_app}:$${MONGO_APP_PASSWORD:-forecast_app_password}@127.0.0.1:27017/$${MONGO_DB:-forecast_2_0}?authSource=$${MONGO_DB:-forecast_2_0}"

# Root user (admin). Override via .env if needed.
mongo-shell-root:
	docker exec -it forecast-mongo mongosh "mongodb://$${MONGO_ROOT_USERNAME:-root}:$${MONGO_ROOT_PASSWORD:-rootpassword}@127.0.0.1:27017/admin"
