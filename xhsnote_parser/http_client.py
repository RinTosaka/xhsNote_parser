import logging
from typing import Dict, Optional

import requests

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/000000000 Safari/537.36"
    )
}
DEFAULT_TIMEOUT = 15


def fetch_note_page(
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = DEFAULT_TIMEOUT,
    session: Optional[requests.Session] = None,
) -> str:
    """Fetch note HTML content with basic error handling."""
    merged_headers = {**DEFAULT_HEADERS, **(headers or {})}
    http_session = session or requests.Session()
    logger.debug("Fetching note url=%s timeout=%s", url, timeout)
    try:
        response = http_session.get(url, headers=merged_headers, timeout=timeout)
        response.raise_for_status()
        logger.info("Fetched note content (%s)", response.status_code)
        return response.text
    except requests.RequestException as exc:
        logger.exception("网络请求失败: %s", exc)
        raise RuntimeError("拉取笔记页面失败") from exc
