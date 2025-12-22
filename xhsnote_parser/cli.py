import argparse
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .http_client import DEFAULT_TIMEOUT
from .logging_utils import configure_logging, resolve_log_level
from .service import parse_note
from .storage import save_note_detail

logger = logging.getLogger(__name__)
_INVALID_FILENAME_CHARS = set('<>:"/\\|?*')
_DEFAULT_OUTPUT_DIR = Path("output")


def _sanitize_segment(value: Optional[Any], fallback: str) -> str:
    if value in (None, ""):
        text = ""
    else:
        text = str(value)
    sanitized = []
    for char in text:
        if char in _INVALID_FILENAME_CHARS or ord(char) < 32:
            sanitized.append("_")
        else:
            sanitized.append(char)
    cleaned = "".join(sanitized).strip().rstrip(". ")
    return cleaned or fallback


def _build_output_path(note_detail: Dict[str, Any], base_dir: Path) -> Path:
    user = note_detail.get("user") or {}
    author = _sanitize_segment(user.get("nickname"), "unknown_author")
    title = _sanitize_segment(note_detail.get("title"), "untitled")
    note_id = _sanitize_segment(note_detail.get("noteId"), "note")
    filename = f"{title}_{note_id}_noteDetail.json"
    return base_dir / f"{author}_notes" / filename


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="解析小红书笔记页面并导出 noteDetail.json"
    )
    parser.add_argument("url", help="小红书笔记 URL")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=_DEFAULT_OUTPUT_DIR,
        help="Output directory for generated JSON (default: output)",
    )
    parser.add_argument(
        "--timeout", type=int, default=DEFAULT_TIMEOUT, help="请求超时时间（秒）"
    )
    parser.add_argument(
        "--user-agent", help="自定义 User-Agent 覆盖默认值", default=None
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        type=resolve_log_level,
        help="日志等级 (DEBUG/INFO/WARNING/ERROR)",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> None:
    parser = build_argument_parser()
    args = parser.parse_args(argv)

    configure_logging(args.log_level)

    headers = {}
    if args.user_agent:
        headers["User-Agent"] = args.user_agent

    try:
        note_detail = parse_note(
            args.url,
            headers=headers or None,
            timeout=args.timeout,
            output_path=None,
        )
        output_dir = args.output or _DEFAULT_OUTPUT_DIR
        output_path = _build_output_path(note_detail, output_dir)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        save_note_detail(note_detail, output_path)
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("解析失败: %s", exc)
        raise SystemExit(1) from exc
