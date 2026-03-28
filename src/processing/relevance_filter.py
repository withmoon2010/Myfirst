from __future__ import annotations

import logging
import re

from src.config import Settings
from src.processing.models import NewsItem

logger = logging.getLogger(__name__)

# ── Region keyword weights ──
REGION_KEYWORDS: dict[str, dict[str, int]] = {
    "US": {
        "federal reserve": 3, "fed ": 2, "fomc": 3, "us economy": 3,
        "wall street": 2, "s&p 500": 2, "nasdaq": 2, "dow jones": 2,
        "treasury": 2, "us dollar": 2, "white house": 2, "congress": 1,
        "united states": 2, "america": 1, "washington": 1,
    },
    "CN": {
        "china": 2, "chinese": 2, "pboc": 3, "beijing": 1, "shanghai": 1,
        "renminbi": 3, "yuan": 2, "cny": 2, "csi 300": 2, "hang seng": 2,
        "中国": 2, "央行": 3, "人民币": 3, "国务院": 2, "发改委": 2,
        "a股": 2, "沪深": 2, "港股": 2, "贸易战": 3, "关税": 3,
    },
    "JP": {
        "japan": 2, "boj": 3, "bank of japan": 3, "nikkei": 2,
        "yen": 2, "jpy": 2, "tokyo": 1, "日本": 2, "日元": 2, "日银": 3,
    },
    "KR": {
        "korea": 2, "south korea": 2, "bok": 3, "kospi": 2,
        "won ": 2, "krw": 2, "seoul": 1, "韩国": 2, "韩元": 2,
    },
    "TW": {
        "taiwan": 2, "tsmc": 2, "taiex": 2, "taipei": 1,
        "台湾": 2, "台积电": 2, "新台币": 2,
    },
    "IN": {
        "india": 2, "rbi": 3, "reserve bank of india": 3, "sensex": 2,
        "nifty": 2, "rupee": 2, "inr": 2, "mumbai": 1, "印度": 2, "卢比": 2,
    },
    "SEA": {
        "southeast asia": 3, "asean": 3, "singapore": 2, "indonesia": 2,
        "vietnam": 2, "thailand": 2, "philippines": 2, "malaysia": 2,
        "东南亚": 3, "东盟": 3, "新加坡": 2, "印尼": 2, "越南": 2,
    },
    "LATAM": {
        "latin america": 3, "brazil": 2, "mexico": 2, "argentina": 2,
        "chile": 2, "colombia": 2, "real ": 1, "peso": 1,
        "拉美": 3, "巴西": 2, "墨西哥": 2, "阿根廷": 2,
    },
}

# ── Category keyword weights ──
CATEGORY_KEYWORDS: dict[str, dict[str, int]] = {
    "macro": {
        "gdp": 3, "inflation": 3, "cpi": 3, "ppi": 2, "pmi": 3,
        "employment": 2, "unemployment": 2, "nonfarm": 3, "payroll": 2,
        "interest rate": 3, "monetary policy": 3, "fiscal": 2, "stimulus": 2,
        "recession": 3, "growth": 1, "deficit": 2, "debt": 2,
        "通胀": 3, "就业": 2, "利率": 3, "货币政策": 3, "财政": 2,
        "经济增长": 2, "衰退": 3,
    },
    "geopolitical": {
        "tariff": 3, "sanctions": 3, "sanction": 3, "trade war": 3,
        "election": 2, "regulation": 2, "war ": 3, "conflict": 2,
        "military": 2, "nuclear": 3, "diplomacy": 2, "embargo": 3,
        "关税": 3, "制裁": 3, "选举": 2, "监管": 2, "战争": 3,
        "冲突": 2, "外交": 2,
    },
    "market": {
        "earnings": 2, "ipo": 2, "stock market": 2, "equity": 1,
        "bond": 2, "yield": 2, "commodity": 2, "crude oil": 2,
        "gold": 2, "copper": 2, "rally": 1, "crash": 3, "selloff": 3,
        "盈利": 2, "股市": 2, "债券": 2, "收益率": 2, "原油": 2,
        "黄金": 2, "大宗商品": 2, "暴跌": 3, "暴涨": 3,
    },
}

# Score threshold for inclusion
RELEVANCE_THRESHOLD = 0.15
PRIMARY_REGION_BOOST = 1.5


class RelevanceFilter:
    def __init__(self, config: Settings) -> None:
        self.primary_regions = set(config.primary_regions)

    def _score_item(self, item: NewsItem) -> NewsItem:
        """Compute relevance score and assign regions/categories."""
        text = f"{item.title} {item.raw_text}".lower()
        total_score = 0.0
        max_possible = 1.0  # avoid division by zero

        # Score regions
        matched_regions: set[str] = set(item.regions)  # keep pre-assigned from collector
        for region, keywords in REGION_KEYWORDS.items():
            region_score = 0
            for kw, weight in keywords.items():
                if kw in text:
                    region_score += weight
                    matched_regions.add(region)
            if region in self.primary_regions:
                region_score *= PRIMARY_REGION_BOOST
            total_score += region_score
            max_possible += sum(keywords.values())

        # Score categories
        matched_categories: set[str] = set()
        for category, keywords in CATEGORY_KEYWORDS.items():
            for kw, weight in keywords.items():
                if kw in text:
                    total_score += weight
                    matched_categories.add(category)
            max_possible += sum(keywords.values())

        # Normalize to 0-1
        normalized = min(total_score / (max_possible * 0.05), 1.0)

        # If no region detected, mark as Global
        if not matched_regions:
            matched_regions.add("Global")

        item.regions = sorted(matched_regions)
        item.categories = sorted(matched_categories)
        item.relevance_score = normalized
        return item

    def filter(self, items: list[NewsItem]) -> list[NewsItem]:
        """Score and filter items by relevance threshold."""
        scored = [self._score_item(item) for item in items]
        passed = [item for item in scored if item.relevance_score >= RELEVANCE_THRESHOLD]
        passed.sort(key=lambda x: x.relevance_score, reverse=True)

        logger.info(
            "Relevance filter: %d -> %d items (threshold=%.2f)",
            len(items),
            len(passed),
            RELEVANCE_THRESHOLD,
        )
        return passed
