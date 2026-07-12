"""app 桥接:从 web.app 重导出 create_app。"""
from __future__ import annotations

from .web.app import create_app

__all__ = ["create_app"]
