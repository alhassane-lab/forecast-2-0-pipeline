# Support de presentation final (structure complete)

Ce support couvre toutes les attentes de la mission:
- contexte,
- demarche technique complete,
- justification des choix,
- schema de base,
- logigramme du processus,
- architecture base de donnees,
- preuves Airbyte (captures),
- reporting qualite + latence,
- preuves AWS (captures).

## Slide 1 - Titre et perimetre
- Titre: `Forecast 2.0 Pipeline - Collecte, Transformation, Stockage et Exploitation`
- Sous-titre: mission Data Engineering (ingestion multi-sources, qualite, observabilite, industrialisation)
- Message cle: pipeline complet, reproductible localement et deployable sur AWS

## Slide 2 - Contexte de la mission
- Besoin metier:
  - centraliser des donnees meteo heterogenes
  - fiabiliser l'acces aux donnees pour analyses et previsions
- Contraintes:
  - formats heterogenes (JSON/JSONL, donnees tabulaires)
  - qualite variable des mesures
  - exigence de disponibilite et tracabilite
- Objectifs:
  - pipeline robuste de bout en bout
  - stockage cible MongoDB avec schema coherent
  - reporting qualite et performance

## Slide 3 - Demarche technique complete (vue macro)
- Phase 1: cadrage technique et modelisation de donnees
- Phase 2: ingestion Airbyte vers S3 raw
- Phase 3: extraction/normalisation/validation via ETL Python
- Phase 4: migration vers MongoDB et creation des index
- Phase 5: tests, metriques, observabilite, industrialisation AWS

## Slide 4 - Architecture technique globale
- Diagramme cible:
  - Airbyte -> S3 raw -> ETL Python -> S3 processed -> MongoDB
  - + logs/rapports + metriques CloudWatch
- A afficher visuellement:
  - sources InfoClimat / Weather Underground
  - buckets S3 raw/processed
  - conteneur pipeline
  - cluster MongoDB (replica set)

## Slide 5 - Logigramme du processus (collecter, transformer, stocker, tester)
- Inserer le logigramme depuis:
  - `docs/process_flowchart.mmd` (export PNG/SVG)
- Commenter le flux:
  - collecte
  - transformation
  - validation
  - chargement
  - verification qualite/latence

## Slide 6 - Schema de la base de donnees
- Collection principale:
  - `weather_measurements`
- Champs majeurs:
  - `station`, `timestamp`, `measurements`, `data_quality`, `metadata`
- Index:
  - unique `station.id + timestamp`
  - `station.network + timestamp`
  - geospatial `station.location_geo`
- Source schema:
  - `src/config/mongodb_schema.json`

## Slide 7 - Architecture de la base de donnees (MongoDB)
- Topologie:
  - replica set 3 noeuds (`mongo-1`, `mongo-2`, `mongo-3`)
  - service discovery prive (Cloud Map)
  - volumes EBS par noeud
- Securite:
  - auth MongoDB activee
  - secret bootstrap dans AWS Secrets Manager
- Disponibilite:
  - election automatique PRIMARY/SECONDARY

## Slide 8 - Installation Airbyte (preuve par capture)
- Captures a inserer:
  1. Connexion source InfoClimat
  2. Connexion source Weather Underground
  3. Destination S3 configuree
  4. Ecran de sync reussie (job status)
- Preuve attendue:
  - flux JSON/Excel/JSONL vers prefixes S3 `airbyte-sync/...`

## Slide 9 - Reporting qualite des donnees
- Indicateurs a presenter:
  - `records_extracted`, `records_validated`, `records_rejected`
  - `rejection_rate`, `completeness_score`
  - anomalies detectees par station/reseau
- Sources:
  - `logs/quality_report_*.json`
  - `logs/migration_report_*.json`
- Recommandation visuelle:
  - tableau KPI + histogramme completeness

## Slide 10 - Reporting temps d'accessibilite
- Indicateurs:
  - latence min / max / moyenne des requetes MongoDB
  - volume retourne (`matched_rows`)
- Source:
  - `logs/query_latency_report_*.json`
- Exemple de narration:
  - \"Temps moyen d'acces <X ms sur N iterations pour la station Y\"

## Slide 11 - Installation AWS (preuve par capture)
- Captures a inserer:
  1. ECS cluster + services MongoDB
  2. CloudWatch logs / alarmes
  3. AWS Backup plan + vault
  4. SNS topic subscription
  5. S3 raw/processed
- Message cle:
  - exploitation production: sauvegardes + monitoring + alerting

## Slide 12 - Justification des choix techniques
- Pourquoi Airbyte:
  - acceleration de l'ingestion multi-connecteurs
  - standardisation de la collecte
- Pourquoi S3:
  - couche raw/processed durable et economique
- Pourquoi ETL Python:
  - controle fin de la logique de normalisation/validation
- Pourquoi MongoDB:
  - schema flexible pour sources heterogenes
  - indexation geospatiale et temporelle
- Pourquoi AWS ECS + Terraform:
  - deploiement reproductible (IaC)
  - scalabilite et operations standardisees
- Pourquoi CloudWatch/AWS Backup:
  - observabilite continue
  - protection des donnees et reprise

## Slide 13 - Limites, risques et ameliorations
- Limites actuelles:
  - dependance a la qualite source
  - besoin de confirmation manuelle SNS email
- Risques:
  - derive schema source
  - incidents reseau inter-services
- Pistes d'amelioration:
  - tests de charge et SLO explicites
  - dashboards metiers
  - automatisation CI/CD complete

## Slide 14 - Conclusion
- Rappel des livrables couverts:
  - architecture, pipeline, schema, logigramme, qualite, latence, Airbyte, AWS
- Valeur apportee:
  - pipeline industrialise, observable, maintenable
- Ouverture:
  - extension a d'autres sources meteo et cas d'usage data science

## Annexes conseillees (backup slides)
- commandes d'execution (`Makefile`, scripts `poetry run ...`)
- extrait `terraform output` (cluster, backup, topic SNS)
- extrait de rapport qualite et latence
