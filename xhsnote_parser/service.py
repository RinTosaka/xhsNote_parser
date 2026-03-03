import logging
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import requests

from .http_client import DEFAULT_TIMEOUT, fetch_note_page_with_final_url
from .note_detail import build_note_detail, extract_note_data
from .storage import save_note_detail

logger = logging.getLogger(__name__)


def parse_note(
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = DEFAULT_TIMEOUT,
    output_path: Optional[Path] = Path("output"),
    session: Optional[requests.Session] = None,
    on_initial_state: Optional[Callable[[Dict[str, Any]], None]] = None,
) -> Dict[str, Any]:
    html, resolved_url = fetch_note_page_with_final_url(
        url, headers=headers, timeout=timeout, session=session
    )
    note_data, initial_state = extract_note_data(html)
    if on_initial_state is not None:
        try:
            on_initial_state(initial_state)
        except Exception as exc:  # pragma: no cover - 回调不应影响主流程
            logger.warning("on_initial_state 回调执行失败: %s", exc, exc_info=True)
    note_detail = build_note_detail(note_data, resolved_url)
    note_detail["inputUrl"] = url
    if output_path:
        save_note_detail(note_detail, output_path)
    return note_detail

