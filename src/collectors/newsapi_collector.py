from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from src.collectors.base import BaseCollector
from src.config import Settings
from src.processing.models import NewsItem

logger = logging.getLogger(__name__)

NEWSAPI_BASE = "https://newsapi.org/v2/everything"

# Targeted queries per topic/region for efficient use of limited API calls
QUERIES = [
    {
        "q": '"Federal Reserve" OR "interest rate" OR "monetary policy" OR "FOMC"',
        "regions": ["US"],
    },
    {
        "q": '"China" AND ("economy" OR "trade" OR "PBOC" OR "yuan" OR "tariff")',
        "regions": ["CN"],
    },
    {
        "q": '"US-China" OR "trade war" OR "sanctions" OR "geopolitical"',
        "regions": ["US", "CN", "Global"],
    },
    {
        "q": '"GDP" OR "inflation" OR "CPI" OR "PMI" OR "nonfarm payrolls"',
        "regions": ["Global"],
    },
    {
        "q": '"Bank of Japan" OR "BOJ" OR "yen" OR "Nikkei"',
        "regions": ["JP"],
    },
    {
        "q": '"India economy" OR "RBI" OR "rupee" OR "sensex"',
        "regions": ["IN"],
    },
    {
        "q": '"Latin America" OR "Brazil economy" OR "Mexico economy" OR "Argentina"',
        "regions": ["LATAM"],
    },
    {
        "q": '"crude oil" OR "gold price" OR "commodity" OR "dollar index"',
        "regions": ["Global"],
    },
]


class NewsAPICollector(BaseCollector):
    def __init__(self, config: Settings) -> None:
        self.config = config
        self.api_key = config.newsapi_key
        self.max_items = config.max_items_per_source

    async def collect(self, since: datetime) -> list[NewsItem]:
        if not self.config.newsapi_enabled or not self.api_key:
            logger.info("NewsAPI disabled or no API key configured, skipping")
            return []

        since_str = since.strftime("%Y-%m-%dT%H:%M:%S")
        all_items: list[NewsItem] = []
        seen_urls: set[str] = set()

        async with httpx.AsyncClient(timeout=20.0) as client:
            for query_info in QUERIES:
                if len(all_items) >= self.max_items:
                    break

                params = {
                    "q": query_info["q"],
                    "from": since_str,
                    "sortBy": "publishedAt",
                    "pageSize": 20,
                    "language": "en",
                    "apiKey": self.api_key,
                }

                try:
                    resp = await client.get(NEWSAPI_BASE, params=params)
                    if resp.status_code == 429:
                        logger.warning("NewsAPI rate limit hit, stopping queries")
                        break
                    resp.raise_for_status()
                    data = resp.json()
                except Exception as e:
                    logger.warning("NewsAPI query failed (%s): %s", query_info["q"][:30], e)
                    continue

                articles = data.get("articles", [])
                for article in articles:
                    url = article.get("url", "")
                    if not url or url in seen_urls:
                        continue
                    seen_urls.add(url)

                    title = article.get("title", "").strip()
                    if not title or title == "[Removed]":
                        continue

                    pub_str = article.get("publishedAt", "")
                    try:
                        pub_dt = datetime.fromisoformat(
                            pub_str.replace("Z", "+00:00")
                        ).astimezone(timezone.utc)
                    except Exception:
                        continue

                    description = article.get("description") or ""
                    content = article.get("content") or ""
                    raw_text = description if len(description) > len(content) else content
                    source_name = article.get("source", {}).get("name", "NewsAPI")

                    all_items.append(
                        NewsItem(
                            title=title,
                            url=url,
                            source=f"NewsAPI:{source_name}",
                            published_at=pub_dt,
                            raw_text=raw_text,
                            language="en",
                            regions=query_info["regions"],
                        )
                    )

                logger.debug(
                    "NewsAPI query '%s': %d articles",
                    query_info["q"][:30],
                    len(articles),
                )

        logger.info("NewsAPI total: collected %d items", len(all_items))
        return all_items
