# Airbyte Setup (Excel + JSON -> S3)

## Objectif
Configurer Airbyte pour:
- lire une source JSON (InfoClimat)
- lire une source Excel/CSV (Weather Underground)
- ecrire dans un bucket S3 (raw zone)

## Prerequis
- Docker Desktop
- compte AWS avec acces S3
- bucket S3: `greenandcoop-raw-data`

## Installation Airbyte (local)
Option recommandee (Airbyte OSS via `abctl`):

```bash
curl -LsfS https://get.airbyte.com | bash
abctl local install
abctl local credentials
```

UI Airbyte: `http://localhost:8000`

## Connexion destination S3
Creer une destination `Amazon S3` avec:
- Bucket: `greenandcoop-raw-data`
- Region: `eu-west-1`
- Output format: `JSONL`
- Path prefix: `airbyte-sync/`

## Source 1: JSON (InfoClimat)
- Type source: `File` ou `HTTP API` (selon votre connecteur)
- Format: JSON
- Stream name: `infoclimat`

## Source 2: Excel/CSV (Weather Underground)
- Type source: `File`
- Format: CSV/XLSX
- Stream name: `wunderground`

## Connections
- Connection A: `InfoClimat -> S3`
  - Prefix conseille: `airbyte-sync/infoclimat/`
- Connection B: `Wunderground -> S3`
  - Prefix conseille: `airbyte-sync/wunderground/`

## Verification
Verifier la presence de fichiers `.jsonl` dans S3:

```bash
aws s3 ls s3://greenandcoop-raw-data/airbyte-sync/ --recursive
```

## Preuve attendue pour soutenance
Capture ecran de:
- la page Connections Airbyte
- le statut de sync `Succeeded`
- le bucket S3 montrant les fichiers synchro
