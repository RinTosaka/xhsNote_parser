from __future__ import annotations

import re

import pytest

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


def test_build_note_detail_reports_empty_note_detail_map() -> None:
    with pytest.raises(ValueError, match="页面未返回笔记详情"):
        build_note_detail({"noteDetailMap": {}}, "https://example.com/note/note123")


def test_build_note_detail_accepts_direct_note_entry() -> None:
    detail = build_note_detail(
        {
            "noteDetailMap": {
                "note123": {
                    "noteId": "note123",
                    "title": "标题",
                    "imageList": [],
                }
            }
        },
        "https://example.com/note/note123",
    )

    assert detail["noteId"] == "note123"
    assert detail["title"] == "标题"
