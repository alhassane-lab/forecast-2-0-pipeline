# Migration MongoDB: logique et execution

## Logique
1. Extraction depuis S3 de donnees InfoClimat + Wunderground.
2. Transformation vers schema cible MongoDB (`station`, `timestamp`, `measurements`, `data_quality`, `metadata`).
3. Validation (champs obligatoires, coherence, plages de valeurs).
4. Export des donnees validees vers `S3_PROCESSED_BUCKET` (prefix `processed/`, format `processed/weather_data_YYYYMMDD_HHMMSS.json`).
5. Import en base MongoDB ECS replica set depuis S3 processed (insert/upsert).
6. Rapport qualite post-migration (`error_rate`, rejet, completude).

## Scripts
- `src/scripts/transform_to_mongodb.py`: transformation + validation + rapport qualite.
- `src/scripts/migrate_to_mongodb.py`: migration MongoDB + rapport post-migration.
- `src/scripts/mongodb_crud.py`: operations CRUD (Create, Read, Update, Delete).
- `src/scripts/query_latency_report.py`: mesure du temps d'accessibilite des donnees.

## Commandes

```bash
# 1) Transformation depuis S3
poetry run transform-mongodb --date 2026-02-12

# 2) Migration MongoDB (insert)
poetry run migrate-mongodb --input ./data/processed/mongodb_ready_records.json

# 3) Migration MongoDB (upsert)
poetry run migrate-mongodb --input ./data/processed/mongodb_ready_records.json --upsert

# 4) Migration MongoDB depuis S3 (dernier fichier de la date)
poetry run migrate-mongodb --input-s3-date 2026-02-12

# 5) Migration MongoDB depuis S3 (dernier fichier global)
poetry run migrate-mongodb --input-s3-latest

# 6) CRUD demo
poetry run mongodb-crud

# 7) Reporting latence
poetry run latency-report --station-id ILAMAD25 --date 2026-02-12 --iterations 10
```

## Qualite des donnees
Le script de migration produit un rapport JSON dans `logs/` contenant:
- `input_records`
- `loaded_records`
- `rejected_records`
- `error_rate`
- details qualite (`completeness`, anomalies, etc.)
