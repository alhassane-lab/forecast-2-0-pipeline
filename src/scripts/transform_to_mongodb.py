"""Transforme les donnees meteo en format compatible MongoDB."""

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv
from loguru import logger

from pipeline.extractors.infoclimat_extractor import InfoClimatExtractor
from pipeline.extractors.wunderground_extractor import WundergroundExtractor
from pipeline.transformers.data_harmonizer import DataHarmonizer
from pipeline.transformers.data_validator import DataValidator
from pipeline.transformers.quality_checker import QualityChecker
from utils.logger import setup_logger

PROJECT_ROOT = Path.cwd()
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "src" / "config" / "pipeline_config.json"
LOGS_DIR = PROJECT_ROOT / "logs"
DATA_DIR = PROJECT_ROOT / "data"


def _load_config(config_path: str) -> Dict:
    path = Path(config_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path

    if not path.exists():
        logger.warning(f"Config introuvable: {path}. Fallback minimal utilise.")
        return {
            "mongodb": {"database": "forecast_2_0", "collection": "weather_measurements"},
            "validation": {"strict_mode": False},
        }

    return json.loads(path.read_text(encoding="utf-8"))


def _extract_records(
    config: Dict,
    date: Optional[datetime],
) -> Dict[str, List[Dict]]:
    info = InfoClimatExtractor(config)
    wu = WundergroundExtractor(config)

    target_date = date or datetime.utcnow()
    return {
        "infoclimat": info.extract(target_date),
        "wunderground": wu.extract(target_date),
    }


def _transform_and_validate(config: Dict, extracted: Dict[str, List[Dict]]) -> Dict[str, List[Dict]]:
    harmonizer = DataHarmonizer(config)
    validator = DataValidator(config)

    transformed: List[Dict] = []
    rejected = 0

    for rec in extracted.get("infoclimat", []):
        try:
            transformed.append(harmonizer.harmonize_infoclimat(rec))
        except Exception as exc:
            rejected += 1
            logger.warning(f"Harmonisation InfoClimat rejetee: {exc}")

    for rec in extracted.get("wunderground", []):
        try:
            transformed.append(harmonizer.harmonize_wunderground(rec))
        except Exception as exc:
            rejected += 1
            logger.warning(f"Harmonisation Wunderground rejetee: {exc}")

    validated: List[Dict] = []
    validation_errors = 0
    for rec in transformed:
        result = validator.validate(rec)
        if result["is_valid"]:
            validated.append(rec)
        else:
            validation_errors += 1

    stats = {
        "records_extracted": len(extracted.get("infoclimat", [])) + len(extracted.get("wunderground", [])),
        "records_transformed": len(transformed),
        "records_validated": len(validated),
        "records_rejected": rejected + validation_errors,
    }

    return {
        "transformed": transformed,
        "validated": validated,
        "stats": stats,
    }


def _write_quality_report(validated: List[Dict], stats: Dict) -> Path:
    checker = QualityChecker()
    report = checker.generate_report(validated, stats)

    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = LOGS_DIR / f"quality_report_transform_{datetime.utcnow():%Y%m%d_%H%M%S}.json"
    report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return report_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser("Transform weather data to MongoDB-compatible JSON")
    parser.add_argument("--date", help="Date cible YYYY-MM-DD pour extraction S3")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Chemin config JSON")
    parser.add_argument(
        "--output",
        default=str(DATA_DIR / "processed" / "mongodb_ready_records.json"),
        help="Fichier de sortie JSON",
    )
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    args = parse_args()
    setup_logger(args.log_level)

    config = _load_config(args.config)
    target_date = datetime.strptime(args.date, "%Y-%m-%d") if args.date else None

    extracted = _extract_records(
        config=config,
        date=target_date,
    )

    result = _transform_and_validate(config, extracted)
    validated = result["validated"]
    stats = result["stats"]

    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = PROJECT_ROOT / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validated, indent=2, default=str), encoding="utf-8")

    quality_report_path = _write_quality_report(validated, stats)

    logger.success(f"{len(validated)} enregistrements MongoDB-ready ecrits dans {output_path}")
    logger.info(f"Rapport qualite transformation: {quality_report_path}")


if __name__ == "__main__":
    main()
