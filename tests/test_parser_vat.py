"""测试增值税发票字段解析。"""
from __future__ import annotations

from fapiao_helper.parser import vat_invoice


SAMPLE_FULL = """电子发票
发票号码 2441200000012345
开票日期 2024年03月15日
购买方:
名称: 北京科技有限公司
纳税人识别号 91110108MA01ABCDEF
销售方:
名称: 上海餐饮管理有限公司
纳税人识别号 91310115MA1K2G3H4J
货物或应税劳务名称  规格型号 单位 数量 单价 金额 税率 税额
餐饮服务          次      1     1000  1000.00  6%  60.00
合计                      1000.00      60.00
价税合计 (大写) 壹仟零陆拾元 (小写) ¥1060.00
"""


def test_parse_invoice_no():
    inv = vat_invoice.parse(SAMPLE_FULL)
    assert inv.invoice_no == "2441200000012345"


def test_parse_date_cn():
    inv = vat_invoice.parse(SAMPLE_FULL)
    assert inv.invoice_date == "2024-03-15"


def test_parse_buyer_seller():
    inv = vat_invoice.parse(SAMPLE_FULL)
    assert "北京科技" in inv.buyer
    assert "上海餐饮" in inv.seller


def test_parse_tax_ids():
    inv = vat_invoice.parse(SAMPLE_FULL)
    assert inv.buyer_tax_id == "91110108MA01ABCDEF"
    assert inv.seller_tax_id == "91310115MA1K2G3H4J"


def test_parse_amounts():
    inv = vat_invoice.parse(SAMPLE_FULL)
    assert inv.total == 1060.00
    assert inv.amount == 1000.00
    assert inv.tax == 60.00


def test_parse_items():
    inv = vat_invoice.parse(SAMPLE_FULL)
    assert len(inv.items) >= 1
    assert any("餐饮" in it.name for it in inv.items)


def test_parse_confidence():
    inv = vat_invoice.parse(SAMPLE_FULL)
    assert inv.confidence > 0.5
    assert not inv.needs_review


def test_parse_date_iso():
    inv = vat_invoice.parse("发票号码 12345678\n开票日期 2024-12-25\n价税合计 (小写) ¥500.00\n")
    assert inv.invoice_date == "2024-12-25"
    assert inv.total == 500.00


def test_parse_disorder():
    inv = vat_invoice.parse("""价税合计 (小写) ¥888.88
销售方:
名称: 深圳办公用品店
发票号码 99887766
开票日期 2024年01月01日
购买方:
名称: 广州贸易公司
""")
    assert inv.invoice_no == "99887766"
    assert inv.invoice_date == "2024-01-01"
    assert inv.total == 888.88


def test_parse_missing_fields():
    inv = vat_invoice.parse("这是乱七八糟的文本\n没有发票号码\n")
    assert inv.invoice_no == ""
    assert inv.needs_review is True


def test_parse_empty():
    inv = vat_invoice.parse("")
    assert inv.invoice_no == ""
    assert inv.needs_review is True


def test_parse_old_invoice_no():
    inv = vat_invoice.parse("发票号码 12345678\n开票日期 2023年05月20日\n价税合计 ¥100.00\n")
    assert inv.invoice_no == "12345678"


def test_parse_thousands_amount():
    inv = vat_invoice.parse("""发票号码 2441200000011111
开票日期 2024年03月15日
金额 1,234,567.89 税额 12,345.68
价税合计 ¥1,246,913.57
""")
    assert inv.amount == 1234567.89
    assert inv.tax == 12345.68
    assert inv.total == 1246913.57
