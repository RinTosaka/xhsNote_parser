from __future__ import annotations

import json

from xhsnote_parser.note_detail import extract_note_data


def _sample_state() -> dict:
    return {
        "note": {
            "noteDetailMap": {
                "note123": {
                    "note": {
                        "noteId": "note123",
                        "title": "标题",
                        "desc": "包含 } 和 undefined 文本",
                        "imageList": [],
                    }
                }
            }
        }
    }


def test_extract_note_data_supports_script_attributes_and_semicolon() -> None:
    raw_json = json.dumps(_sample_state(), ensure_ascii=False)
    html = (
        '<html><script nonce="abc" type="text/javascript">\n'
        f"  window.__INITIAL_STATE__ = {raw_json};\n"
        "</script></html>"
    )

    note_data, full_state = extract_note_data(html)

    assert full_state == _sample_state()
    assert note_data["noteDetailMap"]["note123"]["note"]["noteId"] == "note123"


def test_extract_note_data_replaces_undefined_values_only() -> None:
    html = """
    <script>
      window.__INITIAL_STATE__ = {
        "note": {
          "noteDetailMap": {
            "note123": {
              "note": {
                "noteId": "note123",
                "title": "undefined should stay in strings",
                "desc": undefined,
                "imageList": []
              }
            }
          }
        }
      }
    </script>
    """

    note_data, _full_state = extract_note_data(html)

    note = note_data["noteDetailMap"]["note123"]["note"]
    assert note["title"] == "undefined should stay in strings"
    assert note["desc"] is None
