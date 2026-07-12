"""Worker:执行发票识别 Job。"""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from .. import db

logger = logging.getLogger(__name__)


class JobWorker:
    """Job 执行器。"""

    def __init__(self, db_path: Path | str, config=None):
        self.db_path = db_path
        self.config = config

    def _sha256(self, file_path: Path) -> str:
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    def process_file(self, file_path: Path, default_project: str = "", job_id: int | None = None) -> dict:
        """处理单个发票文件,返回 invoice_data dict。"""
        # 延迟导入,避免模块加载时拉起可选依赖
        from ..ocr.preprocess import to_images
        from ..ocr.engine import get_engine
        from ..parser import vat_invoice
        from ..parser import classify
        from ..parser import llm_fallback
        from ..llm.router import get_router
        from ..library.organizer import organize

        file_path = Path(file_path)
        logger.info("处理文件: %s", file_path)

        # a. 计算 sha256
        sha = self._sha256(file_path)

        # b. 查重
        existing = db.get_invoice_by_sha(self.db_path, sha)
        if existing:
            logger.info("文件已存在(sha256 重复): %s", file_path)
            return {**existing, "skipped": True}

        # c. OCR
        images = to_images(file_path)
        all_lines: list[str] = []
        confs: list[float] = []
        if images:
            engine = get_engine(self.config)
            for img in images:
                items, avg_conf = engine.recognize(img)
                for box, text, conf in items:
                    all_lines.append(str(text))
                confs.append(avg_conf)
        avg_ocr_conf = sum(confs) / len(confs) if confs else 0.0

        # d. 解析
        parsed = vat_invoice.parse(all_lines, avg_ocr_conf)

        # e. 分类
        category, cat_score = classify.classify_from_parsed(
            parsed.to_dict(),
            self.config.classify_threshold if self.config else 0.3,
        )

        # f. LLM 兜底
        if parsed.confidence < (self.config.confidence_min if self.config else 0.5):
            router = get_router(self.config)
            if router.has_provider():
                logger.info("置信度 %.3f 低于阈值,触发 LLM 兜底", parsed.confidence)
                fallback_result = llm_fallback.fallback(
                    parsed.raw_text, router, avg_ocr_conf
                )
                # 只在兜底结果更优时采用
                if fallback_result.confidence > parsed.confidence:
                    parsed = fallback_result

        # g. 组装 invoice_data
        project = default_project or "默认项目"
        invoice_data: dict[str, Any] = {
            "sha256": sha,
            "src_path": str(file_path),
            "invoice_no": parsed.invoice_no,
            "invoice_date": parsed.invoice_date,
            "buyer": parsed.buyer,
            "seller": parsed.seller,
            "buyer_tax_id": parsed.buyer_tax_id,
            "seller_tax_id": parsed.seller_tax_id,
            "amount": parsed.amount,
            "tax": parsed.tax,
            "total": parsed.total,
            "category": category,
            "project": project,
            "status": "pending",
            "needs_review": parsed.needs_review,
            "confidence": parsed.confidence,
            "raw_json": parsed.to_dict(),
        }

        # h. 整理原件到 library
        stored_path = None
        try:
            if self.config:
                stored_path = organize(file_path, invoice_data, self.config.library)
                invoice_data["stored_path"] = str(stored_path)
        except Exception as e:
            logger.error("原件整理失败: %s", e)
            db.add_log(self.db_path, "ERROR", f"原件整理失败: {e}", scope="worker")

        # i. 入库
        invoice_id = db.insert_invoice(self.db_path, invoice_data)
        if invoice_id and job_id:
            db.add_job_item(self.db_path, job_id, invoice_id)

        # j. 日志
        db.add_log(
            self.db_path, "INFO",
            f"处理完成: {file_path.name} -> invoice_id={invoice_id}, confidence={parsed.confidence:.3f}",
            scope="worker",
        )

        invoice_data["id"] = invoice_id
        return invoice_data

    def run_job(self, job_id: int, files: list[Path], default_project: str = "") -> None:
        """顺序处理 files,更新 job 进度。"""
        db.update_job(self.db_path, job_id, status="running")
        done = 0
        failed = 0
        for f in files:
            try:
                self.process_file(Path(f), default_project, job_id)
                done += 1
            except Exception as e:
                failed += 1
                logger.error("处理文件失败 %s: %s", f, e)
                db.add_log(self.db_path, "ERROR", f"处理失败 {f}: {e}", scope="worker")
            db.update_job(self.db_path, job_id, done=done, failed=failed)

        final_status = "done" if failed == 0 else "failed" if done == 0 else "done"
        db.update_job(self.db_path, job_id, status=final_status)
        logger.info("Job %d 完成: done=%d, failed=%d", job_id, done, failed)
