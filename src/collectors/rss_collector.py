from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path

import feedparser
import httpx
import yaml

from src.collectors.base import BaseCollector
from src.config import Settings
from src.processing.models import NewsItem

logger = logging.getLogger(__name__)

FEEDS_PATH = Path(__file__).parent / "feeds.yaml"


def _parse_published(entry: dict) -> datetime | None:
    """Extract and parse published datetime from a feed entry."""
    for key in ("published_parsed", "updated_parsed"):
        tp = entry.get(key)
        if tp:
            from calendar import timegm

            return datetime.fromtimestamp(timegm(tp), tz=timezone.utc)
    # Try parsing date string directly
    for key in ("published", "updated"):
        raw = entry.get(key)
        if raw:
            try:
                from email.utils import parsedate_to_datetime

                return parsedate_to_datetime(raw).astimezone(timezone.utc)
            except Exception:
                pass
    return None


def _extract_text(entry: dict) -> str:
    """Extract the best available text content from a feed entry."""
    if entry.get("summary"):
        return entry["summary"]
    if entry.get("content"):
        return entry["content"][0].get("value", "")
    if entry.get("description"):
        return entry["description"]
    return ""


class RSSCollector(BaseCollector):
    def __init__(self, config: Settings) -> None:
        self.config = config
        self.max_items = config.max_items_per_source

    def _load_feeds(self) -> list[dict]:
        with open(FEEDS_PATH) as f:
            data = yaml.safe_load(f)
        return data.get("feeds", [])

    async def _fetch_feed(
        self,
        client: httpx.AsyncClient,
        feed_info: dict,
        since: datetime,
        semaphore: asyncio.Semaphore,
    ) -> list[NewsItem]:
        url = feed_info["url"]
        name = feed_info.get("name", url)
        language = feed_info.get("language", "en")
        regions = feed_info.get("regions", [])

        async with semaphore:
            try:
                resp = await client.get(url, timeout=15.0)
                resp.raise_for_status()
            except Exception as e:
                logger.warning("Failed to fetch RSS feed %s: %s", name, e)
                return []

        parsed = feedparser.parse(resp.text)
        items: list[NewsItem] = []

        for entry in parsed.entries:
            pub_dt = _parse_published(entry)
            if pub_dt is None:
                continue
            if pub_dt < since:
                continue

            title = entry.get("title", "").strip()
            link = entry.get("link", "").strip()
            if not title or not link:
                continue

            items.append(
                NewsItem(
                    title=title,
                    url=link,
                    source=name,
                    published_at=pub_dt,
                    raw_text=_extract_text(entry),
                    language=language,
                    regions=regions,
                )
            )

            if len(items) >= self.max_items:
                break

        logger.info("RSS [%s]: collected %d items", name, len(items))
        return items

    async def collect(self, since: datetime) -> list[NewsItem]:
        feeds = self._load_feeds()
        if not feeds:
            logger.warning("No RSS feeds configured in feeds.yaml")
            return []

        semaphore = asyncio.Semaphore(5)
        all_items: list[NewsItem] = []

        async with httpx.AsyncClient(
            headers={"User-Agent": "DailyMacroBrief/1.0"},
            follow_redirects=True,
        ) as client:
            tasks = [
                self._fetch_feed(client, feed, since, semaphore) for feed in feeds
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                logger.warning("RSS collector task failed: %s", result)
            else:
                all_items.extend(result)

        logger.info("RSS total: collected %d items from %d feeds", len(all_items), len(feeds))
        return all_items
