#!/usr/bin/env python3
"""CLI entry point for building a PDF report from a scraped CSV.

Example:
    python report.py --csv output/tiktok_ads_GB_nike.csv
    python report.py --csv output/tiktok_ads_GB_nike.csv --out report.pdf --title "Nike on TikTok"

The report is a styled A4 PDF rendered with headless chromium via Playwright.
"""

import argparse
import sys
from pathlib import Path

from tiktok_ads import report as report_lib


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build a styled PDF report from a TikTok Ads Library CSV."
    )
    parser.add_argument("--csv", required=True, help="Path to the scraped CSV file.")
    parser.add_argument("--out", default="", help="Output PDF path. Default is the CSV path with a .pdf extension.")
    parser.add_argument("--title", default="", help="Optional report title.")
    return parser.parse_args()


def main():
    args = parse_args()
    csv_path = args.csv
    if not Path(csv_path).exists():
        print(f"CSV not found: {csv_path}", file=sys.stderr)
        sys.exit(1)

    out_path = args.out or report_lib.default_pdf_path(csv_path)
    html_string = report_lib.build_html(csv_path, title=args.title or None)
    print(f"Built report HTML from {csv_path} ({len(html_string)} bytes)")

    written = report_lib.render_pdf(html_string, out_path)
    print(f"Done. PDF written to {written}")


if __name__ == "__main__":
    main()
