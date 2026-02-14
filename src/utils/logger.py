"""
Configuration du système de logging
"""

import sys
from pathlib import Path
from loguru import logger


def setup_logger(
    level: str = "INFO",
    log_file: str | None = None,
    console_level: str | None = None,
    file_level: str | None = None,
):
    """
    Configure le système de logging avec loguru

    Args:
        level: Niveau de log (DEBUG, INFO, WARNING, ERROR)
        log_file: Chemin vers le fichier de log (optionnel)
        console_level: Niveau pour la console (optionnel, fallback sur `level`)
        file_level: Niveau pour le fichier (optionnel, fallback sur `level`)
    """
    # Supprimer la configuration par défaut
    logger.remove()

    # Format personnalisé
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )

    console_lvl = console_level or level
    file_lvl = file_level or level

    # Handler pour la console
    logger.add(
        sys.stdout,
        format=log_format,
        level=console_lvl,
        colorize=True
    )

    # Handler pour fichier si spécifié
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        logger.add(
            log_file,
            format=log_format,
            level=file_lvl,
            rotation="500 MB",
            retention="30 days",
            compression="zip"
        )
    else:
        # Log par défaut dans logs/
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)

        logger.add(
            logs_dir / "pipeline_{time:YYYY-MM-DD}.log",
            format=log_format,
            level=file_lvl,
            rotation="00:00",
            retention="30 days",
            compression="zip"
        )

    logger.info(
        f"Logger configuré - console={console_lvl} file={file_lvl} (default={level})"
    )
