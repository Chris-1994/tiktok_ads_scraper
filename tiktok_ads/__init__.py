"""TikTok Ads Library scraper package.

Modules:
  browser  : Playwright launch, URL building, navigation, pagination.
  extract  : DOM extraction JavaScript for list and detail pages.
  storage  : Resume support (load existing ad_ids) and incremental CSV append.
  report   : Build an HTML report from a CSV and render it to PDF.
  ranking   : deterministic longevity-weighted winner scoring.
  advertiser: resolve a brand to its business id, cached in brands.json.
  download  : download winner ad videos via the browser session.
  media     : ffmpeg keyframes and optional whisper transcript.
"""

__all__ = ["browser", "extract", "storage", "report", "ranking", "advertiser", "download", "media"]
