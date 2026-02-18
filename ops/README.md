# Ops Scripts

Ce dossier contient uniquement des scripts shell d'exploitation/infra.

- `ops/cron-run-pipeline.sh`: execution cron locale du pipeline.
- `ops/aws/build_push_mongodb_rs_image.sh`: build/push de l'image MongoDB replica set.
- `ops/aws/deploy_mongodb_rs_terraform.sh`: deploiement Terraform MongoDB ECS.

Le code Python executable du pipeline reste dans `src/scripts/` et s'utilise via `poetry run ...`.
