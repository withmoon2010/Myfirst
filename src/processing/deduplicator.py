from __future__ import annotations

import logging
from difflib import SequenceMatcher
from urllib.parse import urlparse, urlunparse

from src.processing.models import NewsItem

logger = logging.getLogger(__name__)

# Higher quality sources are preferred when deduplicating
SOURCE_PRIORITY = {
    "Reuters Business": 10,
    "Reuters World": 10,
    "Bloomberg Markets": 9,
    "Financial Times": 9,
    "CNBC Top News": 8,
    "Caixin Global": 8,
    "SCMP Business": 7,
    "Nikkei Asia": 7,
}


def _normalize_url(url: str) -> str:
    """Strip query params and fragment for comparison."""
    parsed = urlparse(url)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))


def _title_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _source_priority(source: str) -> int:
    for key, priority in SOURCE_PRIORITY.items():
        if key in source:
            return priority
    return 5  # default


class Deduplicator:
    def __init__(self, similarity_threshold: float = 0.75) -> None:
        self.threshold = similarity_threshold

    def deduplicate(self, items: list[NewsItem]) -> list[NewsItem]:
        if not items:
            return []

        # Layer 1: URL dedup
        url_map: dict[str, NewsItem] = {}
        for item in items:
            norm_url = _normalize_url(item.url)
            existing = url_map.get(norm_url)
            if existing is None:
                url_map[norm_url] = item
            elif _source_priority(item.source) > _source_priority(existing.source):
                url_map[norm_url] = item

        candidates = list(url_map.values())
        url_dedup_count = len(items) - len(candidates)

        # Layer 2: Title similarity dedup
        kept: list[NewsItem] = []
        for item in candidates:
            is_dup = False
            for existing in kept:
                if _title_similarity(item.title, existing.title) > self.threshold:
                    # Keep the higher-priority source
                    if _source_priority(item.source) > _source_priority(existing.source):
                        kept.remove(existing)
                        kept.append(item)
                    is_dup = True
                    break
            if not is_dup:
                kept.append(item)

        title_dedup_count = len(candidates) - len(kept)
        logger.info(
            "Dedup: %d -> %d items (URL: -%d, title: -%d)",
            len(items),
            len(kept),
            url_dedup_count,
            title_dedup_count,
        )
        return kept
