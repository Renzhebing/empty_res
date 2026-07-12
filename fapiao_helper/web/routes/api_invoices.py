"""发票 API:上传/查询/编辑/重识别/统计。"""
from __future__ import annotations

import json
import threading
from pathlib import Path

from flask import Blueprint, abort, current_app, jsonify, request
from werkzeug.utils import secure_filename

from ... import db, paths
from ...jobs.manager import JobManager
from ...jobs.worker import JobWorker
from ...llm.router import get_router
from ...parser.llm_fallback import build_prompt, parse_llm_response

bp = Blueprint("api_invoices", __name__)


def _db_path() -> Path:
    """从 current_app 取数据库路径。"""
    return current_app.config["DB_PATH"]


@bp.route("/api/invoices/upload", methods=["POST"])
def upload():  # type: ignore[no-untyped-def]
    """multipart 上传:files[] + folder + default_project。

    保存到 inbox,创建识别 Job 并在后台线程执行。
    """
    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "未提供文件"}), 400

    default_project = request.form.get("default_project", "") or ""
    inbox = current_app.config["CONFIG"].inbox

    saved: list[Path] = []
    for f in files:
        if not f or not f.filename:
            continue
        safe_name = secure_filename(f.filename)
        if not safe_name:
            safe_name = "upload.bin"
        dest = paths.unique_path(inbox, safe_name)
        f.save(str(dest))
        saved.append(dest)

    if not saved:
        return jsonify({"error": "无有效文件"}), 400

    manager = JobManager(_db_path(), config=current_app.config["CONFIG"])
    worker = JobWorker(_db_path(), config=current_app.config["CONFIG"])
    job_id = manager.create_recognize_job(saved, default_project=default_project)

    # 后台线程跑 job
    threading.Thread(
        target=worker.run_job,
        args=(job_id, saved, default_project),
        daemon=True,
    ).start()

    return jsonify({"job_id": job_id, "count": len(saved)}), 202


@bp.route("/api/invoices", methods=["GET"])
def list_invoices_view():  # type: ignore[no-untyped-def]
    """查询发票列表,支持 status/project/month/q/page 过滤。"""
    page = request.args.get("page", default=1, type=int)
    result = db.list_invoices(
        _db_path(),
        status=request.args.get("status") or None,
        project=request.args.get("project") or None,
        month=request.args.get("month") or None,
        q=request.args.get("q") or None,
        page=page,
    )
    return jsonify(result)


@bp.route("/api/invoices/<int:invoice_id>", methods=["GET"])
def get_invoice_view(invoice_id: int):  # type: ignore[no-untyped-def]
    """取单个发票详情。"""
    inv = db.get_invoice(_db_path(), invoice_id)
    if inv is None:
        abort(404)
    return jsonify(inv)


@bp.route("/api/invoices/<int:invoice_id>", methods=["PATCH"])
def update_invoice_view(invoice_id: int):  # type: ignore[no-untyped-def]
    """部分更新发票字段。"""
    fields = request.get_json(silent=True) or {}
    if not fields:
        return jsonify({"error": "无字段"}), 400
    ok = db.update_invoice(_db_path(), invoice_id, fields)
    if not ok:
        abort(404)
    return jsonify({"ok": True})


@bp.route("/api/invoices/<int:invoice_id>/status", methods=["POST"])
def set_status_view(invoice_id: int):  # type: ignore[no-untyped-def]
    """更新发票状态。"""
    body = request.get_json(silent=True) or {}
    status = body.get("status")
    if not status:
        return jsonify({"error": "缺少 status"}), 400
    ok = db.set_invoice_status(_db_path(), invoice_id, str(status))
    if not ok:
        abort(404)
    return jsonify({"ok": True})


@bp.route("/api/invoices/<int:invoice_id>/re-recognize", methods=["POST"])
def re_recognize_view(invoice_id: int):  # type: ignore[no-untyped-def]
    """用 LLM 重新识别发票字段。

    从 raw_json 取 OCR 原文,调 LLM 兜底解析,更新入库。
    """
    inv = db.get_invoice(_db_path(), invoice_id)
    if inv is None:
        abort(404)

    # 解析 raw_json(数据库存为字符串)
    raw_json_str = inv.get("raw_json") or "{}"
    try:
        raw_json = json.loads(raw_json_str) if isinstance(raw_json_str, str) else (raw_json_str or {})
    except (json.JSONDecodeError, TypeError):
        raw_json = {}

    # 取 OCR 原文:优先 raw_text,缺失时退化为已知字段拼接
    ocr_text = raw_json.get("raw_text") or ""
    if not ocr_text:
        ocr_text = "\n".join(
            str(v) for v in (
                raw_json.get("invoice_no"),
                raw_json.get("invoice_date"),
                raw_json.get("buyer"),
                raw_json.get("seller"),
                raw_json.get("buyer_tax_id"),
                raw_json.get("seller_tax_id"),
                raw_json.get("total"),
            ) if v not in (None, "")
        )

    router = get_router(current_app.config["CONFIG"])
    if not router.has_provider():
        return jsonify({"ok": False, "needs_review": True, "error": "无可用 LLM provider"}), 400

    prompt = build_prompt(ocr_text)
    content = router.complete(prompt)
    parsed = parse_llm_response(content, ocr_text=ocr_text, ocr_conf=0.0)

    fields = {
        "invoice_no": parsed.invoice_no,
        "invoice_date": parsed.invoice_date,
        "buyer": parsed.buyer,
        "seller": parsed.seller,
        "buyer_tax_id": parsed.buyer_tax_id,
        "seller_tax_id": parsed.seller_tax_id,
        "amount": parsed.amount,
        "tax": parsed.tax,
        "total": parsed.total,
        "needs_review": 1 if parsed.needs_review else 0,
        "confidence": parsed.confidence,
        "raw_json": parsed.to_dict(),
    }
    db.update_invoice(_db_path(), invoice_id, fields)
    return jsonify({"ok": True, "needs_review": bool(parsed.needs_review)})


@bp.route("/api/stats", methods=["GET"])
def stats_view():  # type: ignore[no-untyped-def]
    """聚合统计。"""
    return jsonify(
        db.stats(
            _db_path(),
            project=request.args.get("project") or None,
            month=request.args.get("month") or None,
        )
    )
