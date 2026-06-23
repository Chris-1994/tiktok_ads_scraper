from tiktok_ads import advertiser


class _BoomBrowser:
    """A browser that fails if a live search is attempted."""

    def search_advertisers(self, brand, region):
        raise AssertionError("built-in brand must resolve without a live search")


def test_builtin_brand_resolves_without_search(tmp_path):
    result = advertiser.resolve(
        "gymshark", "GB", _BoomBrowser(), str(tmp_path / "brands.json")
    )
    assert result["biz_id"] == "7647240890083328016"
    assert result["exact_name"] == "GYMSHARK LTD"


def test_builtin_lookup_is_case_insensitive(tmp_path):
    result = advertiser.resolve(
        "  GymShark ", "GB", _BoomBrowser(), str(tmp_path / "brands.json")
    )
    assert result["biz_id"] == "7647240890083328016"
