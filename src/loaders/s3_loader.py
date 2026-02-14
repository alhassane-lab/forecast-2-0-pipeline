"""
Loader pour sauvegarder les données transformées dans S3
"""

import json
import os
from datetime import datetime
from typing import List, Dict
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

        # Construire le chemin S3
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        s3_key = f"processed/{date.strftime('%Y/%m/%d')}/weather_data_{timestamp}.json"

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
