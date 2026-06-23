from tiktok_ads import download


class FakeBrowser:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def fetch_bytes(self, url):
        self.calls.append(url)
        return self.payload


def test_download_writes_files(tmp_path):
    rows = [{"ad_id": "100", "video_url": "https://x/v.mp4"}]
    browser = FakeBrowser(b"DATA")
    saved = download.download_videos(browser, rows, tmp_path)
    assert (tmp_path / "100.mp4").read_bytes() == b"DATA"
    assert saved == [str(tmp_path / "100.mp4")]


def test_download_skips_rows_without_url(tmp_path):
    rows = [{"ad_id": "100", "video_url": ""}]
    browser = FakeBrowser(b"DATA")
    assert download.download_videos(browser, rows, tmp_path) == []


def test_download_skips_existing_file(tmp_path):
    (tmp_path / "100.mp4").write_bytes(b"OLD")
    rows = [{"ad_id": "100", "video_url": "https://x/v.mp4"}]
    browser = FakeBrowser(b"NEW")
    download.download_videos(browser, rows, tmp_path)
    assert (tmp_path / "100.mp4").read_bytes() == b"OLD"
    assert browser.calls == []
