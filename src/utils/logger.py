"""Configuration du système de logging avec sortie JSON / EMF friendly."""

import os
import sys
from pathlib import Path
from loguru import logger

def setup_logger(
    level: str = "INFO",
    log_file: str | None = None,
    console_level: str | None = None,
    file_level: str | None = None,
    log_format: str | None = None,
):
    """Configure loguru avec contextes, format JSON ou texte et rotation disque.

    Args:
        level: Niveau par défaut (DEBUG/INFO/WARNING/ERROR).
        log_file: Fichier de log optionnel (sinon `logs/pipeline_{date}.log`).
        console_level: Niveau console (sinon `level`).
        file_level: Niveau fichier (sinon `level`).
        log_format: `plain` ou `json`. Par défaut, lit `LOG_FORMAT` env ou `json`.
    """
    logger.remove()

    console_lvl = console_level or level
    file_lvl = file_level or level

    format_choice = (log_format or os.getenv("LOG_FORMAT", "json")).lower()
    if format_choice not in {"plain", "json"}:
        format_choice = "json"

    use_json = format_choice == "json"
    plain_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )
    sink_format = "{message}" if use_json else plain_format

    logger.add(
        sys.stdout,
        format=sink_format,
        level=console_lvl,
        colorize=not use_json,
        serialize=use_json,
    )

    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        logger.add(
            log_file,
            format=sink_format,
            level=file_lvl,
            serialize=use_json,
            rotation="500 MB",
            retention="30 days",
            compression="zip",
        )
    else:
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)

        logger.add(
            logs_dir / "pipeline_{time:YYYY-MM-DD}.log",
            format=sink_format,
            level=file_lvl,
            serialize=use_json,
            rotation="00:00",
            retention="30 days",
            compression="zip",
        )

    logger.info(
        f"Logger configuré - format={format_choice} console={console_lvl} file={file_lvl}"
    )
