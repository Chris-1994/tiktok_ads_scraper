# TikTok Competitor Ad Intelligence — Design

Date: 2026-06-23
Status: Approved (brainstorming), ready for implementation planning
Repo: `tiktok_ads_scraper/` (own git repo, remote `github.com/Chris-1994/tiktok_ads_scraper`, branch `main`)

## Goal

Extend the existing TikTok Ads Library scraper so it can, for a named competitor brand:

1. Target that brand's own ad account precisely (not a fuzzy keyword match).
2. Download a controlled number of the brand's best ads into a per-brand CSV and folder, including the actual video files.
3. Let an AI find the patterns across the winning ads (using the real creative, not just metadata).
4. Produce one `brief.md` per brand: the extracted patterns plus ready-to-shoot new-ad concepts, written so a downstream video-generation AI can build from it.

## Constraints carried from prior work

These are confirmed facts about the data source, recorded so the design does not promise what the library cannot give:

- The TikTok Ads Library (`library.tiktok.com/ads`) is the EU/EEA DSA transparency tool. No spend, cost, CTR, clicks, conversions, or exact impressions are ever published. The only performance-adjacent signals are: how long an ad ran (`first_shown` to `last_shown`), and a bucketed "unique users seen" reach range (for example `0-1K`, `700K-800K`).
- CSS class names are obfuscated. Extraction anchors on `a[href*="ad_id="]` and parses visible text. Results are JS-rendered, so a render wait is required.
- The "Total ads" counter is display-capped at 1,000.
- `region=` is an ISO country code (EU/EEA only; `GB` works for the UK). `adv_name=` with `query_type=1` is a fuzzy caption match. `adv_biz_ids=` is the exact advertiser-account isolation param and needs the brand's business id.

## Decisions (from brainstorming)

- Winners are chosen by a deterministic longevity-weighted score, not by AI judgment.
- Analysis is video-aware: download the MP4s, extract keyframes and a transcript, then have the AI read the actual creative.
- Brand targeting auto-resolves a brand name to its business id and caches it, with an assisted fallback when resolution is ambiguous.
- The pattern analysis and brief generation run as a Claude Code skill (no API key), reading the per-brand folder.
- Media processing may depend on `ffmpeg` and `faster-whisper` locally, degrading gracefully to frames-only if Whisper is absent.
- All work is built inside the existing `tiktok_ads_scraper/` package.

## Architecture: four composable stages

Each stage does one job and hands off through the per-brand folder on disk. Any stage can run alone or be re-run without repeating earlier ones.

```
resolve  ->  scrape + rank  ->  download + process  ->  analyze (skill)
```

- `resolve` finds and caches the brand's business id.
- `scrape + rank` collects the brand's ads, computes the winner score, writes `ads.csv` and `winners.csv`.
- `download + process` downloads the top-N winner videos, then extracts keyframes and a transcript for each.
- `analyze` is the Claude Code skill that reads the folder and writes `brief.md`.

An optional `run.py` orchestrator chains all four for a one-command run. A monolithic single command and a fully API-driven pipeline were both considered and rejected: the monolith couples scraping to ffmpeg/whisper and makes failures all-or-nothing, and the API pipeline was ruled out by the no-API-key decision.

## Per-brand folder layout (the data contract)

```
output/<brand>/
  ads.csv              # every scraped ad, includes winner_score
  winners.csv          # top-N rows after ranking (the download set)
  videos/<ad_id>.mp4   # downloaded creatives
  frames/<ad_id>/*.jpg # keyframes per ad (hook, middle, end)
  transcripts/<ad_id>.txt
  brief.md             # AI output: patterns + new-ad concepts
brands.json            # cache: { "<brand>": { biz_id, exact_name, region } }
```

`<brand>` is a lowercased, hyphenated slug, consistent with the existing default output naming.

## Modules (each small, one responsibility)

| File | New/Edit | Responsibility |
|---|---|---|
| `tiktok_ads/advertiser.py` | new | Resolve brand name to exact `adv_biz_id`; read/write `brands.json` cache |
| `tiktok_ads/ranking.py` | new | Parse reach bucket to a number, compute `winner_score`, sort, select top-N |
| `tiktok_ads/download.py` | new | Download winner MP4s into `videos/` |
| `tiktok_ads/media.py` | new | ffmpeg keyframe extraction and optional Whisper transcription |
| `tiktok_ads/browser.py` | edit | Send `adv_biz_ids` when a biz id is known (exact mode); keep fuzzy mode |
| `tiktok_ads/storage.py` | edit | Per-brand folder paths and the `winner_score` column |
| `scraper.py` | edit | Add `--top`, exact-brand mode, optional `--download` |
| `skills/tiktok-ad-brief/SKILL.md` | new | Analysis skill that writes `brief.md` |

The existing `tiktok-ad-report` PDF skill and `tiktok_ads/report.py` are left untouched.

## Winner score (deterministic)

No AI in the ranking. Reach buckets map to a numeric midpoint (for example `"700K-800K"` -> `750000`, `"0-1K"` -> `500`). Then:

```
winner_score = active_for_days * log10(reach_midpoint + 10)
```

Rationale: a long-running ad is the strongest available proxy for "this converts," because advertisers keep paying for what works. Reach acts as a tie-breaker so a long-running ad with wide reach ranks above an equally old ad few people saw. Before scoring, rows are filtered to ads whose `last_shown` is recent (still running), so the ranking reflects current winners rather than retired ones. The mapping table and the formula live in one documented function in `ranking.py` so the weighting is easy to tune later.

`active_for_days` already exists via `extract.parse_active_days`. Ranking reuses it.

## Brand-id auto-resolve

`advertiser.resolve(brand, region)`:

1. If `brands.json` already has the brand, return the cached id.
2. Otherwise fuzzy-search the brand name (the current `adv_name` + `query_type=1` path), collect the rendered results, and group them by exact advertiser name.
3. Pick the advertiser whose name best matches the requested brand, read its business id, and cache `{ biz_id, exact_name, region }` to `brands.json`.
4. If no single candidate is clearly best, print the candidate advertisers and their ids and let the user choose once; the chosen entry is cached too.

A normal brand scrape calls `resolve` automatically and uses the cached id when present, so exact targeting is the default. The standalone `--resolve` command is only a way to pre-populate or refresh the cache without scraping.

Known technical risk: the exact location of the business id in the page is not yet confirmed. It may be in the advertiser link or only in an XHR payload. The first implementation task is a short live-page investigation to confirm where the id is exposed. The assisted fallback in step 4 means the feature is usable even if fully automatic detection proves unreliable. Once an id is cached, scraping uses `adv_biz_ids` for exact isolation.

## Video-aware processing

`media.py` runs after download, per winner video:

- Keyframes: `ffmpeg` extracts a small set of frames (hook at the start, one or two in the middle, one near the end) into `frames/<ad_id>/`. Claude reads these images directly during analysis, including any burned-in on-screen text.
- Transcript: `faster-whisper` transcribes the audio to `transcripts/<ad_id>.txt`. It runs locally on Apple Silicon with a one-time model download (about 150MB).
- Graceful degrade: if `faster-whisper` is not installed, processing still extracts frames and skips the transcript, so analysis continues on visuals and burned-in captions alone. The brief notes when transcripts were unavailable.

Both tools are external. `ffmpeg` is required for frames; `faster-whisper` is optional. The implementation checks for them and reports a clear message if `ffmpeg` is missing.

## The skill and brief.md

`skills/tiktok-ad-brief/SKILL.md` defines `/tiktok-ad-brief <brand>`. It reads `winners.csv`, the per-ad frames, and the transcripts for that brand, then writes `output/<brand>/brief.md` with two parts:

1. Pattern findings: the hook types, formats, pacing, copy angles, on-screen text style, and CTA style that the winners share, with the ad ids that evidence each pattern.
2. New-ad concepts: several ready-to-shoot scripts derived from those patterns, each as hook line, beats, on-screen text, and CTA.

The brief is structured so a downstream video-generation AI (for example the existing higgsfield skills) can build directly from it. One `brief.md` per brand.

## CLI / usage

```
# one-time or cached automatically
python scraper.py --resolve --brand "gymshark" --region GB

# scrape that brand's own account, rank, keep the top 20, download + process them
python scraper.py --brand "gymshark" --region GB --days 30 --top 20 --download

# write the brief
/tiktok-ad-brief gymshark
```

`--limit` stays as the scrape pool size; `--top` is the number of ranked winners to download. Without `--download`, the run stops after writing `ads.csv` and `winners.csv`.

## Out of scope (YAGNI)

- No database. CSV and folders are sufficient.
- No scheduler or recurring runs.
- No auto-posting or auto-generation into higgsfield. The brief is the handoff point.
- No changes to the existing PDF report skill.

## Testing approach

- `ranking.py`: unit tests for reach-bucket parsing (including malformed buckets) and the score ordering. Pure functions, no browser.
- `advertiser.py`: unit test the cache read/write and the candidate-selection logic against captured fixture rows; the live search is exercised manually during the id-location investigation.
- `media.py`: test the ffmpeg and whisper wrappers against one short sample video, and confirm the no-whisper path degrades to frames-only.
- `scraper.py`: a small end-to-end run against one brand with a low `--top` to confirm the folder layout and resume behavior.

## Open risks

1. Business id location in the page is unconfirmed (mitigated by the assisted fallback).
2. Video URLs from the detail page may be time-limited or require headers; download must be verified against a real ad and may need to reuse the browser session rather than a bare HTTP GET.
3. Local Whisper performance on longer videos; mitigated because ads are short and transcription is optional.
