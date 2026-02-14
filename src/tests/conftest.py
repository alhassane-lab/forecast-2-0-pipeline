"""
Configuration pytest et fixtures partagées
"""

import pytest
import os
from datetime import datetime
from pathlib import Path

from loguru import logger

from utils.logger import setup_logger


@pytest.fixture(scope="session", autouse=True)
def configure_test_logging() -> None:
    """Configure des logs plus detailles pour les tests.

    - Fichier: logs/pytest_*.log en DEBUG (par defaut)
    - Console: INFO (par defaut) pour limiter le bruit, configurable via env
    """
    console_level = os.getenv("PYTEST_CONSOLE_LOG_LEVEL", "INFO")
    file_level = os.getenv("PYTEST_FILE_LOG_LEVEL", "DEBUG")

    log_path = Path("logs") / f"pytest_{datetime.utcnow():%Y%m%d_%H%M%S}.log"
    setup_logger(log_file=str(log_path), console_level=console_level, file_level=file_level)
    logger.info(f"Pytest logging actif: console={console_level} file={file_level} path={log_path}")


def pytest_sessionfinish(session, exitstatus: int) -> None:
    """Log a deterministic test summary (useful in CI logs)."""
    stats = session.testscollected or 0
    tr = session.config.pluginmanager.get_plugin("terminalreporter")
    if tr is None:
        logger.info(f"Pytest terminé: collected={stats} exitstatus={exitstatus}")
        return

    # terminalreporter.stats keys: passed, failed, skipped, error, xfailed, xpassed, ...
    def _count(key: str) -> int:
        return len(tr.stats.get(key, []))

    logger.info(
        "Pytest summary: "
        f"{_count('passed')} passed, "
        f"{_count('failed')} failed, "
        f"{_count('error')} errors, "
        f"{_count('skipped')} skipped "
        f"(collected={stats}, exitstatus={exitstatus})"
    )


def pytest_runtest_logreport(report) -> None:
    """Optionally log each passing test name (disabled by default)."""
    if os.getenv("PYTEST_LOG_PASSED", "").strip().lower() not in {"1", "true", "yes", "y"}:
        return
    if report.when != "call":
        return
    if report.passed:
        logger.info(f"[TEST PASS] {report.nodeid}")
    elif report.failed:
        logger.error(f"[TEST FAIL] {report.nodeid}")


@pytest.fixture(scope="session")
def test_data_dir():
    """Retourne le chemin vers le répertoire de données de test"""
    return Path(__file__).parent / "data"


@pytest.fixture(scope="session")
def mock_env_vars():
    """Mock des variables d'environnement pour les tests"""
    os.environ["AWS_REGION"] = "eu-west-1"
    os.environ["S3_RAW_BUCKET"] = "test-raw-bucket"
    os.environ["S3_PROCESSED_BUCKET"] = "test-processed-bucket"
    os.environ["MONGODB_URI"] = "mongodb://localhost:27017/test"
    os.environ["MONGODB_DATABASE"] = "test_db"
    os.environ["MONGODB_COLLECTION"] = "test_collection"


@pytest.fixture
def sample_config():
    """Configuration de test standard"""
    return {
        "s3": {
            "raw_bucket": "test-raw-bucket",
            "processed_bucket": "test-processed-bucket"
        },
        "mongodb": {
            "database": "test_db",
            "collection": "test_collection"
        },
        "validation": {
            "strict_mode": False
        }
    }
