"""LLM 兜底解析:当正则解析失败或置信度低时,调用云端 LLM 补全字段。

输出 JSON Schema,缺失字段不阻塞入库(仅标记 needs_review=true)。
"""
from __future__ import annotations

import json
import logging
from typing import Any

from .vat_invoice import ParsedInvoice

logger = logging.getLogger(__name__)

_RESPONSE_SCHEMA = {
    "invoice_no": "发票号码(字符串)",
    "invoice_date": "开票日期 YYYY-MM-DD",
    "buyer": "购买方名称",
    "seller": "销售方名称",
    "buyer_tax_id": "购买方纳税人识别号",
    "seller_tax_id": "销售方纳税人识别号",
    "amount": "金额(数字,不含税)",
    "tax": "税额(数字)",
    "total": "价税合计(数字)",
    "items": "明细列表,每项含 name/amount",
}

_PROMPT_TEMPLATE = """请从以下发票 OCR 文本中提取字段,严格输出 JSON(不要 markdown 代码块)。
字段说明:
{schema}

若某字段无法识别,填 null。金额输出数字(不要带 ¥ 或逗号)。

OCR 文本:
---
{text}
---
"""


def build_prompt(ocr_text: str) -> str:
    schema_str = "\n".join(f"- {k}: {v}" for k, v in _RESPONSE_SCHEMA.items())
    return _PROMPT_TEMPLATE.format(schema=schema_str, text=ocr_text[:4000])


def parse_llm_response(content: str, ocr_text: str = "", ocr_conf: float = 0.0) -> ParsedInvoice:
    """解析 LLM 返回的 JSON 文本为 ParsedInvoice。"""
    inv = ParsedInvoice(raw_text=ocr_text)
    data: dict[str, Any] = {}

    try:
        cleaned = content.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            cleaned = "\n".join(lines)
        data = json.loads(cleaned)
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning("LLM 返回非合法 JSON: %s", e)
        inv.needs_review = True
        return inv

    inv.invoice_no = str(data.get("invoice_no") or "")
    inv.invoice_date = str(data.get("invoice_date") or "")
    inv.buyer = str(data.get("buyer") or "")
    inv.seller = str(data.get("seller") or "")
    inv.buyer_tax_id = str(data.get("buyer_tax_id") or "")
    inv.seller_tax_id = str(data.get("seller_tax_id") or "")

    def _num(v: Any) -> float | None:
        if v is None:
            return None
        try:
            return round(float(v), 2)
        except (TypeError, ValueError):
            return None

    inv.amount = _num(data.get("amount"))
    inv.tax = _num(data.get("tax"))
    inv.total = _num(data.get("total"))

    items_raw = data.get("items") or []
    if isinstance(items_raw, list):
        from .vat_invoice import InvoiceItem
        for it in items_raw:
            if isinstance(it, dict):
                inv.items.append(
                    InvoiceItem(
                        name=str(it.get("name") or ""),
                        amount=str(it.get("amount") or ""),
                    )
                )

    hit = sum(1 for v in [inv.invoice_no, inv.invoice_date, inv.total, inv.buyer, inv.seller] if v)
    inv.confidence = round(hit / 5 * 0.7 + ocr_conf * 0.3, 3)

    critical = [inv.invoice_no, inv.invoice_date, inv.total]
    inv.needs_review = any(c == "" or c is None for c in critical) or inv.confidence < 0.5

    return inv


def fallback(ocr_text: str, llm_router: Any, ocr_conf: float = 0.0) -> ParsedInvoice:
    """调用 LLM 兜底解析。"""
    if llm_router is None or not llm_router.has_provider():
        logger.info("无可用 LLM provider,跳过兜底")
        return ParsedInvoice(raw_text=ocr_text, needs_review=True, confidence=0.0)

    prompt = build_prompt(ocr_text)
    try:
        content = llm_router.complete(prompt)
        return parse_llm_response(content, ocr_text, ocr_conf)
    except Exception as e:
        logger.warning("LLM 兜底调用失败: %s", e)
        return ParsedInvoice(raw_text=ocr_text, needs_review=True, confidence=0.0)
