import logging
from pathlib import Path

from xhsnote_parser.logging_utils import configure_logging


def test_configure_logging_writes_file(tmp_path: Path) -> None:
    log_dir = tmp_path / "logs"
    configure_logging(logging.INFO, log_dir=log_dir, enable_file=True)

    logger = logging.getLogger("xhsnote_parser.tests")
    logger.info("hello file logging")

    log_file = log_dir / "xhsnote_parser.log"
    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8")
    assert "hello file logging" in content
