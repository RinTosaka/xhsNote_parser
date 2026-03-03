from __future__ import annotations

from pathlib import Path

import pytest

from xhsnote_parser.api_utils import delete_output_file


def test_delete_output_file_removes_target_and_prunes_empty_parents(
    sandbox_tmp_path: Path,
) -> None:
    base_dir = sandbox_tmp_path / "output"
    target = base_dir / "author_notes" / "note_noteDetail.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("{}", encoding="utf-8")

    assert target.exists()
    delete_output_file(base_dir, "author_notes/note_noteDetail.json")

    assert not target.exists()
    assert not (base_dir / "author_notes").exists()


def test_delete_output_file_does_not_prune_non_empty_parent(sandbox_tmp_path: Path) -> None:
    base_dir = sandbox_tmp_path / "output"
    base_dir.mkdir(parents=True, exist_ok=True)
    parent = base_dir / "author_notes"
    parent.mkdir(parents=True, exist_ok=True)
    target = parent / "note_noteDetail.json"
    sibling = parent / "keep_initial_state.json"
    target.write_text("{}", encoding="utf-8")
    sibling.write_text("{}", encoding="utf-8")

    delete_output_file(base_dir, "author_notes/note_noteDetail.json")

    assert not target.exists()
    assert sibling.exists()
    assert parent.exists()


def test_delete_output_file_rejects_escaping_paths(sandbox_tmp_path: Path) -> None:
    base_dir = sandbox_tmp_path / "output"
    base_dir.mkdir(parents=True, exist_ok=True)

    with pytest.raises(ValueError):
        delete_output_file(base_dir, "../evil.json")

