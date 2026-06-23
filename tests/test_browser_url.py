from tiktok_ads import browser


def test_fuzzy_mode_uses_adv_name():
    url = browser.build_list_url("GB", 1000, 2000, "gymshark")
    assert "adv_name=gymshark" in url
    assert "adv_biz_ids=" in url
    assert "adv_biz_ids=123" not in url


def test_exact_mode_uses_biz_id_and_clears_name():
    url = browser.build_list_url("GB", 1000, 2000, "gymshark", biz_id="123456789")
    assert "adv_biz_ids=123456789" in url
    assert "adv_name=&" in url or url.rstrip().endswith("adv_name=")


def test_region_and_window_present():
    url = browser.build_list_url("FR", 1111, 2222, "")
    assert "region=FR" in url
    assert "start_time=1111" in url
    assert "end_time=2222" in url
