"""SQLite 数据访问层:schema 初始化 + 增删改查。

表结构遵循 PLAN.md 第 4 节数据契约。
"""
from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

from . import paths

# 线程局部连接,避免多线程共用同一连接
_local = threading.local()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sha256 TEXT UNIQUE NOT NULL,
    src_path TEXT NOT NULL,
    stored_path TEXT,
    invoice_no TEXT,
    invoice_date TEXT,
    buyer TEXT,
    seller TEXT,
    buyer_tax_id TEXT,
    seller_tax_id TEXT,
    amount REAL,
    tax REAL,
    total REAL,
    category TEXT,
    project TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    needs_review INTEGER NOT NULL DEFAULT 0,
    recognized_at TEXT,
    updated_at TEXT,
    confidence REAL,
    raw_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_invoices_status_project ON invoices(status, project);
CREATE INDEX IF NOT EXISTS idx_invoices_date ON invoices(invoice_date);
CREATE INDEX IF NOT EXISTS idx_invoices_sha256 ON invoices(sha256);

CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    total INTEGER NOT NULL DEFAULT 0,
    done INTEGER NOT NULL DEFAULT 0,
    failed INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS job_items (
    job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    invoice_id INTEGER REFERENCES invoices(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'pending',
    error TEXT,
    PRIMARY KEY (job_id, invoice_id)
);

CREATE TABLE IF NOT EXISTS run_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    level TEXT NOT NULL,
    scope TEXT,
    msg TEXT NOT NULL,
    ctx_json TEXT
);

CREATE TABLE IF NOT EXISTS projects (
    name TEXT PRIMARY KEY,
    note TEXT,
    created_at TEXT NOT NULL
);
"""

# 可更新的发票字段白名单(sha256 是去重键,不可更新)
_INVOICE_UPDATABLE = {
    "invoice_no", "invoice_date", "buyer", "seller", "buyer_tax_id",
    "seller_tax_id", "amount", "tax", "total", "category", "project",
    "status", "needs_review", "stored_path", "confidence",
}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def connect(db_path: Path | str) -> sqlite3.Connection:
    """打开/复用当前线程的数据库连接。"""
    key = str(db_path)
    conn = getattr(_local, "conn", None)
    cur_key = getattr(_local, "db_key", None)
    if conn is None or cur_key != key:
        if conn is not None:
            conn.close()
        conn = sqlite3.connect(str(db_path), check_same_thread=False, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        _local.conn = conn
        _local.db_key = key
    return conn


def init_db(db_path: Path | str) -> None:
    """初始化 schema。"""
    paths.ensure_dir(Path(db_path).parent)
    conn = connect(db_path)
    conn.executescript(_SCHEMA)
    conn.commit()


@contextmanager
def transaction(db_path: Path | str) -> Iterator[sqlite3.Connection]:
    """事务上下文:提交或回滚。"""
    conn = connect(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


# ----------------- invoices -----------------


def insert_invoice(db_path: Path | str, data: dict[str, Any]) -> int | None:
    """插入发票;若 sha256 重复则返回 None。"""
    cols = [
        "sha256", "src_path", "stored_path", "invoice_no", "invoice_date",
        "buyer", "seller", "buyer_tax_id", "seller_tax_id",
        "amount", "tax", "total", "category", "project", "status",
        "needs_review", "recognized_at", "updated_at", "confidence", "raw_json",
    ]
    values = {k: data.get(k) for k in cols}
    if values.get("status") is None:
        values["status"] = "pending"
    if values.get("needs_review") is None:
        values["needs_review"] = 0
    values["needs_review"] = 1 if values["needs_review"] else 0
    if values.get("recognized_at") is None:
        values["recognized_at"] = _now()
    values["updated_at"] = _now()
    if isinstance(values.get("raw_json"), (dict, list)):
        values["raw_json"] = json.dumps(values["raw_json"], ensure_ascii=False)

    col_list = ", ".join(cols)
    placeholders = ", ".join(["?"] * len(cols))
    sql = f"INSERT INTO invoices ({col_list}) VALUES ({placeholders})"

    try:
        with transaction(db_path) as conn:
            cur = conn.execute(sql, [values[c] for c in cols])
            return cur.lastrowid
    except sqlite3.IntegrityError:
        return None


def get_invoice(db_path: Path | str, invoice_id: int) -> dict[str, Any] | None:
    conn = connect(db_path)
    row = conn.execute("SELECT * FROM invoices WHERE id = ?", [invoice_id]).fetchone()
    return dict(row) if row else None


def get_invoice_by_sha(db_path: Path | str, sha256: str) -> dict[str, Any] | None:
    conn = connect(db_path)
    row = conn.execute("SELECT * FROM invoices WHERE sha256 = ?", [sha256]).fetchone()
    return dict(row) if row else None


def list_invoices(
    db_path: Path | str,
    status: str | None = None,
    project: str | None = None,
    month: str | None = None,
    q: str | None = None,
    page: int = 1,
    page_size: int = 100,
) -> dict[str, Any]:
    """分页查询发票列表。返回 {items, total, page, page_size}。"""
    where = []
    params: list[Any] = []
    if status:
        where.append("status = ?")
        params.append(status)
    if project:
        where.append("project = ?")
        params.append(project)
    if month:
        where.append("invoice_date LIKE ?")
        params.append(f"{month}%")
    if q:
        where.append("(invoice_no LIKE ? OR seller LIKE ? OR buyer LIKE ?)")
        kw = f"%{q}%"
        params.extend([kw, kw, kw])

    where_sql = (" WHERE " + " AND ".join(where)) if where else ""
    conn = connect(db_path)

    total = conn.execute(f"SELECT COUNT(*) AS c FROM invoices{where_sql}", params).fetchone()["c"]
    offset = (max(page, 1) - 1) * page_size
    rows = conn.execute(
        f"SELECT * FROM invoices{where_sql} ORDER BY id DESC LIMIT ? OFFSET ?",
        params + [page_size, offset],
    ).fetchall()
    return {
        "items": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def update_invoice(db_path: Path | str, invoice_id: int, fields: dict[str, Any]) -> bool:
    """部分更新发票字段。返回是否命中。"""
    updates = {k: v for k, v in fields.items() if k in _INVOICE_UPDATABLE}
    if not updates:
        return False
    if "needs_review" in updates:
        updates["needs_review"] = 1 if updates["needs_review"] else 0
    updates["updated_at"] = _now()
    set_sql = ", ".join([f"{k} = ?" for k in updates])
    params = list(updates.values()) + [invoice_id]
    with transaction(db_path) as conn:
        cur = conn.execute(f"UPDATE invoices SET {set_sql} WHERE id = ?", params)
        return cur.rowcount > 0


def set_invoice_status(db_path: Path | str, invoice_id: int, status: str) -> bool:
    return update_invoice(db_path, invoice_id, {"status": status})


def list_invoices_by_ids(db_path: Path | str, ids: list[int]) -> list[dict[str, Any]]:
    if not ids:
        return []
    placeholders = ", ".join(["?"] * len(ids))
    conn = connect(db_path)
    rows = conn.execute(
        f"SELECT * FROM invoices WHERE id IN ({placeholders}) ORDER BY id", ids
    ).fetchall()
    return [dict(r) for r in rows]


# ----------------- jobs -----------------


def create_job(db_path: Path | str, kind: str, total: int) -> int:
    now = _now()
    with transaction(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO jobs (kind, status, total, done, failed, created_at, updated_at) "
            "VALUES (?, 'pending', ?, 0, 0, ?, ?)",
            [kind, total, now, now],
        )
        return cur.lastrowid


def get_job(db_path: Path | str, job_id: int) -> dict[str, Any] | None:
    conn = connect(db_path)
    row = conn.execute("SELECT * FROM jobs WHERE id = ?", [job_id]).fetchone()
    return dict(row) if row else None


def list_jobs(db_path: Path | str, status: str | None = None) -> list[dict[str, Any]]:
    conn = connect(db_path)
    if status:
        rows = conn.execute(
            "SELECT * FROM jobs WHERE status = ? ORDER BY id DESC", [status]
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM jobs ORDER BY id DESC").fetchall()
    return [dict(r) for r in rows]


def update_job(
    db_path: Path | str,
    job_id: int,
    status: str | None = None,
    done: int | None = None,
    failed: int | None = None,
    error: str | None = None,
) -> None:
    updates: dict[str, Any] = {"updated_at": _now()}
    if status is not None:
        updates["status"] = status
    if done is not None:
        updates["done"] = done
    if failed is not None:
        updates["failed"] = failed
    if error is not None:
        updates["error"] = error
    set_sql = ", ".join([f"{k} = ?" for k in updates])
    params = list(updates.values()) + [job_id]
    with transaction(db_path) as conn:
        conn.execute(f"UPDATE jobs SET {set_sql} WHERE id = ?", params)


def add_job_item(db_path: Path | str, job_id: int, invoice_id: int | None) -> None:
    with transaction(db_path) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO job_items (job_id, invoice_id, status) VALUES (?, ?, 'pending')",
            [job_id, invoice_id],
        )


def update_job_item(db_path: Path | str, job_id: int, invoice_id: int, status: str, error: str | None = None) -> None:
    with transaction(db_path) as conn:
        conn.execute(
            "UPDATE job_items SET status = ?, error = ? WHERE job_id = ? AND invoice_id = ?",
            [status, error, job_id, invoice_id],
        )


def list_job_items(db_path: Path | str, job_id: int) -> list[dict[str, Any]]:
    conn = connect(db_path)
    rows = conn.execute(
        "SELECT * FROM job_items WHERE job_id = ? ORDER BY invoice_id", [job_id]
    ).fetchall()
    return [dict(r) for r in rows]


# ----------------- run_logs -----------------


def add_log(
    db_path: Path | str,
    level: str,
    msg: str,
    scope: str | None = None,
    ctx: dict[str, Any] | None = None,
) -> None:
    ctx_json = json.dumps(ctx, ensure_ascii=False) if ctx else None
    with transaction(db_path) as conn:
        conn.execute(
            "INSERT INTO run_logs (ts, level, scope, msg, ctx_json) VALUES (?, ?, ?, ?, ?)",
            [_now(), level, scope, msg, ctx_json],
        )


def list_logs(db_path: Path | str, limit: int = 200) -> list[dict[str, Any]]:
    conn = connect(db_path)
    rows = conn.execute(
        "SELECT * FROM run_logs ORDER BY id DESC LIMIT ?", [limit]
    ).fetchall()
    return [dict(r) for r in rows]


# ----------------- projects -----------------


def upsert_project(db_path: Path | str, name: str, note: str = "") -> None:
    with transaction(db_path) as conn:
        conn.execute(
            "INSERT INTO projects (name, note, created_at) VALUES (?, ?, ?) "
            "ON CONFLICT(name) DO UPDATE SET note = excluded.note",
            [name, note, _now()],
        )


def delete_project(db_path: Path | str, name: str) -> bool:
    with transaction(db_path) as conn:
        cur = conn.execute("DELETE FROM projects WHERE name = ?", [name])
        return cur.rowcount > 0


def list_projects(db_path: Path | str) -> list[dict[str, Any]]:
    conn = connect(db_path)
    rows = conn.execute("SELECT * FROM projects ORDER BY name").fetchall()
    return [dict(r) for r in rows]


def sync_projects(db_path: Path | str, projects: list[dict[str, Any]]) -> None:
    """与 config 同步:插入缺失的项目。"""
    for p in projects:
        name = p.get("name")
        if name:
            upsert_project(db_path, name, p.get("note", ""))


# ----------------- stats -----------------


def stats(db_path: Path | str, project: str | None = None, month: str | None = None) -> dict[str, Any]:
    """聚合统计。"""
    where = []
    params: list[Any] = []
    if project:
        where.append("project = ?")
        params.append(project)
    if month:
        where.append("invoice_date LIKE ?")
        params.append(f"{month}%")
    where_sql = (" WHERE " + " AND ".join(where)) if where else ""

    conn = connect(db_path)
    row = conn.execute(
        f"SELECT COUNT(*) AS c, "
        f"COALESCE(SUM(amount), 0) AS sum_amount, "
        f"COALESCE(SUM(tax), 0) AS sum_tax, "
        f"COALESCE(SUM(total), 0) AS sum_total "
        f"FROM invoices{where_sql}",
        params,
    ).fetchone()

    status_rows = conn.execute(
        f"SELECT status, COUNT(*) AS c FROM invoices{where_sql} GROUP BY status", params
    ).fetchall()
    cat_rows = conn.execute(
        f"SELECT COALESCE(category, '未分类') AS category, COUNT(*) AS c, "
        f"COALESCE(SUM(total), 0) AS sum_total "
        f"FROM invoices{where_sql} GROUP BY category",
        params,
    ).fetchall()

    return {
        "count": row["c"],
        "sum_amount": round(row["sum_amount"], 2),
        "sum_tax": round(row["sum_tax"], 2),
        "sum_total": round(row["sum_total"], 2),
        "by_status": {r["status"]: r["c"] for r in status_rows},
        "by_category": [
            {"category": r["category"], "count": r["c"], "sum_total": round(r["sum_total"], 2)}
            for r in cat_rows
        ],
    }
