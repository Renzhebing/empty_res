"""Job 管理器:创建/查询/恢复 Job。"""
from __future__ import annotations

import logging
from pathlib import Path

from .. import db

logger = logging.getLogger(__name__)


class JobManager:
    """Job 管理器。"""

    def __init__(self, db_path: Path | str, config=None):
        self.db_path = db_path
        self.config = config
        self._pending_files: dict[int, list[Path]] = {}
        self._pending_project: dict[int, str] = {}

    def create_recognize_job(self, files: list[Path], default_project: str = "") -> int:
        """创建识别 Job,记录待处理文件。"""
        job_id = db.create_job(self.db_path, "recognize", len(files))
        self._pending_files[job_id] = list(files)
        self._pending_project[job_id] = default_project
        # 占位 job_items(invoice_id 暂为 None)
        for _ in files:
            db.add_job_item(self.db_path, job_id, None)
        logger.info("创建 Job %d,共 %d 个文件", job_id, len(files))
        return job_id

    def get_job(self, job_id: int) -> dict | None:
        return db.get_job(self.db_path, job_id)

    def list_jobs(self, status: str | None = None) -> list[dict]:
        return db.list_jobs(self.db_path, status)

    def get_job_detail(self, job_id: int) -> dict:
        """返回 {**job, items: [...]}。"""
        job = db.get_job(self.db_path, job_id) or {}
        items = db.list_job_items(self.db_path, job_id)
        return {**job, "items": items}

    def get_pending_files(self, job_id: int) -> list[Path]:
        return self._pending_files.get(job_id, [])

    def get_pending_project(self, job_id: int) -> str:
        return self._pending_project.get(job_id, "")

    def recover_pending(self) -> None:
        """启动时恢复 pending/running 的 Job(简化实现:仅查询不重跑)。"""
        pending = db.list_jobs(self.db_path, status="pending")
        running = db.list_jobs(self.db_path, status="running")
        for job in pending + running:
            logger.warning("发现未完成 Job %d (status=%s),需手动恢复", job["id"], job["status"])
