"""
Extracteur Weather Underground (Airbyte JSONL)
- Lit le dernier fichier .jsonl par station depuis S3
- Parse les observations Weather Underground
- Nettoie et convertit les mesures numériques
- Robuste aux fichiers manquants
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
import re
import os

import boto3
from botocore.exceptions import ClientError
from loguru import logger


class WundergroundExtractor:
    """
    Extracteur Weather Underground depuis S3 (Airbyte)
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.s3_client = boto3.client("s3")
        # Allow env override to keep Docker/CI config simple.
        self.bucket = os.getenv("S3_RAW_BUCKET") or config.get("s3", {}).get("raw_bucket", "greenandcoop-raw-data")
        self.s3_prefix = os.getenv("S3_PREFIX", "airbyte-sync/").lstrip("/")

        self.stations_metadata = self._load_stations_metadata()

    def _load_stations_metadata(self) -> Dict[str, Any]:
        """Charge les metadonnees WU depuis src/config/stations_metadata.json."""
        default = {
            "IICHTE19": {
                "name": "WeerstationBS",
                "latitude": 51.092,
                "longitude": 2.999,
                "elevation": 15,
                "city": "Ichtegem",
                "country": "Belgium",
                "region": "West-Vlaanderen",
                "hardware": "other",
                "software": "EasyWeatherV1.6.6",
                "s3_folder": "data_wunderground_Ichtegem",
            },
            "ILAMAD25": {
                "name": "La Madeleine",
                "latitude": 50.659,
                "longitude": 3.07,
                "elevation": 23,
                "city": "La Madeleine",
                "country": "France",
                "region": "Hauts-de-France",
                "hardware": "other",
                "software": "EasyWeatherPro_V5.1.6",
                "s3_folder": "data_wunderground_madelaine",
            },
        }

        try:
            cfg_path = Path(__file__).resolve().parents[2] / "config" / "stations_metadata.json"
            payload = json.loads(cfg_path.read_text(encoding="utf-8"))
            stations = payload.get("wunderground")
            return stations if isinstance(stations, dict) else default
        except Exception as e:
            logger.warning(f"Impossible de charger stations_metadata.json (wunderground): {e}")
            return default

    # ------------------------------------------------------------------
    # PUBLIC API
    # ------------------------------------------------------------------

    def extract(self, date: datetime) -> List[Dict[str, Any]]:
        """
        Extrait les données Weather Underground pour toutes les stations
        (lit le dernier fichier Airbyte par station)
        """
        logger.info(f"Extraction données Weather Underground pour {date.strftime('%Y-%m-%d')}")
        all_records: List[Dict[str, Any]] = []

        for station_id in self.stations_metadata:
            try:
                records = self._extract_station(station_id, target_date=date)
                all_records.extend(records)
            except Exception as e:
                logger.error(f"Erreur extraction station {station_id}: {e}")

        logger.success(f"✓ {len(all_records)} enregistrements Weather Underground extraits")
        return all_records

    # ------------------------------------------------------------------
    # INTERNALS
    # ------------------------------------------------------------------

    def _extract_station(self, station_id: str, target_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        station_info = self.stations_metadata.get(station_id)
        if not station_info:
            logger.warning(f"Station inconnue: {station_id}")
            return []

        s3_folder = station_info.get("s3_folder")
        if not s3_folder:
            logger.warning(f"Station {station_id} sans s3_folder configuré")
            return []

        prefix = f"{self.s3_prefix}wunderground/{s3_folder}/"
        latest_key = self._get_latest_jsonl_key(prefix, target_date=target_date)
        if not latest_key:
            logger.warning(f"Aucun fichier trouvé pour {station_id}")
            return []

        logger.info(f"Lecture Wunderground {station_id} : s3://{self.bucket}/{latest_key}")

        try:
            response = self.s3_client.get_object(Bucket=self.bucket, Key=latest_key)
            raw_text = response["Body"].read().decode("utf-8")

            raw_lines = [
                json.loads(line) for line in raw_text.splitlines() if line.strip()
            ]

            records = self._parse_wunderground_airbyte(raw_lines, station_id, station_info)

            logger.info(f"{len(records)} mesures Wunderground extraites pour {station_id}")
            return records

        except ClientError as e:
            logger.error(f"Erreur S3 Wunderground {station_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Erreur parsing Wunderground {station_id}: {e}")
            raise

    def _get_latest_jsonl_key(self, prefix: str, target_date: Optional[datetime] = None) -> Optional[str]:
        """
        Retourne la clé S3 du dernier fichier .jsonl (basé sur le timestamp Airbyte)
        """
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
                    f"Aucun fichier Wunderground pour la date {target_date:%Y-%m-%d} sous {prefix}; fallback sur le dernier fichier disponible."
                )
            all_jsonl.sort(key=lambda x: x[1])
            return all_jsonl[-1][0]

        return None

    def _parse_wunderground_airbyte(
        self,
        raw_lines: List[Dict[str, Any]],
        station_id: str,
        station_info: Dict[str, Any],
    ) -> List[Dict[str, Any]]:

        def parse_float(val: Any) -> Optional[float]:
            """Nettoie les caractères invisibles et unités, puis convertit en float"""
            if val is None:
                return None
            s = re.sub(r"[^\d\.-]", "", str(val))
            try:
                return float(s)
            except ValueError:
                return None

        def clean_str(s: Any) -> Optional[str]:
            if s is None:
                return None
            return str(s).replace("\xa0", " ").strip()

        records: List[Dict[str, Any]] = []

        for idx, line in enumerate(raw_lines, start=1):
            airbyte_data = line.get("_airbyte_data")
            if not isinstance(airbyte_data, dict):
                logger.debug(f"Ligne {idx} station {station_id} ignorée (airbyte_data invalide)")
                continue

            record = {
                "source": "wunderground",
                "station_id": station_id,
                "station_name": station_info["name"],
                "latitude": station_info["latitude"],
                "longitude": station_info["longitude"],
                "elevation": station_info["elevation"],
                "city": station_info["city"],
                "country": station_info["country"],
                "region": station_info["region"],
                "hardware": station_info["hardware"],
                "software": station_info["software"],
                "timestamp": airbyte_data.get("Timestamp"),
                "measurements": {
                    "temperature": parse_float(airbyte_data.get("Temperature")),
                    "dewpoint": parse_float(airbyte_data.get("Dew Point")),
                    "humidity": parse_float(airbyte_data.get("Humidity")),
                    "wind_speed": parse_float(airbyte_data.get("Speed")),
                    "wind_gust": parse_float(airbyte_data.get("Gust")),
                    "wind_direction": airbyte_data.get("Wind"),
                    "pressure": parse_float(airbyte_data.get("Pressure")),
                    "precip_rate": parse_float(airbyte_data.get("Precip. Rate.")),
                    "precip_accum": parse_float(airbyte_data.get("Precip. Accum.")),
                    "uv_index": parse_float(airbyte_data.get("UV")),
                    "solar_radiation": parse_float(airbyte_data.get("Solar")),
                },
            }

            records.append(record)

        return records

    def extract_from_local(self, file_path: str, station_id: str = "ILAMAD25") -> List[Dict[str, Any]]:
        """Extrait les donnees Weather Underground depuis un fichier local JSON/JSONL."""
        station_info = self.stations_metadata.get(station_id)
        if not station_info:
            raise ValueError(f"Station inconnue: {station_id}")

        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Fichier introuvable: {file_path}")

        content = path.read_text(encoding="utf-8").strip()
        if not content:
            return []

        raw_lines: List[Dict[str, Any]] = []
        try:
            payload = json.loads(content)
            if isinstance(payload, dict):
                raw_lines = [payload]
            elif isinstance(payload, list):
                raw_lines = [item for item in payload if isinstance(item, dict)]
        except json.JSONDecodeError:
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

        normalized_lines: List[Dict[str, Any]] = []
        for line in raw_lines:
            if "_airbyte_data" in line:
                normalized_lines.append(line)
            else:
                normalized_lines.append({"_airbyte_data": line})

        return self._parse_wunderground_airbyte(normalized_lines, station_id, station_info)
# --------------------------
# Exemple d'utilisation
# --------------------------

#config = {"s3": {"raw_bucket": "greenandcoop-raw-data"}}
#extractor = WundergroundExtractor(config)
#records = extractor.extract(datetime(2026, 2, 7))
#print(len(records))
#print(records[0])
