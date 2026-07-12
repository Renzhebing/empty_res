"""测试发票分类。"""
from __future__ import annotations

from fapiao_helper.parser import classify


def test_classify_restaurant():
    cat, score = classify.classify([{"name": "餐饮服务"}], seller="上海餐饮管理有限公司")
    assert cat == "餐饮住宿"
    assert score > 0


def test_classify_transport():
    cat, score = classify.classify([{"name": "出租车费"}], seller="北京出行科技有限公司")
    assert cat == "交通"


def test_classify_office():
    cat, score = classify.classify([{"name": "A4打印纸"}], seller="办公用品店")
    assert cat == "办公用品"


def test_classify_other():
    cat, score = classify.classify([{"name": "咨询服务费"}], seller="某某咨询公司")
    assert cat == "其他"


def test_classify_string_items():
    cat, score = classify.classify(["酒店住宿费"], seller="某宾馆")
    assert cat == "餐饮住宿"


def test_classify_priority_restaurant_over_transport():
    cat, _ = classify.classify([{"name": "餐费"}, {"name": "出租车"}])
    assert cat == "餐饮住宿"


def test_classify_threshold_low():
    """低于阈值归其他:多类别命中但最高占比不足阈值。"""
    items = [{"name": "餐饮"}, {"name": "出租车"}]
    cat, score = classify.classify(items, seller="", threshold=0.6)
    assert cat == "其他"


def test_classify_threshold_zero():
    items = [{"name": "餐饮"}]
    cat, score = classify.classify(items, seller="", threshold=0.0)
    assert cat == "餐饮住宿"


def test_classify_empty_items():
    cat, score = classify.classify([], seller="")
    assert cat == "其他"
    assert score == 0.0


def test_classify_only_seller():
    cat, score = classify.classify([], seller="某酒店")
    assert cat == "餐饮住宿"


def test_classify_from_parsed():
    parsed = {"items": [{"name": "餐饮服务"}], "seller": "餐饮公司"}
    cat, score = classify.classify_from_parsed(parsed)
    assert cat == "餐饮住宿"


def test_categories():
    assert "餐饮住宿" in classify.CATEGORIES
    assert "交通" in classify.CATEGORIES
    assert "办公用品" in classify.CATEGORIES
    assert "其他" in classify.CATEGORIES
