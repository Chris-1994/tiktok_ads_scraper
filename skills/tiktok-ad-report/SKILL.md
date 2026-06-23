---
name: tiktok-ad-report
description: Scrape the TikTok Ads Library and build a PDF ad report. Use when the user wants to research a brand's TikTok ads, pull competitor ad creatives from the TikTok Ads Library, scrape TikTok ad transparency data, or produce a PDF report of TikTok ads for a region or advertiser.
---

# TikTok Ad Report

This skill scrapes the public TikTok Ads Library (an EU/EEA transparency tool)
and turns the results into a clean PDF report. The data is EU/EEA only, contains
nothing before October 2022, and does not include ad spend or click-through rate.

## Steps

### 1. Ensure dependencies are installed

Work from the repository root (the folder that contains `scraper.py`). Create a
virtual environment and install Playwright with chromium if that has not been
done yet:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
```

If the repository ships an `install.sh`, running `./install.sh` does all of the
above in one step.

### 2. Scrape and rank ads

Run the scraper with a brand keyword and a region (ISO country code, EU/EEA
only such as GB, FR, DE, AT):

```bash
python scraper.py --brand <BRAND> --region GB --top 20
```

Useful flags:

- `--top <N>` keeps the top N ranked winners (default 20).
- `--days <N>` sets the look-back window (default 30).
- `--download` also downloads the winner videos and extracts keyframes and
  transcripts (needs `ffmpeg`; transcripts need the optional `faster-whisper`).
- Omit `--brand` to scrape all advertisers in the region.

The scraper writes `output/<brand>/ads.csv` (all ads, ranked) and
`output/<brand>/winners.csv` (the top N), appending as it goes so a run can be
stopped and resumed.

### 3. Build the PDF report

Point the report tool at the CSV the scraper produced:

```bash
python report.py --csv output/<BRAND>/winners.csv
```

Add `--title "<your title>"` to set a custom heading, or `--out <path.pdf>` to
choose where the PDF lands. By default the PDF sits next to the CSV with a
`.pdf` extension.

## Where outputs land

- All ads (ranked): `output/<brand>/ads.csv`
- Top winners: `output/<brand>/winners.csv`
- PDF report: next to the CSV, with a `.pdf` extension
- With `--download`: `output/<brand>/videos/`, `frames/`, and `transcripts/`

## What to tell the user

Be honest about the limits of this data. Reach is shown only as broad buckets,
TikTok does not publish spend or click-through rate, and keyword search is
fuzzy, so some rows may be unrelated to the advertiser searched. The report
states these caveats on its first page.
