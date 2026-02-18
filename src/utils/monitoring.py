"""Helpers de monitoring : contexte de run et métriques CloudWatch EMF."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from typing import Any, Dict

_RUN_CONTEXT: Dict[str, Any] = {}


def set_run_context(**kwargs: Any) -> None:
    """Met à jour le contexte statique injecté dans chaque log."""
    for key, value in kwargs.items():
        if value is None:
            _RUN_CONTEXT.pop(key, None)
        else:
            _RUN_CONTEXT[key] = value


def get_run_context() -> Dict[str, Any]:
    """Renvoie une copie du contexte courant."""
    return dict(_RUN_CONTEXT)


def patch_log_context(record: Dict[str, Any]) -> None:
    """Ajoute les paires run-context à tous les enregistrements loguru."""
    saved = get_run_context()
    env_name = saved.get("env") or os.getenv("ENVIRONMENT") or os.getenv("ENV") or "dev"
    cluster_name = saved.get("cluster") or os.getenv("CLUSTER_NAME") or "ecs"

    context: Dict[str, Any] = {
        **saved,
        "env": env_name,
        "cluster": cluster_name,
    }

    extra = record.setdefault("extra", {})
    for key, value in context.items():
        if value is not None:
            extra.setdefault(key, value)


def emit_pipeline_metrics(stats: Dict[str, Any]) -> None:
    """Affiche une ligne JSON EMF CloudWatch reprenant les métriques essentielles."""
    timestamp = int(datetime.utcnow().timestamp() * 1000)
    context = get_run_context()
    records_extracted = stats.get("records_extracted", 0)
    records_rejected = stats.get("records_rejected", 0)
    duration = stats.get("duration_seconds", 0.0)
    loaded = stats.get("records_loaded", 0)
    loaded_simulated = stats.get("records_loaded_simulated")
    status = stats.get("status", "UNKNOWN")

    error_rate = (
        (records_rejected / records_extracted * 100)
        if records_extracted
        else 0.0
    )

    payload = {
        "_aws": {
            "Timestamp": timestamp,
            "CloudWatchMetrics": [
                {
                    "Namespace": "Forecast2Pipeline",
                    "Dimensions": [["env", "cluster"]],
                    "Metrics": [
                        {"Name": "duration_seconds", "Unit": "Seconds"},
                        {"Name": "records_extracted", "Unit": "Count"},
                        {"Name": "records_validated", "Unit": "Count"},
                        {"Name": "records_loaded", "Unit": "Count"},
                        {"Name": "records_rejected", "Unit": "Count"},
                        {"Name": "error_rate", "Unit": "Percent"},
                        {"Name": "run_success", "Unit": "Count"},
                    ],
                }
            ],
        },
        "run_id": context.get("run_id"),
        "env": context.get("env"),
        "cluster": context.get("cluster"),
        "target_date": context.get("target_date"),
        "status": status,
        "duration_seconds": round(duration, 3),
        "records_extracted": records_extracted,
        "records_validated": stats.get("records_validated", 0),
        "records_loaded": loaded,
        "records_loaded_simulated": loaded_simulated,
        "records_rejected": records_rejected,
        "error_rate": round(error_rate, 3),
        "run_success": 1 if status == "SUCCESS" else 0,
        "dry_run": bool(context.get("dry_run", False)),
    }

    print(json.dumps(payload, separators=(",", ":")), file=sys.stdout, flush=True)
