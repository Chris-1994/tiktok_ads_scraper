from tiktok_ads import ranking


def test_parse_reach_bucket_range():
    assert ranking.parse_reach_bucket("700K-800K") == 750000


def test_parse_reach_bucket_small_range():
    assert ranking.parse_reach_bucket("0-1K") == 500


def test_parse_reach_bucket_millions():
    assert ranking.parse_reach_bucket("1M-2M") == 1500000


def test_parse_reach_bucket_unparseable():
    assert ranking.parse_reach_bucket("N/A") == 0
    assert ranking.parse_reach_bucket("") == 0


def test_compute_score_zero_days_is_zero():
    assert ranking.compute_score(0, 750000) == 0.0


def test_compute_score_blank_days_is_zero():
    assert ranking.compute_score("", 1000) == 0.0


def test_compute_score_longevity_beats_reach():
    long_small_reach = ranking.compute_score(60, 500)
    short_big_reach = ranking.compute_score(2, 800000)
    assert long_small_reach > short_big_reach


def test_rank_rows_orders_by_score_desc():
    rows = [
        {"ad_id": "a", "first_shown": "01/01/2026", "last_shown": "01/05/2026", "unique_users": "0-1K"},
        {"ad_id": "b", "first_shown": "01/01/2026", "last_shown": "03/01/2026", "unique_users": "700K-800K"},
    ]
    ranked = ranking.rank_rows(rows)
    assert ranked[0]["ad_id"] == "b"
    assert ranked[0]["winner_score"] >= ranked[1]["winner_score"]


def test_select_top_limits_count():
    rows = [
        {"ad_id": str(i), "first_shown": "01/01/2026", "last_shown": "02/01/2026", "unique_users": "0-1K"}
        for i in range(5)
    ]
    assert len(ranking.select_top(rows, 2)) == 2
