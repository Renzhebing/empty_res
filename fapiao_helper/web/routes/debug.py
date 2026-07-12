"""调试 API:运行日志 + 发票调试信息。"""
from __future__ import annotations

import json
from pathlib import Path

from flask import Blueprint, abort, current_app, jsonify

from ... import db

bp = Blueprint("debug", __name__)


def _db_path() -> Path:
    return Path(current_app.config["DB_PATH"])


@bp.route("/debug", methods=["GET"])
def logs_view():  # type: ignore[no-untyped-def]
    """返回最近运行日志。"""
    return jsonify(db.list_logs(_db_path()))


@bp.route("/debug/invoice/<int:invoice_id>", methods=["GET"])
def invoice_debug_view(invoice_id: int):  # type: ignore[no-untyped-def]
    """返回发票调试信息:原 stored_path、raw_json、解析字段。"""
    inv = db.get_invoice(_db_path(), invoice_id)
    if inv is None:
        abort(404)

    raw_json_str = inv.get("raw_json") or "{}"
    try:
        raw_json = json.loads(raw_json_str) if isinstance(raw_json_str, str) else (raw_json_str or {})
    except (json.JSONDecodeError, TypeError):
        raw_json = {}

    # 解析字段(raw_json 内的字段集 + 关键库字段)
    parsed_fields = {
        "invoice_no": inv.get("invoice_no"),
        "invoice_date": inv.get("invoice_date"),
        "buyer": inv.get("buyer"),
        "seller": inv.get("seller"),
        "buyer_tax_id": inv.get("buyer_tax_id"),
        "seller_tax_id": inv.get("seller_tax_id"),
        "amount": inv.get("amount"),
        "tax": inv.get("tax"),
        "total": inv.get("total"),
        "category": inv.get("category"),
        "project": inv.get("project"),
        "status": inv.get("status"),
        "needs_review": inv.get("needs_review"),
        "confidence": inv.get("confidence"),
    }

    return jsonify({
        "id": inv.get("id"),
        "src_path": inv.get("src_path"),
        "stored_path": inv.get("stored_path"),
        "raw_json": raw_json,
        "fields": parsed_fields,
    })
