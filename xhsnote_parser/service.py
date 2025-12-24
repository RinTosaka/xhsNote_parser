from pathlib import Path
from typing import Any, Callable, Dict, Optional

import requests

from .http_client import DEFAULT_TIMEOUT, fetch_note_page
from .note_detail import build_note_detail, extract_note_data
from .storage import save_note_detail


def parse_note(
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = DEFAULT_TIMEOUT,
    output_path: Optional[Path] = Path("output"),
    session: Optional[requests.Session] = None,
    on_initial_state: Optional[Callable[[Dict[str, Any]], None]] = None,
) -> Dict[str, Any]:
    html = fetch_note_page(url, headers=headers, timeout=timeout, session=session)
    note_data, initial_state = extract_note_data(html)
    if on_initial_state is not None:
        on_initial_state(initial_state)
    note_detail = build_note_detail(note_data, url)
    if output_path:
        save_note_detail(note_detail, output_path)
    return note_detail
