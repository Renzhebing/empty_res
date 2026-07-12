"""发票分类:按 items[].name + seller 加权打分,4 类。

类别:餐饮住宿 / 交通 / 办公用品 / 其他。
"""
from __future__ import annotations

from typing import Any

# 4 类关键词表(按命中权重)
_KEYWORDS: dict[str, dict[str, int]] = {
    "餐饮住宿": {
        "餐": 3, "饭店": 3, "餐厅": 3, "餐饮": 3, "美食": 3, "酒店": 3, "住宿": 3,
        "宾馆": 3, "旅馆": 3, "民宿": 3, "茶": 2, "咖啡": 2, "奶茶": 2, "食品": 2,
        "食品店": 3, "小吃": 3, "酒楼": 3, "酒家": 3, "快餐": 3, "外卖": 3,
    },
    "交通": {
        "出租": 3, "网约车": 3, "滴滴": 3, "高铁": 3, "火车": 3, "机票": 3, "航空": 3,
        "机票代理": 3, "客运": 3, "公交": 3, "地铁": 3, "停车": 3, "过路费": 3,
        "加油": 3, "石油": 3, "石化": 3, "代驾": 3, "租车": 3, "出行": 2,
        "铁路": 3, "航空票务": 3, "运输": 2, "车票": 3,
    },
    "办公用品": {
        "文具": 3, "打印": 3, "复印": 3, "纸张": 3, "笔": 2, "笔记本": 2, "办公": 3,
        "电脑": 3, "耗材": 3, "墨盒": 3, "硒鼓": 3, "U盘": 3, "硬盘": 3, "鼠标": 3,
        "键盘": 3, "显示器": 3, "软件": 2, "耗材店": 3, "办公用品": 3, "办公设备": 3,
    },
}

CATEGORIES = list(_KEYWORDS.keys()) + ["其他"]


def classify(items: list[dict[str, Any]] | list[str], seller: str = "", threshold: float = 0.3) -> tuple[str, float]:
    """对发票分类。

    Returns:
        (category, score) score 为 0-1 的归一化置信度。
    """
    texts: list[str] = []
    if items:
        for it in items:
            if isinstance(it, dict):
                name = str(it.get("name", "") or "")
            else:
                name = str(it or "")
            if name:
                texts.append(name)
    if seller:
        texts.append(seller)

    if not texts:
        return "其他", 0.0

    # 打分:每个文本在每个类别取最高权重关键词命中
    scores: dict[str, int] = {cat: 0 for cat in _KEYWORDS}
    for cat, kws in _KEYWORDS.items():
        for text in texts:
            best_w = 0
            for kw, w in kws.items():
                if kw in text and w > best_w:
                    best_w = w
            scores[cat] += best_w

    total_score = sum(scores.values())
    if total_score == 0:
        return "其他", 0.0

    best_cat = max(scores, key=lambda c: scores[c])
    best_score = scores[best_cat]
    normalized = best_score / total_score if total_score > 0 else 0.0

    # 并列最高时按优先级
    top_cats = [c for c, s in scores.items() if s == best_score and s > 0]
    if len(top_cats) > 1:
        priority = ["餐饮住宿", "交通", "办公用品"]
        for p in priority:
            if p in top_cats:
                best_cat = p
                break

    if normalized < threshold or best_score == 0:
        return "其他", round(normalized, 3)

    return best_cat, round(normalized, 3)


def classify_from_parsed(parsed_dict: dict[str, Any], threshold: float = 0.3) -> tuple[str, float]:
    """从 ParsedInvoice.to_dict() 结果分类。"""
    items = parsed_dict.get("items", []) or []
    seller = str(parsed_dict.get("seller", "") or "")
    return classify(items, seller, threshold)
