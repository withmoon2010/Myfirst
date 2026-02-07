"""
FPI Company Checker - Check if Eternal (Zomato) appears on NSDL FPI lists.

List 1: Utilization of 3% Breach Limit Report (date-specific)
List 2: Apex Parent Company Information (static list)
"""

import json
import subprocess
import urllib.parse
from datetime import datetime

from bs4 import BeautifulSoup
from flask import Flask, jsonify, render_template

app = Flask(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

BREACH_URL = "https://www.fpi.nsdl.co.in/web/Reports/Utilization_Breach_Limit_Report.aspx"
APEX_URL = (
    "https://www.fpi.nsdl.co.in/web/StaticReports/"
    "Monitoring_of_Utilization/Apex%20Parent%20Company%20Information.htm"
)

SEARCH_TERMS = ["eternal", "zomato"]


def curl_get(url, cookie_jar=None):
    """Fetch a URL via curl and return the response body."""
    cmd = [
        "curl", "-s", "-L",
        "-H", f"User-Agent: {USER_AGENT}",
        "-H", "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "--max-time", "30",
    ]
    if cookie_jar:
        cmd += ["-b", cookie_jar, "-c", cookie_jar]
    cmd.append(url)
    result = subprocess.run(cmd, capture_output=True, timeout=60)
    # Try UTF-8 first, fall back to latin-1 for windows-1252 encoded pages
    try:
        return result.stdout.decode("utf-8")
    except UnicodeDecodeError:
        return result.stdout.decode("latin-1")


def curl_post(url, form_data, cookie_jar=None):
    """POST form data via curl and return the response body."""
    cmd = [
        "curl", "-s", "-L",
        "-H", f"User-Agent: {USER_AGENT}",
        "-H", "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "-H", "Content-Type: application/x-www-form-urlencoded",
        "--max-time", "30",
        "-X", "POST",
        "-d", urllib.parse.urlencode(form_data),
    ]
    if cookie_jar:
        cmd += ["-b", cookie_jar, "-c", cookie_jar]
    cmd.append(url)
    result = subprocess.run(cmd, capture_output=True, timeout=60)
    try:
        return result.stdout.decode("utf-8")
    except UnicodeDecodeError:
        return result.stdout.decode("latin-1")


def check_breach_report():
    """
    Check the Utilization of 3% Breach Limit Report for today's date.
    Returns a dict with: found (bool), date (str), details (str), matches (list).
    """
    cookie_jar = "/tmp/nsdl_cookies.txt"

    # Step 1: GET the page to obtain ASP.NET tokens
    html = curl_get(BREACH_URL, cookie_jar=cookie_jar)
    soup = BeautifulSoup(html, "lxml")

    viewstate = soup.find("input", {"name": "__VIEWSTATE"})
    viewstate_gen = soup.find("input", {"name": "__VIEWSTATEGENERATOR"})
    event_validation = soup.find("input", {"name": "__EVENTVALIDATION"})

    today_str = datetime.now().strftime("%d-%b-%Y")

    if not viewstate or not event_validation:
        # The initial GET might already contain today's data, check it
        no_rec_div = soup.find("div", {"id": "dvnorecfond"})
        if no_rec_div:
            label_text = no_rec_div.get_text(strip=True)
            if label_text:
                # Check if the displayed date matches today
                date_input = soup.find("input", {"name": "txtDate"})
                displayed_date = date_input["value"] if date_input else "unknown"
                return {
                    "found": False,
                    "date": displayed_date,
                    "details": label_text,
                    "matches": [],
                    "error": False,
                }
        return {
            "found": False,
            "date": today_str,
            "details": "Could not parse form tokens from the NSDL page.",
            "matches": [],
            "error": True,
        }

    # Step 2: POST with today's date
    form_data = {
        "__EVENTTARGET": "",
        "__EVENTARGUMENT": "",
        "__VIEWSTATE": viewstate["value"],
        "__VIEWSTATEGENERATOR": viewstate_gen["value"] if viewstate_gen else "",
        "__EVENTVALIDATION": event_validation["value"],
        "txtDate": today_str,
        "hdnDate": today_str,
        "btn_View_Rpt": "View Report",
    }

    html2 = curl_post(BREACH_URL, form_data, cookie_jar=cookie_jar)
    soup2 = BeautifulSoup(html2, "lxml")

    # Check for "no breaches" message
    no_rec_div = soup2.find("div", {"id": "dvnorecfond"})
    if no_rec_div:
        label_text = no_rec_div.get_text(strip=True)
        if label_text:
            return {
                "found": False,
                "date": today_str,
                "details": label_text,
                "matches": [],
                "error": False,
            }

    # If there is a data table, search for Eternal/Zomato
    page_text = soup2.get_text().lower()
    matches = []
    for term in SEARCH_TERMS:
        if term in page_text:
            matches.append(term)

    # Also try to extract table rows for more detail
    table_details = []
    tables = soup2.find_all("table")
    for table in tables:
        for row in table.find_all("tr"):
            row_text = row.get_text().lower()
            for term in SEARCH_TERMS:
                if term in row_text:
                    cells = [td.get_text(strip=True) for td in row.find_all("td")]
                    table_details.append(cells)

    if matches:
        return {
            "found": True,
            "date": today_str,
            "details": f"Found on breach list: {', '.join(matches)}",
            "matches": matches,
            "table_rows": table_details,
            "error": False,
        }

    return {
        "found": False,
        "date": today_str,
        "details": "Eternal/Zomato not found in today's breach report. (Report may contain other companies.)",
        "matches": [],
        "error": False,
    }


def check_apex_parent_list():
    """
    Check the Apex Parent Company Information list for Eternal/Zomato.
    Returns a dict with: found (bool), details (str), matches (list of dicts).
    """
    html = curl_get(APEX_URL)
    soup = BeautifulSoup(html, "lxml")

    matches = []
    table = soup.find("table")
    if not table:
        return {
            "found": False,
            "details": "Could not find table on Apex Parent Company page.",
            "matches": [],
            "error": True,
        }

    rows = table.find_all("tr")
    for row in rows[1:]:  # skip header
        cells = row.find_all("td")
        if len(cells) >= 3:
            ownership_group = " ".join(cells[0].get_text(strip=True).split())
            apex_company = " ".join(cells[1].get_text(strip=True).split())
            apex_isin = cells[2].get_text(strip=True)

            combined = f"{ownership_group} {apex_company}".lower()
            for term in SEARCH_TERMS:
                if term in combined:
                    matches.append(
                        {
                            "ownership_group": ownership_group,
                            "apex_company": apex_company,
                            "isin": apex_isin,
                            "matched_term": term,
                        }
                    )

    if matches:
        return {
            "found": True,
            "details": f"Found {len(matches)} match(es) on Apex Parent Company list.",
            "matches": matches,
            "error": False,
        }

    return {
        "found": False,
        "details": "Company not found on Apex Parent Company list.",
        "matches": [],
        "error": False,
    }


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/check", methods=["POST"])
def check():
    results = {}

    # Check List 1: Breach Limit Report
    try:
        results["breach_report"] = check_breach_report()
    except Exception as e:
        results["breach_report"] = {
            "found": False,
            "date": datetime.now().strftime("%d-%b-%Y"),
            "details": f"Error fetching breach report: {e}",
            "matches": [],
            "error": True,
        }

    # Check List 2: Apex Parent Company
    try:
        results["apex_parent"] = check_apex_parent_list()
    except Exception as e:
        results["apex_parent"] = {
            "found": False,
            "details": f"Error fetching apex parent list: {e}",
            "matches": [],
            "error": True,
        }

    return jsonify(results)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
