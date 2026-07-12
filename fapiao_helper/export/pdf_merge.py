"""PDF 合并:多 PDF + 图片 + 封面。"""
from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Any

from ..paths import ensure_dir
from ..ocr.preprocess import is_image, is_pdf

logger = logging.getLogger(__name__)


def image_to_pdf(image_path: Path | str) -> Path:
    """把单张图片转成单页 PDF,返回临时 PDF 路径。"""
    import fitz

    image_path = Path(image_path)
    fd, tmp = tempfile.mkstemp(suffix=".pdf", prefix="fapiao_img_")
    import os
    os.close(fd)

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)  # A4
    rect = fitz.Rect(0, 0, 595, 842)
    page.insert_image(rect, filename=str(image_path))
    doc.save(tmp)
    doc.close()
    return Path(tmp)


def merge_pdfs_with_cover(
    pdf_paths: list[Path],
    cover_meta: dict[str, Any],
    export_dir: Path | str,
    filename: str = "merged.pdf",
) -> Path:
    """合并多 PDF + 封面。"""
    import fitz
    from .cover import generate_cover_pdf

    export_dir = Path(export_dir)
    ensure_dir(export_dir)
    out_path = export_dir / filename

    # 生成封面
    cover_path = generate_cover_pdf(cover_meta, export_dir)

    merged = fitz.open()
    try:
        # 插入封面
        cover_doc = fitz.open(str(cover_path))
        merged.insert_pdf(cover_doc)
        cover_doc.close()

        # 追加每个 PDF
        for p in pdf_paths:
            if not p.exists():
                logger.warning("文件不存在,跳过: %s", p)
                continue
            try:
                d = fitz.open(str(p))
                merged.insert_pdf(d)
                d.close()
            except Exception as e:
                logger.error("合并 PDF 失败 %s: %s", p, e)

        merged.save(str(out_path))
    finally:
        merged.close()

    return out_path


def merge_invoice_files(
    file_paths: list[Path],
    cover_meta: dict[str, Any],
    export_dir: Path | str,
    filename: str = "merged.pdf",
) -> Path:
    """统一入口:图片转 PDF,PDF 直接用,然后合并。"""
    pdf_paths: list[Path] = []
    for p in file_paths:
        p = Path(p)
        if is_pdf(p):
            pdf_paths.append(p)
        elif is_image(p):
            try:
                pdf_paths.append(image_to_pdf(p))
            except Exception as e:
                logger.error("图片转 PDF 失败 %s: %s", p, e)
        else:
            logger.warning("跳过非 PDF/图片文件: %s", p)

    return merge_pdfs_with_cover(pdf_paths, cover_meta, export_dir, filename)
