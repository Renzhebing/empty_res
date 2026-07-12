"""测试 PDF 合并。"""
from __future__ import annotations

from pathlib import Path

import fitz

from fapiao_helper.export import pdf_merge


def _make_pdf(path: Path, pages: int = 1) -> Path:
    doc = fitz.open()
    for i in range(pages):
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 72), f"Page {i + 1} of {path.name}", fontsize=12)
    doc.save(str(path))
    doc.close()
    return path


def _make_image(path: Path) -> Path:
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 72), "Image Page", fontsize=12)
    pix = page.get_pixmap()
    pix.save(str(path))
    doc.close()
    return path


def test_merge_multiple_pdfs(tmp_path: Path):
    p1 = _make_pdf(tmp_path / "a.pdf", pages=2)
    p2 = _make_pdf(tmp_path / "b.pdf", pages=3)
    cover_meta = {"generated_at": "2024-03-15", "filter": "全部", "total": "1000.00",
                  "items": [{"invoice_no": "INV001", "seller": "卖方", "total": "1000", "date": "2024-03-15"}]}
    out = pdf_merge.merge_invoice_files([p1, p2], cover_meta, tmp_path, "merged.pdf")
    doc = fitz.open(str(out))
    assert doc.page_count == 1 + 2 + 3  # 封面 + a + b
    doc.close()


def test_merge_with_image(tmp_path: Path):
    p1 = _make_pdf(tmp_path / "a.pdf", pages=1)
    img = _make_image(tmp_path / "img.png")
    cover_meta = {"generated_at": "2024-03-15", "filter": "", "total": "0", "items": []}
    out = pdf_merge.merge_invoice_files([p1, img], cover_meta, tmp_path)
    doc = fitz.open(str(out))
    assert doc.page_count == 1 + 1 + 1  # 封面 + pdf + 图片
    doc.close()


def test_merge_cover_is_first_page(tmp_path: Path):
    p1 = _make_pdf(tmp_path / "a.pdf", pages=1)
    cover_meta = {"generated_at": "2024-03-15", "filter": "测试", "total": "500.00",
                  "items": [{"invoice_no": "X1", "seller": "S", "total": "500", "date": "2024-03-15"}]}
    out = pdf_merge.merge_invoice_files([p1], cover_meta, tmp_path)
    doc = fitz.open(str(out))
    text = doc[0].get_text()
    assert "封面" in text or "2024" in text or "发票" in text
    doc.close()


def test_merge_empty_files(tmp_path: Path):
    cover_meta = {"generated_at": "2024-03-15", "filter": "", "total": "0", "items": []}
    out = pdf_merge.merge_invoice_files([], cover_meta, tmp_path)
    doc = fitz.open(str(out))
    assert doc.page_count == 1  # 只有封面
    doc.close()


def test_merge_skips_non_pdf_non_image(tmp_path: Path):
    p1 = _make_pdf(tmp_path / "a.pdf", pages=1)
    txt = tmp_path / "note.txt"
    txt.write_text("hello", encoding="utf-8")
    cover_meta = {"generated_at": "2024-03-15", "filter": "", "total": "0", "items": []}
    out = pdf_merge.merge_invoice_files([p1, txt], cover_meta, tmp_path)
    doc = fitz.open(str(out))
    assert doc.page_count == 2  # 封面 + a.pdf(txt 被跳过)
    doc.close()


def test_image_to_pdf(tmp_path: Path):
    img = _make_image(tmp_path / "test.png")
    pdf_path = pdf_merge.image_to_pdf(img)
    doc = fitz.open(str(pdf_path))
    assert doc.page_count == 1
    doc.close()


def test_page_count_equals_sum_plus_one(tmp_path: Path):
    p1 = _make_pdf(tmp_path / "a.pdf", pages=3)
    p2 = _make_pdf(tmp_path / "b.pdf", pages=5)
    p3 = _make_pdf(tmp_path / "c.pdf", pages=2)
    cover_meta = {"generated_at": "2024-03-15", "filter": "", "total": "0", "items": []}
    out = pdf_merge.merge_invoice_files([p1, p2, p3], cover_meta, tmp_path)
    doc = fitz.open(str(out))
    assert doc.page_count == 3 + 5 + 2 + 1
    doc.close()
