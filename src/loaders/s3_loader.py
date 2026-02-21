"""Loader pour sauvegarder/lire les données transformées dans S3."""

import json
import os
import re
from datetime import datetime
from typing import Dict, List, Optional
import boto3
from loguru import logger


class S3Loader:
    """
    Classe pour charger les données transformées dans S3
    """

    def __init__(self, config: Dict):
        """
        Initialise le loader S3

        Args:
            config: Configuration contenant les informations S3
        """
        self.config = config
        self.s3_client = boto3.client('s3')
        self.bucket = os.getenv("S3_PROCESSED_BUCKET") or config.get("s3", {}).get(
            "processed_bucket", "greenandcoop-processed-data"
        )

    def _build_processed_prefix(self) -> str:
        """Construit le prefix S3 de stockage processed."""
        return "processed/"

    def _build_reports_prefix(self, run_date: Optional[datetime] = None) -> str:
        """Construit le prefix S3 pour les rapports d'execution."""
        return "logs/"

    def _build_filename(self, date: datetime) -> str:
        """Construit le nom de fichier avec la date dans le nom."""
        timestamp = datetime.utcnow().strftime("%H%M%S")
        return f"weather_data_{date.strftime('%Y%m%d')}_{timestamp}.json"

    def save_processed_data(self, records: List[Dict], date: datetime) -> str:
        """
        Sauvegarde les données transformées dans S3

        Args:
            records: Liste d'enregistrements à sauvegarder
            date: Date de traitement

        Returns:
            Chemin S3 du fichier sauvegardé
        """
        if not records:
            logger.warning("Aucune donnée à sauvegarder dans S3")
            return ""

        # Construire le chemin S3 (sans sous-dossiers date)
        s3_key = f"{self._build_processed_prefix()}{self._build_filename(date)}"

        try:
            # Convertir en JSON
            json_data = json.dumps(records, default=str, indent=2)

            # Upload vers S3
            self.s3_client.put_object(
                Bucket=self.bucket,
                Key=s3_key,
                Body=json_data.encode('utf-8'),
                ContentType='application/json'
            )

            s3_path = f"s3://{self.bucket}/{s3_key}"
            logger.success(f"✓ Données sauvegardées dans S3: {s3_path}")

            return s3_path

        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde dans S3: {e}")
            raise

    def list_processed_keys(self, date: Optional[datetime] = None) -> List[str]:
        """Retourne les clés JSON traitées dans le bucket processed."""
        prefix = self._build_processed_prefix()
        paginator = self.s3_client.get_paginator("list_objects_v2")
        keys: List[str] = []
        date_token = date.strftime("%Y%m%d") if date else None

        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                key = obj.get("Key", "")
                if not key.endswith(".json"):
                    continue
                if date_token is None:
                    keys.append(key)
                    continue

                # Nouveau format attendu: processed/weather_data_YYYYMMDD_HHMMSS.json
                filename = key.rsplit("/", 1)[-1]
                if re.search(rf"^weather_data_{date_token}_\d{{6}}\.json$", filename):
                    keys.append(key)
                    continue

                # Compatibilite anciens objets: processed/YYYY/MM/DD/weather_data_*.json
                legacy_prefix = f"processed/{date.strftime('%Y/%m/%d')}/"
                if key.startswith(legacy_prefix):
                    keys.append(key)

        return sorted(keys)

    def get_latest_processed_key(self, date: Optional[datetime] = None) -> str:
        """Trouve la clé JSON la plus récente dans processed."""
        keys = self.list_processed_keys(date=date)
        if not keys:
            date_label = date.strftime("%Y-%m-%d") if date else "all dates"
            raise FileNotFoundError(
                f"Aucun fichier JSON trouvé dans s3://{self.bucket}/processed/ ({date_label})"
            )
        return keys[-1]

    def load_processed_data(self, key: str) -> List[Dict]:
        """Charge un fichier JSON processed depuis S3."""
        try:
            obj = self.s3_client.get_object(Bucket=self.bucket, Key=key)
            payload = json.loads(obj["Body"].read().decode("utf-8"))
            if not isinstance(payload, list):
                raise ValueError("Le fichier processed S3 doit contenir une liste JSON")
            logger.info(f"Données chargées depuis s3://{self.bucket}/{key} ({len(payload)} records)")
            return payload
        except Exception as e:
            logger.error(f"Erreur chargement S3 s3://{self.bucket}/{key}: {e}")
            raise

    def save_report_json(
        self,
        report_type: str,
        payload: Dict,
        run_date: Optional[datetime] = None,
        file_stem: Optional[str] = None,
    ) -> str:
        """Sauvegarde un rapport JSON d'execution sous logs/."""
        safe_type = re.sub(r"[^a-zA-Z0-9_-]+", "_", report_type).strip("_") or "report"
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        stem = file_stem or f"{safe_type}_{ts}"
        key = f"{self._build_reports_prefix(run_date)}{stem}.json"

        try:
            body = json.dumps(payload, default=str, indent=2).encode("utf-8")
            self.s3_client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=body,
                ContentType="application/json",
            )
            s3_path = f"s3://{self.bucket}/{key}"
            logger.info(f"Rapport publie dans S3: {s3_path}")
            return s3_path
        except Exception as e:
            logger.error(f"Erreur publication rapport S3 ({safe_type}): {e}")
            raise
