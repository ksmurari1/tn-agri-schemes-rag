from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from bs4 import BeautifulSoup

GOS_URL = "https://www.tnagrisnet.tn.gov.in/home/gos"
USER_AGENT = "TamilNaduAgriSchemesRAG/0.1 (source catalogue refresh)"


def normalize_space(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def canonical_url(url: str | None) -> str:
    if not url:
        return ""
    return url.strip().rstrip(")").replace("&amp;", "&")


def _rows_from_browser(url: str, timeout_ms: int = 45000) -> list[dict]:
    """Use a real browser for the DataTables-driven GO page."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        page.wait_for_timeout(1800)
        # The same DataTables approach used manually, but executed reproducibly.
        result = page.evaluate("""() => {
          if (!window.jQuery || !window.jQuery.fn || !window.jQuery.fn.DataTable) {
            return {error: 'jQuery DataTables was not detected on the page'};
          }
          const tables = [...document.querySelectorAll('table')];
          const table = tables.find(t => window.jQuery.fn.DataTable.isDataTable(t));
          if (!table) return {error: 'No initialized DataTables table was detected'};
          const dt = window.jQuery(table).DataTable();
          const rows = dt.rows({ search: 'none' }).nodes().toArray().map(tr => {
            const c = [...tr.cells].map(x => x.innerText.trim().replace(/\\s+/g, ' '));
            const a = tr.querySelector('a[href]');
            return {
              sno: c[0] || '',
              dept: c[1] || '',
              go_no: c[2] || '',
              year: c[3] || '',
              date: c[4] || '',
              subject: c[5] || '',
              section: c[6] || '',
              size: c[7] || '',
              url: a ? a.href : null
            };
          }).filter(r => r.url || r.subject || r.go_no);
          return {rows, count: rows.length};
        }""")
        browser.close()
    if result.get("error"):
        raise RuntimeError(result["error"])
    return result["rows"]


def _rows_from_html(url: str, timeout: int = 25) -> list[dict]:
    """Fallback for pages whose table is present in server-rendered HTML."""
    response = requests.get(
        url,
        timeout=timeout,
        headers={"User-Agent": USER_AGENT},
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    results = []
    for table in soup.find_all("table"):
        for tr in table.find_all("tr"):
            cells = [
                normalize_space(td.get_text(" ", strip=True))
                for td in tr.find_all(["td", "th"])
            ]
            if len(cells) < 7:
                continue
            a = tr.find("a", href=True)
            href = a["href"] if a else None
            if href and href.startswith("/"):
                href = requests.compat.urljoin(url, href)
            if not href and not any(cells):
                continue
            results.append(
                {
                    "sno": cells[0] if len(cells) > 0 else "",
                    "dept": cells[1] if len(cells) > 1 else "",
                    "go_no": cells[2] if len(cells) > 2 else "",
                    "year": cells[3] if len(cells) > 3 else "",
                    "date": cells[4] if len(cells) > 4 else "",
                    "subject": cells[5] if len(cells) > 5 else "",
                    "section": cells[6] if len(cells) > 6 else "",
                    "size": cells[7] if len(cells) > 7 else "",
                    "url": href,
                }
            )
    return results


def fetch_gos_catalogue(url: str = GOS_URL) -> tuple[list[dict], str]:
    """Fetch GO rows, preferring Playwright and falling back to static HTML."""
    try:
        rows = _rows_from_browser(url)
        method = "Playwright/DataTables"
    except Exception as browser_error:
        try:
            rows = _rows_from_html(url)
            method = "Static HTML fallback"
        except Exception as html_error:
            raise RuntimeError(
                "Could not refresh the Government Orders page. "
                f"Browser extraction: {browser_error}; HTML extraction: {html_error}. "
                "Check site availability and install the Playwright Chromium browser."
            ) from html_error

    # Normalize fields and de-duplicate by canonical PDF URL, preserving the first row.
    cleaned, seen_urls = [], set()
    for i, raw in enumerate(rows, start=1):
        row = {
            "sno": normalize_space(raw.get("sno")) or str(i),
            "dept": normalize_space(raw.get("dept")),
            "go_no": normalize_space(raw.get("go_no")),
            "year": normalize_space(raw.get("year")),
            "date": normalize_space(raw.get("date")),
            "subject": normalize_space(raw.get("subject")),
            "section": normalize_space(raw.get("section")),
            "size": normalize_space(raw.get("size")),
            "url": canonical_url(raw.get("url")) or None,
        }
        key = row["url"] or "|".join(
            [row["dept"], row["go_no"], row["date"], row["subject"]]
        )
        if key in seen_urls:
            continue
        seen_urls.add(key)
        cleaned.append(row)
    return cleaned, method


def save_catalogue(
    rows: list[dict], json_path: str | Path, csv_path: str | Path
) -> None:
    json_path, csv_path = Path(json_path), Path(csv_path)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).isoformat()
    payload = {
        "refreshed_at_utc": timestamp,
        "source_url": GOS_URL,
        "record_count": len(rows),
        "records": rows,
    }
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    pd.DataFrame(rows).to_csv(csv_path, index=False, encoding="utf-8-sig")


def load_catalogue(path: str | Path) -> list[dict]:
    path = Path(path)
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    # Support both the original manually exported array and the app's metadata wrapper.
    return data if isinstance(data, list) else data.get("records", [])
