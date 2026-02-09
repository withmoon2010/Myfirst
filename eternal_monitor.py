#!/usr/bin/env python3
"""Monitor Eternal (Zomato) appearance on NSDL lists and notify at 4pm NY time."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import smtplib
from dataclasses import dataclass
from datetime import datetime, timedelta
from email.message import EmailMessage
from typing import Iterable, Optional, Tuple

import pytz
import requests
from bs4 import BeautifulSoup

REPORT_URL = "https://www.fpi.nsdl.co.in/web/Reports/Utilization_Breach_Limit_Report.aspx"
APEX_URL = (
    "https://www.fpi.nsdl.co.in/web/StaticReports/Monitoring_of_Utilization/"
    "Apex%20Parent%20Company%20Information.htm"
)

DEFAULT_DATE_FORMAT = "%d-%m-%Y"
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}

SEARCH_TERMS = ["eternal", "zomato"]
DEFAULT_EMAIL_RECIPIENT = "xiaopeng.zhao@tengyuepartners.com"


@dataclass
class ReportResult:
    report_date: str
    breach_found: bool
    apex_found: bool

    @property
    def breach_pass(self) -> bool:
        return not self.breach_found

    @property
    def apex_pass(self) -> bool:
        return self.apex_found

    @property
    def overall_pass(self) -> bool:
        return self.breach_pass and self.apex_pass

    def summary_lines(self) -> list[str]:
        status = "PASS" if self.overall_pass else "FAIL"
        return [
            f"Eternal (Zomato) NSDL check for {self.report_date}: {status}",
            f"3% limit list: {'NOT FOUND' if self.breach_pass else 'FOUND'}",
            f"Apex company list: {'FOUND' if self.apex_pass else 'NOT FOUND'}",
        ]


class FetchError(RuntimeError):
    pass


def fetch_html(url: str, session: requests.Session) -> str:
    try:
        response = session.get(url, headers=DEFAULT_HEADERS, timeout=30)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise FetchError(f"Failed to fetch {url}: {exc}") from exc
    return response.text


def get_report_date(now: Optional[datetime], override: Optional[str]) -> Tuple[str, datetime]:
    tz = pytz.timezone("America/New_York")
    if now is None:
        now = datetime.now(tz)
    else:
        now = now.astimezone(tz)

    if override:
        date_obj = datetime.strptime(override, "%Y-%m-%d").date()
        return override, datetime.combine(date_obj, datetime.min.time(), tz)

    date_string = now.strftime("%Y-%m-%d")
    return date_string, now


def extract_report_form(html: str) -> dict[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    form = soup.find("form")
    if not form:
        raise FetchError("Unable to find report form")

    payload = {}
    for field in form.find_all("input"):
        name = field.get("name")
        if not name:
            continue
        payload[name] = field.get("value", "")
    return payload


def submit_report(session: requests.Session, report_date: str, date_format: str) -> str:
    initial_html = fetch_html(REPORT_URL, session)
    payload = extract_report_form(initial_html)

    formatted_date = datetime.strptime(report_date, "%Y-%m-%d").strftime(date_format)

    date_field_candidates = [
        name
        for name in payload.keys()
        if "date" in name.lower() and "txt" in name.lower()
    ]

    if not date_field_candidates:
        raise FetchError("Unable to locate report date field")

    date_field = date_field_candidates[0]
    payload[date_field] = formatted_date

    payload.setdefault("__EVENTTARGET", "")
    payload.setdefault("__EVENTARGUMENT", "")

    return post_with_payload(session, payload)


def post_with_payload(session: requests.Session, payload: dict[str, str]) -> str:
    try:
        response = session.post(
            REPORT_URL,
            headers=DEFAULT_HEADERS,
            data=payload,
            timeout=30,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise FetchError(f"Failed to submit report form: {exc}") from exc
    return response.text


def search_terms_in_text(text: str, terms: Iterable[str]) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in terms)


def parse_breach_report(html: str) -> bool:
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)
    return search_terms_in_text(text, SEARCH_TERMS)


def parse_apex_list(html: str) -> bool:
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)
    return search_terms_in_text(text, SEARCH_TERMS)


def build_result(session: requests.Session, report_date: str, date_format: str) -> ReportResult:
    breach_html = submit_report(session, report_date, date_format)
    breach_found = parse_breach_report(breach_html)

    apex_html = fetch_html(APEX_URL, session)
    apex_found = parse_apex_list(apex_html)

    return ReportResult(report_date=report_date, breach_found=breach_found, apex_found=apex_found)


def send_webhook(message: str, webhook_url: str, session: requests.Session) -> None:
    payload = {"text": message}
    try:
        response = session.post(
            webhook_url,
            headers={"Content-Type": "application/json", **DEFAULT_HEADERS},
            data=json.dumps(payload),
            timeout=15,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise FetchError(f"Failed to send webhook message: {exc}") from exc


def send_email(message: str, recipient: str) -> None:
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USERNAME")
    password = os.getenv("SMTP_PASSWORD")
    sender = os.getenv("EMAIL_SENDER", username)

    if not host or not username or not password or not sender:
        raise FetchError(
            "Missing SMTP configuration. Set SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD, and EMAIL_SENDER."
        )

    email_message = EmailMessage()
    email_message["Subject"] = "Eternal (Zomato) NSDL check result"
    email_message["From"] = sender
    email_message["To"] = recipient
    email_message.set_content(message)

    try:
        with smtplib.SMTP(host=host, port=port, timeout=20) as smtp:
            smtp.starttls()
            smtp.login(username, password)
            smtp.send_message(email_message)
    except smtplib.SMTPException as exc:
        raise FetchError(f"Failed to send email: {exc}") from exc


def notify(
    result: ReportResult,
    webhook_url: Optional[str],
    email_recipient: Optional[str],
    session: requests.Session,
) -> None:
    message = "\n".join(result.summary_lines())
    if email_recipient:
        send_email(message, email_recipient)
        return

    if webhook_url:
        send_webhook(message, webhook_url, session)
        return

    print(message)


def wait_until(target: datetime) -> None:
    while True:
        now = datetime.now(pytz.timezone("America/New_York"))
        if now >= target:
            return
        sleep_seconds = min((target - now).total_seconds(), 60)
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)


def next_run_time(reference: datetime) -> datetime:
    tz = pytz.timezone("America/New_York")
    reference = reference.astimezone(tz)
    target = reference.replace(hour=16, minute=0, second=0, microsecond=0)
    if reference >= target:
        target += timedelta(days=1)
    return target


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check Eternal (Zomato) NSDL listings")
    parser.add_argument(
        "--run-once",
        action="store_true",
        help="Run a single check immediately",
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Run continuously, checking every day at 4pm New York time",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv)
    if not args.run_once and not args.daemon:
        print("Specify --run-once or --daemon", file=sys.stderr)
        return 2

    webhook_url = os.getenv("WEBHOOK_URL")
    email_recipient = os.getenv("EMAIL_RECIPIENT", DEFAULT_EMAIL_RECIPIENT)
    report_date_override = os.getenv("REPORT_DATE")
    date_format = os.getenv("REPORT_DATE_FORMAT", DEFAULT_DATE_FORMAT)

    session = requests.Session()

    def run_once() -> None:
        report_date, _ = get_report_date(None, report_date_override)
        result = build_result(session, report_date, date_format)
        notify(result, webhook_url, email_recipient, session)

    if args.run_once:
        run_once()
        return 0

    while True:
        now = datetime.now(pytz.timezone("America/New_York"))
        target = next_run_time(now)
        wait_until(target)
        run_once()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
