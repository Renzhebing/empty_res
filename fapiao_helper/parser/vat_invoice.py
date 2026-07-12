"""增值税发票字段解析。

用关键词锚点 + 正则从 OCR 文本行中提取发票字段。
输出字段:invoice_no, invoice_date, buyer, seller, buyer_tax_id,
seller_tax_id, amount, tax, total, items[], confidence。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class InvoiceItem:
    name: str = ""
    spec: str = ""
    unit: str = ""
    quantity: str = ""
    unit_price: str = ""
    amount: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "spec": self.spec,
            "unit": self.unit,
            "quantity": self.quantity,
            "unit_price": self.unit_price,
            "amount": self.amount,
        }


@dataclass
class ParsedInvoice:
    invoice_no: str = ""
    invoice_date: str = ""
    buyer: str = ""
    seller: str = ""
    buyer_tax_id: str = ""
    seller_tax_id: str = ""
    amount: float | None = None
    tax: float | None = None
    total: float | None = None
    items: list[InvoiceItem] = field(default_factory=list)
    confidence: float = 0.0
    needs_review: bool = False
    raw_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "invoice_no": self.invoice_no,
            "invoice_date": self.invoice_date,
            "buyer": self.buyer,
            "seller": self.seller,
            "buyer_tax_id": self.buyer_tax_id,
            "seller_tax_id": self.seller_tax_id,
            "amount": self.amount,
            "tax": self.tax,
            "total": self.total,
            "items": [it.to_dict() for it in self.items],
            "confidence": self.confidence,
            "needs_review": self.needs_review,
        }


# ----------------- 正则 -----------------

# 发票号码:20 位(全电)或 8 位数字
_RE_INVOICE_NO = re.compile(r"发\s*票\s*号\s*码\s*[:：]?\s*(\d{8,20})")
_RE_INVOICE_NO_BARE = re.compile(r"\b(\d{20})\b")

# 开票日期
_RE_DATE_CN = re.compile(
    r"开\s*票\s*日\s*期\s*[:：]?\s*(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日"
)
_RE_DATE_ISO = re.compile(
    r"开\s*票\s*日\s*期\s*[:：]?\s*(\d{4}[-/]\d{1,2}[-/]\d{1,2})"
)

# 税号:按长度降序匹配,避免 18/20 位税号被截断为 15 位
_RE_TAX_ID = re.compile(
    r"纳税人识别号\s*[:：]?\s*([0-9A-Z]{20}|[0-9A-Z]{18}|[0-9A-Z]{15})"
)
_RE_TAX_ID_BARE = re.compile(r"\b([0-9A-Z]{20}|[0-9A-Z]{18}|[0-9A-Z]{15})\b")

# 金额模式
_AMOUNT_PATTERN = r"¥?\s*([0-9]+(?:,?[0-9]{3})*(?:\.[0-9]{1,2})?)"
_AMOUNT_LOOSE = r"([0-9]+(?:\.[0-9]{1,2})?)"

# 价税合计(兼容全角/半角括号)
_RE_TOTAL = re.compile(
    r"价\s*税\s*合\s*计\s*[:：（\(]?\s*(?:大写)?\s*" + _AMOUNT_PATTERN
)
_RE_TOTAL_ALT = re.compile(r"[（(]\s*小写\s*[）)]\s*¥?\s*" + _AMOUNT_LOOSE)
_RE_TOTAL_ALT2 = re.compile(r"小写\s*[：:]?\s*¥?\s*" + _AMOUNT_LOOSE)

# 金额/税额成对
_RE_AMOUNT_TAX = re.compile(
    r"(?:金\s*额|合\s*计)\s*(?:税\s*额)?\s*" + _AMOUNT_PATTERN + r"\s*"
    r"(?:税\s*额)?\s*" + _AMOUNT_PATTERN
)


def _to_float(s: str | None) -> float | None:
    if s is None or s == "":
        return None
    s = s.replace(",", "").replace("¥", "").strip()
    try:
        return round(float(s), 2)
    except ValueError:
        return None


def _normalize_date(y: str, m: str, d: str) -> str:
    return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"


# ----------------- 主解析函数 -----------------


def parse(lines: list[str] | str, ocr_conf: float = 0.0) -> ParsedInvoice:
    """解析发票文本。"""
    if isinstance(lines, str):
        lines = lines.splitlines()
    lines = [ln.strip() for ln in lines]
    text = "\n".join(lines)
    joined = "".join(lines)

    inv = ParsedInvoice(raw_text=text)
    hit = 0
    total_fields = 8

    # 1. 发票号码
    m = _RE_INVOICE_NO.search(joined) or _RE_INVOICE_NO.search(text)
    if m:
        inv.invoice_no = m.group(1)
        hit += 1
    else:
        m = _RE_INVOICE_NO_BARE.search(joined)
        if m:
            inv.invoice_no = m.group(1)
            hit += 1

    # 2. 开票日期
    m = _RE_DATE_CN.search(text) or _RE_DATE_CN.search(joined)
    if m:
        inv.invoice_date = _normalize_date(m.group(1), m.group(2), m.group(3))
        hit += 1
    else:
        m = _RE_DATE_ISO.search(text) or _RE_DATE_ISO.search(joined)
        if m:
            d = m.group(1).replace("/", "-")
            parts = d.split("-")
            if len(parts) == 3:
                inv.invoice_date = _normalize_date(parts[0], parts[1], parts[2])
            hit += 1

    # 3. 购买方/销售方
    buyer_idx, seller_idx = _find_buyer_seller(lines)
    if buyer_idx is not None:
        inv.buyer = _clean_name(lines[buyer_idx])
        hit += 1
    if seller_idx is not None:
        inv.seller = _clean_name(lines[seller_idx])
        hit += 1

    # 4. 税号
    inv.buyer_tax_id, inv.seller_tax_id = _find_tax_ids(lines, buyer_idx, seller_idx, joined)
    if inv.buyer_tax_id:
        hit += 1
    if inv.seller_tax_id:
        hit += 1

    # 5. 金额
    inv.amount, inv.tax, inv.total = _find_amounts(text, joined)
    if inv.total is not None:
        hit += 1
    if inv.amount is not None:
        hit += 1
    if inv.total is not None and inv.amount is not None and inv.tax is None:
        diff = round(inv.total - inv.amount, 2)
        if abs(diff) < inv.total:
            inv.tax = diff

    # 6. 明细
    inv.items = _find_items(lines)

    # 置信度
    inv.confidence = round(hit / total_fields * 0.7 + ocr_conf * 0.3, 3)

    # 需复核
    critical = [inv.invoice_no, inv.invoice_date, inv.total]
    inv.needs_review = any(c == "" or c is None for c in critical) or inv.confidence < 0.5

    return inv


def _find_buyer_seller(lines: list[str]) -> tuple[int | None, int | None]:
    """定位购买方/销售方名称行索引。"""
    buyer_idx = None
    seller_idx = None
    for i, ln in enumerate(lines):
        if ("购" in ln or "买方" in ln) and buyer_idx is None:
            buyer_idx = _extract_name_line(lines, i)
        if ("销" in ln or "卖方" in ln or "销售方" in ln) and seller_idx is None:
            seller_idx = _extract_name_line(lines, i)
        if buyer_idx is not None and seller_idx is not None:
            break

    if buyer_idx is None or seller_idx is None:
        name_lines = [i for i, ln in enumerate(lines) if "名称" in ln]
        if len(name_lines) >= 2:
            if buyer_idx is None:
                buyer_idx = _extract_name_line(lines, name_lines[0])
            if seller_idx is None:
                for idx in name_lines:
                    if idx != buyer_idx:
                        seller_idx = _extract_name_line(lines, idx)
                        break
    return buyer_idx, seller_idx


def _extract_name_line(lines: list[str], anchor_idx: int) -> int | None:
    """从锚点行提取名称:可能在同行或下一行。"""
    if anchor_idx >= len(lines):
        return None
    ln = lines[anchor_idx]
    m = re.search(r"名\s*称\s*[:：]?\s*(\S.+)", ln)
    if m:
        return anchor_idx
    if anchor_idx + 1 < len(lines):
        nxt = lines[anchor_idx + 1].strip()
        if nxt and "名称" in nxt:
            return anchor_idx + 1
        if nxt and ("公司" in nxt or "中心" in nxt or "店" in nxt or "厂" in nxt):
            return anchor_idx + 1
    return None


def _clean_name(s: str) -> str:
    """清洗名称文本。"""
    s = re.sub(r"名\s*称\s*[:：]?", "", s)
    s = re.sub(r"^(购|销|买|卖).*?[：:]", "", s)
    s = re.split(r"纳税人|统一社会|地址|电话|开户行|账号", s)[0]
    return s.strip()


def _find_tax_ids(
    lines: list[str],
    buyer_idx: int | None,
    seller_idx: int | None,
    joined: str,
) -> tuple[str, str]:
    """定位购买方/销售方税号。"""
    buyer_tax = ""
    seller_tax = ""

    for i, ln in enumerate(lines):
        m = _RE_TAX_ID.search(ln)
        if not m:
            continue
        val = m.group(1)
        if buyer_idx is not None and seller_idx is not None:
            if i <= (buyer_idx + seller_idx) // 2 and not buyer_tax:
                buyer_tax = val
            elif not seller_tax:
                seller_tax = val
        else:
            if not buyer_tax:
                buyer_tax = val
            elif not seller_tax:
                seller_tax = val

    if not buyer_tax or not seller_tax:
        all_ids = _RE_TAX_ID_BARE.findall(joined)
        for tid in all_ids:
            if tid == buyer_tax or tid == seller_tax:
                continue
            if not buyer_tax:
                buyer_tax = tid
            elif not seller_tax:
                seller_tax = tid
    return buyer_tax, seller_tax


def _find_amounts(text: str, joined: str) -> tuple[float | None, float | None, float | None]:
    """提取金额、税额、价税合计。"""
    total = None
    tax = None
    amount = None

    m = _RE_TOTAL.search(text) or _RE_TOTAL.search(joined)
    if m:
        total = _to_float(m.group(1))
    if total is None:
        m = _RE_TOTAL_ALT.search(text) or _RE_TOTAL_ALT2.search(text)
        if m:
            total = _to_float(m.group(1))

    m = _RE_AMOUNT_TAX.search(text) or _RE_AMOUNT_TAX.search(joined)
    if m:
        amount = _to_float(m.group(1))
        tax = _to_float(m.group(2))

    if amount is None:
        m = re.search(r"金\s*额\s*[:：]?\s*" + _AMOUNT_PATTERN, text)
        if m:
            amount = _to_float(m.group(1))
    if tax is None:
        m = re.search(r"税\s*额\s*[:：]?\s*" + _AMOUNT_PATTERN, text)
        if m:
            tax = _to_float(m.group(1))

    return amount, tax, total


def _find_items(lines: list[str]) -> list[InvoiceItem]:
    """提取货物明细行。"""
    items: list[InvoiceItem] = []
    header_idx = None
    for i, ln in enumerate(lines):
        if "货物或应税劳务" in ln or "货物或应税" in ln or ("项目名称" in ln and "规格" in ln):
            header_idx = i
            break
    if header_idx is None:
        return items

    for ln in lines[header_idx + 1:]:
        if not ln:
            continue
        if "合计" in ln or "价税合计" in ln or "小写" in ln:
            break
        if re.search(r"规格型号|单位|数量|单价|金额|税率|税额", ln):
            continue
        name = re.split(r"\s{2,}|\t", ln, maxsplit=1)[0].strip()
        nums = re.findall(_AMOUNT_LOOSE, ln)
        item = InvoiceItem(
            name=name,
            amount=nums[-1] if nums else "",
        )
        if len(nums) >= 3:
            item.quantity = nums[-3]
            item.unit_price = nums[-2]
        items.append(item)
    return items


def extract_text(invoice: ParsedInvoice) -> str:
    """返回原始 OCR 文本(调试用)。"""
    return invoice.raw_text
