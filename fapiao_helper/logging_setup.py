"""日志配置:同时写文件(data/logs/YYYY-MM-DD.log)和 run_logs 表。"""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from . import paths


class DbLogHandler(logging.Handler):
    """把日志写入 run_logs 表(懒加载 db_path,避免循环依赖)。"""

    def __init__(self, db_path_getter):
        super().__init__()
        self._db_path_getter = db_path_getter

    def emit(self, record: logging.LogRecord) -> None:
        try:
            from . import db
            db.add_log(
                self._db_path_getter(),
                level=record.levelname,
                msg=record.getMessage(),
                scope=record.name,
                ctx=None,
            )
        except Exception:
            pass


def setup_logging(logs_dir: Path | str, db_path_getter=None, level: int = logging.INFO) -> logging.Logger:
    """配置根 logger:控制台 + 每日文件 + 可选 DB。"""
    logs_dir = Path(logs_dir)
    paths.ensure_dir(logs_dir)

    log_file = logs_dir / f"{datetime.now().strftime('%Y-%m-%d')}.log"
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(level)
    for h in list(root.handlers):
        root.removeHandler(h)

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    root.addHandler(console)

    file_handler = logging.FileHandler(str(log_file), encoding="utf-8")
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    if db_path_getter is not None:
        db_handler = DbLogHandler(db_path_getter)
        db_handler.setLevel(logging.WARNING)
        root.addHandler(db_handler)

    return logging.getLogger("fapiao_helper")
