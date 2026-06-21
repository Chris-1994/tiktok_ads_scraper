"""Build a styled HTML report from a scraped CSV and render it to PDF.

The HTML building (build_html) is pure and needs no network or browser, so it
can be unit tested on its own. PDF rendering uses headless chromium through
Playwright, because page.pdf only works in headless chromium.
"""

import csv
import html
import os
import re
import tempfile
from datetime import datetime


# Reach buckets ordered from smallest to largest audience. The index doubles as
# a sort key (larger reach sorts first when we reverse).
REACH_ORDER = [
    "0-1K",
    "1K-10K",
    "10K-100K",
    "100K-700K",
    "700K-800K",
]

# Badge colors keyed by bucket. Unknown buckets fall back to a neutral grey.
REACH_COLORS = {
    "0-1K": "#9aa0a6",
    "1K-10K": "#5b8def",
    "10K-100K": "#7e57c2",
    "100K-700K": "#9c3fc4",
    "700K-800K": "#c2185b",
}

NEUTRAL_BADGE = "#9aa0a6"


def read_rows(csv_path):
    """Read all rows from the CSV into a list of dicts."""
    with open(csv_path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def reach_bucket(value):
    """Normalize a unique_users cell to one of the known reach buckets.

    The Ads Library shows ranges such as "1K-10K". Returns the matched bucket
    string, or the original value when nothing matches.
    """
    text = (value or "").strip()
    for bucket in REACH_ORDER:
        if bucket.lower() in text.lower():
            return bucket
    return text


def reach_sort_key(value):
    """Return a numeric sort key so larger reach buckets sort first."""
    bucket = reach_bucket(value)
    if bucket in REACH_ORDER:
        return REACH_ORDER.index(bucket)
    return -1


def sort_rows(rows):
    """Sort rows by reach bucket, largest audience first."""
    return sorted(rows, key=lambda r: reach_sort_key(r.get("unique_users", "")), reverse=True)


def derive_meta_from_filename(csv_path):
    """Pull region and brand hints out of an output filename.

    Expects names like tiktok_ads_GB_nike.csv. Returns (region, brand) where
    either may be an empty string when not derivable.
    """
    name = os.path.splitext(os.path.basename(csv_path))[0]
    match = re.match(r"tiktok_ads_([A-Za-z]{2})_(.+)", name)
    if not match:
        return "", ""
    region = match.group(1).upper()
    brand = match.group(2).replace("-", " ").replace("_", " ").strip()
    if brand.lower() == "all":
        brand = ""
    return region, brand


def reach_split(rows):
    """Return a dict mapping each present reach bucket to its row count."""
    counts = {}
    for row in rows:
        bucket = reach_bucket(row.get("unique_users", ""))
        counts[bucket] = counts.get(bucket, 0) + 1
    return counts


def _badge(value):
    """Return an HTML span styled as a colored reach badge."""
    bucket = reach_bucket(value)
    color = REACH_COLORS.get(bucket, NEUTRAL_BADGE)
    label = html.escape(value or "-")
    return f'<span class="badge" style="background:{color}">{label}</span>'


def _row_html(row, detailed):
    """Render a single results table row."""
    advertiser = html.escape(row.get("advertiser") or "-")
    first_shown = html.escape(row.get("first_shown") or "-")
    last_shown = html.escape(row.get("last_shown") or "-")
    detail_url = html.escape(row.get("detail_url") or "")
    link = f'<a href="{detail_url}">view</a>' if detail_url else "-"
    cells = [
        f"<td>{advertiser}</td>",
        f"<td>{_badge(row.get('unique_users'))}</td>",
        f"<td>{first_shown}</td>",
        f"<td>{last_shown}</td>",
    ]
    if detailed:
        caption = html.escape((row.get("caption_text") or "-")[:120])
        cells.append(f'<td class="caption">{caption}</td>')
    cells.append(f"<td>{link}</td>")
    return "<tr>" + "".join(cells) + "</tr>"


def build_html(csv_path, title=None):
    """Build the full HTML report as a string. No network or browser needed."""
    rows = sort_rows(read_rows(csv_path))
    detailed = any("caption_text" in (row or {}) for row in rows)
    region, brand = derive_meta_from_filename(csv_path)
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")

    if not title:
        scope = brand if brand else "all advertisers"
        title = f"TikTok Ads Library report: {scope}"

    split = reach_split(rows)
    split_text = ", ".join(
        f"{html.escape(bucket)}: {count}"
        for bucket, count in sorted(split.items(), key=lambda kv: reach_sort_key(kv[0]), reverse=True)
    ) or "no rows"

    meta_items = [
        ("Source", "TikTok Ads Library (library.tiktok.com)"),
        ("Region", html.escape(region) if region else "not derivable"),
        ("Brand", html.escape(brand) if brand else "all advertisers"),
        ("Ads in report", str(len(rows))),
        ("Reach split", html.escape(split_text)),
        ("Generated", html.escape(generated)),
    ]
    meta_html = "".join(
        f'<div class="meta-item"><span class="meta-label">{label}</span>'
        f'<span class="meta-value">{value}</span></div>'
        for label, value in meta_items
    )

    headers = ["Advertiser", "Reach", "First shown", "Last shown"]
    if detailed:
        headers.append("Caption")
    headers.append("Detail")
    head_html = "".join(f"<th>{html.escape(h)}</th>" for h in headers)
    body_html = "".join(_row_html(row, detailed) for row in rows) or (
        f'<tr><td colspan="{len(headers)}">No ads found in this CSV.</td></tr>'
    )

    safe_title = html.escape(title)
    return _PAGE_TEMPLATE.format(
        title=safe_title,
        meta=meta_html,
        head=head_html,
        body=body_html,
    )


def render_pdf(html_string, out_path):
    """Render an HTML string to a PDF file using headless chromium.

    Writes the HTML to a temporary file, opens it with a file:// URL, and saves
    an A4 PDF. Imports Playwright lazily so build_html stays usable without it.
    """
    from playwright.sync_api import sync_playwright

    out_path = os.path.abspath(out_path)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".html", delete=False, encoding="utf-8"
    )
    try:
        tmp.write(html_string)
        tmp.close()
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto("file://" + tmp.name, wait_until="networkidle")
            page.pdf(path=out_path, format="A4", print_background=True)
            browser.close()
    finally:
        if os.path.exists(tmp.name):
            os.remove(tmp.name)
    return out_path


def default_pdf_path(csv_path):
    """Return the CSV path with a .pdf extension."""
    base, _ = os.path.splitext(csv_path)
    return base + ".pdf"


_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
  :root {{
    --accent: #7e57c2;
    --accent-dark: #2a2140;
    --ink: #1f2330;
    --muted: #6b7280;
    --line: #e6e6ef;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
      Helvetica, Arial, "Apple Color Emoji", "Segoe UI Emoji", sans-serif;
    color: var(--ink);
    margin: 0;
    padding: 0 0 40px;
    font-size: 13px;
    line-height: 1.5;
  }}
  .band {{
    background: linear-gradient(120deg, var(--accent-dark), var(--accent));
    color: #fff;
    padding: 28px 36px;
  }}
  .band h1 {{ margin: 0; font-size: 22px; font-weight: 700; }}
  .band p {{ margin: 6px 0 0; opacity: 0.85; font-size: 12px; }}
  .wrap {{ padding: 0 36px; }}
  .meta {{
    display: flex;
    flex-wrap: wrap;
    gap: 14px 28px;
    margin: 24px 0;
    padding: 18px 20px;
    border: 1px solid var(--line);
    border-radius: 10px;
    background: #fafafe;
  }}
  .meta-item {{ display: flex; flex-direction: column; }}
  .meta-label {{
    font-size: 10px; text-transform: uppercase; letter-spacing: 0.06em;
    color: var(--muted);
  }}
  .meta-value {{ font-size: 13px; font-weight: 600; margin-top: 2px; }}
  .caveats {{
    border-left: 3px solid var(--accent);
    background: #f6f3fc;
    padding: 12px 16px;
    border-radius: 0 8px 8px 0;
    font-size: 11.5px;
    color: #4a4458;
    margin: 0 0 24px;
  }}
  .caveats strong {{ color: var(--ink); }}
  table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
  th {{
    text-align: left;
    background: var(--accent-dark);
    color: #fff;
    padding: 9px 10px;
    font-weight: 600;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.03em;
  }}
  td {{ padding: 8px 10px; border-bottom: 1px solid var(--line); vertical-align: top; }}
  tbody tr:nth-child(even) {{ background: #faf9fd; }}
  td.caption {{ color: #4a4458; max-width: 220px; }}
  a {{ color: var(--accent); text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  .badge {{
    display: inline-block;
    color: #fff;
    padding: 2px 9px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 600;
    white-space: nowrap;
  }}
  .foot {{ margin-top: 28px; color: var(--muted); font-size: 10.5px; }}
</style>
</head>
<body>
  <div class="band">
    <h1>{title}</h1>
    <p>Public EU/EEA ad transparency data from the TikTok Ads Library</p>
  </div>
  <div class="wrap">
    <div class="meta">{meta}</div>
    <div class="caveats">
      <strong>Read this first.</strong> Reach is reported only as broad buckets,
      not exact numbers. TikTok does not publish ad spend or click-through rate,
      so neither appears here. Keyword search is fuzzy, so some rows may be
      unrelated to the advertiser you searched for. Treat this as directional
      competitive intelligence, not precise metrics.
    </div>
    <table>
      <thead><tr>{head}</tr></thead>
      <tbody>{body}</tbody>
    </table>
    <p class="foot">
      Generated by tiktok_ads_scraper. Data is sourced from the public TikTok
      Ads Library, an EU/EEA Digital Services Act transparency tool.
    </p>
  </div>
</body>
</html>
"""
