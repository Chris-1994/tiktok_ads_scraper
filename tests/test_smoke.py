def test_package_imports():
    import tiktok_ads
    assert "browser" in tiktok_ads.__all__
