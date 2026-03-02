from __future__ import annotations

import re

from xhsnote_parser.note_detail import build_note_detail


def test_build_note_detail_renames_time_to_create_time() -> None:
    note_data = {
        "noteDetailMap": {
            "k": {
                "note": {
                    "noteId": "note123",
                    "time": 1700000000000,
                    "lastUpdateTime": 1700000005000,
                    "imageList": [],
                }
            }
        }
    }

    detail = build_note_detail(note_data, "https://example.com/note/note123")

    assert "time" not in detail
    assert "CreateTime" in detail
    assert isinstance(detail["CreateTime"], str)
    assert re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$", detail["CreateTime"])
    assert isinstance(detail["lastUpdateTime"], str)
    assert re.match(
        r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$", detail["lastUpdateTime"]
    )
