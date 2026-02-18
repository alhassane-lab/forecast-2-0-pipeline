# Deployment MongoDB Atlas

Ce projet est deploie en mode conteneur Docker, avec MongoDB Atlas comme destination.
L'infra AWS managée (ECS/Terraform) n'est pas requise.

## Prerequis

- Docker Desktop
- Acces AWS S3 pour lire les donnees brutes
- URI MongoDB Atlas valide (`MONGODB_URI`)

## Variables attendues

Dans `.env`:

- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_REGION` (par defaut `eu-west-1`)
- `S3_RAW_BUCKET`
- `S3_PROCESSED_BUCKET`
- `MONGODB_URI`

## Run local (Poetry)

```bash
poetry install
poetry run forecast-pipeline --log-level INFO
```

## Run Docker Compose

```bash
docker compose build
# Run reel (par defaut) + MongoDB Atlas (MONGODB_URI requis dans .env)
docker compose up --build
```

## Run Docker Compose (Mongo local "clean", sans profiles)

```bash
# Lance Mongo local + pipeline via un override compose
docker compose -f docker-compose.yml -f docker-compose.local.yml up --build
```

## Smoke checks

```bash
poetry run forecast-pipeline --help
docker run --rm forecast-2-0-pipeline:dev --help
pytest src/tests
```

## Notes d'architecture runtime

- Import path unifie autour de `src` comme racine Python (`pipeline`, `loaders`, `utils`).
- Entree conteneur: `python -m main`.
- `InfoClimatExtractor.extract_from_local()` permet les tests locaux sans dependance reseau.

## AWS credentials (local)

Deux options:
- Recommande: `AWS_PROFILE` + montage `${HOME}/.aws` (deja configure dans `docker-compose.yml`).
- Alternative: `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` dans `.env` (moins securise).

## Notes Compass (Atlas)

Si tu te connectes a Atlas avec un user limite a `readWrite` sur un seul DB, Mongo Compass peut afficher "aucune database" dans la liste (il manque la permission `listDatabases`). Dans ce cas:
- connecte-toi avec un user admin pour verifier rapidement, ou
- ajoute un role/permission permettant `listDatabases` (ou `readAnyDatabase`) selon ton besoin.

## Observabilité et planification

- Les logs de `loguru`, enrichis par `set_run_context`, sont sérialisés en JSON (`LOG_FORMAT=json`) et incluent `stage`, `run_id`, `target_date`, `records_*`, `error_rate`, `duration_seconds` et `dry_run`. `utils.monitoring.emit_pipeline_metrics` imprime une ligne EMF CloudWatch à chaque exécution (namespace `Forecast2Pipeline`, dims `env` + `cluster`) : configure un log group ECS/CloudWatch pour transformer ces lignes en métriques sans déployer d’agent supplémentaire.
- Le fichier `logs/pipeline_status.json` donne un résumé exploitable par un job externe (CI, DataDog, Airflow) : `status`, `duration_seconds`, `records_loaded`, `records_loaded_simulated`.
- Le script `scripts/cron-run-pipeline.sh` automatise un run quotidien depuis un Cron Linux : il source `.env`, génère `RUN_ID` si absent, calcule la date (sans argument, hier UTC) et lance `docker compose run --rm pipeline --date ...`. Ajoute par exemple la ligne suivante à `crontab -e` :
  ```
  0 5 * * * /bin/bash /path/to/forecast-2-0-pipeline/scripts/cron-run-pipeline.sh >> /path/to/forecast-2-0-pipeline/logs/cron.log 2>&1
  ```
