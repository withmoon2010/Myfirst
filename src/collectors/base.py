from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from src.processing.models import NewsItem


class BaseCollector(ABC):
    @abstractmethod
    async def collect(self, since: datetime) -> list[NewsItem]:
        """Collect news items published after `since` (UTC)."""
        ...
