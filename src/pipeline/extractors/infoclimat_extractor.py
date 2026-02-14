"""
Extracteur de données InfoClimat robuste
Lit les données JSON ou JSONL depuis S3 ou local, gère les erreurs et les données manquantes.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
import os
import boto3
from botocore.exceptions import ClientError
from loguru import logger


class InfoClimatExtractor:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.s3_client = boto3.client('s3')
        # Allow env override to keep Docker/CI config simple.
        self.bucket = os.getenv("S3_RAW_BUCKET") or config.get("s3", {}).get("raw_bucket", "greenandcoop-raw-data")
        self.s3_prefix = os.getenv("S3_PREFIX", "airbyte-sync/").lstrip("/")
        self.stations_metadata = self._load_stations_metadata()

    def _load_stations_metadata(self) -> Dict[str, Any]:
        """Charge les metadonnees stations depuis src/config/stations_metadata.json."""
        default = {
            "07015": {"name": "Lille-Lesquin", "type": "synop", "latitude": 50.575, "longitude": 3.092, "elevation": 47, "city": "Lille", "country": "France", "region": "Hauts-de-France"},
            "00052": {"name": "Armentières", "type": "static", "latitude": 50.689, "longitude": 2.877, "elevation": 16, "city": "Armentières", "country": "France", "region": "Hauts-de-France"},
            "000R5": {"name": "Bergues", "type": "static", "latitude": 50.968, "longitude": 2.441, "elevation": 17, "city": "Bergues", "country": "France", "region": "Hauts-de-France"},
            "STATIC0010": {"name": "Hazebrouck", "type": "static", "latitude": 50.734, "longitude": 2.545, "elevation": 31, "city": "Hazebrouck", "country": "France", "region": "Hauts-de-France"},
        }

        try:
            cfg_path = Path(__file__).resolve().parents[2] / "config" / "stations_metadata.json"
            payload = json.loads(cfg_path.read_text(encoding="utf-8"))
            stations = payload.get("infoclimat")
            return stations if isinstance(stations, dict) else default
        except Exception as e:
            logger.warning(f"Impossible de charger stations_metadata.json (infoclimat): {e}")
            return default

    def extract(self, date: datetime) -> List[Dict[str, Any]]:
        logger.info(f"Extraction données InfoClimat pour {date.strftime('%Y-%m-%d')}")

        prefix = f"{self.s3_prefix}infoclimat/data_infoclimat/"

        latest_key = self._get_latest_jsonl_key(prefix, target_date=date)

        if not latest_key:
            logger.warning(f"Aucun fichier InfoClimat trouvé dans s3://{self.bucket}/{prefix}")
            return []

        logger.info(f"Lecture du dernier fichier InfoClimat : s3://{self.bucket}/{latest_key}")

        try:
            response = self.s3_client.get_object(Bucket=self.bucket, Key=latest_key)
            raw_text = response["Body"].read().decode("utf-8")
            raw_lines = [json.loads(line) for line in raw_text.splitlines() if line.strip()]
            records = self._parse_infoclimat_data(raw_lines)

            logger.success(f"✓ {len(records)} enregistrements InfoClimat extraits")
            return records

        except ClientError as e:
            logger.error(f"Erreur S3 InfoClimat: {e}")
            raise
        except Exception as e:
            logger.error(f"Erreur parsing InfoClimat: {e}")
            raise

    def _get_latest_jsonl_key(self, prefix: str, target_date: Optional[datetime] = None) -> str | None:
        paginator = self.s3_client.get_paginator("list_objects_v2")

        candidates: List[tuple[str, datetime]] = []
        all_jsonl: List[tuple[str, datetime]] = []

        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if key.endswith(".jsonl"):
                    lm = obj.get("LastModified")
                    if isinstance(lm, datetime):
                        all_jsonl.append((key, lm))
                        if target_date is not None and lm.date() == target_date.date():
                            candidates.append((key, lm))

        if candidates:
            candidates.sort(key=lambda x: x[1])
            return candidates[-1][0]

        if all_jsonl:
            if target_date is not None:
                logger.warning(
                    f"Aucun fichier InfoClimat pour la date {target_date:%Y-%m-%d}; fallback sur le dernier fichier disponible."
                )
            all_jsonl.sort(key=lambda x: x[1])
            return all_jsonl[-1][0]

        return None

    def _parse_infoclimat_data(self, raw_lines: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        records = []
        for idx, line in enumerate(raw_lines, start=1):
            try:
                js = line if isinstance(line, dict) else json.loads(line)
                airbyte_data = js.get("_airbyte_data", {})
                hourly_data = airbyte_data.get("hourly", {})
                metadata = airbyte_data.get("metadata", {})

                for station_id, measurements in hourly_data.items():
                    station_info = self.stations_metadata.get(station_id, {
                        "name": "Unknown",
                        "type": "unknown",
                        "latitude": None,
                        "longitude": None,
                        "elevation": None,
                        "city": None,
                        "country": None,
                        "region": None
                    })

                    for measurement in measurements:
                        if not isinstance(measurement, dict):
                            # Ignorer silencieusement la station _params
                            if station_id != "_params":
                                logger.warning(
                                    f"Ligne {idx}, station {station_id} : mesure inattendue (non dict), ignorée : {measurement}")
                            continue

                        # Vérification timestamp
                        timestamp = measurement.get("dh_utc")
                        if timestamp:
                            try:
                                datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                            except ValueError:
                                logger.warning(f"Ligne {idx}, station {station_id} : timestamp invalide '{timestamp}'")
                                timestamp = None

                        record = {
                            "source": "infoclimat",
                            "station_id": station_id,
                            "station_name": station_info.get("name"),
                            "station_type": station_info.get("type"),
                            "latitude": station_info.get("latitude"),
                            "longitude": station_info.get("longitude"),
                            "elevation": station_info.get("elevation"),
                            "city": station_info.get("city"),
                            "country": station_info.get("country"),
                            "region": station_info.get("region"),
                            "timestamp": timestamp,
                            "measurements": {k: measurement.get(k) for k in [
                                "temperature", "pression", "humidite", "point_de_rosee",
                                "visibilite", "vent_moyen", "vent_rafales", "vent_direction",
                                "pluie_1h", "pluie_3h", "neige_au_sol", "nebulosite", "temps_omm"
                            ]},
                            "metadata": metadata
                        }
                        records.append(record)

                    logger.debug(f"Ligne {idx} : {len(measurements)} mesures extraites pour la station {station_id}")

            except Exception as e:
                logger.error(f"Erreur sur la ligne {idx} : {e}")
                continue  # Ignore la ligne et continue

        logger.info(f"Total des enregistrements extraits : {len(records)}")
        return records

    def extract_from_local(self, file_path: str) -> List[Dict[str, Any]]:
        """Extrait des donnees InfoClimat depuis un fichier local JSON/JSONL.

        Supports:
        - un document JSON unique (Airbyte ou brut)
        - un fichier JSONL (1 objet JSON par ligne)
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Fichier introuvable: {file_path}")

        content = path.read_text(encoding="utf-8").strip()
        if not content:
            return []

        raw_lines: List[Dict[str, Any]] = []

        # Tentative 1: fichier JSON complet
        try:
            payload = json.loads(content)
            if isinstance(payload, dict):
                raw_lines = [payload]
            elif isinstance(payload, list):
                raw_lines = [item for item in payload if isinstance(item, dict)]
        except json.JSONDecodeError:
            # Tentative 2: JSONL
            raw_lines = []
            for line in content.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    decoded = json.loads(line)
                    if isinstance(decoded, dict):
                        raw_lines.append(decoded)
                except json.JSONDecodeError:
                    logger.warning(f"Ligne JSON invalide ignorée dans {file_path}")

        # Uniformiser vers la structure attendue (_airbyte_data)
        normalized_lines: List[Dict[str, Any]] = []
        for line in raw_lines:
            if "_airbyte_data" in line:
                normalized_lines.append(line)
            else:
                normalized_lines.append({"_airbyte_data": line})

        return self._parse_infoclimat_data(normalized_lines)
