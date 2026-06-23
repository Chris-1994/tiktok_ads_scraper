"""TikTok Ads Library scraper package.

Modules:
  browser  : Playwright launch, URL building, navigation, pagination.
  extract  : DOM extraction JavaScript for list and detail pages.
  storage  : Resume support (load existing ad_ids) and incremental CSV append.
  report   : Build an HTML report from a CSV and render it to PDF.
"""

__all__ = ["browser", "extract", "storage", "report", "ranking", "advertiser", "download", "media"]
