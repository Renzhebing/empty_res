"""封面生成:reportlab 生成 A4 单页 PDF。"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from ..paths import ensure_dir

logger = logging.getLogger(__name__)


def generate_cover_pdf(cover_meta: dict[str, Any], export_dir: Path | str) -> Path:
    """生成封面 PDF,返回路径。"""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors

    export_dir = Path(export_dir)
    ensure_dir(export_dir)
    out_path = export_dir / "_cover.pdf"

    # 注册中文字体
    font_name = "Helvetica"
    try:
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
        font_name = "STSong-Light"
    except Exception as e:
        logger.warning("注册中文字体失败,使用 Helvetica: %s", e)

    doc = SimpleDocTemplate(str(out_path), pagesize=A4)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("CNTitle", parent=styles["Title"], fontName=font_name, fontSize=20)
    body_style = ParagraphStyle("CNBody", parent=styles["Normal"], fontName=font_name, fontSize=11)
    cell_style = ParagraphStyle("CNCell", parent=styles["Normal"], fontName=font_name, fontSize=9)

    elems: list = []
    elems.append(Paragraph("发票合并打印封面", title_style))
    elems.append(Spacer(1, 20))
    elems.append(Paragraph(f"生成日期: {cover_meta.get('generated_at', '')}", body_style))
    elems.append(Paragraph(f"筛选条件: {cover_meta.get('filter', '全部')}", body_style))
    elems.append(Paragraph(f"合计金额: {cover_meta.get('total', '0')}", body_style))
    elems.append(Spacer(1, 15))

    items = cover_meta.get("items") or []
    if items:
        data = [["发票号", "销售方", "金额", "日期"]]
        for item in items[:20]:
            data.append([
                Paragraph(str(item.get("invoice_no", "")), cell_style),
                Paragraph(str(item.get("seller", "")), cell_style),
                Paragraph(str(item.get("total", "")), cell_style),
                Paragraph(str(item.get("date", "")), cell_style),
            ])
        if len(items) > 20:
            data.append([Paragraph(f"...(共 {len(items)} 条)", cell_style), "", "", ""])

        table = Table(data, colWidths=[120, 200, 80, 80])
        table.setStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ])
        elems.append(table)

    doc.build(elems)
    return out_path
