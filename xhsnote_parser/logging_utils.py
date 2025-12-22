import argparse
import logging

logger = logging.getLogger(__name__)


def configure_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )
    logger.debug("Logger configured with level %s", logging.getLevelName(level))


def resolve_log_level(level_name: str) -> int:
    normalized = level_name.upper()
    level = getattr(logging, normalized, None)
    if not isinstance(level, int):
        raise argparse.ArgumentTypeError(f"未知日志等级: {level_name}")
    return level
