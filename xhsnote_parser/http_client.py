import logging
import re
from typing import Dict, Optional, Tuple
from urllib.parse import urljoin, urlparse

import requests

logger = logging.getLogger(__name__)

_URL_PATTERN = re.compile(r"https?://[^\s\"'<>]+")
_XHS_NOTE_URL_HINT = re.compile(
    r"https?://(?:www\.)?xiaohongshu\.com/(?:explore|discovery/item)/[^\s\"'<>]+",
    re.IGNORECASE,
)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/000000000 Safari/537.36"
    )
}
DEFAULT_TIMEOUT = 15


def _extract_first_url(text: str) -> Optional[str]:
    if not text:
        return None
    match = _URL_PATTERN.search(text)
    if not match:
        return None
    candidate = match.group(0).strip()
    return candidate.rstrip(").,;:!?]}'\"，。；：！？）】」》")


def _normalize_input_to_url(value: str) -> str:
    candidate = _extract_first_url(value)
    return (candidate or value).strip()


def _is_xiaohongshu_host(host: Optional[str]) -> bool:
    if not host:
        return False
    lowered = host.lower()
    return lowered == "xiaohongshu.com" or lowered.endswith(".xiaohongshu.com")


def _find_note_url_in_html(html: str) -> Optional[str]:
    if not html:
        return None
    match = _XHS_NOTE_URL_HINT.search(html)
    if not match:
        return None
    return match.group(0).strip()


def _coerce_absolute_url(base_url: str, value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        return cleaned
    if cleaned.startswith(("http://", "https://")):
        return cleaned
    return urljoin(base_url, cleaned)


def _extract_best_note_url(response: requests.Response, fallback: str) -> str:
    try:
        parsed = urlparse(response.url)
    except Exception:  # pragma: no cover - defensive
        parsed = None

    if parsed and _is_xiaohongshu_host(parsed.hostname):
        return response.url

    for entry in reversed(getattr(response, "history", []) or []):
        location = getattr(entry, "headers", {}).get("Location")
        if not location:
            continue
        absolute = _coerce_absolute_url(response.url or fallback, location)
        try:
            loc_parsed = urlparse(absolute)
        except Exception:  # pragma: no cover - defensive
            continue
        if _is_xiaohongshu_host(loc_parsed.hostname):
            return absolute

    embedded = _find_note_url_in_html(getattr(response, "text", ""))
    if embedded:
        return embedded

    return response.url or fallback


def _has_initial_state(html: str) -> bool:
    return "window.__INITIAL_STATE__" in (html or "")


def fetch_note_page_with_final_url(
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = DEFAULT_TIMEOUT,
    session: Optional[requests.Session] = None,
) -> Tuple[str, str]:
    """Fetch note HTML content and best-effort resolve the final note URL.

    - 支持将「分享文案」作为输入：自动提取第一个 http(s) URL。
    - 支持 xhslink.com 短链：自动跟随跳转并尽量返回最终笔记链接。
    """

    normalized_url = _normalize_input_to_url(url)
    merged_headers = {**DEFAULT_HEADERS, **(headers or {})}
    http_session = session or requests.Session()
    logger.debug(
        "Fetching note url=%s normalized=%s timeout=%s", url, normalized_url, timeout
    )
    try:
        response = http_session.get(
            normalized_url, headers=merged_headers, timeout=timeout, allow_redirects=True
        )
        response.raise_for_status()
        html = response.text

        resolved_url = _extract_best_note_url(response, normalized_url)
        if not _has_initial_state(html) and resolved_url and resolved_url != response.url:
            logger.debug("Re-fetching resolved note url=%s", resolved_url)
            refetched = http_session.get(
                resolved_url,
                headers=merged_headers,
                timeout=timeout,
                allow_redirects=True,
            )
            refetched.raise_for_status()
            html = refetched.text
            resolved_url = refetched.url or resolved_url

        logger.info(
            "Fetched note content (%s) resolved=%s", response.status_code, resolved_url
        )
        return html, resolved_url
    except requests.RequestException as exc:
        logger.exception("ç¼ƒæˆ ç²¶ç’‡é”‹çœ°æ¾¶è¾«è§¦: %s", exc)
        raise RuntimeError("éŽ·å¤Šå½‡ç»—æ—‡î†‡æ¤¤ç”¸æ½°æ¾¶è¾«è§¦") from exc


def fetch_note_page(
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = DEFAULT_TIMEOUT,
    session: Optional[requests.Session] = None,
) -> str:
    """Fetch note HTML content with basic error handling."""
    html, _final_url = fetch_note_page_with_final_url(
        url, headers=headers, timeout=timeout, session=session
    )
    return html
