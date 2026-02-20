# Documentation Finale - Forecast 2.0 Pipeline

## Sommaire
- [1. Objectif du projet](#sec-1)
- [2. Architecture globale](#sec-2)
- [3. Stack technique](#sec-3)
- [4. Structure du dépôt](#sec-4)
- [5. Pipeline applicatif détaillé](#sec-5)
- [51. Orchestration (`src/main.py`)](#sec-51)
- [52. Gestion de la date](#sec-52)
- [53. Gestion des erreurs](#sec-53)
- [6. Extraction des données](#sec-6)
- [61. InfoClimat (`src/pipeline/extractors/infoclimat_extractor.py`)](#sec-61)
- [62. Weather Underground (`src/pipeline/extractors/wunderground_extractor.py`)](#sec-62)
- [7. Harmonisation et validation](#sec-7)
- [71. Harmonisation (`src/pipeline/transformers/data_harmonizer.py`)](#sec-71)
- [72. Validation (`src/pipeline/transformers/data_validator.py`)](#sec-72)
- [73. Qualité (`src/pipeline/transformers/quality_checker.py`)](#sec-73)
- [8. Chargement et modèle MongoDB](#sec-8)
- [81. Loader MongoDB (`src/loaders/mongodb_loader.py`)](#sec-81)
- [82. Schéma cible (`src/config/mongodb_schema.json`)](#sec-82)
- [9. CLI et scripts d'exploitation applicative](#sec-9)
- [91. Entrée principale](#sec-91)
- [92. Scripts spécialisés](#sec-92)
- [10. Conteneurisation](#sec-10)
- [101. Conteneur pipeline (`Dockerfile`)](#sec-101)
- [102. Compose principal (`docker-compose.yml`)](#sec-102)
- [103. Compose local Mongo (`docker-compose.local.yml`)](#sec-103)
- [104. Makefile](#sec-104)
- [11. Infrastructure AWS (Terraform)](#sec-11)
- [111. Composants déployés](#sec-111)
- [112. Sauvegardes (AWS Backup)](#sec-112)
- [113. Monitoring AWS](#sec-113)
- [114. Backend Terraform](#sec-114)
- [12. Opérations AWS et runbooks](#sec-12)
- [121. Build/push image MongoDB RS](#sec-121)
- [122. Déploiement infra MongoDB ECS](#sec-122)
- [123. Gestion utilisateur applicatif MongoDB ECS](#sec-123)
- [124. Planification pipeline](#sec-124)
- [13. Observabilité applicative](#sec-13)
- [14. Sécurité](#sec-14)
- [15. Tests et qualité logicielle](#sec-15)
- [16. Configuration environnement](#sec-16)
- [17. Procédures de déploiement](#sec-17)
- [171. Local (pipeline + mongo local)](#sec-171)
- [172. Pipeline avec Mongo distant (ECS/Atlas)](#sec-172)
- [173. Infra AWS MongoDB ECS](#sec-173)
- [18. Troubleshooting](#sec-18)
- [181. `MONGODB_URI non définie`](#sec-181)
- [182. `Server selection timed out`](#sec-182)
- [183. `command usersInfo requires authentication`](#sec-183)
- [184. Subscription SNS non reçue](#sec-184)
- [19. Documents complémentaires](#sec-19)
- [20. État actuel (référence opérationnelle)](#sec-20)


<a id="sec-1"></a>
## 1. Objectif du projet

Forecast 2.0 Pipeline est une chaîne Data Engineering qui couvre de bout en bout :
- l'extraction de données météo multi-sources (InfoClimat, Weather Underground),
- le stockage de données brutes et transformées sur S3,
- l'harmonisation vers un schéma unifié MongoDB,
- la validation qualité et le calcul de métriques de complétude,
- le chargement vers MongoDB (local ou ECS),
- l'observabilité (logs, rapports, métriques EMF, alarmes CloudWatch),
- l'exploitation production (conteneurs, Terraform, backups, monitoring).

Le projet est orienté production avec exécution locale Docker et déploiement AWS ECS.

<a id="sec-2"></a>
## 2. Architecture globale

### 2.1 Flux logique

`Airbyte/Raw -> S3 Raw -> Extract -> Harmonize -> Validate -> Save Processed S3 -> Load MongoDB -> Reports + Metrics`

### 2.2 Composants principaux

- Sources : exports Airbyte en JSON/JSONL (InfoClimat et Weather Underground).
- Stockage brut : bucket S3 raw (`S3_RAW_BUCKET`).
- ETL Python : orchestré par `src/main.py`.
- Stockage transformé : bucket S3 processed (`S3_PROCESSED_BUCKET`, préfixe `processed/`).
- Stockage cible : MongoDB (`weather_measurements` dans `forecast_2_0`).
- Observabilité app : logs `loguru`, rapports JSON, métriques EMF.
- Observabilité infra : CloudWatch Logs/Alarms + SNS.
- Infra AWS : ECS Fargate, Cloud Map, EBS managé, Secrets Manager, VPC endpoints, AWS Backup.

<a id="sec-3"></a>
## 3. Stack technique

### 3.1 Langage et packaging

- Python `^3.10` (runtime Docker en `3.11-slim`).
- Poetry (`pyproject.toml`) avec scripts CLI.

### 3.2 Librairies métier clés

- `boto3`, `botocore` : accès S3 et services AWS.
- `pymongo`, `dnspython`, `certifi` : connexion et opérations MongoDB.
- `pydantic`, `jsonschema` : validation/config.
- `loguru`, `python-json-logger` : logs structurés.
- `tenacity` : base de retry côté utilitaires.

### 3.3 Dev/Test/Qualité

- `pytest`, `pytest-cov`, `pytest-mock`, `pytest-asyncio`.
- `black`, `flake8`, `mypy`, `isort`, `pylint`.

<a id="sec-4"></a>
## 4. Structure du dépôt

- `src/main.py` : orchestrateur du pipeline complet.
- `src/pipeline/extractors/` : extracteurs InfoClimat / Weather Underground.
- `src/pipeline/transformers/` : harmonisation, validation, qualité.
- `src/loaders/` : chargement MongoDB et S3 processed.
- `src/scripts/` : scripts unitaires (transform, migrate, CRUD, latence).
- `src/config/` : configuration pipeline, schéma MongoDB, métadonnées stations.
- `infra/terraform/mongodb-ecs/` : stack MongoDB ECS + monitoring + backup.
- `ops/` : scripts d'exploitation (cron, build image, deploy Terraform, création user app).
- `docker/` : artefacts conteneur MongoDB RS et init local.
- `docs/` : audits, guides migration et déploiement.

<a id="sec-5"></a>
## 5. Pipeline applicatif détaillé

<a id="sec-51"></a>
## 5.1 Orchestration (`src/main.py`)

Le pipeline exécute les étapes suivantes dans l'ordre :

1. `extract_data()`
- Lit InfoClimat et Weather Underground via S3 (ou fallback date récente disponible).
- Alimente les compteurs `records_extracted`.

2. `transform_data()`
- Convertit chaque record source vers un format unifié MongoDB (`DataHarmonizer`).
- Comptabilise les rejets d'harmonisation.

3. `validate_data()`
- Applique les règles métier (`DataValidator`).
- Sépare valide/rejeté, enrichit `data_quality`.

4. `save_validated_to_s3()`
- Persiste le lot validé dans `s3://<processed-bucket>/processed/weather_data_YYYYMMDD_HHMMSS.json`.

5. `load_data()`
- Charge MongoDB via `MongoDBLoader.bulk_insert()`.
- En mode `--dry-run`, simule sans écrire.

6. `generate_quality_report()`
- Produit `logs/quality_report_*.json`.

7. Finalisation
- Écrit `logs/pipeline_status.json`.
- Émet métriques EMF via `emit_pipeline_metrics()`.

<a id="sec-52"></a>
## 5.2 Gestion de la date

- Si `--date` absent, la date cible est J-1 UTC.
- Les extracteurs essaient le dernier fichier de la date puis fallback dernier fichier disponible.

<a id="sec-53"></a>
## 5.3 Gestion des erreurs

- Les erreurs par source sont collectées dans `stats["errors"]`.
- En cas d'exception globale : statut `FAILED`, métriques tout de même émises.
- Code de sortie CLI : `0` sans erreurs, `1` sinon.

<a id="sec-6"></a>
## 6. Extraction des données

<a id="sec-61"></a>
## 6.1 InfoClimat (`src/pipeline/extractors/infoclimat_extractor.py`)

- Lit des `.jsonl` depuis `airbyte-sync/infoclimat/data_infoclimat/`.
- Parse `_airbyte_data.hourly` par station.
- Utilise `stations_metadata.json` pour enrichir localisation/station.
- Nettoie timestamps et structure les mesures brutes.

<a id="sec-62"></a>
## 6.2 Weather Underground (`src/pipeline/extractors/wunderground_extractor.py`)

- Lit le dernier `.jsonl` par station dans `airbyte-sync/wunderground/<folder>/`.
- Parse `_airbyte_data` et convertit les champs numériques.
- Enrichit avec métadonnées station (matériel, software, géographie).

<a id="sec-7"></a>
## 7. Harmonisation et validation

<a id="sec-71"></a>
## 7.1 Harmonisation (`src/pipeline/transformers/data_harmonizer.py`)

- Produit un document cible avec blocs :
  - `station`,
  - `timestamp`,
  - `measurements` (structure `{ value, unit }`),
  - `data_quality`,
  - `metadata`.
- Normalise la direction du vent WU (cardinal -> degrés).
- Gère plusieurs formats timestamp (ISO, formats US AM/PM).
- Crée `station.location_geo` GeoJSON pour index 2dsphere.

<a id="sec-72"></a>
## 7.2 Validation (`src/pipeline/transformers/data_validator.py`)

- Vérifie champs obligatoires (station, timestamp, localisation).
- Valide plages de mesures (température, humidité, pression, etc.).
- Vérifie cohérences métier :
  - `dewpoint <= temperature`,
  - `wind_gust >= wind_speed`.
- Calcule `completeness_score` et liste des champs manquants.
- Mode strict optionnel (`validation.strict_mode`).

<a id="sec-73"></a>
## 7.3 Qualité (`src/pipeline/transformers/quality_checker.py`)

Génère un rapport agrégé avec :
- résumé exécution et taux de rejet,
- stats par station et réseau,
- complétude par champ,
- couverture temporelle,
- distribution des scores qualité,
- anomalies détectées (limitée à 100).

<a id="sec-8"></a>
## 8. Chargement et modèle MongoDB

<a id="sec-81"></a>
## 8.1 Loader MongoDB (`src/loaders/mongodb_loader.py`)

- Lit la connexion depuis `MONGODB_URI` (obligatoire hors dry-run).
- Supporte TLS configurable via env (`MONGODB_TLS`, `MONGODB_TLS_ALLOW_INVALID_CERTS`).
- Crée les index :
  - unique : `station.id + timestamp`,
  - recherche : `station.network + timestamp`,
  - géospatial : `station.location_geo` (`2dsphere`).
- Supprime les doublons existants avant création index unique.
- Modes : `insert_many` et `upsert`.

<a id="sec-82"></a>
## 8.2 Schéma cible (`src/config/mongodb_schema.json`)

Collection principale : `weather_measurements`.

Structure métier :
- `station` (id, réseau, localisation, matériel éventuel),
- `timestamp`,
- `measurements`,
- `data_quality`,
- `metadata`.

<a id="sec-9"></a>
## 9. CLI et scripts d'exploitation applicative

<a id="sec-91"></a>
## 9.1 Entrée principale

- `poetry run forecast-pipeline --date YYYY-MM-DD --log-level INFO [--dry-run]`

<a id="sec-92"></a>
## 9.2 Scripts spécialisés

- Transformation only :
  - `poetry run transform-mongodb --source-mode s3 --date 2026-02-18`
  - `poetry run transform-mongodb --source-mode local --infoclimat-file ... --wunderground-file ...`

- Migration Mongo :
  - `poetry run migrate-mongodb --input data/processed/mongodb_ready_records.json`
  - `poetry run migrate-mongodb --input-s3-date 2026-02-18`
  - `poetry run migrate-mongodb --upsert`

- CRUD smoke :
  - `poetry run mongodb-crud`

- Latence requêtes :
  - `poetry run latency-report --station-id ILAMAD25 --date 2026-02-18 --iterations 10`

<a id="sec-10"></a>
## 10. Conteneurisation

<a id="sec-101"></a>
## 10.1 Conteneur pipeline (`Dockerfile`)

- Base : `python:3.11-slim`.
- Installe Poetry, dépendances `main`.
- Copie `src/` uniquement.
- EntryPoint : `python -m main`.

<a id="sec-102"></a>
## 10.2 Compose principal (`docker-compose.yml`)

Service `pipeline` :
- image build locale,
- injecte env AWS/Mongo,
- monte `./logs` et `${HOME}/.aws` (read-only),
- commande défaut `--log-level INFO`.

<a id="sec-103"></a>
## 10.3 Compose local Mongo (`docker-compose.local.yml`)

Ajoute :
- service `mongo` (image `mongo:6`),
- init script `docker/mongo-init/10-create-app-user.js` (create/update user applicatif),
- override `MONGODB_URI` du service `pipeline` vers mongo local.

<a id="sec-104"></a>
## 10.4 Makefile

Cibles utiles :
- `make up-ecs`, `make up-local`, `make down-local`, `make logs`, `make test`.
- `make mongo-shell`, `make mongo-shell-root`.

<a id="sec-11"></a>
## 11. Infrastructure AWS (Terraform)

Répertoire : `infra/terraform/mongodb-ecs/`.

<a id="sec-111"></a>
## 11.1 Composants déployés

- Réseau : subnets privés dédiés Mongo, NAT, route table, VPC endpoints.
- Sécurité : security groups Mongo + endpoints.
- Service discovery : namespace privé Cloud Map + services `mongo-1/2/3`.
- Secrets : secret bootstrap (root password + repl key).
- ECS : cluster + task definitions + services Fargate (3 noeuds).
- Stockage : volumes EBS managés attachés aux services ECS.
- Logs : CloudWatch log group Mongo.

<a id="sec-112"></a>
## 11.2 Sauvegardes (AWS Backup)

Déployé et actif :
- `aws_backup_vault.mongodb`
- `aws_backup_plan.mongodb`
- `aws_backup_selection.mongodb_ebs_by_tag`
- IAM role Backup + policies

Configuration par variables :
- `enable_backups`
- `backup_schedule`
- `backup_start_window_minutes`
- `backup_completion_window_minutes`
- `backup_cold_storage_after_days`
- `backup_delete_after_days`

Sorties Terraform associées :
- `backup_vault_name`
- `backup_plan_id`

<a id="sec-113"></a>
## 11.3 Monitoring AWS

Déployé et actif :
- SNS topic : `forecast-prod-mongo-alerts`
- Alarmes ECS par service :
  - running task count bas,
  - CPU high,
  - memory high.
- Metric filter logs Mongo (`s=E/F`) + alarme `mongo_error_logs`.

Configuration par variables :
- `enable_monitoring`
- `alarm_notification_emails`
- `ecs_running_task_minimum`
- `ecs_cpu_high_threshold`
- `ecs_memory_high_threshold`
- `mongodb_error_log_alarm_threshold`

Sortie Terraform associée :
- `alarm_topic_arn`

<a id="sec-114"></a>
## 11.4 Backend Terraform

- Backend S3 via `backend.tf` + `backend.hcl.example`.
- Script de déploiement : `ops/aws/deploy_mongodb_rs_terraform.sh`.
- Variables backend requises :
  - `TF_BACKEND_BUCKET`
  - `TF_BACKEND_KEY`

<a id="sec-12"></a>
## 12. Opérations AWS et runbooks

<a id="sec-121"></a>
## 12.1 Build/push image MongoDB RS

- Script : `ops/aws/build_push_mongodb_rs_image.sh`
- Actions : create repo ECR si absent, login ECR, build `docker/mongodb-rs/Dockerfile`, push image.

<a id="sec-122"></a>
## 12.2 Déploiement infra MongoDB ECS

- Script : `ops/aws/deploy_mongodb_rs_terraform.sh`
- Exécute : `terraform init` (backend), `plan`, `apply`.

<a id="sec-123"></a>
## 12.3 Gestion utilisateur applicatif MongoDB ECS

- Script : `ops/aws/create_mongo_app_user.sh`
- Fonction : create/update user applicatif sur DB cible via `ecs execute-command`.
- Inputs requis : `APP_USER`, `APP_PASS`.

<a id="sec-124"></a>
## 12.4 Planification pipeline

- Cron local : `ops/cron-run-pipeline.sh`.
- Environnement AWS : EventBridge (règle externe au repo).

<a id="sec-13"></a>
## 13. Observabilité applicative

Fichiers générés dans `logs/` :
- `pipeline_status.json`
- `quality_report_*.json`
- `migration_report_*.json`
- `query_latency_report_*.json`
- logs journaliers `pipeline_YYYY-MM-DD.log`.

Métriques EMF imprimées sur stdout (`utils.monitoring.emit_pipeline_metrics`) :
- `duration_seconds`,
- `records_extracted`, `records_validated`, `records_loaded`, `records_rejected`,
- `error_rate`,
- `run_success`.

Namespace CloudWatch EMF : `Forecast2Pipeline`.

<a id="sec-14"></a>
## 14. Sécurité

- Secrets runtime Mongo root/repl key stockés dans AWS Secrets Manager.
- Auth MongoDB activée (`--auth`) et replica key file obligatoire.
- Communications intra-RS sécurisées par keyFile.
- Principle of least privilege partiel appliqué sur rôles ECS.
- TLS Mongo géré côté URI/env (notamment pour connexions externes).
- Variables sensibles non hardcodées dans le code applicatif.

<a id="sec-15"></a>
## 15. Tests et qualité logicielle

Tests présents :
- `src/tests/test_transformers.py`
- `src/tests/test_integration.py`
- `src/tests/test_pipeline_local.py`

Commande standard :
- `poetry run pytest -vv src/tests`

<a id="sec-16"></a>
## 16. Configuration environnement

Exemple de référence : `env.example`.

Variables critiques :
- AWS : `AWS_REGION`, `AWS_PROFILE`, `S3_RAW_BUCKET`, `S3_PROCESSED_BUCKET`.
- Mongo : `MONGODB_URI`, `MONGODB_DATABASE`, `MONGODB_COLLECTION`.
- Optionnel local : `MONGO_APP_USERNAME`, `MONGO_APP_PASSWORD`, etc.

<a id="sec-17"></a>
## 17. Procédures de déploiement

<a id="sec-171"></a>
## 17.1 Local (pipeline + mongo local)

1. `cp env.example .env`
2. Adapter `.env`
3. `make up-local`
4. Tester pipeline / scripts
5. `make down-local` pour nettoyage

<a id="sec-172"></a>
## 17.2 Pipeline avec Mongo distant (ECS/Atlas)

1. Définir `MONGODB_URI` valide
2. `make up-ecs`
3. Exécuter scripts `poetry run ...` ou `docker compose run --rm pipeline ...`

<a id="sec-173"></a>
## 17.3 Infra AWS MongoDB ECS

1. Configurer `infra/terraform/mongodb-ecs/terraform.tfvars`
2. Exporter variables backend Terraform
3. `bash ops/aws/deploy_mongodb_rs_terraform.sh`
4. Valider `terraform output`

<a id="sec-18"></a>
## 18. Troubleshooting

<a id="sec-181"></a>
## 18.1 `MONGODB_URI non définie`

- Vérifier `.env` et variables injectées dans Docker/CI.

<a id="sec-182"></a>
## 18.2 `Server selection timed out`

- Vérifier état replica set (`rs.status()`).
- Vérifier DNS Cloud Map (`mongo-1.mongo.internal`, etc.).
- Vérifier SG/route/subnets.

<a id="sec-183"></a>
## 18.3 `command usersInfo requires authentication`

- Utiliser un utilisateur authentifié (root ou app user).
- Vérifier `authSource` correct.

<a id="sec-184"></a>
## 18.4 Subscription SNS non reçue

- Vérifier état `PendingConfirmation` via `aws sns list-subscriptions-by-topic`.
- Confirmer le lien email envoyé par AWS SNS.

<a id="sec-19"></a>
## 19. Documents complémentaires

- `README.md` : guide principal d'usage.
- `docs/deployment_mongodb_ecs.md` : historique déploiement ECS.
- `docs/audit_complet_2026-02-18.md` et `docs/audit_ecs_only_2026-02-18.md` : audits techniques.
- `docs/airbyte_setup_s3.md` : setup ingestion Airbyte.
- `docs/mongodb_migration.md` : migration MongoDB.

<a id="sec-20"></a>
## 20. État actuel (référence opérationnelle)

- MongoDB ECS replica set actif en 3 noeuds.
- Sauvegardes AWS Backup configurées.
- Alarming CloudWatch + SNS configurés.
- Subscription email définie sur `ali75009@gmail.com` (confirmation email requise côté boîte mail).

---

Ce document est la référence consolidée de l'architecture, de l'exploitation et du déploiement du projet Forecast 2.0 Pipeline.
