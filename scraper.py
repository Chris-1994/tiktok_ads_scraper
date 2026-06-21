#!/usr/bin/env python3
"""CLI entry point for scraping the TikTok Ads Library.

Example:
    python scraper.py --brand nike --region GB --days 30 --limit 50
    python scraper.py --region FR --detailed --limit 20

Output is written incrementally to a CSV so a run can be resumed safely.
"""

import argparse
from pathlib import Path

from tiktok_ads import extract, storage
from tiktok_ads.browser import (
    AdsLibraryBrowser,
    build_list_url,
    collect_list_rows,
    time_window_ms,
)

ROOT = Path(__file__).resolve().parent


def parse_args():
    parser = argparse.ArgumentParser(
        description="Scrape ads from the TikTok Ads Library (EU/EEA transparency data)."
    )
    parser.add_argument("--brand", default="", help="Advertiser keyword. Omit to scrape all advertisers.")
    parser.add_argument("--region", default="GB", help="ISO country code, EU/EEA only (e.g. GB, FR, DE, AT).")
    parser.add_argument("--days", type=int, default=30, help="Look-back window in days.")
    parser.add_argument("--limit", type=int, default=50, help="Target number of ads to collect.")
    parser.add_argument("--detailed", action="store_true", help="Visit each ad detail page for richer fields.")
    parser.add_argument("--headful", action="store_true", help="Show the browser window (default is headless).")
    parser.add_argument("--out", default="", help="Output CSV path. Default is output/tiktok_ads_<REGION>_<brand-or-all>.csv")
    return parser.parse_args()


def default_out_path(region, brand):
    """Build the default output CSV path under the local output folder."""
    slug = brand.strip().lower().replace(" ", "-") if brand.strip() else "all"
    return str(ROOT / "output" / f"tiktok_ads_{region.upper()}_{slug}.csv")


def enrich_row(row, brand, browser):
    """Visit the detail page for a row and merge in the richer fields."""
    detail = browser.extract_detail(row["detail_url"])
    row.update(detail)
    row["active_for_days"] = extract.parse_active_days(
        row.get("first_shown", ""), row.get("last_shown", "")
    )
    row["mentions_brand"] = extract.mentions_brand(
        brand, row.get("advertiser", ""), row.get("caption_text", "")
    )
    return row


def main():
    args = parse_args()
    out_path = args.out or default_out_path(args.region, args.brand)

    existing_ids = storage.load_existing_ids(out_path)
    if existing_ids:
        print(f"Resuming: {len(existing_ids)} ads already saved in {out_path}")

    start_ms, end_ms = time_window_ms(args.days)
    url = build_list_url(args.region, start_ms, end_ms, args.brand)
    scope = args.brand if args.brand else "all advertisers"
    print(f"Scraping TikTok Ads Library: region={args.region}, brand={scope}, days={args.days}, limit={args.limit}")
    print(f"URL: {url}")

    fieldnames = storage.columns_for(args.detailed)
    saved = 0

    browser = AdsLibraryBrowser(headful=args.headful)
    try:
        browser.__enter__()
        browser.open_list(url)
        rows = collect_list_rows(browser, args.limit)
        print(f"Found {len(rows)} ads in the list. Saving new ones to {out_path}")

        with storage.CsvWriter(out_path, fieldnames) as writer:
            for row in rows:
                if saved >= args.limit:
                    break
                ad_id = row.get("ad_id")
                if not ad_id or ad_id in existing_ids:
                    continue
                if args.detailed:
                    enrich_row(row, args.brand, browser)
                writer.write_row(row)
                existing_ids.add(ad_id)
                saved += 1
                print(f"  [{saved}] {ad_id} {row.get('advertiser', '')[:40]} ({row.get('unique_users', '')})")
    finally:
        browser.close()

    print(f"Done. Saved {saved} new ads. Output: {out_path}")


if __name__ == "__main__":
    main()
