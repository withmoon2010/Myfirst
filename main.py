#!/usr/bin/env python3
"""Daily Macro Brief - News newsletter for portfolio managers.

Usage:
    python main.py                  # Full run: collect, summarize, send email
    python main.py --dry-run        # Collect and summarize, save to output/ (no email)
    python main.py --preview        # Dry run + open HTML in browser
    python main.py --since 48       # Override lookback to 48 hours
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import webbrowser
from datetime import datetime, timedelta, timezone

from src.collectors.newsapi_collector import NewsAPICollector
from src.collectors.rss_collector import RSSCollector
from src.config import Settings
from src.delivery.email_sender import EmailSender
from src.formatter.docx_formatter import DocxFormatter
from src.formatter.html_formatter import HTMLFormatter
from src.processing.deduplicator import Deduplicator
from src.processing.freshness_validator import FreshnessValidator
from src.processing.relevance_filter import RelevanceFilter
from src.summarizer.claude_summarizer import ClaudeSummarizer

logger = logging.getLogger("daily_macro_brief")


def setup_logging(level: str = "INFO") -> None:
    from pathlib import Path

    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_dir / "newsletter.log", encoding="utf-8"),
        ],
    )


async def run_newsletter(
    dry_run: bool = False,
    preview: bool = False,
    since_hours: int | None = None,
) -> None:
    config = Settings()
    setup_logging(config.log_level)

    lookback = since_hours or config.news_lookback_hours
    since = datetime.now(timezone.utc) - timedelta(hours=lookback)
    logger.info("Starting Daily Macro Brief (lookback=%dh, since=%s)", lookback, since.isoformat())

    # ── Step 1: Collect from all sources concurrently ──
    logger.info("Step 1: Collecting news...")
    collectors = [RSSCollector(config)]
    if config.newsapi_enabled and config.newsapi_key:
        collectors.append(NewsAPICollector(config))

    results = await asyncio.gather(
        *[c.collect(since) for c in collectors],
        return_exceptions=True,
    )

    all_items = []
    for result in results:
        if isinstance(result, Exception):
            logger.error("Collector failed: %s", result)
        else:
            all_items.extend(result)

    logger.info("Collected %d raw items from %d sources", len(all_items), len(collectors))

    if not all_items:
        logger.warning("No items collected, aborting")
        return

    # ── Step 2: Freshness validation ──
    logger.info("Step 2: Validating freshness...")
    validator = FreshnessValidator(lookback_hours=lookback)
    fresh_items = validator.validate(all_items)

    # ── Step 3: Deduplication ──
    logger.info("Step 3: Deduplicating...")
    deduplicator = Deduplicator()
    unique_items = deduplicator.deduplicate(fresh_items)

    # ── Step 4: Relevance filtering ──
    logger.info("Step 4: Filtering by relevance...")
    relevance_filter = RelevanceFilter(config)
    filtered_items = relevance_filter.filter(unique_items)

    if not filtered_items:
        logger.warning("No relevant items after filtering, aborting")
        return

    # ── Step 5: AI Summarization (parallel by region) ──
    logger.info("Step 5: Summarizing with Claude (parallel by region)...")
    summarizer = ClaudeSummarizer(config)
    newsletter = await summarizer.summarize(filtered_items)

    # ── Step 6: Format outputs ──
    logger.info("Step 6: Formatting outputs...")
    html_formatter = HTMLFormatter()
    html = html_formatter.render(newsletter)

    docx_formatter = DocxFormatter()
    doc = docx_formatter.render(newsletter)

    if dry_run or preview:
        html_path = html_formatter.save(html)
        docx_path = docx_formatter.save(doc)
        logger.info("Dry run: saved HTML to %s, DOCX to %s", html_path, docx_path)

        if preview:
            webbrowser.open(f"file://{html_path.resolve()}")
            logger.info("Opened preview in browser")
        return

    # ── Step 7: Save DOCX and send email ──
    logger.info("Step 7: Sending email...")
    docx_path = docx_formatter.save(doc)

    sender = EmailSender(config)
    first_takeaway = newsletter.key_takeaways[0][:60] if newsletter.key_takeaways else ""
    await sender.send(
        html=html,
        newsletter_date=newsletter.date,
        docx_path=docx_path,
        subject_suffix=first_takeaway,
    )

    logger.info("Daily Macro Brief completed successfully!")


def main() -> None:
    parser = argparse.ArgumentParser(description="Daily Macro Brief Newsletter")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Collect and summarize but don't send email; save to output/",
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Dry run + open HTML in browser",
    )
    parser.add_argument(
        "--since",
        type=int,
        default=None,
        help="Override lookback period in hours (default: 24)",
    )
    args = parser.parse_args()

    asyncio.run(
        run_newsletter(
            dry_run=args.dry_run or args.preview,
            preview=args.preview,
            since_hours=args.since,
        )
    )


if __name__ == "__main__":
    main()
