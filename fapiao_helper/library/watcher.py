"""文件夹监控:watchdog 监听 inbox 新文件。"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)

_DEFAULT_PATTERNS = [".pdf", ".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tiff"]


def default_patterns() -> list[str]:
    """返回默认扩展名列表。"""
    return list(_DEFAULT_PATTERNS)


def scan_inbox(inbox_dir: Path | str, patterns: list[str] | None = None) -> list[Path]:
    """扫描 inbox_dir 返回匹配文件列表(不调回调)。"""
    inbox_dir = Path(inbox_dir)
    pats = [p.lower() for p in (patterns or _DEFAULT_PATTERNS)]
    result: list[Path] = []
    if not inbox_dir.exists():
        return result
    for p in inbox_dir.iterdir():
        if p.is_file() and p.suffix.lower() in pats:
            result.append(p)
    return result


class InboxWatcher:
    """文件夹监控器。"""

    def __init__(
        self,
        inbox_dir: Path | str,
        on_new_file: Callable[[Path], None],
        patterns: list[str] | None = None,
    ):
        self.inbox_dir = Path(inbox_dir)
        self.on_new_file = on_new_file
        self.patterns = [p.lower() for p in (patterns or _DEFAULT_PATTERNS)]
        self._observer = None

    def start(self) -> None:
        """启动 watchdog Observer(未安装则降级为 no-op)。"""
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler
        except ImportError:
            logger.warning("watchdog 未安装,文件夹监控不可用")
            return

        class _Handler(FileSystemEventHandler):
            def __init__(self, watcher: "InboxWatcher"):
                self.watcher = watcher

            def _handle(self, path: str | None):
                if path is None:
                    return
                p = Path(path)
                if p.is_file() and p.suffix.lower() in self.watcher.patterns:
                    self.watcher.on_new_file(p)

            def on_created(self, event):
                self._handle(event.src_path if not event.is_directory else None)

            def on_moved(self, event):
                self._handle(getattr(event, "dest_path", None))

        self._observer = Observer()
        self._observer.schedule(_Handler(self), str(self.inbox_dir), recursive=False)
        self._observer.start()
        logger.info("InboxWatcher 已启动: %s", self.inbox_dir)

    def stop(self) -> None:
        """停止 observer。"""
        if self._observer is not None:
            self._observer.stop()
            self._observer.join()
            self._observer = None

    def scan_once(self) -> list[Path]:
        """扫描一次 inbox,对每个文件调 on_new_file,返回处理列表。"""
        files = scan_inbox(self.inbox_dir, self.patterns)
        for f in files:
            try:
                self.on_new_file(f)
            except Exception as e:
                logger.error("处理文件 %s 失败: %s", f, e)
        return files
