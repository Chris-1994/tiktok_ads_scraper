#!/usr/bin/env python3
"""CLI for scraping a competitor's TikTok ads, ranking winners, and pulling video.

Examples:
    # resolve and cache a brand's business id (optional; scraping does this too)
    python scraper.py --resolve --brand "gymshark" --region GB

    # scrape the brand's own account, rank, keep the top 20, download + process
    python scraper.py --brand "gymshark" --region GB --days 30 --top 20 --download

Output is written under output/<brand>/ so a run can be resumed safely.
"""

import argparse
from pathlib import Path

from tiktok_ads import advertiser, download, extract, media, ranking, storage
from tiktok_ads.browser import (
    AdsLibraryBrowser,
    build_list_url,
    collect_list_rows,
    time_window_ms,
)

ROOT = Path(__file__).resolve().parent
OUTPUT_ROOT = ROOT / "output"
BRANDS_PATH = str(ROOT / "brands.json")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Scrape, rank, and download a competitor's TikTok ads."
    )
    parser.add_argument("--brand", default="", help="Brand name to target.")
    parser.add_argument("--region", default="GB", help="ISO country code, EU/EEA only.")
    parser.add_argument("--days", type=int, default=30, help="Look-back window in days.")
    parser.add_argument("--limit", type=int, default=100, help="Scrape pool size before ranking.")
    parser.add_argument("--top", type=int, default=20, help="How many ranked winners to keep.")
    parser.add_argument("--download", action="store_true", help="Download and process winner videos.")
    parser.add_argument("--resolve", action="store_true", help="Resolve the brand id and exit.")
    parser.add_argument("--headful", action="store_true", help="Show the browser window.")
    return parser.parse_args()


def resolve_brand(brand, region, browser):
    """Resolve a brand id, printing candidates and stopping if ambiguous."""
    result = advertiser.resolve(brand, region, browser, BRANDS_PATH)
    if result.get("ambiguous"):
        candidates = result.get("candidates", [])
        if not candidates:
            print(f"No ads found for '{brand}' in region {region}. Try a different spelling or region.")
        else:
            print(f"Could not pin down '{brand}' to one account. Candidates:")
            for cand in candidates:
                print(f"  {cand['biz_id']}  {cand['advertiser']}")
            print("Seed the right one into brands.json and re-run.")
        return None
    print(f"Resolved {brand} -> biz_id {result['biz_id']} ({result['exact_name']})")
    return result["biz_id"]


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


def write_csv(path, fieldnames, rows):
    """Write rows to a fresh CSV at path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with storage.CsvWriter(str(path), fieldnames) as writer:
        for row in rows:
            writer.write_row(row)


def main():
    args = parse_args()
    paths = storage.brand_paths(OUTPUT_ROOT, args.brand)

    browser = AdsLibraryBrowser(headful=args.headful)
    try:
        browser.__enter__()

        biz_id = resolve_brand(args.brand, args.region, browser) if args.brand else ""
        if args.brand and biz_id is None:
            return
        if args.resolve:
            return

        start_ms, end_ms = time_window_ms(args.days)
        url = build_list_url(args.region, start_ms, end_ms, args.brand, biz_id=biz_id or "")
        print(f"Scraping: region={args.region}, brand={args.brand or 'all'}, days={args.days}")
        print(f"URL: {url}")

        browser.open_list(url)
        rows = collect_list_rows(browser, args.limit)
        print(f"Found {len(rows)} ads. Ranking and keeping top {args.top}.")

        ranked = ranking.rank_rows(rows)
        winners = ranked[: args.top] if args.top > 0 else ranked

        write_csv(paths["ads_csv"], storage.columns_for(detailed=False, ranked=True), ranked)

        for index, row in enumerate(winners, 1):
            enrich_row(row, args.brand, browser)
            print(f"  [{index}] {row.get('ad_id')} {row.get('advertiser', '')[:40]} score={row.get('winner_score')}")
        write_csv(paths["winners_csv"], storage.columns_for(detailed=True, ranked=True), winners)
        print(f"Wrote {paths['ads_csv']} and {paths['winners_csv']}")

        if args.download:
            saved = download.download_videos(browser, winners, paths["videos_dir"])
            print(f"Downloaded {len(saved)} videos.")
            for row in winners:
                video = paths["videos_dir"] / f"{row.get('ad_id')}.mp4"
                if video.exists():
                    media.process_video(
                        video,
                        paths["frames_dir"] / row["ad_id"],
                        paths["transcripts_dir"] / f"{row['ad_id']}.txt",
                    )
            print(f"Processed videos into {paths['frames_dir']} and {paths['transcripts_dir']}")
    finally:
        browser.close()

    print(f"Done. Brand folder: {paths['dir']}")


if __name__ == "__main__":
    main()
