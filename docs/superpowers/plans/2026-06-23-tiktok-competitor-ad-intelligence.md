# TikTok Competitor Ad Intelligence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the TikTok Ads Library scraper to target a competitor brand's own account, download a controlled number of its longevity-ranked winning video ads into a per-brand folder, and let a Claude Code skill turn the creative into a per-brand `brief.md` of patterns and new-ad concepts.

**Architecture:** Four composable stages handing off through a per-brand folder on disk: resolve (brand name to business id), scrape + rank (collect ads, deterministic winner score), download + process (MP4s, ffmpeg keyframes, optional transcript), analyze (a Claude Code skill that writes `brief.md`). New work lives in small single-responsibility modules under the existing `tiktok_ads/` package.

**Tech Stack:** Python 3.14, Playwright (sync), ffmpeg/ffprobe (already installed), optional faster-whisper, pytest. The existing package modules are `browser`, `extract`, `storage`, `report`.

## Global Constraints

- Build everything inside `tiktok_ads_scraper/` (its own git repo, branch `main`). Do not modify the parent scratch folder.
- Per the user's git-safety rules: do NOT commit on `main`. Create a feature branch first (Task 1, Step 0). Commit freely on that branch. Do NOT push unless the user explicitly asks.
- Run tests from the repo root with `.venv/bin/python -m pytest`.
- Data source reality (never promise otherwise): no spend, cost, CTR, clicks, conversions, or exact impressions exist. Only `first_shown`/`last_shown` dates and a bucketed `unique_users` reach range. Region codes are EU/EEA only (`GB` works).
- Ranking is deterministic. No AI in the scoring path.
- Selectors are obfuscated; DOM extraction anchors on `a[href*="ad_id="]` and visible text, never on CSS class names.
- Do not touch the existing `report.py` module or the `tiktok-ad-report` skill.
- ffmpeg is required for keyframes. faster-whisper is optional; the pipeline degrades to frames-only when it is absent.
- One `brief.md` per brand, written for a downstream video-generation AI to consume.

---

### Task 1: Feature branch, test harness, and dependencies

**Files:**
- Modify: `requirements.txt`
- Create: `tests/test_smoke.py`

**Interfaces:**
- Consumes: nothing.
- Produces: a working `.venv/bin/python -m pytest` run; pytest available for all later tasks.

- [ ] **Step 0: Create a feature branch (never work on main)**

```bash
cd /Users/ChrisV/Desktop/YouTube/scrape_tiktok_adlibrary/tiktok_ads_scraper
git checkout -b feat/competitor-ad-intelligence
```

- [ ] **Step 1: Add pytest and the optional transcription note to requirements**

Replace the contents of `requirements.txt` with:

```
playwright>=1.40
pytest>=8

# Optional: spoken-audio transcription for video-aware analysis.
# Install only if it has a wheel for your Python version. The scraper
# degrades to frames-only when this package is absent.
# faster-whisper>=1.0
```

- [ ] **Step 2: Install pytest into the existing venv**

Run: `.venv/bin/python -m pip install pytest>=8`
Expected: `Successfully installed ... pytest-8...`

- [ ] **Step 3: Write a smoke test that imports the package**

Create `tests/test_smoke.py`:

```python
def test_package_imports():
    import tiktok_ads
    assert "browser" in tiktok_ads.__all__
```

- [ ] **Step 4: Run the smoke test**

Run: `.venv/bin/python -m pytest tests/test_smoke.py -v`
Expected: `1 passed`

- [ ] **Step 5: Commit**

```bash
git add requirements.txt tests/test_smoke.py docs/superpowers/
git commit -m "chore: add pytest harness and competitor-intelligence spec/plan"
```

---

### Task 2: Deterministic winner ranking (`ranking.py`)

**Files:**
- Create: `tiktok_ads/ranking.py`
- Test: `tests/test_ranking.py`

**Interfaces:**
- Consumes: `tiktok_ads.extract.parse_active_days(first_shown, last_shown) -> int | ""`.
- Produces:
  - `parse_reach_bucket(bucket: str) -> int` (reach midpoint, 0 when unparseable)
  - `compute_score(active_days, reach_midpoint: int) -> float`
  - `rank_rows(rows: list[dict]) -> list[dict]` (adds `"winner_score"` key, returns rows sorted by it, descending)
  - `select_top(rows: list[dict], top: int) -> list[dict]`

- [ ] **Step 1: Write failing tests**

Create `tests/test_ranking.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_ranking.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tiktok_ads.ranking'`

- [ ] **Step 3: Implement `ranking.py`**

Create `tiktok_ads/ranking.py`:

```python
"""Deterministic winner ranking for scraped ads.

No AI in this path. A winning ad is approximated by longevity (how many days
it ran), because advertisers keep paying for ads that convert. Reach acts as a
tie breaker so an equally old ad seen by more people ranks higher.

    winner_score = active_days * log10(reach_midpoint + 10)

The reach value is a bucketed range like "700K-800K"; it is reduced to a
numeric midpoint before scoring.
"""

import math
import re

from . import extract

_SUFFIX = {"": 1, "K": 1_000, "M": 1_000_000, "B": 1_000_000_000}


def parse_reach_bucket(bucket):
    """Return the numeric midpoint of a reach range like "700K-800K".

    Returns 0 when no numbers can be read (for example "N/A" or "").
    """
    if not bucket:
        return 0
    numbers = []
    for value, suffix in re.findall(r"([\d.]+)\s*([KMB]?)", bucket.upper()):
        try:
            numbers.append(float(value) * _SUFFIX[suffix])
        except (ValueError, KeyError):
            continue
    if not numbers:
        return 0
    return int(sum(numbers) / len(numbers))


def compute_score(active_days, reach_midpoint):
    """Longevity weighted score. Invalid or negative days score 0.0."""
    try:
        days = int(active_days)
    except (ValueError, TypeError):
        return 0.0
    if days < 0:
        days = 0
    return round(days * math.log10(reach_midpoint + 10), 4)


def rank_rows(rows):
    """Add a winner_score to each row and return rows sorted high to low."""
    for row in rows:
        active_days = extract.parse_active_days(
            row.get("first_shown", ""), row.get("last_shown", "")
        )
        reach = parse_reach_bucket(row.get("unique_users", ""))
        row["winner_score"] = compute_score(active_days, reach)
    return sorted(rows, key=lambda r: r["winner_score"], reverse=True)


def select_top(rows, top):
    """Rank rows and return the top N. A non-positive top returns all rows."""
    ranked = rank_rows(rows)
    if top and top > 0:
        return ranked[:top]
    return ranked
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_ranking.py -v`
Expected: `8 passed`

- [ ] **Step 5: Commit**

```bash
git add tiktok_ads/ranking.py tests/test_ranking.py
git commit -m "feat: deterministic longevity-weighted winner ranking"
```

---

### Task 3: Per-brand storage layout and winner_score column (`storage.py`)

**Files:**
- Modify: `tiktok_ads/storage.py`
- Test: `tests/test_storage.py`

**Interfaces:**
- Consumes: existing `storage.LIST_COLUMNS`, `storage.DETAIL_COLUMNS`.
- Produces:
  - `brand_slug(brand: str) -> str`
  - `brand_paths(output_root, brand: str) -> dict` with keys `dir, ads_csv, winners_csv, videos_dir, frames_dir, transcripts_dir, brief_md` (all `pathlib.Path`)
  - `columns_for(detailed: bool, ranked: bool = False) -> list[str]` (appends `"winner_score"` when `ranked`)

- [ ] **Step 1: Write failing tests**

Create `tests/test_storage.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_storage.py -v`
Expected: FAIL with `AttributeError: module 'tiktok_ads.storage' has no attribute 'brand_slug'`

- [ ] **Step 3: Implement the additions in `storage.py`**

Add this import near the top of `tiktok_ads/storage.py` (it currently imports `csv` and `os`):

```python
from pathlib import Path
```

Add this constant directly below the existing `DETAIL_COLUMNS` list:

```python
RANK_COLUMN = "winner_score"
```

Replace the existing `columns_for` function with:

```python
def columns_for(detailed, ranked=False):
    """Return the ordered column list for the chosen mode.

    When ranked is True a trailing winner_score column is appended.
    """
    cols = list(LIST_COLUMNS)
    if detailed:
        cols += DETAIL_COLUMNS
    if ranked:
        cols.append(RANK_COLUMN)
    return cols
```

Add these two functions at the end of the module:

```python
def brand_slug(brand):
    """Lowercase, hyphenated folder name for a brand. Empty brand is "all"."""
    cleaned = (brand or "").strip().lower()
    return cleaned.replace(" ", "-") if cleaned else "all"


def brand_paths(output_root, brand):
    """Return the per-brand folder paths used by every stage."""
    base = Path(output_root) / brand_slug(brand)
    return {
        "dir": base,
        "ads_csv": base / "ads.csv",
        "winners_csv": base / "winners.csv",
        "videos_dir": base / "videos",
        "frames_dir": base / "frames",
        "transcripts_dir": base / "transcripts",
        "brief_md": base / "brief.md",
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_storage.py -v`
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add tiktok_ads/storage.py tests/test_storage.py
git commit -m "feat: per-brand folder layout and winner_score column"
```

---

### Task 4: Exact-advertiser URL mode (`browser.build_list_url`)

**Files:**
- Modify: `tiktok_ads/browser.py:29-45`
- Test: `tests/test_browser_url.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `build_list_url(region, start_ms, end_ms, brand, biz_id="") -> str`. When `biz_id` is set, `adv_biz_ids` carries it and `adv_name` is empty (exact account isolation). When `biz_id` is empty, behavior is unchanged (fuzzy `adv_name`).

- [ ] **Step 1: Write failing tests**

Create `tests/test_browser_url.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_browser_url.py -v`
Expected: FAIL with `TypeError: build_list_url() got an unexpected keyword argument 'biz_id'`

- [ ] **Step 3: Replace `build_list_url` in `browser.py`**

Replace the existing `build_list_url` function (lines 29-45) with:

```python
def build_list_url(region, start_ms, end_ms, brand, biz_id=""):
    """Build the Ads Library list URL for the given region and time window.

    start_ms and end_ms are epoch milliseconds. When biz_id is supplied the
    URL isolates that exact advertiser account (adv_biz_ids) and the fuzzy
    adv_name is cleared. When biz_id is empty, brand is used as a fuzzy
    adv_name keyword; an empty brand returns all advertisers.
    """
    adv_name = "" if biz_id else (quote(brand) if brand else "")
    return (
        "https://library.tiktok.com/ads"
        f"?region={region}"
        f"&start_time={start_ms}"
        f"&end_time={end_ms}"
        f"&adv_name={adv_name}"
        f"&adv_biz_ids={biz_id}"
        "&query_type=1"
        "&sort_type=last_shown_date,desc"
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_browser_url.py -v`
Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add tiktok_ads/browser.py tests/test_browser_url.py
git commit -m "feat: exact-advertiser URL mode via adv_biz_ids"
```

---

### Task 5: Brand-id cache and candidate selection (`advertiser.py`)

**Files:**
- Create: `tiktok_ads/advertiser.py`
- Test: `tests/test_advertiser.py`

**Interfaces:**
- Consumes: nothing new.
- Produces:
  - `load_brands(path) -> dict`
  - `cached_biz_id(path, brand) -> str | None`
  - `save_brand(path, brand, biz_id, exact_name, region) -> None`
  - `choose_candidate(brand, candidates: list[dict]) -> dict | None` where each candidate is `{"advertiser": str, "biz_id": str}`; returns the single best match or `None` when ambiguous.

  (The live `resolve(...)` that drives the browser is added in Task 6, because its extraction depends on the spike.)

- [ ] **Step 1: Write failing tests**

Create `tests/test_advertiser.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_advertiser.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tiktok_ads.advertiser'`

- [ ] **Step 3: Implement `advertiser.py` (cache + selection only)**

Create `tiktok_ads/advertiser.py`:

```python
"""Resolve a brand name to its exact TikTok advertiser business id.

The resolved ids are cached in a brands.json file so a brand is only looked up
once. This module holds the pure cache and candidate-selection logic; the live
browser search is added as resolve() in a later step.
"""

import json
import os


def load_brands(path):
    """Return the cached brand map, or an empty dict if missing or invalid."""
    if not path or not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as handle:
        try:
            return json.load(handle)
        except json.JSONDecodeError:
            return {}


def cached_biz_id(path, brand):
    """Return the cached business id for a brand, or None."""
    entry = load_brands(path).get((brand or "").strip().lower())
    return entry.get("biz_id") if entry else None


def save_brand(path, brand, biz_id, exact_name, region):
    """Write or update one brand entry in the cache file."""
    data = load_brands(path)
    data[(brand or "").strip().lower()] = {
        "biz_id": biz_id,
        "exact_name": exact_name,
        "region": region,
    }
    parent = os.path.dirname(os.path.abspath(path))
    os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)


def choose_candidate(brand, candidates):
    """Pick the single best advertiser candidate, or None when ambiguous.

    Each candidate is {"advertiser": str, "biz_id": str}. Preference order:
    one exact (case-insensitive) name match, then one substring match, then a
    single distinct id across all candidates. Anything else is ambiguous.
    """
    needle = (brand or "").strip().lower()
    valid = [c for c in candidates if c.get("biz_id")]
    if not valid:
        return None

    exact = [c for c in valid if c["advertiser"].strip().lower() == needle]
    if exact:
        ids = {c["biz_id"] for c in exact}
        return exact[0] if len(ids) == 1 else None

    contains = [c for c in valid if needle and needle in c["advertiser"].strip().lower()]
    if len(contains) == 1:
        return contains[0]

    ids = {c["biz_id"] for c in valid}
    if len(ids) == 1:
        return valid[0]
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_advertiser.py -v`
Expected: `6 passed`

- [ ] **Step 5: Commit**

```bash
git add tiktok_ads/advertiser.py tests/test_advertiser.py
git commit -m "feat: brand-id cache and candidate selection"
```

---

### Task 6: Live business-id extraction and resolve (spike + wiring)

This is the riskiest unknown: where TikTok exposes the business id. The extraction below looks in the two most likely places (advertiser anchors and embedded JSON). Steps 4-5 validate it against a real brand and adjust the regex if the real location differs.

**Files:**
- Modify: `tiktok_ads/extract.py` (add `ADVERTISER_JS`)
- Modify: `tiktok_ads/browser.py` (add `search_advertisers` method)
- Modify: `tiktok_ads/advertiser.py` (add `resolve`)
- Create: `docs/superpowers/notes/biz-id-location.md` (record the confirmed location)

**Interfaces:**
- Consumes: `browser.build_list_url`, `browser.time_window_ms`, `advertiser.choose_candidate`, `advertiser.save_brand`, `advertiser.cached_biz_id`.
- Produces:
  - `extract.ADVERTISER_JS` (string of page JS returning `[{advertiser, biz_id}, ...]`)
  - `AdsLibraryBrowser.search_advertisers(brand, region) -> list[dict]`
  - `advertiser.resolve(brand, region, browser, brands_path) -> dict`. Returns `{"biz_id", "exact_name", "region"}` on success, or `{"ambiguous": True, "candidates": [...]}` when no single candidate wins.

- [ ] **Step 1: Add `ADVERTISER_JS` to `extract.py`**

Append to `tiktok_ads/extract.py`:

```python
# JavaScript that scans a rendered search page for advertiser business ids.
# It checks the two most likely locations: anchor hrefs that carry an
# advertiser/business id parameter, and embedded JSON blobs in <script> tags.
ADVERTISER_JS = r"""
() => {
  const out = [];
  const seen = new Set();
  const push = (name, id) => {
    name = (name || '').trim();
    id = String(id || '');
    if (!name || !id) return;
    const key = name + '|' + id;
    if (seen.has(key)) return;
    seen.add(key);
    out.push({ advertiser: name, biz_id: id });
  };
  for (const a of document.querySelectorAll('a[href]')) {
    const href = a.getAttribute('href') || '';
    const m = href.match(/(?:adv_biz_ids|advertiser_id|adv_id)=(\d{5,})/i);
    if (m) push(a.innerText || a.getAttribute('title'), m[1]);
  }
  for (const s of document.querySelectorAll('script')) {
    const txt = s.textContent || '';
    if (!/adv_biz_id|advertiser_id|business_id/i.test(txt)) continue;
    const re = /"(?:adv_biz_id|advertiser_id|business_id)"\s*:\s*"?(\d{5,})"?[\s\S]{0,120}?"(?:advertiser_name|adv_name|name)"\s*:\s*"([^"]+)"/gi;
    let m;
    while ((m = re.exec(txt))) push(m[2], m[1]);
  }
  return out;
}
"""
```

- [ ] **Step 2: Add `search_advertisers` to `AdsLibraryBrowser`**

Add this method to the `AdsLibraryBrowser` class in `browser.py`, after `extract_detail`:

```python
    def search_advertisers(self, brand, region):
        """Fuzzy-search a brand over a wide window and return id candidates."""
        start_ms, end_ms = time_window_ms(365)
        url = build_list_url(region, start_ms, end_ms, brand)
        self.open_list(url)
        return self.page.evaluate(extract.ADVERTISER_JS)
```

- [ ] **Step 3: Add `resolve` to `advertiser.py`**

Append to `tiktok_ads/advertiser.py`:

```python
def resolve(brand, region, browser, brands_path):
    """Resolve a brand to its business id, using the cache when present.

    On a cache miss this drives a live advertiser search through the browser.
    Returns the resolved entry, or an ambiguous result carrying the candidate
    list so the caller can ask the user to choose.
    """
    cached = cached_biz_id(brands_path, brand)
    if cached:
        return load_brands(brands_path)[(brand or "").strip().lower()]

    candidates = browser.search_advertisers(brand, region)
    chosen = choose_candidate(brand, candidates)
    if not chosen:
        return {"ambiguous": True, "candidates": candidates}

    save_brand(brands_path, brand, chosen["biz_id"], chosen["advertiser"], region)
    return {"biz_id": chosen["biz_id"], "exact_name": chosen["advertiser"], "region": region}
```

- [ ] **Step 4: Spike — confirm extraction against a real brand**

Run this one-off probe (headful so you can watch). It prints whatever candidates the extraction finds for a known brand:

```bash
.venv/bin/python -c "
from tiktok_ads.browser import AdsLibraryBrowser
b = AdsLibraryBrowser(headful=True)
b.__enter__()
try:
    print(b.search_advertisers('gymshark', 'GB'))
finally:
    b.close()
"
```

Expected: a non-empty list like `[{'advertiser': 'Gymshark', 'biz_id': '...'}]`.

If the list is empty, open the page manually and find where the id lives:

```bash
.venv/bin/python -c "
from tiktok_ads.browser import AdsLibraryBrowser, build_list_url, time_window_ms
b = AdsLibraryBrowser(headful=True); b.__enter__()
s,e = time_window_ms(365)
b.page.goto(build_list_url('GB', s, e, 'gymshark'), wait_until='domcontentloaded')
import time; time.sleep(6)
html = b.page.content()
open('/tmp/tt_search.html','w').write(html)
print('adv_biz_ids' in html, 'advertiser_id' in html, 'business_id' in html)
b.close()
"
grep -oE '(adv_biz_ids|advertiser_id|business_id)[^,}\"]{0,40}' /tmp/tt_search.html | head
```

Adjust the regex/selectors in `ADVERTISER_JS` (Step 1) to match the real attribute name found, then re-run the probe until it returns a correct id.

- [ ] **Step 5: Record the confirmed location**

Create `docs/superpowers/notes/biz-id-location.md` with one short paragraph: which element/param holds the id, the brand and id you verified with, and the date. This protects the next person when TikTok changes the page.

- [ ] **Step 6: Commit**

```bash
git add tiktok_ads/extract.py tiktok_ads/browser.py tiktok_ads/advertiser.py docs/superpowers/notes/biz-id-location.md
git commit -m "feat: live advertiser business-id resolution"
```

---

### Task 7: Winner video download (`download.py`)

**Files:**
- Create: `tiktok_ads/download.py`
- Modify: `tiktok_ads/browser.py` (add `fetch_bytes`)
- Test: `tests/test_download.py`

**Interfaces:**
- Consumes: a browser-like object exposing `fetch_bytes(url) -> bytes | None`; rows carrying `video_url` and `ad_id`.
- Produces:
  - `AdsLibraryBrowser.fetch_bytes(url) -> bytes | None` (uses the Playwright request context so cookies/headers from the session apply)
  - `download.download_videos(browser, rows, videos_dir) -> list[str]` (paths saved; skips rows with no `video_url`, and skips files already present)

- [ ] **Step 1: Write failing tests**

Create `tests/test_download.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_download.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tiktok_ads.download'`

- [ ] **Step 3: Implement `download.py`**

Create `tiktok_ads/download.py`:

```python
"""Download winner ad videos into a per-brand videos folder.

Downloads run through the browser's request context so the session cookies and
headers apply; bare HTTP GETs to the TikTok CDN can be rejected. Files already
on disk are skipped so a run resumes cleanly.
"""

from pathlib import Path


def download_videos(browser, rows, videos_dir):
    """Download each row's video_url to videos_dir/<ad_id>.mp4.

    Returns the list of saved file paths. Rows without a video_url or ad_id are
    skipped, as are videos already present on disk.
    """
    out_dir = Path(videos_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    saved = []
    for row in rows:
        url = row.get("video_url", "")
        ad_id = row.get("ad_id", "")
        if not url or not ad_id:
            continue
        dest = out_dir / f"{ad_id}.mp4"
        if dest.exists() and dest.stat().st_size > 0:
            saved.append(str(dest))
            continue
        data = browser.fetch_bytes(url)
        if data:
            dest.write_bytes(data)
            saved.append(str(dest))
    return saved
```

- [ ] **Step 4: Add `fetch_bytes` to `AdsLibraryBrowser`**

Add this method to the `AdsLibraryBrowser` class in `browser.py`, after `search_advertisers`:

```python
    def fetch_bytes(self, url):
        """Fetch a URL using the session's request context. None on failure."""
        try:
            response = self._context.request.get(url)
            if response.ok:
                return response.body()
        except Exception:
            return None
        return None
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_download.py -v`
Expected: `3 passed`

- [ ] **Step 6: Manual verification against one real ad**

After Task 9 wires the CLI you will be able to run a real `--download`. For now, sanity-check that `video_url` is actually captured by `extract.DETAIL_JS` on a live detail page (open one ad in headful mode and confirm a non-empty `video_url`). If the `<video>` src is blob-based rather than a direct URL, note it in `docs/superpowers/notes/biz-id-location.md` as a follow-up; the download then needs to capture the network response instead. Record the result.

- [ ] **Step 7: Commit**

```bash
git add tiktok_ads/download.py tiktok_ads/browser.py tests/test_download.py
git commit -m "feat: download winner videos via session request context"
```

---

### Task 8: Keyframes and optional transcript (`media.py`)

**Files:**
- Create: `tiktok_ads/media.py`
- Test: `tests/test_media.py`

**Interfaces:**
- Consumes: ffmpeg/ffprobe on PATH; optional `faster_whisper`.
- Produces:
  - `has_ffmpeg() -> bool`
  - `video_duration(video_path) -> float`
  - `extract_keyframes(video_path, frames_dir, fractions=(0.05,0.25,0.5,0.75,0.95)) -> list[str]`
  - `transcribe(video_path, transcript_path) -> str | None` (None when faster-whisper is absent)
  - `process_video(video_path, frames_dir, transcript_path) -> dict` with keys `frames` and `transcript`

- [ ] **Step 1: Write failing tests**

Create `tests/test_media.py`:

```python
import subprocess

import pytest

from tiktok_ads import media


@pytest.fixture
def sample_video(tmp_path):
    path = tmp_path / "sample.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i",
         "testsrc=duration=2:size=128x128:rate=10", str(path)],
        capture_output=True, check=True,
    )
    return path


def test_has_ffmpeg_true():
    assert media.has_ffmpeg() is True


def test_video_duration(sample_video):
    assert media.video_duration(sample_video) == pytest.approx(2.0, abs=0.3)


def test_extract_keyframes_writes_files(sample_video, tmp_path):
    frames = media.extract_keyframes(sample_video, tmp_path / "frames")
    assert len(frames) >= 3
    for f in frames:
        assert f.endswith(".jpg")


def test_transcribe_degrades_without_whisper(sample_video, tmp_path, monkeypatch):
    import builtins
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name.startswith("faster_whisper"):
            raise ImportError("simulated missing whisper")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert media.transcribe(sample_video, tmp_path / "t.txt") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_media.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tiktok_ads.media'`

- [ ] **Step 3: Implement `media.py`**

Create `tiktok_ads/media.py`:

```python
"""Turn a downloaded ad video into AI-readable inputs.

Keyframes (via ffmpeg) let Claude see the creative, including burned-in
on-screen text. A spoken transcript (via the optional faster-whisper package)
captures the voiceover. Transcription degrades to None when faster-whisper is
not installed, so the pipeline keeps working on frames alone.
"""

import shutil
import subprocess
from pathlib import Path


def has_ffmpeg():
    """True when ffmpeg is available on PATH."""
    return shutil.which("ffmpeg") is not None


def video_duration(video_path):
    """Return the video duration in seconds, or 0.0 if it cannot be read."""
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(video_path)],
        capture_output=True, text=True,
    )
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 0.0


def extract_keyframes(video_path, frames_dir, fractions=(0.05, 0.25, 0.5, 0.75, 0.95)):
    """Extract one frame at each fraction of the duration. Returns file paths."""
    out_dir = Path(frames_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    duration = video_duration(video_path)
    paths = []
    for index, fraction in enumerate(fractions):
        timestamp = duration * fraction if duration else float(index)
        dest = out_dir / f"frame_{index:02d}.jpg"
        subprocess.run(
            ["ffmpeg", "-y", "-ss", str(timestamp), "-i", str(video_path),
             "-frames:v", "1", "-q:v", "3", str(dest)],
            capture_output=True,
        )
        if dest.exists() and dest.stat().st_size > 0:
            paths.append(str(dest))
    return paths


def transcribe(video_path, transcript_path):
    """Transcribe audio with faster-whisper. None when it is not installed."""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return None
    model = WhisperModel("base", device="cpu", compute_type="int8")
    segments, _ = model.transcribe(str(video_path))
    text = " ".join(segment.text.strip() for segment in segments).strip()
    dest = Path(transcript_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")
    return text


def process_video(video_path, frames_dir, transcript_path):
    """Extract keyframes and (when available) a transcript for one video."""
    frames = extract_keyframes(video_path, frames_dir) if has_ffmpeg() else []
    transcript = transcribe(video_path, transcript_path)
    return {"frames": frames, "transcript": transcript}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_media.py -v`
Expected: `4 passed` (the transcribe test passes whether or not faster-whisper is installed, because it simulates the missing import).

- [ ] **Step 5: Commit**

```bash
git add tiktok_ads/media.py tests/test_media.py
git commit -m "feat: ffmpeg keyframes and optional whisper transcript"
```

---

### Task 9: Wire the competitor pipeline into the CLI (`scraper.py`)

**Files:**
- Modify: `tiktok_ads/__init__.py` (export new modules)
- Modify: `scraper.py` (whole file rewritten below)
- Test: manual end-to-end run

**Interfaces:**
- Consumes: `advertiser.resolve`, `ranking.select_top`, `ranking.rank_rows`, `storage.brand_paths`, `storage.columns_for`, `storage.CsvWriter`, `download.download_videos`, `media.process_video`, existing `browser` helpers and `enrich_row`.
- Produces: a CLI that resolves a brand, scrapes its account, ranks, writes `ads.csv` + `winners.csv`, and (with `--download`) downloads and processes the top-N into the per-brand folder.

- [ ] **Step 1: Export the new modules from the package**

Replace the `__all__` line in `tiktok_ads/__init__.py` with:

```python
__all__ = ["browser", "extract", "storage", "report", "ranking", "advertiser", "download", "media"]
```

- [ ] **Step 2: Rewrite `scraper.py`**

Replace the entire contents of `scraper.py` with:

```python
#!/usr/bin/env python3
"""CLI for scraping a competitor's TikTok ads, ranking winners, and pulling video.

Examples:
    # resolve and cache a brand's business id (optional; scraping does this too)
    python scraper.py --resolve --brand "gymshark" --region GB

    # scrape the brand's own account, rank, keep the top 20, download + process
    python scraper.py --brand "gymshark" --region GB --days 30 --top 20 --download

Output is written under output/<brand>/ so a run can be resumed safely.
"""

import argparse
from pathlib import Path

from tiktok_ads import advertiser, download, extract, media, ranking, storage
from tiktok_ads.browser import (
    AdsLibraryBrowser,
    build_list_url,
    collect_list_rows,
    time_window_ms,
)

ROOT = Path(__file__).resolve().parent
OUTPUT_ROOT = ROOT / "output"
BRANDS_PATH = str(ROOT / "brands.json")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Scrape, rank, and download a competitor's TikTok ads."
    )
    parser.add_argument("--brand", default="", help="Brand name to target.")
    parser.add_argument("--region", default="GB", help="ISO country code, EU/EEA only.")
    parser.add_argument("--days", type=int, default=30, help="Look-back window in days.")
    parser.add_argument("--limit", type=int, default=100, help="Scrape pool size before ranking.")
    parser.add_argument("--top", type=int, default=20, help="How many ranked winners to keep.")
    parser.add_argument("--download", action="store_true", help="Download and process winner videos.")
    parser.add_argument("--resolve", action="store_true", help="Resolve the brand id and exit.")
    parser.add_argument("--headful", action="store_true", help="Show the browser window.")
    return parser.parse_args()


def resolve_brand(brand, region, browser):
    """Resolve a brand id, printing candidates and stopping if ambiguous."""
    result = advertiser.resolve(brand, region, browser, BRANDS_PATH)
    if result.get("ambiguous"):
        print("Could not auto-resolve the brand. Candidates found:")
        for cand in result.get("candidates", []):
            print(f"  {cand['biz_id']}  {cand['advertiser']}")
        print("Add the correct one to brands.json and re-run.")
        return None
    print(f"Resolved {brand} -> biz_id {result['biz_id']} ({result['exact_name']})")
    return result["biz_id"]


def enrich_row(row, brand, browser):
    """Visit the detail page for a row and merge in the richer fields."""
    detail = browser.extract_detail(row["detail_url"])
    row.update(detail)
    row["active_for_days"] = extract.parse_active_days(
        row.get("first_shown", ""), row.get("last_shown", "")
    )
    row["mentions_brand"] = extract.mentions_brand(
        brand, row.get("advertiser", ""), row.get("caption_text", "")
    )
    return row


def write_csv(path, fieldnames, rows):
    """Write rows to a fresh CSV at path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with storage.CsvWriter(str(path), fieldnames) as writer:
        for row in rows:
            writer.write_row(row)


def main():
    args = parse_args()
    paths = storage.brand_paths(OUTPUT_ROOT, args.brand)

    browser = AdsLibraryBrowser(headful=args.headful)
    try:
        browser.__enter__()

        biz_id = resolve_brand(args.brand, args.region, browser) if args.brand else ""
        if args.brand and biz_id is None:
            return
        if args.resolve:
            return

        start_ms, end_ms = time_window_ms(args.days)
        url = build_list_url(args.region, start_ms, end_ms, args.brand, biz_id=biz_id or "")
        print(f"Scraping: region={args.region}, brand={args.brand or 'all'}, days={args.days}")
        print(f"URL: {url}")

        browser.open_list(url)
        rows = collect_list_rows(browser, args.limit)
        print(f"Found {len(rows)} ads. Ranking and keeping top {args.top}.")

        ranked = ranking.rank_rows(rows)
        winners = ranked[: args.top] if args.top > 0 else ranked

        write_csv(paths["ads_csv"], storage.columns_for(detailed=False, ranked=True), ranked)

        for index, row in enumerate(winners, 1):
            enrich_row(row, args.brand, browser)
            print(f"  [{index}] {row.get('ad_id')} {row.get('advertiser', '')[:40]} score={row.get('winner_score')}")
        write_csv(paths["winners_csv"], storage.columns_for(detailed=True, ranked=True), winners)
        print(f"Wrote {paths['ads_csv']} and {paths['winners_csv']}")

        if args.download:
            saved = download.download_videos(browser, winners, paths["videos_dir"])
            print(f"Downloaded {len(saved)} videos.")
            for row in winners:
                video = paths["videos_dir"] / f"{row.get('ad_id')}.mp4"
                if video.exists():
                    media.process_video(
                        video,
                        paths["frames_dir"] / row["ad_id"],
                        paths["transcripts_dir"] / f"{row['ad_id']}.txt",
                    )
            print(f"Processed videos into {paths['frames_dir']} and {paths['transcripts_dir']}")
    finally:
        browser.close()

    print(f"Done. Brand folder: {paths['dir']}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Re-run the whole unit suite to confirm nothing regressed**

Run: `.venv/bin/python -m pytest -v`
Expected: all tests pass.

- [ ] **Step 4: Manual end-to-end run (small)**

Run: `.venv/bin/python scraper.py --brand "gymshark" --region GB --days 30 --limit 20 --top 3 --download --headful`
Expected: `output/gymshark/ads.csv`, `output/gymshark/winners.csv`, `output/gymshark/videos/*.mp4`, frames and transcripts folders populated (transcripts only if faster-whisper is installed). Confirm `ads.csv` has a `winner_score` column and `winners.csv` has `video_url` filled for downloaded ads.

If `video_url` is empty or downloads are 0 bytes, apply the network-capture follow-up noted in Task 7, Step 6 before continuing.

- [ ] **Step 5: Commit**

```bash
git add tiktok_ads/__init__.py scraper.py
git commit -m "feat: competitor pipeline CLI (resolve, rank, download, process)"
```

---

### Task 10: Analysis skill that writes `brief.md`

**Files:**
- Create: `skills/tiktok-ad-brief/SKILL.md`

**Interfaces:**
- Consumes: the per-brand folder produced by Task 9 (`winners.csv`, `frames/<ad_id>/*.jpg`, `transcripts/<ad_id>.txt`).
- Produces: `output/<brand>/brief.md`.

- [ ] **Step 1: Write the skill file**

Create `skills/tiktok-ad-brief/SKILL.md`:

```markdown
---
name: tiktok-ad-brief
description: Analyze a scraped competitor's winning TikTok ads and write a per-brand brief.md of creative patterns plus ready-to-shoot new-ad concepts. Use after running scraper.py with --download for a brand, when the user asks to "find patterns", "analyze the winners", or "make a brief" for a scraped brand.
---

# TikTok Ad Brief

Turn a scraped brand's winning ads into one `brief.md` a video-generation AI can build from.

## Inputs

Everything lives under `output/<brand>/` (produced by `scraper.py --download`):
- `winners.csv` — the top-ranked ads with `winner_score`, `caption_text`, `objective`, dates, `unique_users`.
- `frames/<ad_id>/*.jpg` — keyframes (hook, middle, end) for each winner.
- `transcripts/<ad_id>.txt` — spoken transcript when available (may be absent).

## Steps

1. Read `winners.csv`. Work through the ads in `winner_score` order (highest first).
2. For each ad: read its keyframes (look at hook frame, middle, end) and its transcript if present. Note the hook style, format (talking-head, demo, UGC, text-on-screen), pacing, on-screen text, copy angle, and CTA.
3. Find what the top winners share. Back every pattern with the specific `ad_id`s that show it. State plainly when transcripts were missing so the spoken-hook analysis is known to be partial.
4. Write `output/<brand>/brief.md` with exactly these two sections.

## brief.md structure

```
# <Brand> — Winning Ad Patterns

## Patterns
For each pattern: a name, a one-line description, the ad_ids that evidence it,
and why it likely works. Cover hooks, formats, pacing, on-screen text, copy
angles, and CTAs.

## New Ad Concepts
3 to 5 ready-to-shoot concepts built from the patterns above. Each concept:
- Hook line (first 2 seconds)
- Beats (shot-by-shot, 4 to 8 lines)
- On-screen text
- CTA
```

## Rules

- Ground every claim in the actual frames, transcripts, and CSV. Do not invent metrics; this data has no spend, CTR, or conversions.
- Keep concepts concrete enough that a video-generation tool (for example the higgsfield skills) can shoot them directly.
- Write one `brief.md` per brand. Do not overwrite another brand's folder.
```

- [ ] **Step 2: Verify the skill loads**

Confirm the file parses by checking the frontmatter has `name` and `description` and the body renders. If a local skill index/validator exists, run it; otherwise visually confirm the structure matches the other skill in `skills/tiktok-ad-report/SKILL.md`.

- [ ] **Step 3: Dry-run the skill against the scraped brand**

With `output/gymshark/` populated from Task 9, invoke `/tiktok-ad-brief gymshark` and confirm it writes `output/gymshark/brief.md` containing the two sections, with ad_id citations. Read the brief and sanity-check that the patterns reflect what the frames actually show.

- [ ] **Step 4: Commit**

```bash
git add skills/tiktok-ad-brief/SKILL.md
git commit -m "feat: tiktok-ad-brief analysis skill"
```

---

## Self-Review

**Spec coverage:**
- Targeting a brand's own account: Tasks 4 (exact URL), 5 (cache/selection), 6 (live resolve). Covered.
- Controlled count into CSV + folder: Tasks 3 (layout), 7 (download), 9 (`--top`, `ads.csv`/`winners.csv`). Covered.
- Winners by longevity (deterministic): Task 2. Covered.
- Video-aware analysis (frames + transcript): Task 8. Covered.
- AI patterns + per-brand brief.md: Task 10. Covered.
- Auto-resolve + cache with assisted fallback: Tasks 5-6 and `resolve_brand` in Task 9. Covered.
- Graceful degrade without whisper: Task 8 (`transcribe` returns None), tested. Covered.
- Build inside `tiktok_ads_scraper/`, don't touch report skill: Global Constraints. Covered.

**Placeholder scan:** No TBD/TODO. The one genuine unknown (id location) is handled by a concrete defensive extraction plus a validation spike, not a placeholder.

**Type consistency:** `build_list_url(..., biz_id="")`, `resolve(...) -> {biz_id, exact_name, region} | {ambiguous, candidates}`, `choose_candidate(brand, candidates) -> dict | None`, `download_videos(browser, rows, videos_dir) -> list[str]`, `process_video(video_path, frames_dir, transcript_path) -> {frames, transcript}`, `columns_for(detailed, ranked=False)`, `brand_paths(output_root, brand) -> dict`. Names used in Task 9 match their definitions in Tasks 2-8.

## Known risks carried into execution

1. Business-id location is confirmed only at Task 6 Step 4. The assisted fallback (`resolve_brand` printing candidates) keeps the tool usable if auto-detect is weak.
2. `video_url` may be a blob/streamed source rather than a direct URL. Task 7 Step 6 and Task 9 Step 4 both gate on this; the follow-up is to capture the network response instead of a request-context GET.
3. faster-whisper may have no wheel for Python 3.14. That is expected and handled: transcription is optional and the suite proves the frames-only path.
