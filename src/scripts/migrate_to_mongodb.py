"""Migre un fichier JSON MongoDB-ready vers MongoDB Atlas."""

import argparse
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from dotenv import load_dotenv
from loguru import logger

from loaders.mongodb_loader import MongoDBLoader
from pipeline.transformers.quality_checker import QualityChecker
from utils.logger import setup_logger

PROJECT_ROOT = Path.cwd()
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "src" / "config" / "pipeline_config.json"
LOGS_DIR = PROJECT_ROOT / "logs"
DEFAULT_INPUT = PROJECT_ROOT / "data" / "processed" / "mongodb_ready_records.json"


def _load_config(config_path: str) -> Dict:
    path = Path(config_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path

    if not path.exists():
        return {"mongodb": {"database": "forecast_2_0", "collection": "weather_measurements"}}

    return json.loads(path.read_text(encoding="utf-8"))


def _load_records(input_path: str) -> List[Dict]:
    path = Path(input_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path

    if not path.exists():
        raise FileNotFoundError(f"Fichier introuvable: {path}")

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Le fichier d'entree doit contenir une liste JSON")

    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser("Migrate MongoDB-ready JSON data to MongoDB")
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Fichier JSON d'entree")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Configuration pipeline")
    parser.add_argument("--dry-run", action="store_true", help="Simule sans ecriture en base")
    parser.add_argument("--upsert", action="store_true", help="Utilise upsert au lieu de insert_many")
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    args = parse_args()
    setup_logger(args.log_level)

    config = _load_config(args.config)
    records = _load_records(args.input)

    loader = MongoDBLoader(config=config, dry_run=args.dry_run)
    start = time.perf_counter()

    if args.upsert:
        loaded = loader.upsert_records(records)
    else:
        loaded = loader.bulk_insert(records)

    elapsed = time.perf_counter() - start

    rejected = max(0, len(records) - loaded)
    error_rate = (rejected / len(records)) if records else 0.0

    stats = {
        "start_time": datetime.utcnow(),
        "records_extracted": len(records),
        "records_transformed": len(records),
        "records_validated": len(records),
        "records_loaded": loaded,
        "records_rejected": rejected,
        "duration_seconds": round(elapsed, 4),
        "errors": [],
    }

    quality_report = QualityChecker().generate_report(records[:loaded] if loaded else [], stats)

    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    migration_report_path = LOGS_DIR / f"migration_report_{datetime.utcnow():%Y%m%d_%H%M%S}.json"
    payload = {
        "summary": {
            "input_records": len(records),
            "loaded_records": loaded,
            "rejected_records": rejected,
            "error_rate": round(error_rate, 4),
            "duration_seconds": round(elapsed, 4),
            "mode": "dry-run" if args.dry_run else ("upsert" if args.upsert else "insert"),
        },
        "quality": quality_report,
    }
    migration_report_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    logger.success(f"Migration terminee. Charges: {loaded}/{len(records)} | error_rate={error_rate:.2%}")
    logger.info(f"Rapport migration: {migration_report_path}")

    loader.close()


if __name__ == "__main__":
    main()
