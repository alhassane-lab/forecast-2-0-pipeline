.DEFAULT_GOAL := help

.PHONY: help up logs test run-pipeline run-pipeline-dry

DATE ?=
LOG_LEVEL ?= INFO

help:
	@printf "%s\n" \
		"Targets:" \
		"  up               Start pipeline container with build" \
		"  logs             Follow docker compose logs" \
		"  test             Run pytest" \
		"  run-pipeline     Run ETL pipeline (use DATE=YYYY-MM-DD LOG_LEVEL=INFO)" \
		"  run-pipeline-dry Run ETL pipeline in dry-run mode (no Mongo writes)"

up:
	docker compose up --build

logs:
	docker compose logs -f --tail=200

test:
	poetry run pytest -vv src/tests

run-pipeline:
	poetry run forecast-pipeline $(if $(DATE),--date $(DATE),) --log-level $(LOG_LEVEL)

run-pipeline-dry:
	poetry run forecast-pipeline $(if $(DATE),--date $(DATE),) --dry-run --log-level $(LOG_LEVEL)
