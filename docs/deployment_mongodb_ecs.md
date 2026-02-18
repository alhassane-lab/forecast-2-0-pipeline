# Deployment MongoDB ECS

Ce projet est deploye sur AWS ECS (Fargate) avec MongoDB replica set sur ECS.

## Prerequis

- Docker Desktop (build image locale)
- AWS CLI configuree (`aws sts get-caller-identity`)
- Acces ECR / ECS / S3
- Cluster ECS: `forecast-prod-mongo-cluster`
- Task definitions:
  - `forecast-pipeline-ecs:3` (pipeline ETL -> S3 processed -> Mongo)
  - `forecast-pipeline-ecs:4` (migration S3 processed -> Mongo)

## Variables attendues

Dans `.env` (local):
- `AWS_PROFILE=default`
- `AWS_REGION=eu-west-1`
- `AWS_DEFAULT_REGION=eu-west-1`
- `S3_RAW_BUCKET`
- `S3_PROCESSED_BUCKET`
- `MONGODB_URI` (si run local depuis une machine qui resolv `mongo.internal`)

## Run local (Poetry)

```bash
poetry install
poetry run forecast-pipeline --log-level INFO
```

## Run ECS one-shot (pipeline)

```bash
aws ecs run-task \
  --cluster forecast-prod-mongo-cluster \
  --launch-type FARGATE \
  --task-definition forecast-pipeline-ecs:3 \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-01ec17ee34fdbcbf6,subnet-0403a7c24fb649b8c,subnet-0631d4f7da0f7a822],securityGroups=[sg-062056db10833656d],assignPublicIp=ENABLED}" \
  --region eu-west-1
```

## Run ECS one-shot (migration S3 -> Mongo)

```bash
aws ecs run-task \
  --cluster forecast-prod-mongo-cluster \
  --launch-type FARGATE \
  --task-definition forecast-pipeline-ecs:4 \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-01ec17ee34fdbcbf6,subnet-0403a7c24fb649b8c,subnet-0631d4f7da0f7a822],securityGroups=[sg-062056db10833656d],assignPublicIp=ENABLED}" \
  --region eu-west-1
```

## Notes d'architecture runtime

- Entree conteneur pipeline: `python -m main`
- Entree conteneur migration: `python -m scripts.migrate_to_mongodb --input-s3-latest`
- S3 processed: `s3://greenandcoop-processed-data/processed/weather_data_YYYYMMDD_HHMMSS.json`
- Les noms `mongo-*.mongo.internal` sont resolvables seulement dans le VPC AWS.

## Observabilite et planification

- Logs JSON `loguru` + EMF CloudWatch (`Namespace=Forecast2Pipeline`).
- Rule EventBridge active:
  - `forecast-pipeline-weekly`
  - `cron(0 22 ? * WED *)` (UTC)
  - cible `forecast-pipeline-ecs:3`
