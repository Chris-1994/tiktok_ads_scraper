"""Integration test: extract_detail waits for the video src to render.

TikTok detail pages set the <video> src after load, so a fixed short sleep
often reads an empty video_url in headless mode. This test loads a local
fixture whose src appears after a delay longer than the old fixed sleep, and
asserts the captured video_url is non-empty -- proving the page is waited on
rather than read too early. It launches a real (headless) browser, so it is
slower than the pure-logic tests.
"""

from tiktok_ads.browser import AdsLibraryBrowser

# The src is attached ~4s after load -- past the old 3s fixed sleep, within the
# hardened wait window.
FIXTURE = """<!doctype html>
<html><body>
<video></video>
<script>
  setTimeout(function () {
    document.querySelector('video').setAttribute('src', 'clip.mp4');
  }, 4000);
</script>
</body></html>"""


def test_extract_detail_waits_for_video_src(tmp_path):
    page = tmp_path / "detail.html"
    page.write_text(FIXTURE, encoding="utf-8")

    browser = AdsLibraryBrowser()
    browser.__enter__()
    try:
        detail = browser.extract_detail(page.as_uri())
    finally:
        browser.close()

    assert detail["video_url"] == "clip.mp4"
