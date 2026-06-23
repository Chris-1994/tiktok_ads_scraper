"""Playwright browser control: launch, URL building, navigation, pagination.

This module owns the Playwright sync session. It builds the Ads Library URL,
opens a realistic desktop browser, waits for the list to render, and clicks
"View more" to load additional ads until a target count is reached.
"""

import time
from urllib.parse import quote

from playwright.sync_api import sync_playwright

from . import extract


USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

VIEWPORT = {"width": 1280, "height": 900}

LIST_RENDER_WAIT_SECONDS = 5
VIEW_MORE_WAIT_SECONDS = 3
DETAIL_RENDER_WAIT_SECONDS = 3


def build_list_url(region, start_ms, end_ms, brand, biz_id=""):
    """Build the Ads Library list URL for the given region and time window.

    start_ms and end_ms are epoch milliseconds. When biz_id is supplied the
    URL isolates that exact advertiser account (adv_biz_ids) and the fuzzy
    adv_name is cleared. When biz_id is empty, brand is used as a fuzzy
    adv_name keyword; an empty brand returns all advertisers.
    """
    adv_name = "" if biz_id else (quote(brand) if brand else "")
    return (
        "https://library.tiktok.com/ads"
        f"?region={region}"
        f"&start_time={start_ms}"
        f"&end_time={end_ms}"
        f"&adv_name={adv_name}"
        f"&adv_biz_ids={biz_id}"
        "&query_type=1"
        "&sort_type=last_shown_date,desc"
    )


def time_window_ms(days):
    """Return (start_ms, end_ms) for a look-back window of the given days."""
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - days * 24 * 60 * 60 * 1000
    return start_ms, now_ms


class AdsLibraryBrowser:
    """Thin wrapper around a Playwright chromium session for the Ads Library."""

    def __init__(self, headful=False):
        self.headful = headful
        self._playwright = None
        self._browser = None
        self._context = None
        self.page = None

    def __enter__(self):
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=not self.headful)
        self._context = self._browser.new_context(
            user_agent=USER_AGENT,
            viewport=VIEWPORT,
        )
        self.page = self._context.new_page()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def close(self):
        """Tear down the page, context, browser, and Playwright in order."""
        for closer in (self._context, self._browser):
            if closer is not None:
                try:
                    closer.close()
                except Exception:
                    pass
        if self._playwright is not None:
            try:
                self._playwright.stop()
            except Exception:
                pass
        self._context = None
        self._browser = None
        self._playwright = None
        self.page = None

    def open_list(self, url):
        """Navigate to the list URL and wait for ads to render."""
        self.page.goto(url, wait_until="domcontentloaded")
        try:
            self.page.wait_for_selector('a[href*="ad_id="]', timeout=LIST_RENDER_WAIT_SECONDS * 1000)
        except Exception:
            time.sleep(LIST_RENDER_WAIT_SECONDS)

    def extract_list(self):
        """Return the list rows currently rendered on the page."""
        return self.page.evaluate(extract.LIST_JS)

    def click_view_more(self):
        """Click the View more control. Returns True if a button was clicked."""
        clicked = self.page.evaluate(extract.VIEW_MORE_JS)
        time.sleep(VIEW_MORE_WAIT_SECONDS)
        return bool(clicked)

    def extract_detail(self, detail_url):
        """Open a detail page, extract richer fields, and return them as a dict."""
        self.page.goto(detail_url, wait_until="domcontentloaded")
        time.sleep(DETAIL_RENDER_WAIT_SECONDS)
        return self.page.evaluate(extract.DETAIL_JS)

    def search_advertisers(self, brand, region):
        """Find advertiser business-id candidates for a brand.

        The TikTok Ads Library only exposes the numeric adv_biz_ids on the ad
        detail page (in the "See all ads" anchor).  This method:
          1. Loads the keyword-search list page for the brand.
          2. Collects every distinct ad_id visible on that page.
          3. Visits each detail page in turn until at least one candidate whose
             advertiser handle contains the brand keyword is found, or all ids
             are exhausted (max 10 detail pages to limit latency).
        Returns a de-duplicated list of {advertiser, biz_id} dicts.
        """
        start_ms, end_ms = time_window_ms(365)
        url = build_list_url(region, start_ms, end_ms, brand)
        self.open_list(url)
        rows = self.extract_list()

        seen_biz = set()
        candidates = []
        needle = (brand or "").strip().lower()

        for row in rows[:10]:
            detail_url = row.get("detail_url", "")
            if not detail_url:
                continue
            self.page.goto(detail_url, wait_until="domcontentloaded")
            time.sleep(DETAIL_RENDER_WAIT_SECONDS)
            found = self.page.evaluate(extract.ADVERTISER_JS)
            for item in found:
                biz_id = item.get("biz_id", "")
                advertiser_name = item.get("advertiser", "")
                if not biz_id or biz_id in seen_biz:
                    continue
                seen_biz.add(biz_id)
                candidates.append(item)
                # Short-circuit when we find a match for the brand keyword
                if needle and needle in advertiser_name.lower():
                    return candidates

        return candidates


def collect_list_rows(browser, limit):
    """Page through the list until limit rows are seen or no new ads appear.

    Returns a de-duplicated list of row dicts in discovery order. Pagination
    stops after two consecutive clicks that add no new ads.
    """
    seen_ids = set()
    rows = []
    stale_tries = 0

    def absorb():
        added = 0
        for row in browser.extract_list():
            ad_id = row.get("ad_id")
            if ad_id and ad_id not in seen_ids:
                seen_ids.add(ad_id)
                rows.append(row)
                added += 1
        return added

    absorb()
    while len(rows) < limit and stale_tries < 2:
        browser.click_view_more()
        if absorb() == 0:
            stale_tries += 1
        else:
            stale_tries = 0

    return rows
