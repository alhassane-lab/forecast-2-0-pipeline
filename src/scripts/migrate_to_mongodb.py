"""Migre un fichier JSON MongoDB-ready vers MongoDB sur AWS ECS."""

import argparse
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from dotenv import load_dotenv
from loguru import logger

from loaders.mongodb_loader import MongoDBLoader
from loaders.s3_loader import S3Loader
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


def _load_records_from_s3(config: Dict, s3_key: str) -> List[Dict]:
    loader = S3Loader(config)
    return loader.load_processed_data(s3_key)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser("Migrate MongoDB-ready JSON data to MongoDB")
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Fichier JSON d'entree")
    parser.add_argument("--input-s3-key", help="Cle S3 explicite (ex: processed/weather_data_20260218_194202.json)")
    parser.add_argument("--input-s3-date", help="Date cible S3 (YYYY-MM-DD), charge le dernier JSON du prefix")
    parser.add_argument("--input-s3-latest", action="store_true", help="Charge le dernier JSON de processed/ depuis S3")
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

    input_mode_count = sum(bool(v) for v in [args.input_s3_key, args.input_s3_date, args.input_s3_latest])
    if input_mode_count > 1:
        raise ValueError("Utiliser un seul mode d'entree S3: --input-s3-key, --input-s3-date ou --input-s3-latest")

    s3_source = None
    s3_bucket = None
    if args.input_s3_key or args.input_s3_date or args.input_s3_latest:
        s3_loader = S3Loader(config)
        s3_bucket = s3_loader.bucket
        if args.input_s3_key:
            s3_source = args.input_s3_key
        elif args.input_s3_date:
            target_date = datetime.strptime(args.input_s3_date, "%Y-%m-%d")
            s3_source = s3_loader.get_latest_processed_key(date=target_date)
        else:
            s3_source = s3_loader.get_latest_processed_key()
        records = _load_records_from_s3(config, s3_source)
        logger.info(f"Source migration S3: s3://{s3_loader.bucket}/{s3_source}")
    else:
        records = _load_records(args.input)

    loader = MongoDBLoader(config=config, dry_run=args.dry_run)
    started_at = datetime.utcnow()
    start = time.perf_counter()

    if args.upsert:
        upsert_stats = loader.upsert_records_with_stats(records)
        loaded = upsert_stats["upserted_records"]
        duplicates_ignored = 0
        failed_records = upsert_stats["failed_records"]
    else:
        insert_stats = loader.bulk_insert_with_stats(records)
        loaded = insert_stats["inserted_records"]
        duplicates_ignored = insert_stats["duplicates_ignored"]
        failed_records = insert_stats["failed_records"]

    elapsed = time.perf_counter() - start
    ended_at = datetime.utcnow()

    error_rate = (failed_records / len(records)) if records else 0.0

    stats = {
        "start_time": started_at,
        "end_time": ended_at,
        "records_extracted": len(records),
        "records_transformed": len(records),
        "records_validated": len(records),
        "records_loaded": loaded,
        "records_rejected": failed_records,
        "duration_seconds": round(elapsed, 4),
        "errors": [],
    }

    quality_report = QualityChecker().generate_report(records[:loaded] if loaded else [], stats)

    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    migration_report_path = LOGS_DIR / f"migration_report_{datetime.utcnow():%Y%m%d_%H%M%S}.json"
    payload = {
        "summary": {
            "input_records": len(records),
            "input_source": f"s3://{s3_bucket}/{s3_source}" if s3_source else str(Path(args.input)),
            "loaded_records": loaded,
            "duplicates_ignored": duplicates_ignored,
            "failed_records": failed_records,
            "error_rate": round(error_rate, 4),
            "duration_seconds": round(elapsed, 4),
            "mode": "dry-run" if args.dry_run else ("upsert" if args.upsert else "insert"),
        },
        "quality": quality_report,
    }
    migration_report_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    report_loader = S3Loader(config)
    migration_s3_path = report_loader.save_report_json(
        report_type="migration_report",
        payload=payload,
        run_date=ended_at,
    )
    logger.info(json.dumps({
        "event": "report_published",
        "report_type": "migration_report",
        "s3_path": migration_s3_path,
    }))

    logger.success(
        "Migration terminee. "
        f"Charges: {loaded}/{len(records)} | "
        f"doublons={duplicates_ignored} | "
        f"failed={failed_records} | "
        f"error_rate={error_rate:.2%}"
    )
    logger.info(f"Rapport migration: {migration_report_path}")

    loader.close()


if __name__ == "__main__":
    main()
