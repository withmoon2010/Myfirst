from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from src.processing.models import NewsItem

logger = logging.getLogger(__name__)


class FreshnessValidator:
    def __init__(self, lookback_hours: int = 24) -> None:
        self.lookback_hours = lookback_hours

    def validate(self, items: list[NewsItem]) -> list[NewsItem]:
        """Drop items outside the lookback window. Normalizes to UTC."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.lookback_hours)
        valid: list[NewsItem] = []
        dropped_old = 0
        dropped_no_date = 0

        for item in items:
            pub = item.published_at
            if pub is None:
                dropped_no_date += 1
                continue

            # Ensure timezone-aware (assume UTC if naive)
            if pub.tzinfo is None:
                pub = pub.replace(tzinfo=timezone.utc)
                item.published_at = pub

            if pub < cutoff:
                dropped_old += 1
                continue

            valid.append(item)

        logger.info(
            "Freshness check: %d passed, %d too old, %d no date (cutoff: %s)",
            len(valid),
            dropped_old,
            dropped_no_date,
            cutoff.isoformat(),
        )
        return valid
