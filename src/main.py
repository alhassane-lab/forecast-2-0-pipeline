"""Point d'entree du pipeline ETL Forecast 2.0.

Ce module orchestre le cycle complet d'execution:
1. extraction multi-sources (InfoClimat, Weather Underground)
2. harmonisation et validation des donnees
3. chargement MongoDB
4. generation des rapports de qualite et du statut d'execution

Le binaire est pilote via la CLI (`python -m src.main`) et peut fonctionner
en mode normal ou `--dry-run` (sans ecriture MongoDB).
"""

import argparse
import sys
import json
import time
import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger
from dotenv import load_dotenv

from pipeline.extractors.infoclimat_extractor import InfoClimatExtractor
from pipeline.extractors.wunderground_extractor import WundergroundExtractor
from pipeline.transformers.data_harmonizer import DataHarmonizer
from pipeline.transformers.data_validator import DataValidator
from pipeline.transformers.quality_checker import QualityChecker
from loaders.s3_loader import S3Loader
from loaders.mongodb_loader import MongoDBLoader
from utils.logger import setup_logger
from utils.monitoring import emit_pipeline_metrics, set_run_context

# ---------------------------------------------------------------------------
# CONFIG PATH ROBUSTE (LOCAL + DOCKER)
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
DEFAULT_CONFIG_PATH = BASE_DIR / "config" / "pipeline_config.json"
LOGS_DIR = PROJECT_ROOT / "logs"

def _sanitize_runtime_env() -> None:
    """Sanitize env vars that break SDKs when set to empty strings.

    Docker Compose often injects empty values (e.g. `AWS_PROFILE=`) which
    botocore interprets as an explicit profile name and then fails with
    ProfileNotFound.
    """
    for key in (
        "AWS_PROFILE",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AWS_SHARED_CREDENTIALS_FILE",
        "AWS_CONFIG_FILE",
        "MONGODB_URI",
    ):
        val = os.environ.get(key)
        if val is not None and val.strip() == "":
            os.environ.pop(key, None)


# ---------------------------------------------------------------------------
# PIPELINE
# ---------------------------------------------------------------------------

class Forecast2Pipeline:
    """Orchestrateur principal du pipeline Forecast 2.0.

    Attributes:
        config: Configuration chargee depuis `pipeline_config.json`.
        dry_run: Si True, desactive les ecritures MongoDB.
        stats: Compteurs et metadonnees d'execution utilises pour le reporting.
    """

    def __init__(self, config: Dict, dry_run: bool = False):
        """Initialise les composants ETL et les compteurs internes."""
        self.config = config
        self.dry_run = dry_run

        # Composants
        self.infoclimat_extractor = InfoClimatExtractor(config)
        self.wunderground_extractor = WundergroundExtractor(config)
        self.harmonizer = DataHarmonizer(config)
        self.validator = DataValidator(config)
        self.quality_checker = QualityChecker()
        self.s3_loader = S3Loader(config)
        self.mongodb_loader = MongoDBLoader(config, dry_run=dry_run)

        # Stats internes
        self.stats = {
            "start_time": datetime.utcnow(),
            "records_extracted": 0,
            "records_transformed": 0,
            "records_validated": 0,
            "processed_s3_path": None,
            "records_loaded": 0,
            "records_rejected": 0,
            "errors": []
        }

        logger.info("Pipeline Forecast 2.0 initialisé")
        if dry_run:
            logger.warning("Mode DRY-RUN activé – aucune écriture MongoDB")

    # -----------------------------------------------------------------------

    def extract_data(self, date: Optional[datetime] = None) -> Dict[str, List[Dict]]:
        """Extrait les donnees brutes depuis les deux sources.

        Args:
            date: Date cible de l'extraction. Si absente, J-1 UTC est utilise.

        Returns:
            Dictionnaire par source (`infoclimat`, `wunderground`).
        """
        if date is None:
            date = datetime.utcnow() - timedelta(days=1)

        logger.info(f"Extraction des données pour le {date:%Y-%m-%d}")

        extracted = {"infoclimat": [], "wunderground": []}

        try:
            data = self.infoclimat_extractor.extract(date)
            extracted["infoclimat"] = data
            logger.success(f"✓ {len(data)} InfoClimat extraits")
        except Exception as e:
            logger.error(f"Extraction InfoClimat échouée: {e}")
            self.stats["errors"].append(str(e))

        try:
            data = self.wunderground_extractor.extract(date)
            extracted["wunderground"] = data
            logger.success(f"✓ {len(data)} Weather Underground extraits")
        except Exception as e:
            logger.error(f"Extraction Wunderground échouée: {e}")
            self.stats["errors"].append(str(e))

        total = len(extracted["infoclimat"]) + len(extracted["wunderground"])
        self.stats["records_extracted"] = total

        return extracted

    # -----------------------------------------------------------------------

    def transform_data(self, raw_data: Dict[str, List[Dict]]) -> List[Dict]:
        """Harmonise les formats source vers un schema commun."""
        logger.info("Transformation des données")

        results = []

        for record in raw_data.get("infoclimat", []):
            try:
                results.append(self.harmonizer.harmonize_infoclimat(record))
            except Exception:
                self.stats["records_rejected"] += 1

        for record in raw_data.get("wunderground", []):
            try:
                results.append(self.harmonizer.harmonize_wunderground(record))
            except Exception:
                self.stats["records_rejected"] += 1

        self.stats["records_transformed"] = len(results)
        logger.success(f"✓ {len(results)} enregistrements transformés")

        return results

    # -----------------------------------------------------------------------

    def validate_data(self, records: List[Dict]) -> List[Dict]:
        """Valide les enregistrements et filtre ceux rejetes."""
        logger.info(f"Validation de {len(records)} enregistrements")

        valid = []

        for record in records:
            try:
                res = self.validator.validate(record)
                if res["is_valid"]:
                    valid.append(record)
                else:
                    self.stats["records_rejected"] += 1
            except Exception:
                self.stats["records_rejected"] += 1

        self.stats["records_validated"] = len(valid)
        logger.success(f"✓ {len(valid)} enregistrements validés")

        return valid

    # -----------------------------------------------------------------------

    def load_data(self, records: List[Dict]) -> int:
        """Charge les enregistrements valides en base MongoDB."""
        if not records:
            logger.warning("Aucune donnée à charger")
            return 0

        count = self.mongodb_loader.bulk_insert(records)
        if self.dry_run:
            # bulk_insert() already logs "[DRY-RUN] ... auraient ete inseres".
            self.stats["records_loaded"] = 0
            self.stats["records_loaded_simulated"] = count
            logger.warning(f"[DRY-RUN] ✓ {count} documents auraient été chargés MongoDB")
            return 0

        self.stats["records_loaded"] = count
        logger.success(f"✓ {count} documents chargés MongoDB")
        return count

    # -----------------------------------------------------------------------
    def save_validated_to_s3(self, records: List[Dict], target_date: datetime) -> str:
        """Persist les données validées dans le bucket processed S3."""
        if not records:
            logger.warning("Aucune donnée validée à sauvegarder dans S3")
            return ""

        s3_path = self.s3_loader.save_processed_data(records, target_date)
        self.stats["processed_s3_path"] = s3_path
        return s3_path

    # -----------------------------------------------------------------------

    def generate_quality_report(self, records: List[Dict]) -> Dict:
        """Genere et persiste un rapport de qualite JSON horodate."""
        report = self.quality_checker.generate_report(records, self.stats)

        report_path = LOGS_DIR / f"quality_report_{datetime.utcnow():%Y%m%d_%H%M%S}.json"
        report_path.parent.mkdir(exist_ok=True)

        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, default=str)

        logger.info(f"Rapport qualité sauvegardé: {report_path}")
        return report

    # -----------------------------------------------------------------------

    def write_status_file(self, status: str, duration: float):
        """Ecrit un fichier JSON de statut pour suivi externe."""
        status_data = {
            "status": status,
            "dry_run": bool(self.dry_run),
            "records_extracted": self.stats["records_extracted"],
            "records_validated": self.stats["records_validated"],
            "processed_s3_path": self.stats.get("processed_s3_path"),
            "records_loaded": self.stats.get("records_loaded", 0),
            "records_loaded_simulated": self.stats.get("records_loaded_simulated", 0),
            "duration_seconds": duration,
            "timestamp": datetime.utcnow().isoformat(),
        }

        log_dir = LOGS_DIR
        log_dir.mkdir(exist_ok=True)

        status_path = log_dir / "pipeline_status.json"

        with open(status_path, "w", encoding="utf-8") as f:
            json.dump(status_data, f, indent=4)

        logger.info(f"Status pipeline écrit: {status_path}")

    # -----------------------------------------------------------------------

    def run(self, target_date: Optional[datetime] = None):
        """Execute un run ETL complet.

        Args:
            target_date: Date cible pour l'extraction. Si None, extraction J-1.

        Returns:
            Dictionnaire `stats` agregeant compteurs et erreurs.
        """

        start_time = time.time()
        status = "SUCCESS"

        effective_date = target_date or (datetime.utcnow() - timedelta(days=1))
        try:
            logger.info("======================================================================")
            logger.info("DÉMARRAGE PIPELINE FORECAST 2.0")
            logger.info("======================================================================")

            set_run_context(stage="extract")
            # 1️⃣ EXTRACT
            extracted_data = self.extract_data(effective_date)

            set_run_context(stage="transform")
            # 2️⃣ TRANSFORM
            transformed_data = self.transform_data(extracted_data)

            set_run_context(stage="validate")
            # 3️⃣ VALIDATE
            validated_data = self.validate_data(transformed_data)

            set_run_context(stage="save_processed_s3")
            # 4️⃣ SAVE VALIDATED DATA TO S3 PROCESSED
            self.save_validated_to_s3(validated_data, effective_date)

            set_run_context(stage="load")
            # 5️⃣ LOAD
            self.load_data(validated_data)

            set_run_context(stage="report")
            # 6️⃣ REPORT
            self.generate_quality_report(validated_data)

            logger.success("PIPELINE TERMINÉ AVEC SUCCÈS")

        except Exception as e:
            status = "FAILED"
            logger.error(f"Erreur pipeline: {e}")
            raise

        finally:
            duration = time.time() - start_time
            self.stats["end_time"] = datetime.utcnow()
            self.stats["duration_seconds"] = duration
            self.stats["status"] = status
            self.write_status_file(status, duration)
            logger.info(f"Durée totale: {duration:.2f}s")

        return self.stats


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_arguments():
    """Construit et parse les arguments CLI du pipeline."""
    parser = argparse.ArgumentParser("Forecast 2.0 Pipeline")
    parser.add_argument(
        "--date",
        type=str,
        help="Date cible d'extraction au format YYYY-MM-DD (defaut: J-1 UTC).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Execute sans ecriture MongoDB.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Niveau de log (DEBUG, INFO, WARNING, ERROR).",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=str(DEFAULT_CONFIG_PATH),
        help="Chemin vers pipeline_config.json"
    )
    return parser.parse_args()


def load_config(config_path: str) -> Dict:
    """Charge la configuration JSON du pipeline.

    Si le fichier n'existe pas, un fallback minimal est retourne pour
    permettre l'execution de base.
    """
    path = Path(config_path)

    if not path.is_absolute():
        path = BASE_DIR / path

    try:
        with open(path, "r", encoding="utf-8") as f:
            logger.info(f"Configuration chargée: {path}")
            return json.load(f)
    except FileNotFoundError:
        logger.warning(f"Config introuvable: {path}")
        return {
            "mongodb": {
                "database": "forecast_2_0",
                "collection": "weather_measurements"
            }
        }


def main():
    """Point d'entree CLI: charge la config puis lance le pipeline."""
    load_dotenv()
    _sanitize_runtime_env()

    args = parse_arguments()
    setup_logger(level=args.log_level)

    config = load_config(args.config)

    target_date = (
        datetime.strptime(args.date, "%Y-%m-%d")
        if args.date else datetime.utcnow() - timedelta(days=1)
    )

    run_id = os.getenv("RUN_ID") or str(uuid.uuid4())
    set_run_context(
        run_id=run_id,
        target_date=target_date.strftime("%Y-%m-%d"),
        dry_run=args.dry_run,
    )

    pipeline = Forecast2Pipeline(config, dry_run=args.dry_run)
    stats: Dict[str, Any] = {}
    try:
        stats = pipeline.run(target_date)
    finally:
        emit_pipeline_metrics(stats or pipeline.stats)

    sys.exit(0 if not stats.get("errors") else 1)


if __name__ == "__main__":
    main()
