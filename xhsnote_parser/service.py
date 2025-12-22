from pathlib import Path
from typing import Any, Dict, Optional

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
) -> Dict[str, Any]:
    html = fetch_note_page(url, headers=headers, timeout=timeout, session=session)
    note_data = extract_note_data(html)
    note_detail = build_note_detail(note_data, url)
    if output_path:
        save_note_detail(note_detail, output_path)
    return note_detail
