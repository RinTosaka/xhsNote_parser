from __future__ import annotations

import os
import time
from pathlib import Path

from xhsnote_parser.api_utils import cleanup_outputs


def test_cleanup_outputs_deletes_old_outputs_only(sandbox_tmp_path: Path) -> None:
    base_dir = sandbox_tmp_path / "output"
    base_dir.mkdir(parents=True, exist_ok=True)

    old_note = base_dir / "a" / "old_note_noteDetail.json"
    old_state = base_dir / "a" / "old_note_initial_state.json"
    new_note = base_dir / "b" / "new_note_noteDetail.json"
    other_json = base_dir / "b" / "keep.json"

    for path in [old_note, old_state, new_note, other_json]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8")

    now = time.time()
    os.utime(old_note, (now - 10_000, now - 10_000))
    os.utime(old_state, (now - 10_000, now - 10_000))
    os.utime(new_note, (now - 10, now - 10))
    os.utime(other_json, (now - 10_000, now - 10_000))

    deleted = cleanup_outputs(base_dir, max_age_seconds=3600)

    assert sorted(deleted) == sorted(
        [
            "a/old_note_noteDetail.json",
            "a/old_note_initial_state.json",
        ]
    )
    assert not old_note.exists()
    assert not old_state.exists()
    assert new_note.exists()
    assert other_json.exists()

