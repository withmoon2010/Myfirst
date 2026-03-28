from __future__ import annotations

import logging
from datetime import date
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import aiosmtplib

from src.config import Settings

logger = logging.getLogger(__name__)


def _html_to_plaintext(html: str) -> str:
    """Simple HTML to plaintext conversion."""
    import re

    text = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL)
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = re.sub(r"</p>", "\n\n", text)
    text = re.sub(r"</tr>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"&middot;", "·", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&#\d+;", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


class EmailSender:
    def __init__(self, config: Settings) -> None:
        self.config = config

    async def send(
        self,
        html: str,
        newsletter_date: date,
        docx_path: Path | None = None,
        subject_suffix: str = "",
    ) -> None:
        if not self.config.smtp_user or not self.config.recipient_list:
            logger.warning("SMTP not configured or no recipients, skipping email send")
            return

        subject = f"[Daily Macro Brief] {newsletter_date.strftime('%Y-%m-%d')}"
        if subject_suffix:
            subject += f" - {subject_suffix}"

        for recipient in self.config.recipient_list:
            msg = MIMEMultipart("mixed")
            msg["Subject"] = subject
            msg["From"] = f"{self.config.sender_name} <{self.config.sender_email}>"
            msg["To"] = recipient
            msg["Reply-To"] = self.config.sender_email

            # HTML + plaintext alternative
            alt = MIMEMultipart("alternative")
            plaintext = _html_to_plaintext(html)
            alt.attach(MIMEText(plaintext, "plain", "utf-8"))
            alt.attach(MIMEText(html, "html", "utf-8"))
            msg.attach(alt)

            # Attach DOCX if available
            if docx_path and docx_path.exists():
                with open(docx_path, "rb") as f:
                    docx_attachment = MIMEApplication(
                        f.read(),
                        _subtype="vnd.openxmlformats-officedocument.wordprocessingml.document",
                    )
                    docx_attachment.add_header(
                        "Content-Disposition",
                        "attachment",
                        filename=docx_path.name,
                    )
                    msg.attach(docx_attachment)

            try:
                await aiosmtplib.send(
                    msg,
                    hostname=self.config.smtp_host,
                    port=self.config.smtp_port,
                    username=self.config.smtp_user,
                    password=self.config.smtp_password,
                    start_tls=True,
                )
                logger.info("Email sent to %s", recipient)
            except Exception as e:
                logger.error("Failed to send email to %s: %s", recipient, e)
                raise
