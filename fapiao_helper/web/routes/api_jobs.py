"""Job API:创建/查询/列表。"""
from __future__ import annotations

from pathlib import Path

from flask import Blueprint, abort, current_app, jsonify, request

from ...jobs.manager import JobManager

bp = Blueprint("api_jobs", __name__)


def _db_path() -> Path:
    return Path(current_app.config["DB_PATH"])


@bp.route("/api/jobs", methods=["POST"])
def create_job_view():  # type: ignore[no-untyped-def]
    """创建识别 Job(不自动执行)。

    Body: {files: [path...], default_project: str}
    """
    body = request.get_json(silent=True) or {}
    files_raw = body.get("files") or []
    if not files_raw:
        return jsonify({"error": "缺少 files"}), 400

    files = [Path(f) for f in files_raw]
    default_project = body.get("default_project", "") or ""

    manager = JobManager(_db_path())
    job_id = manager.create_recognize_job(files, default_project=default_project)
    return jsonify({"job_id": job_id}), 201


@bp.route("/api/jobs/<int:job_id>", methods=["GET"])
def get_job_view(job_id: int):  # type: ignore[no-untyped-def]
    """取 Job 详情(含 items)。"""
    manager = JobManager(_db_path())
    detail = manager.get_job_detail(job_id)
    if not detail.get("id"):
        abort(404)
    return jsonify(detail)


@bp.route("/api/jobs", methods=["GET"])
def list_jobs_view():  # type: ignore[no-untyped-def]
    """列出 Job,可选 status 过滤。"""
    manager = JobManager(_db_path())
    status = request.args.get("status") or None
    return jsonify(manager.list_jobs(status=status))
