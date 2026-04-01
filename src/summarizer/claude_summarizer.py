from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict
from datetime import date

import anthropic

from src.config import Settings
from src.processing.models import (
    Newsletter,
    NewsItem,
    NewsletterSection,
    RegionalSummaryResult,
    SpecialTopic,
    SummarizedItem,
)

logger = logging.getLogger(__name__)

# Region display names
REGION_LABELS = {
    "US": "United States",
    "CN": "China",
    "JP": "Japan",
    "KR": "South Korea",
    "TW": "Taiwan",
    "IN": "India",
    "SEA": "Southeast Asia",
    "LATAM": "Latin America",
    "Global": "Global / Commodities / FX",
}

# Merge small regions for summarization
REGION_GROUPS = {
    "US": ["US"],
    "CN": ["CN"],
    "Asia": ["JP", "KR", "TW"],
    "IN_SEA": ["IN", "SEA"],
    "LATAM": ["LATAM"],
    "Global": ["Global"],
}


def _build_regional_prompt(region_label: str, items: list[NewsItem], today: str) -> str:
    items_text = ""
    for i, item in enumerate(items, 1):
        items_text += (
            f"\n[{i}] {item.title}\n"
            f"    Source: {item.source} | Published: {item.published_at.isoformat()}\n"
            f"    Language: {item.language}\n"
            f"    Text: {item.raw_text[:500]}\n"
            f"    URL: {item.url}\n"
        )

    return f"""You are a senior macro analyst preparing a daily briefing for a portfolio manager
focused on China and US markets, with secondary coverage of Japan, Korea, Taiwan, India,
Southeast Asia, and Latin America.

Today's date: {today}
Region focus: {region_label}

Below are {len(items)} news items from the last 24 hours for this region.
{items_text}

Your tasks:

1. SUMMARIZE each item:
   - "title": concise headline (keep original language - Chinese items in Chinese, English in English)
   - "summary": 1-2 sentence summary in the item's original language
   - "market_implication": 1 sentence on what this means for portfolio positioning (in the item's language)
   - "urgency": "high" if market-moving or acute risk, "medium" for notable, "low" for informational
   - "url": the original URL
   - "source": the original source name
   - "published_at": the original published datetime

2. MAJOR EVENT DETECTION:
   - Look across ALL items: is there a dominant theme or major geopolitical/macro event?
   - Examples: trade escalation, central bank surprise, election shock, military conflict, regulatory crackdown
   - Set "has_major_event" to true if you detect one, with a brief title and description.

3. Drop trivial or purely corporate items (unless market-cap > $50B or systemic importance).

Return ONLY valid JSON matching this schema:
{{
  "region": "{region_label}",
  "items": [
    {{
      "title": "...",
      "url": "...",
      "source": "...",
      "published_at": "...",
      "summary": "...",
      "market_implication": "...",
      "urgency": "high|medium|low"
    }}
  ],
  "has_major_event": false,
  "major_event_title": "",
  "major_event_description": ""
}}"""


def _build_special_topic_prompt(
    event_title: str, event_description: str, region: str, items: list[NewsItem], today: str
) -> str:
    items_text = ""
    for i, item in enumerate(items, 1):
        items_text += f"\n[{i}] {item.title}\n    {item.raw_text[:300]}\n"

    return f"""You are a senior macro strategist writing a deep-dive special topic for a portfolio manager.

Today: {today}
Topic: {event_title}
Region: {region}
Context: {event_description}

Related news items:
{items_text}

Write a comprehensive special topic analysis. Return ONLY valid JSON:
{{
  "title": "{event_title}",
  "region": "{region}",
  "background": "2-3 paragraphs: context, timeline of events, key players (keep original language where appropriate)",
  "analysis": "2-3 paragraphs: multi-angle analysis - bull case, bear case, base case",
  "portfolio_implications": "1-2 paragraphs: specific positioning suggestions - what to overweight/underweight, hedging ideas, timeline for resolution"
}}"""


def _build_synthesis_prompt(
    regional_results: list[RegionalSummaryResult],
    special_topics: list[SpecialTopic],
    today: str,
) -> str:
    summaries_text = ""
    for result in regional_results:
        high_urgency = [it for it in result.items if it.urgency == "high"]
        summaries_text += f"\n## {result.region}\n"
        summaries_text += f"Items: {len(result.items)} | High-urgency: {len(high_urgency)}\n"
        for item in result.items[:5]:
            summaries_text += f"  - {item.title} [{item.urgency}]\n"
        if result.has_major_event:
            summaries_text += f"  ** MAJOR EVENT: {result.major_event_title}\n"

    topics_text = ""
    for topic in special_topics:
        topics_text += f"\n- {topic.title} ({topic.region})\n"

    return f"""You are the chief macro strategist synthesizing a daily briefing for the portfolio manager.

Today: {today}

Regional summaries:
{summaries_text}

Special topics identified: {topics_text if topics_text else "None"}

Generate the cross-region synthesis. Return ONLY valid JSON:
{{
  "key_takeaways": [
    "3-5 bullet points, each 1-2 sentences. Actionable. Mention specific asset/region implications. Use the language matching the primary region discussed in each point (Chinese for China-focused points, English for US-focused points)."
  ],
  "risk_alerts": [
    {{
      "title": "...",
      "url": "",
      "source": "synthesis",
      "published_at": "{today}T00:00:00+00:00",
      "summary": "What happened and why it matters",
      "market_implication": "Specific portfolio impact",
      "urgency": "high"
    }}
  ]
}}"""


def _parse_json_response(text: str) -> dict:
    """Extract JSON from Claude response, handling markdown code blocks."""
    # Try direct parse first
    text = text.strip()
    if text.startswith("```"):
        # Remove markdown code block
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON object in the text
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
        raise


class ClaudeSummarizer:
    def __init__(self, config: Settings) -> None:
        self.config = config
        self.client = anthropic.AsyncAnthropic(api_key=config.anthropic_api_key)
        self.model = config.claude_model

    async def _call_claude(self, prompt: str, max_tokens: int = 4096) -> str:
        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        except Exception as e:
            logger.error("Claude API call failed: %s", e)
            raise

    def _group_items_by_region(self, items: list[NewsItem]) -> dict[str, list[NewsItem]]:
        """Group items by region groups for parallel processing."""
        groups: dict[str, list[NewsItem]] = defaultdict(list)
        assigned: set[int] = set()

        for group_name, region_codes in REGION_GROUPS.items():
            for item in items:
                item_id = id(item)
                if item_id in assigned:
                    continue
                if any(r in item.regions for r in region_codes):
                    groups[group_name].append(item)
                    assigned.add(item_id)

        # Assign unmatched items to Global
        for item in items:
            if id(item) not in assigned:
                groups["Global"].append(item)

        return dict(groups)

    async def _summarize_region(
        self, region: str, items: list[NewsItem], today: str
    ) -> RegionalSummaryResult:
        """Summarize a single region's items via Claude API."""
        if not items:
            return RegionalSummaryResult(region=region)

        label = REGION_LABELS.get(region, region)
        prompt = _build_regional_prompt(label, items, today)

        try:
            raw = await self._call_claude(prompt)
            data = _parse_json_response(raw)
            result = RegionalSummaryResult(**data)
            logger.info(
                "Region %s: %d items, major_event=%s",
                region, len(result.items), result.has_major_event,
            )
            return result
        except Exception as e:
            logger.error("Failed to summarize region %s: %s", region, e)
            # Fallback: return raw headlines
            fallback_items = [
                SummarizedItem(
                    title=item.title,
                    url=item.url,
                    source=item.source,
                    published_at=item.published_at,
                    summary=item.raw_text[:200],
                    market_implication="",
                    urgency="medium",
                )
                for item in items[:10]
            ]
            return RegionalSummaryResult(region=region, items=fallback_items)

    async def _generate_special_topic(
        self, event_title: str, event_desc: str, region: str, items: list[NewsItem], today: str
    ) -> SpecialTopic | None:
        """Generate a deep-dive special topic."""
        prompt = _build_special_topic_prompt(event_title, event_desc, region, items, today)
        try:
            raw = await self._call_claude(prompt, max_tokens=2048)
            data = _parse_json_response(raw)
            return SpecialTopic(**data)
        except Exception as e:
            logger.error("Failed to generate special topic '%s': %s", event_title, e)
            return None

    async def _synthesize(
        self,
        regional_results: list[RegionalSummaryResult],
        special_topics: list[SpecialTopic],
        today: str,
    ) -> tuple[list[str], list[SummarizedItem]]:
        """Final synthesis: key takeaways + risk alerts."""
        prompt = _build_synthesis_prompt(regional_results, special_topics, today)
        try:
            raw = await self._call_claude(prompt, max_tokens=2048)
            data = _parse_json_response(raw)
            takeaways = data.get("key_takeaways", [])
            risk_alerts = [SummarizedItem(**ra) for ra in data.get("risk_alerts", [])]
            return takeaways, risk_alerts
        except Exception as e:
            logger.error("Synthesis failed: %s", e)
            return ["Unable to generate synthesis - see regional sections below."], []

    async def summarize(self, items: list[NewsItem]) -> Newsletter:
        """Full summarization pipeline with parallel regional processing."""
        today = date.today().isoformat()
        grouped = self._group_items_by_region(items)

        # Step 1: Parallel regional summarization
        logger.info("Starting parallel regional summarization for %d groups", len(grouped))
        regional_tasks = [
            self._summarize_region(region, region_items, today)
            for region, region_items in grouped.items()
        ]
        regional_results = await asyncio.gather(*regional_tasks, return_exceptions=True)

        # Filter out exceptions
        valid_results: list[RegionalSummaryResult] = []
        for result in regional_results:
            if isinstance(result, Exception):
                logger.error("Regional summarization failed: %s", result)
            else:
                valid_results.append(result)

        # Step 2: Parallel special topic deep-dives (if any major events detected)
        special_topics: list[SpecialTopic] = []
        topic_tasks = []
        for result in valid_results:
            if result.has_major_event and result.major_event_title:
                region_items = grouped.get(result.region, [])
                topic_tasks.append(
                    self._generate_special_topic(
                        result.major_event_title,
                        result.major_event_description,
                        result.region,
                        region_items,
                        today,
                    )
                )

        if topic_tasks:
            logger.info("Generating %d special topic deep-dives", len(topic_tasks))
            topic_results = await asyncio.gather(*topic_tasks, return_exceptions=True)
            for tr in topic_results:
                if isinstance(tr, SpecialTopic):
                    special_topics.append(tr)
                elif isinstance(tr, Exception):
                    logger.error("Special topic generation failed: %s", tr)

        # Step 3: Cross-region synthesis
        logger.info("Running cross-region synthesis")
        key_takeaways, risk_alerts = await self._synthesize(
            valid_results, special_topics, today
        )

        # Build newsletter sections
        sections: list[NewsletterSection] = []
        for result in valid_results:
            if result.items:
                label = REGION_LABELS.get(result.region, result.region)
                sections.append(
                    NewsletterSection(
                        region=result.region,
                        region_label=label,
                        items=result.items,
                    )
                )

        newsletter = Newsletter(
            date=date.today(),
            key_takeaways=key_takeaways,
            risk_alerts=risk_alerts,
            special_topics=special_topics,
            sections=sections,
        )

        logger.info(
            "Newsletter built: %d takeaways, %d risk alerts, %d special topics, %d sections",
            len(newsletter.key_takeaways),
            len(newsletter.risk_alerts),
            len(newsletter.special_topics),
            len(newsletter.sections),
        )
        return newsletter
