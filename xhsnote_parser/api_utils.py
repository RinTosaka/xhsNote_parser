from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

_INVALID_FILENAME_CHARS = set('<>:"/\\|?*')


def sanitize_segment(value: Optional[Any], fallback: str) -> str:
    if value in (None, ""):
        text = ""
    else:
        text = str(value)
    sanitized = []
    for char in text:
        if char in _INVALID_FILENAME_CHARS or ord(char) < 32:
            sanitized.append("_")
        else:
            sanitized.append(char)
    cleaned = "".join(sanitized).strip().rstrip(". ")
    return cleaned or fallback


def build_output_path(
    note_detail: Dict[str, Any],
    base_dir: Path,
    *,
    suffix: str = "noteDetail",
) -> Path:
    user = note_detail.get("user") or {}
    author = sanitize_segment(user.get("nickname"), "unknown_author")
    title = sanitize_segment(note_detail.get("title"), "untitled")
    note_id = sanitize_segment(note_detail.get("noteId"), "note")
    filename = f"{title}_{note_id}_{suffix}.json"
    return base_dir / f"{author}_notes" / filename


def safe_resolve(base_dir: Path, relative_path: str) -> Path:
    candidate = Path(relative_path)
    if candidate.is_absolute() or ":" in relative_path:
        raise ValueError("Absolute paths are not allowed.")
    resolved = (base_dir / candidate).resolve()
    base_resolved = base_dir.resolve()
    if resolved != base_resolved and base_resolved not in resolved.parents:
        raise ValueError("Path escapes output directory.")
    return resolved


def _cleanup_empty_parents(target: Path, *, base_dir: Path) -> None:
    base_resolved = base_dir.resolve()
    current = target.parent.resolve()
    while current != base_resolved and base_resolved in current.parents:
        try:
            current.rmdir()
        except OSError:
            break
        current = current.parent.resolve()


def delete_output_file(base_dir: Path, relative_path: str) -> Path:
    """Delete a persisted JSON output file under base_dir.

    Ensures relative_path cannot escape base_dir and prunes empty parent folders.
    """

    target = safe_resolve(base_dir, relative_path)
    if not target.exists():
        raise FileNotFoundError(relative_path)
    if not target.is_file():
        raise IsADirectoryError(relative_path)
    target.unlink()
    _cleanup_empty_parents(target, base_dir=base_dir)
    return target


def cleanup_outputs(base_dir: Path, *, max_age_seconds: int) -> List[str]:
    """Delete persisted output JSON files older than max_age_seconds.

    Returns the list of deleted relative paths.
    """

    if max_age_seconds <= 0:
        return []
    if not base_dir.exists():
        return []

    now_ts = datetime.now().timestamp()
    cutoff_ts = now_ts - max_age_seconds
    deleted: List[str] = []

    for path in base_dir.rglob("*.json"):
        if not path.is_file():
            continue
        name = path.name
        if not (name.endswith("_noteDetail.json") or name.endswith("_initial_state.json")):
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        if stat.st_mtime >= cutoff_ts:
            continue
        relative = path.relative_to(base_dir).as_posix()
        try:
            path.unlink()
        except OSError:
            continue
        _cleanup_empty_parents(path, base_dir=base_dir)
        deleted.append(relative)

    return deleted


@dataclass(frozen=True)
class OutputItem:
    relative_path: str
    absolute_path: str
    size: int
    modified_time: str
    kind: str


def list_outputs(base_dir: Path, *, limit: int = 50) -> List[OutputItem]:
    if not base_dir.exists():
        return []
    items: List[OutputItem] = []
    for path in base_dir.rglob("*.json"):
        if not path.is_file():
            continue
        name = path.name
        if name.endswith("_noteDetail.json"):
            kind = "noteDetail"
        elif name.endswith("_initial_state.json"):
            kind = "initial_state"
        else:
            continue
        stat = path.stat()
        relative = path.relative_to(base_dir).as_posix()
        items.append(
            OutputItem(
                relative_path=relative,
                absolute_path=str(path),
                size=stat.st_size,
                modified_time=datetime.fromtimestamp(stat.st_mtime).isoformat(),
                kind=kind,
            )
        )
    items.sort(key=lambda item: item.modified_time, reverse=True)
    return items[:limit]
