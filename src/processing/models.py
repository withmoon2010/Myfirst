from __future__ import annotations

from datetime import date, datetime
from pydantic import BaseModel, Field


class NewsItem(BaseModel):
    title: str
    url: str
    source: str  # e.g. "Reuters RSS", "NewsAPI"
    published_at: datetime
    raw_text: str = ""  # snippet or full article text
    language: str = "en"  # "en", "zh", etc.
    regions: list[str] = Field(default_factory=list)  # assigned during filtering
    categories: list[str] = Field(default_factory=list)  # "macro", "geopolitical", "market"
    relevance_score: float = 0.0  # 0.0-1.0


class SummarizedItem(BaseModel):
    title: str
    url: str
    source: str
    published_at: datetime
    summary: str  # 1-2 sentence summary in original language
    market_implication: str  # 1 sentence on portfolio impact
    urgency: str = "medium"  # "high" | "medium" | "low"


class SpecialTopic(BaseModel):
    title: str  # e.g. "US-China Trade Escalation"
    region: str
    background: str  # context and timeline
    analysis: str  # multi-angle analysis
    portfolio_implications: str  # what it means for positioning
    related_items: list[SummarizedItem] = Field(default_factory=list)


class NewsletterSection(BaseModel):
    region: str  # "US", "CN", "Asia", "LATAM", "Global"
    region_label: str  # display name e.g. "United States", "China"
    items: list[SummarizedItem] = Field(default_factory=list)


class RegionalSummaryResult(BaseModel):
    """Output from a single regional Claude API call."""
    region: str
    items: list[SummarizedItem] = Field(default_factory=list)
    has_major_event: bool = False
    major_event_title: str = ""
    major_event_description: str = ""


class Newsletter(BaseModel):
    date: date
    key_takeaways: list[str] = Field(default_factory=list)  # 3-5 bullet points
    risk_alerts: list[SummarizedItem] = Field(default_factory=list)
    special_topics: list[SpecialTopic] = Field(default_factory=list)
    sections: list[NewsletterSection] = Field(default_factory=list)
