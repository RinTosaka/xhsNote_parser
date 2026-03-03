from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any, Dict, List

import requests

from xhsnote_parser.service import parse_note


@dataclass
class FakeResponse:
    url: str
    text: str
    status_code: int = 200
    headers: Dict[str, str] = field(default_factory=dict)
    history: List["FakeResponse"] = field(default_factory=list)

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self, mapping: Dict[str, FakeResponse]) -> None:
        self._mapping = mapping

    def get(self, url: str, **_kwargs: Any) -> FakeResponse:
        try:
            return self._mapping[url]
        except KeyError as exc:
            raise AssertionError(f"Unexpected GET url={url}") from exc


def _build_note_html(note_url: str, note_id: str = "note123") -> str:
    initial_state = {
        "note": {
            "noteDetailMap": {
                note_id: {
                    "note": {
                        "noteId": note_id,
                        "title": "标题",
                        "user": {"nickname": "作者"},
                        "imageList": [],
                        "time": 1700000000000,
                        "lastUpdateTime": 1700000000000,
                        "shareLink": note_url,
                    }
                }
            }
        }
    }
    raw_json = json.dumps(initial_state, ensure_ascii=False)
    return f"<html><script>window.__INITIAL_STATE__={raw_json}</script></html>"


def test_parse_note_supports_xhslink_short_link_share_text() -> None:
    short_url = "http://xhslink.com/o/4zq6oYT9J5F"
    resolved_url = "https://www.xiaohongshu.com/explore/note123"
    share_text = f"我的入春漂亮18图 {short_url}\n复制后打开【小红书】查看笔记！"

    open_app_html = "<html>open app</html>"
    redirect = FakeResponse(
        url=short_url,
        text="",
        status_code=302,
        headers={"Location": resolved_url},
    )
    open_app = FakeResponse(
        url="https://xhslink.com/openapp",
        text=open_app_html,
        history=[redirect],
    )
    note_page = FakeResponse(
        url=resolved_url,
        text=_build_note_html(resolved_url),
    )
    session = FakeSession(
        {
            short_url: open_app,
            resolved_url: note_page,
        }
    )

    result = parse_note(share_text, output_path=None, session=session)  # type: ignore[arg-type]

    assert result["noteId"] == "note123"
    assert result["noteUrl"] == resolved_url
    assert result["inputUrl"] == share_text
