# Forecast 2.0 Pipeline
## Collecte, Transformation, Stockage et Exploitation AWS
- Mission Data Engineering
- Airbyte + S3 + ETL Python + MongoDB + AWS ECS
- Auteur: Alhassane AHMED

---

# 1. Contexte de la mission
- Centraliser des donnees meteo heterogenes
- Garantir qualite, disponibilite, tracabilite
- Produire un pipeline industrialisable en production

Objectifs:
- Collecte automatisee
- Transformation vers schema unique
- Stockage MongoDB exploitable
- Reporting qualite et performance

---

# 2. Demarche technique complete
1. Cadrage et modelisation des donnees
2. Ingestion Airbyte vers S3 raw
3. ETL Python (extract, harmonize, validate)
4. Persistance S3 processed + MongoDB
5. Tests, reporting, observabilite
6. Deploiement AWS ECS via Terraform

---

# 3. Architecture globale (end-to-end)
`Airbyte -> S3 Raw -> ETL Python -> S3 Processed -> MongoDB`

Composants:
- Sources: InfoClimat, Weather Underground
- ETL: scripts Python + orchestrateur `src/main.py`
- Base: MongoDB Replica Set (3 noeuds)
- Ops: CloudWatch, SNS, AWS Backup

---

# 4. Logigramme du processus
- Collecter (Airbyte/S3)
- Extraire (InfoClimat + WU)
- Transformer (schema cible)
- Valider (regles qualite)
- Stocker (S3 processed + MongoDB)
- Tester (CRUD, latence, rapports)

Visuel a inserer:
- `docs/process_flowchart.mmd` (export PNG/SVG)

---

# 5. Schema de la base de donnees
Collection principale:
- `forecast_2_0.weather_measurements`

Blocs principaux:
- `station`
- `timestamp`
- `measurements`
- `data_quality`
- `metadata`

Source schema:
- `src/config/mongodb_schema.json`

---

# 6. Architecture MongoDB
Topologie:
- Replica set 3 noeuds: `mongo-1`, `mongo-2`, `mongo-3`
- Service discovery prive (Cloud Map)
- Volumes EBS manages par service ECS

Securite:
- Auth MongoDB activee
- Secrets Manager (root + replica key)

---

# 7. Justification des choix techniques
- Airbyte: ingestion rapide multi-connecteurs
- S3: zone raw/processed durable et economique
- Python ETL: logique metier fine et testable
- MongoDB: flexibilite schema + index geospatial
- ECS + Terraform: deploiement reproductible et maintenable
- CloudWatch/SNS + Backup: exploitation production

---

# 8. Installation Airbyte (preuves)
Captures a inserer:
1. Source InfoClimat configuree
2. Source Weather Underground configuree
3. Destination S3 configuree
4. Job sync reussi (status)

Message cle:
- Les flux sont bien ingestes vers `airbyte-sync/...` dans S3

---

# 9. Detailler la pipeline applicative
Orchestration:
- `extract_data()`
- `transform_data()`
- `validate_data()`
- `save_validated_to_s3()`
- `load_data()`
- `generate_quality_report()`

Livrables d'execution:
- `logs/pipeline_status.json`
- `logs/quality_report_*.json`
- `logs/migration_report_*.json`

---

# 10. Reporting qualite des donnees
KPIs:
- records_extracted
- records_validated
- records_rejected
- rejection_rate
- completeness_score
- anomalies_detected

Sources:
- `logs/quality_report_*.json`
- `logs/migration_report_*.json`

---

# 11. Reporting temps d'accessibilite
Mesure:
- latence min/max/moyenne des requetes MongoDB
- volume de lignes retournees

Source:
- `logs/query_latency_report_*.json`

Commande type:
- `poetry run latency-report --station-id ILAMAD25 --date 2026-02-18 --iterations 10`

---

# 12. Installation AWS (preuves)
Captures a inserer:
1. ECS Cluster + services MongoDB
2. CloudWatch alarms
3. SNS topic/subscription
4. AWS Backup vault + plan
5. Buckets S3 raw/processed

Message cle:
- Infrastructure exploitable, monitorable et sauvegardee

---

# 13. Resultats et valeur apportee
- Pipeline operationnel de bout en bout
- Qualite de donnees mesurable
- Acces aux donnees testable par latence
- Stack production AWS stabilisee
- Documentation et runbooks disponibles

---

# 14. Limites et ameliorations
Limites:
- qualite dependante des donnees source
- confirmation manuelle initiale SNS email

Ameliorations:
- dashboard metier (KPI qualite/latence)
- CI/CD complet
- tests de charge + objectifs SLO

---

# 15. Conclusion
- Mission couverte: architecture, stack, pipeline, schema, process, preuves Airbyte/AWS, qualite, performance
- Solution: industrialisable, maintenable, observable
- Prochaine etape: extension de sources et automatisation CI/CD
