"""Mesure le temps d'accessibilite des donnees via requete MongoDB."""

import argparse
import json
import time
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger

from loaders.mongodb_loader import MongoDBLoader
from utils.logger import setup_logger

PROJECT_ROOT = Path.cwd()
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "src" / "config" / "pipeline_config.json"
LOGS_DIR = PROJECT_ROOT / "logs"


def _load_config(config_path: str) -> dict:
    path = Path(config_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    if not path.exists():
        return {"mongodb": {"database": "forecast_2_0", "collection": "weather_measurements"}}
    return json.loads(path.read_text(encoding="utf-8"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser("Query latency reporter")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    parser.add_argument("--station-id", required=True, help="Ex: ILAMAD25")
    parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--iterations", type=int, default=5)
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    args = parse_args()
    setup_logger(args.log_level)

    loader = MongoDBLoader(_load_config(args.config), dry_run=False)
    col = loader.collection

    target_day = datetime.strptime(args.date, "%Y-%m-%d")
    next_day = target_day + timedelta(days=1)

    date_start_iso = target_day.strftime("%Y-%m-%dT00:00:00")
    date_end_iso = target_day.strftime("%Y-%m-%dT23:59:59")
    date_start_space = target_day.strftime("%Y-%m-%d 00:00:00")
    date_end_space = target_day.strftime("%Y-%m-%d 23:59:59")

    query = {
        "station.id": args.station_id,
        "$or": [
            {"timestamp": {"$gte": target_day, "$lt": next_day}},
            {"timestamp": {"$gte": date_start_iso, "$lte": date_end_iso}},
            {"timestamp": {"$gte": date_start_space, "$lte": date_end_space}},
        ],
    }

    durations = []
    matched = 0
    for _ in range(max(1, args.iterations)):
        start = time.perf_counter()
        rows = list(col.find(query).limit(10000))
        elapsed = (time.perf_counter() - start) * 1000
        durations.append(elapsed)
        matched = len(rows)

    report = {
        "query": query,
        "iterations": len(durations),
        "matched_rows": matched,
        "latency_ms": {
            "min": round(min(durations), 3),
            "max": round(max(durations), 3),
            "avg": round(sum(durations) / len(durations), 3),
        },
        "generated_at": datetime.utcnow().isoformat(),
    }

    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = LOGS_DIR / f"query_latency_report_{datetime.utcnow():%Y%m%d_%H%M%S}.json"
    report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    logger.success(
        f"Latency avg={report['latency_ms']['avg']}ms | matched={matched} | report={report_path}"
    )

    loader.close()


if __name__ == "__main__":
    main()
