"""pytest 公共 fixture。"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture()
def tmp_db(tmp_path: Path) -> Path:
    """临时数据库路径。"""
    db_path = tmp_path / "test.db"
    yield db_path
    for suffix in ("", "-wal", "-shm"):
        p = Path(str(db_path) + suffix)
        if p.exists():
            try:
                p.unlink()
            except OSError:
                pass
