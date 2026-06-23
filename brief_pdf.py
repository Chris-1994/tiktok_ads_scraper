#!/usr/bin/env python3
"""CLI entry point for rendering a brief.md into a styled PDF.

Example:
    python brief_pdf.py --md output/gymshark/brief.md
    python brief_pdf.py --md output/gymshark/brief.md --title "Gymshark — New Ad Concepts"

The PDF is a styled A4 document rendered with headless chromium via Playwright.
"""

import argparse
import sys
from pathlib import Path

from tiktok_ads import brief_report


def parse_args():
    parser = argparse.ArgumentParser(
        description="Render a brief.md (ad concepts) into a styled PDF."
    )
    parser.add_argument("--md", required=True, help="Path to the brief.md file.")
    parser.add_argument("--out", default="", help="Output PDF path. Default is the .md path with a .pdf extension.")
    parser.add_argument("--title", default="", help="Optional report title.")
    return parser.parse_args()


def main():
    args = parse_args()
    md_path = args.md
    if not Path(md_path).exists():
        print(f"Markdown not found: {md_path}", file=sys.stderr)
        sys.exit(1)

    title = args.title or "New Ad Concepts"
    out_path = args.out or brief_report.default_brief_pdf_path(md_path)
    written = brief_report.render_brief_pdf(md_path, out_path=out_path, title=title)
    print(f"Done. PDF written to {written}")


if __name__ == "__main__":
    main()
