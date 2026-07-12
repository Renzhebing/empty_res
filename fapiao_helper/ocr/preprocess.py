"""PDF/图像预处理。"""
from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tiff"}


def is_image(path: Path | str) -> bool:
    """按扩展名判断是否为图片。"""
    return Path(path).suffix.lower() in _IMAGE_EXTS


def is_pdf(path: Path | str) -> bool:
    """按扩展名判断是否为 PDF。"""
    return Path(path).suffix.lower() == ".pdf"


def render_pdf_to_images(pdf_path: Path | str, dpi: int = 200) -> list[Path]:
    """用 PyMuPDF 把 PDF 每页渲染为 PNG。"""
    try:
        import fitz  # 懒加载
    except ImportError:
        logger.error("PyMuPDF 未安装,无法渲染 PDF")
        return []

    pdf_path = Path(pdf_path)
    tmp_dir = Path(tempfile.mkdtemp(prefix="fapiao_pdf_"))
    images: list[Path] = []
    doc = None
    try:
        doc = fitz.open(str(pdf_path))
        for i, page in enumerate(doc):
            pix = page.get_pixmap(dpi=dpi)
            img_path = tmp_dir / f"page_{i:03d}.png"
            pix.save(str(img_path))
            images.append(img_path)
    except Exception as e:
        logger.error("PDF 渲染失败 %s: %s", pdf_path, e)
        return []
    finally:
        if doc is not None:
            doc.close()
    return images


def preprocess_image(image_path: Path | str) -> Path:
    """简单预处理占位(当前直接返回原路径,预留旋转矫正/二值化接口)。"""
    return Path(image_path)


def to_images(path: Path | str) -> list[Path]:
    """统一入口:PDF 则渲染,图片则返回单元素列表。"""
    path = Path(path)
    if is_pdf(path):
        return render_pdf_to_images(path)
    if is_image(path):
        return [preprocess_image(path)]
    return []
