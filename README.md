# Forecast 2.0 Pipeline - Livrables Mission

## 1) Contexte
Ce projet met en place une chaine Data Engineering pour:
- collecter des donnees meteo depuis des sources Excel et JSON via Airbyte,
- stocker les donnees brutes dans AWS S3,
- transformer les donnees vers un schema compatible MongoDB,
- migrer les donnees vers MongoDB,
- mesurer la qualite des donnees et le temps d'accessibilite.

## 2) Architecture technique

`Airbyte (JSON + Excel) -> S3 (raw) -> ETL Python (transform/validate) -> MongoDB -> reporting qualite + latence`

## 3) Logigramme processus
Le logigramme formel est disponible dans `docs/process_flowchart.mmd`.

```mermaid
flowchart TD
    A([Debut pipeline]) --> B[Airbyte Sync JSON/Excel -> S3 Raw]
    B --> C{Fichiers S3 disponibles ?}
    C -- Non --> Z[Log erreur + arret]
    C -- Oui --> D[Extraction InfoClimat + Wunderground]
    D --> E[Transformation schema MongoDB]
    E --> F[Validation + controles qualite]
    F --> G{Enregistrement valide ?}
    G -- Non --> H[Compter rejet + journaliser]
    G -- Oui --> I[Ajouter au lot MongoDB-ready]
    H --> J{Fin des enregistrements ?}
    I --> J
    J -- Non --> G
    J -- Oui --> K[Migration MongoDB insert/upsert]
    K --> L[CRUD verification + requete latence]
    L --> M[Rapports: qualite + migration + latence]
    M --> N([Fin pipeline])
```

## 4) Installation environnement

### Prerequis
- Python 3.10+
- Poetry
- Docker Desktop
- AWS credentials (acces S3)
- URI MongoDB Atlas

### Installation
```bash
poetry install
cp env.example .env
# renseigner .env
```

## 4bis) requirements.txt
Le fichier `requirements.txt` est fourni avec versions exactes (pinned) pour recreer un environnement virtuel compatible:

```bash
pip install -r requirements.txt
```

## 5) Airbyte -> S3 (Excel + JSON)
Guide complet: `docs/airbyte_setup_s3.md`

Objectif attendu:
- Connection Airbyte JSON -> S3 prefix `airbyte-sync/infoclimat/`
- Connection Airbyte Excel/CSV -> S3 prefix `airbyte-sync/wunderground/`

## 6) Scripts livrables

### A. Transformation vers format MongoDB
Script: `src/scripts/transform_to_mongodb.py`

```bash
# Mode S3
poetry run transform-mongodb --source-mode s3 --date 2026-02-12

# Mode local (debug)
poetry run transform-mongodb \
  --source-mode local \
  --infoclimat-file ./data/raw/infoclimat.json \
  --wunderground-file ./data/raw/wunderground.json
```

Sortie:
- `data/processed/mongodb_ready_records.json`
- `logs/quality_report_transform_*.json`

### B. Migration vers MongoDB
Script: `src/scripts/migrate_to_mongodb.py`

```bash
# Insert
poetry run migrate-mongodb --input ./data/processed/mongodb_ready_records.json

# Upsert
poetry run migrate-mongodb --input ./data/processed/mongodb_ready_records.json --upsert
```

Sortie:
- `logs/migration_report_*.json`
- inclut `error_rate` post migration

### C. CRUD MongoDB via script Python
Script: `src/scripts/mongodb_crud.py`

```bash
poetry run mongodb-crud
```

Operations executees:
- Create
- Read
- Update
- Delete

### D. Reporting temps d'accessibilite
Script: `src/scripts/query_latency_report.py`

```bash
poetry run latency-report --station-id ILAMAD25 --date 2026-02-12 --iterations 10
```

Sortie:
- `logs/query_latency_report_*.json`
- `min/max/avg` de latence requete

## 7) Qualite des donnees post migration
Le taux d'erreur est calcule dans `migrate_to_mongodb.py`:
- `error_rate = rejected_records / input_records`

Les details qualite sont fournis par `QualityChecker`.

## 8) Collections MongoDB et schema
Schema cible: `src/config/mongodb_schema.json`

Collection principale:
- `weather_measurements`

Index crees via `MongoDBLoader`:
- `station.id + timestamp`
- `station.network + timestamp`
- index geospatial `station.location`

## 9) Support de presentation
Trame prete: `docs/presentation_support.md`

Inclut les elements demandes:
- contexte mission
- demarche technique
- justification des choix
- schema base
- logigramme
- preuves Airbyte et AWS (captures)
- reporting qualite et latence

## 10) Tests
```bash
pytest -vv src/tests
```

## 11) Docker (Atlas vs Mongo local)

### Atlas (mode default)
Prerequis: `MONGODB_URI` dans `.env`.

```bash
docker compose up --build
```

### Mongo local "clean" (sans profiles)

```bash
docker compose -f docker-compose.yml -f docker-compose.local.yml up --build
```

Test rapide de la collection via mongosh (local):
```bash
make mongo-shell
# puis dans mongosh:
# use forecast_2_0
# db.weather_measurements.countDocuments()
```
