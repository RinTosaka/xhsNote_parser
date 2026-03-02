from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest


@pytest.fixture
def sandbox_tmp_path() -> Path:
    """在仓库内创建可写的临时目录，避免依赖系统 TEMP 目录权限。"""

    base_dir = Path(__file__).resolve().parent / ".tmp"
    base_dir.mkdir(parents=True, exist_ok=True)
    case_dir = base_dir / uuid4().hex
    case_dir.mkdir(parents=True, exist_ok=True)
    return case_dir

