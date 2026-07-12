"""导出 API:XLSX 与 PDF 合并。"""
from __future__ import annotations

from pathlib import Path

from flask import Blueprint, current_app, jsonify, request, send_file

from ... import db
from ...export.pdf_merge import merge_invoice_files
from ...export.xlsx import export_xlsx

bp = Blueprint("api_export", __name__)


def _db_path() -> Path:
    return Path(current_app.config["DB_PATH"])


def _export_dir() -> Path:
    return current_app.config["CONFIG"].exports


@bp.route("/api/export/xlsx", methods=["POST"])
def export_xlsx_view():  # type: ignore[no-untyped-def]
    """导出 XLSX。

    Body: {filter: {...}, selected_ids: [int]}
    selected_ids 优先,否则按 filter 取 list_invoices。
    """
    body = request.get_json(silent=True) or {}
    selected_ids = body.get("selected_ids") or []
    flt = body.get("filter") or {}

    if selected_ids:
        invoices = db.list_invoices_by_ids(_db_path(), [int(i) for i in selected_ids])
    else:
        result = db.list_invoices(
            _db_path(),
            status=flt.get("status") or None,
            project=flt.get("project") or None,
            month=flt.get("month") or None,
            q=flt.get("q") or None,
            page=1,
            page_size=100000,
        )
        invoices = result.get("items", [])

    path = export_xlsx(invoices, _export_dir())
    return send_file(str(path), as_attachment=True)


@bp.route("/api/export/pdf-merge", methods=["POST"])
def export_pdf_merge_view():  # type: ignore[no-untyped-def]
    """合并发票原件 PDF。

    Body: {selected_ids: [int], cover_meta: {...}}
    """
    body = request.get_json(silent=True) or {}
    selected_ids = body.get("selected_ids") or []
    cover_meta = body.get("cover_meta") or {}

    if not selected_ids:
        return jsonify({"error": "缺少 selected_ids"}), 400

    invoices = db.list_invoices_by_ids(_db_path(), [int(i) for i in selected_ids])
    file_paths: list[Path] = []
    for inv in invoices:
        sp = inv.get("stored_path")
        if sp:
            p = Path(sp)
            if p.exists():
                file_paths.append(p)

    if not file_paths:
        return jsonify({"error": "无可合并的文件"}), 400

    path = merge_invoice_files(file_paths, cover_meta, _export_dir())
    return send_file(str(path), as_attachment=True)
