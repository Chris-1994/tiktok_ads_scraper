from tiktok_ads import advertiser


def test_choose_exact_single():
    cands = [
        {"advertiser": "Gymshark", "biz_id": "111"},
        {"advertiser": "Gymshark Fan Page", "biz_id": "222"},
    ]
    assert advertiser.choose_candidate("gymshark", cands)["biz_id"] == "111"


def test_choose_contains_single():
    cands = [{"advertiser": "Gymshark Ltd", "biz_id": "333"}]
    assert advertiser.choose_candidate("gymshark", cands)["biz_id"] == "333"


def test_choose_ambiguous_returns_none():
    cands = [
        {"advertiser": "Nike Running", "biz_id": "1"},
        {"advertiser": "Nike Football", "biz_id": "2"},
    ]
    assert advertiser.choose_candidate("nike", cands) is None


def test_choose_skips_candidates_without_id():
    cands = [{"advertiser": "Gymshark", "biz_id": ""}]
    assert advertiser.choose_candidate("gymshark", cands) is None


def test_cache_roundtrip(tmp_path):
    path = tmp_path / "brands.json"
    advertiser.save_brand(str(path), "Gymshark", "999", "Gymshark", "GB")
    assert advertiser.cached_biz_id(str(path), "gymshark") == "999"


def test_cached_biz_id_missing_file(tmp_path):
    assert advertiser.cached_biz_id(str(tmp_path / "nope.json"), "x") is None
