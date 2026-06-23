from pathlib import Path

from tiktok_ads import storage


def test_brand_slug_basic():
    assert storage.brand_slug("Gymshark") == "gymshark"
    assert storage.brand_slug("My Brand") == "my-brand"
    assert storage.brand_slug("") == "all"


def test_brand_paths_layout():
    paths = storage.brand_paths("output", "Gymshark")
    assert paths["dir"] == Path("output") / "gymshark"
    assert paths["ads_csv"] == Path("output") / "gymshark" / "ads.csv"
    assert paths["winners_csv"] == Path("output") / "gymshark" / "winners.csv"
    assert paths["videos_dir"] == Path("output") / "gymshark" / "videos"
    assert paths["frames_dir"] == Path("output") / "gymshark" / "frames"
    assert paths["transcripts_dir"] == Path("output") / "gymshark" / "transcripts"
    assert paths["brief_md"] == Path("output") / "gymshark" / "brief.md"


def test_columns_for_ranked_appends_score():
    cols = storage.columns_for(detailed=False, ranked=True)
    assert cols[-1] == "winner_score"
    assert "ad_id" in cols


def test_columns_for_unranked_unchanged():
    assert storage.columns_for(detailed=False) == list(storage.LIST_COLUMNS)
