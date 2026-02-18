# Audit ECS-only - 2026-02-18

## Objectif
Supprimer les reliquats Atlas et aligner le projet sur une architecture MongoDB ECS only.

## Constat initial
- README: sections et prerequis encore centres Atlas.
- Makefile: target `up-atlas`.
- Docker compose: commentaires Atlas.
- Scripts/docs: mentions Atlas (`migrate_to_mongodb.py`, `docs/mongodb_migration.md`, ancien guide `docs/deployment_mongodb_atlas.md`).
- Monitoring: dimension `cluster` par defaut = `atlas`.

## Corrections appliquees
- Code:
  - `src/utils/monitoring.py`: default cluster passe a `ecs`.
  - `src/scripts/migrate_to_mongodb.py`: docstring neutralisee (MongoDB ECS/local).
- Runtime/local:
  - `.env`: suppression des cles statiques AWS, passage a `AWS_PROFILE=default` + regions explicites.
  - `env.example`: suppression exemple `mongodb+srv`, exemples ECS/local Mongo.
  - `docker-compose.yml`: commentaires generalises ECS/local.
  - `Makefile`: target `up-ecs` remplace `up-atlas`.
- Documentation:
  - `README.md`: sections Atlas remplacees par ECS/remote.
  - `README.md`: run ECS one-shot mis a jour (`forecast-pipeline-ecs:3`) + migration ECS (`:4`).
  - `docs/mongodb_migration.md`: import cible MongoDB ECS replica set.
  - ancien guide Atlas supprime: `docs/deployment_mongodb_atlas.md`.
  - nouveau guide ajoute: `docs/deployment_mongodb_ecs.md`.

## Validation operationnelle
- Pipeline ECS execute avec succes (task `forecast-pipeline-ecs:3`, exit code 0).
- Migration S3 processed -> Mongo ECS executee avec succes (task `forecast-pipeline-ecs:4`, exit code 0).
- Schedule hebdomadaire actif:
  - Rule: `forecast-pipeline-weekly`
  - Expression: `cron(0 22 ? * WED *)` (UTC)
  - Cible ECS: `forecast-pipeline-ecs:3`

## Optimisations architecture recommandees (prochaine iteration)
- Remplacer EventBridge Rule par EventBridge Scheduler avec timezone explicite (`Europe/Paris`) si besoin metier "22h locale".
- Versionner les images ECR avec tags immuables (`vYYYYMMDD-HHMM`) et garder `latest` seulement pour dev.
- Exporter/archiver les rapports `migration_report_*.json` vers S3 pour audit trail centralise.
- Ajouter une task definition dediee "migration" (famille separee) pour eviter de mixer run pipeline/migration.
