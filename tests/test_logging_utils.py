import logging
from pathlib import Path

from xhsnote_parser.logging_utils import configure_logging


def test_configure_logging_writes_file(sandbox_tmp_path: Path) -> None:
    log_dir = sandbox_tmp_path / "logs"
    configure_logging(logging.INFO, log_dir=log_dir, enable_file=True)

    logger = logging.getLogger("xhsnote_parser.tests")
    logger.info("hello file logging")

    logging.shutdown()

    log_files = list(log_dir.glob("*.log"))
    assert log_files
    content = log_files[0].read_text(encoding="utf-8")
    assert "hello file logging" in content
