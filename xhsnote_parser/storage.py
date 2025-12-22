import json
import logging
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)


def save_note_detail(note_detail: Dict[str, Any], path: Path) -> Path:
    path.write_text(json.dumps(note_detail, ensure_ascii=False, indent=4), encoding="utf-8")
    logger.info("笔记内容写入 %s", path)
    return path
