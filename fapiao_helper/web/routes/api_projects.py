"""项目 API:增删查。"""
from __future__ import annotations

from pathlib import Path

from flask import Blueprint, current_app, jsonify, request

from ... import db

bp = Blueprint("api_projects", __name__)


def _db_path() -> Path:
    return Path(current_app.config["DB_PATH"])


@bp.route("/api/projects", methods=["GET"])
def list_projects_view():  # type: ignore[no-untyped-def]
    """列出所有项目。"""
    return jsonify(db.list_projects(_db_path()))


@bp.route("/api/projects", methods=["POST"])
def upsert_project_view():  # type: ignore[no-untyped-def]
    """新增或更新项目。

    Body: {name, note}
    """
    body = request.get_json(silent=True) or {}
    name = body.get("name")
    if not name:
        return jsonify({"error": "缺少 name"}), 400
    note = body.get("note", "") or ""
    db.upsert_project(_db_path(), str(name), note)
    return jsonify({"ok": True}), 201


@bp.route("/api/projects/<name>", methods=["DELETE"])
def delete_project_view(name: str):  # type: ignore[no-untyped-def]
    """删除项目。"""
    ok = db.delete_project(_db_path(), name)
    if not ok:
        return jsonify({"ok": False, "error": "项目不存在"}), 404
    return jsonify({"ok": True})
