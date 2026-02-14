"""Exemples CRUD MongoDB sur la collection weather_measurements."""

import argparse
import json
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger

from loaders.mongodb_loader import MongoDBLoader
from utils.logger import setup_logger

PROJECT_ROOT = Path.cwd()
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "src" / "config" / "pipeline_config.json"


def _load_config(config_path: str) -> dict:
    path = Path(config_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    if not path.exists():
        return {"mongodb": {"database": "forecast_2_0", "collection": "weather_measurements"}}
    return json.loads(path.read_text(encoding="utf-8"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser("MongoDB CRUD demo")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    args = parse_args()
    setup_logger(args.log_level)

    loader = MongoDBLoader(_load_config(args.config), dry_run=False)
    col = loader.collection

    # CREATE
    sample = {
        "station": {
            "id": "DEMO001",
            "name": "Demo Station",
            "network": "Demo",
            "location": {"latitude": 50.63, "longitude": 3.06, "elevation": 30},
        },
        "timestamp": datetime.utcnow().isoformat(),
        "measurements": {"temperature": {"value": 21.5, "unit": "°C"}},
        "data_quality": {"completeness_score": 1.0, "validation_passed": True},
        "metadata": {"source_file": "crud_demo", "pipeline_version": "1.0.0"},
    }
    inserted_id = col.insert_one(sample).inserted_id
    logger.info(f"CREATE ok: _id={inserted_id}")

    # READ
    doc = col.find_one({"_id": inserted_id})
    logger.info(f"READ ok: station={doc['station']['name']}")

    # UPDATE
    col.update_one({"_id": inserted_id}, {"$set": {"measurements.temperature.value": 22.0}})
    updated = col.find_one({"_id": inserted_id})
    logger.info(f"UPDATE ok: temperature={updated['measurements']['temperature']['value']}")

    # DELETE
    col.delete_one({"_id": inserted_id})
    deleted = col.find_one({"_id": inserted_id})
    logger.info(f"DELETE ok: exists={deleted is not None}")

    loader.close()


if __name__ == "__main__":
    main()
