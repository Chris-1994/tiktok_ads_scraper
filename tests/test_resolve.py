"""Offline unit tests for advertiser.resolve().

Uses a fake browser that returns canned candidates so no network is needed.
"""

from tiktok_ads import advertiser


class FakeBrowser:
    """Minimal stand-in for AdsLibraryBrowser with canned search results."""

    def __init__(self, candidates):
        self._candidates = candidates

    def search_advertisers(self, brand, region):
        return self._candidates


def test_resolve_cache_hit(tmp_path):
    """resolve() returns cached entry immediately; browser is never called."""
    brands_path = str(tmp_path / "brands.json")
    advertiser.save_brand(brands_path, "gymshark", "999", "Gymshark", "GB")

    called = []

    class NeverCalledBrowser:
        def search_advertisers(self, brand, region):
            called.append(True)
            return []

    result = advertiser.resolve("gymshark", "GB", NeverCalledBrowser(), brands_path)
    assert called == [], "browser.search_advertisers should not be called on cache hit"
    assert result["biz_id"] == "999"
    assert result["exact_name"] == "Gymshark"


def test_resolve_successful_live_lookup(tmp_path):
    """resolve() calls browser, picks the right candidate, saves, and returns it."""
    brands_path = str(tmp_path / "brands.json")
    candidates = [
        {"advertiser": "Gymshark", "biz_id": "12345"},
        {"advertiser": "Gymshark Fan Page", "biz_id": "99999"},
    ]
    browser = FakeBrowser(candidates)

    result = advertiser.resolve("gymshark", "GB", browser, brands_path)

    assert result == {"biz_id": "12345", "exact_name": "Gymshark", "region": "GB"}
    # Should be persisted to cache
    assert advertiser.cached_biz_id(brands_path, "gymshark") == "12345"


def test_resolve_ambiguous(tmp_path):
    """resolve() returns ambiguous dict when choose_candidate can't pick one."""
    brands_path = str(tmp_path / "brands.json")
    candidates = [
        {"advertiser": "Nike Running", "biz_id": "1"},
        {"advertiser": "Nike Football", "biz_id": "2"},
    ]
    browser = FakeBrowser(candidates)

    result = advertiser.resolve("nike", "GB", browser, brands_path)

    assert result["ambiguous"] is True
    assert result["candidates"] == candidates
    # Nothing should be cached for an ambiguous result
    assert advertiser.cached_biz_id(brands_path, "nike") is None


def test_resolve_no_candidates(tmp_path):
    """resolve() returns ambiguous with empty candidates list when browser finds nothing."""
    brands_path = str(tmp_path / "brands.json")
    browser = FakeBrowser([])

    result = advertiser.resolve("unknownbrand", "GB", browser, brands_path)

    assert result["ambiguous"] is True
    assert result["candidates"] == []
