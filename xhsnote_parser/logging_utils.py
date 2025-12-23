import argparse
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)
_LOG_FILENAME = f"xhsnote_parser_{datetime.now():%Y%m%d_%H%M%S}.log"


def configure_logging(
    level: int = logging.INFO,
    *,
    log_dir: Optional[Path] = None,
    enable_file: bool = False,
) -> None:
    handlers = [logging.StreamHandler()]
    log_path: Optional[Path] = None
    if enable_file and log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / _LOG_FILENAME
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        handlers.append(file_handler)

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        handlers=handlers,
        force=True,
    )

    logger.debug("Logger configured with level %s", logging.getLevelName(level))


def resolve_log_level(level_name: str) -> int:
    normalized = level_name.upper()
    level = getattr(logging, normalized, None)
    if not isinstance(level, int):
        raise argparse.ArgumentTypeError(f"传入级别名称无效： {level_name}")
    return level
