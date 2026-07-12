"""路径解析:把 config 中相对项目根的路径解析为绝对路径。"""
from __future__ import annotations

from pathlib import Path

# 项目根目录(fapiao_helper/ 的上一级)
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def resolve(path_str: str) -> Path:
    """把相对项目根的路径解析为绝对路径;已是绝对路径则原样返回。"""
    p = Path(path_str)
    if p.is_absolute():
        return p
    return (PROJECT_ROOT / p).resolve()


def ensure_dir(path: Path) -> Path:
    """确保目录存在,不存在则创建(含父目录)。"""
    path.mkdir(parents=True, exist_ok=True)
    return path


def default_dirs() -> dict[str, Path]:
    """返回默认目录映射(用于首次启动自动创建)。"""
    return {
        "inbox": resolve("invoices/inbox"),
        "library": resolve("invoices/library"),
        "exports": resolve("invoices/exports"),
        "logs": resolve("data/logs"),
        "models": resolve("data/models"),
    }


def unique_path(dest_dir: Path, filename: str) -> Path:
    """生成不冲突的目标路径:若重名自动追加 _2、_3 后缀,不覆盖。"""
    stem = Path(filename).stem
    suffix = Path(filename).suffix
    candidate = dest_dir / filename
    n = 2
    while candidate.exists():
        candidate = dest_dir / f"{stem}_{n}{suffix}"
        n += 1
    return candidate
