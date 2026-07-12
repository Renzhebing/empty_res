"""原件整理:把发票复制到 library/YYYY-MM/项目/。"""
from __future__ import annotations

import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from ..paths import ensure_dir, unique_path


def safe_project_name(name: str) -> str:
    """替换文件系统非法字符为 _。"""
    return re.sub(r'[\\/:*?"<>|]', "_", name).strip() or "未分类"


def organize(src_path: Path, invoice_data: dict[str, Any], library_root: Path) -> Path:
    """把原件复制到 library/YYYY-MM/项目/。

    Args:
        src_path: 源文件路径。
        invoice_data: 发票数据(取 invoice_date 和 project)。
        library_root: 库根目录。

    Returns:
        stored_path: 存储后的路径。
    """
    # 月份目录:invoice_date 前 7 位 YYYY-MM,缺失用当前月份
    invoice_date = str(invoice_data.get("invoice_date") or "")
    if len(invoice_date) >= 7:
        month = invoice_date[:7]
    else:
        month = datetime.now().strftime("%Y-%m")

    # 项目目录
    project = safe_project_name(str(invoice_data.get("project") or "未分类"))

    dest_dir = library_root / month / project
    ensure_dir(dest_dir)

    src_path = Path(src_path)
    dest_path = unique_path(dest_dir, src_path.name)
    shutil.copy2(src_path, dest_path)
    return dest_path
