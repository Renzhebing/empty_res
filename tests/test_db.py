"""测试 SQLite 数据访问层。"""
from __future__ import annotations

import threading
from pathlib import Path

from fapiao_helper import db


def _sample_invoice(sha: str = "abc123", **overrides):
    data = {
        "sha256": sha, "src_path": "/tmp/test.pdf",
        "invoice_no": "INV001", "invoice_date": "2024-03-15",
        "buyer": "买方", "seller": "卖方",
        "amount": 1000.00, "tax": 60.00, "total": 1060.00,
        "category": "餐饮住宿", "project": "默认项目", "status": "pending",
        "needs_review": False, "confidence": 0.9, "raw_json": {"key": "value"},
    }
    data.update(overrides)
    return data


def test_init_db(tmp_db: Path):
    db.init_db(tmp_db)
    assert tmp_db.exists()
    conn = db.connect(tmp_db)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    for t in ("invoices", "jobs", "job_items", "run_logs", "projects"):
        assert t in tables


def test_insert_and_get(tmp_db: Path):
    db.init_db(tmp_db)
    inv_id = db.insert_invoice(tmp_db, _sample_invoice())
    assert inv_id is not None
    inv = db.get_invoice(tmp_db, inv_id)
    assert inv["invoice_no"] == "INV001"
    assert inv["total"] == 1060.00


def test_insert_duplicate_sha256(tmp_db: Path):
    db.init_db(tmp_db)
    id1 = db.insert_invoice(tmp_db, _sample_invoice(sha="dup"))
    assert id1 is not None
    id2 = db.insert_invoice(tmp_db, _sample_invoice(sha="dup"))
    assert id2 is None


def test_list_invoices(tmp_db: Path):
    db.init_db(tmp_db)
    db.insert_invoice(tmp_db, _sample_invoice(sha="s1", status="pending"))
    db.insert_invoice(tmp_db, _sample_invoice(sha="s2", status="done"))
    db.insert_invoice(tmp_db, _sample_invoice(sha="s3", status="pending", project="P2"))
    assert db.list_invoices(tmp_db)["total"] == 3
    assert db.list_invoices(tmp_db, status="pending")["total"] == 2
    assert db.list_invoices(tmp_db, project="P2")["total"] == 1
    assert db.list_invoices(tmp_db, month="2024-03")["total"] == 3


def test_update_invoice(tmp_db: Path):
    db.init_db(tmp_db)
    inv_id = db.insert_invoice(tmp_db, _sample_invoice())
    db.update_invoice(tmp_db, inv_id, {"status": "done", "total": 2000.00})
    inv = db.get_invoice(tmp_db, inv_id)
    assert inv["status"] == "done"
    assert inv["total"] == 2000.00


def test_update_invoice_whitelist(tmp_db: Path):
    """sha256 不在白名单,不应被更新。"""
    db.init_db(tmp_db)
    inv_id = db.insert_invoice(tmp_db, _sample_invoice())
    ok = db.update_invoice(tmp_db, inv_id, {"sha256": "hacked"})
    assert ok is False


def test_jobs(tmp_db: Path):
    db.init_db(tmp_db)
    job_id = db.create_job(tmp_db, "recognize", 3)
    assert db.get_job(tmp_db, job_id)["total"] == 3
    db.update_job(tmp_db, job_id, status="running", done=1)
    assert db.get_job(tmp_db, job_id)["done"] == 1


def test_projects(tmp_db: Path):
    db.init_db(tmp_db)
    db.upsert_project(tmp_db, "项目A", "备注")
    assert any(p["name"] == "项目A" for p in db.list_projects(tmp_db))
    assert db.delete_project(tmp_db, "项目A") is True


def test_stats(tmp_db: Path):
    db.init_db(tmp_db)
    db.insert_invoice(tmp_db, _sample_invoice(sha="s1", total=1000.00, amount=900.00, tax=100.00, status="done"))
    db.insert_invoice(tmp_db, _sample_invoice(sha="s2", total=2000.00, amount=1800.00, tax=200.00, status="pending"))
    s = db.stats(tmp_db)
    assert s["count"] == 2
    assert s["sum_total"] == 3000.00


def test_concurrent_writes(tmp_db: Path):
    db.init_db(tmp_db)
    errors = []

    def writer(start: int):
        try:
            for i in range(start, start + 10):
                db.insert_invoice(tmp_db, _sample_invoice(sha=f"c_{start}_{i}"))
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=writer, args=(i * 10,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    assert db.list_invoices(tmp_db)["total"] == 40


def test_needs_review_bool(tmp_db: Path):
    db.init_db(tmp_db)
    db.insert_invoice(tmp_db, _sample_invoice(sha="r1", needs_review=True))
    assert db.get_invoice_by_sha(tmp_db, "r1")["needs_review"] == 1
