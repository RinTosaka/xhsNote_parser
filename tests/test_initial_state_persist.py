from __future__ import annotations

from pathlib import Path

import pytest

from xhsnote_parser import api, cli
from xhsnote_parser.api_models import ParseOptions


def _sample_initial_state() -> dict:
    return {
        "note": {
            "noteDetailMap": {
                "key": {
                    "note": {
                        "title": "标题",
                        "noteId": "note123",
                        "user": {"nickname": "作者"},
                    }
                }
            }
        }
    }


def test_cli_saves_initial_state_even_when_parse_note_fails(
    sandbox_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = _sample_initial_state()
    url = "https://www.xiaohongshu.com/explore/note123"

    def fake_parse_note(*args, **kwargs):  # type: ignore[no-untyped-def]
        callback = kwargs.get("on_initial_state")
        assert callback is not None
        callback(state)
        raise ValueError("boom")

    monkeypatch.setattr(cli, "parse_note", fake_parse_note)

    with pytest.raises(SystemExit) as excinfo:
        cli.main([url, "--save-initial-state", "-o", str(sandbox_tmp_path)])

    assert excinfo.value.code == 1
    expected = sandbox_tmp_path / "作者_notes" / "标题_note123_initial_state.json"
    assert expected.exists()


def test_api_saves_initial_state_even_when_parse_note_fails(
    sandbox_tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = _sample_initial_state()
    url = "https://www.xiaohongshu.com/explore/note123"

    def fake_parse_note(*args, **kwargs):  # type: ignore[no-untyped-def]
        callback = kwargs.get("on_initial_state")
        assert callback is not None
        callback(state)
        raise ValueError("boom")

    monkeypatch.setattr(api, "parse_note", fake_parse_note)

    settings = api.ApiSettings(
        default_timeout=15,
        output_dir=sandbox_tmp_path,
        cors_origins=["*"],
        allow_all_origins=True,
        save_log=False,
        log_dir=None,
        static_dir=None,
        version="test",
    )
    options = ParseOptions(save=False, save_initial_state=True)

    with pytest.raises(api.ParseFailure):
        api._parse_note_sync(url, options=options, settings=settings)

    expected = sandbox_tmp_path / "作者_notes" / "标题_note123_initial_state.json"
    assert expected.exists()
