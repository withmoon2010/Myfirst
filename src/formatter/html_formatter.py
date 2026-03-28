from __future__ import annotations

import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from src.processing.models import Newsletter

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates"


class HTMLFormatter:
    def __init__(self) -> None:
        self.env = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            autoescape=True,
        )

    def render(self, newsletter: Newsletter) -> str:
        template = self.env.get_template("newsletter.html")
        html = template.render(newsletter=newsletter)
        logger.info("Rendered HTML newsletter (%d chars)", len(html))
        return html

    def save(self, html: str, output_dir: str = "output") -> Path:
        from datetime import date

        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"Daily_Macro_Brief_{date.today().isoformat()}.html"
        path.write_text(html, encoding="utf-8")
        logger.info("Saved HTML to %s", path)
        return path
