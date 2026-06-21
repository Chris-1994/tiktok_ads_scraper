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


def build_list_url(region, start_ms, end_ms, brand):
    """Build the Ads Library list URL for the given region and time window.

    start_ms and end_ms are epoch milliseconds. brand is an optional advertiser
    keyword; when empty, all advertisers are returned.
    """
    adv_name = quote(brand) if brand else ""
    return (
        "https://library.tiktok.com/ads"
        f"?region={region}"
        f"&start_time={start_ms}"
        f"&end_time={end_ms}"
        f"&adv_name={adv_name}"
        "&adv_biz_ids="
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
