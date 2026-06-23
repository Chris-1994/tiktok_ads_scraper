# TikTok Ads Scraper — guide for Claude

A standalone Python + Playwright tool that scrapes the **public TikTok Ads
Library** (an EU/EEA transparency tool), ranks a brand's "winning" ads, can
download the videos, and builds a PDF report. No API keys or accounts are
needed — it reads public data.

## Setup

From the repository root, run the one-step installer:

```bash
./install.sh
```

It creates `.venv`, installs dependencies, downloads chromium for Playwright,
and installs the two bundled skills into `~/.claude/skills/`. Activate the
environment before running commands:

```bash
source .venv/bin/activate
```

To confirm everything works: `python -m pytest`.

## Running the scraper

```bash
# Scrape a brand, rank winners, keep the top 20
python scraper.py --brand gymshark --region GB --days 30 --top 20

# Also download winner videos + extract keyframes/transcripts
python scraper.py --brand gymshark --region GB --top 20 --download
```

Flags: `--brand` (omit to scrape all), `--region` (ISO code, EU/EEA only),
`--days` (look-back, default 30), `--limit` (pool before ranking, default 100),
`--top` (winners to keep, default 20), `--download`, `--resolve` (resolve the
brand id and exit), `--headful` (show the browser).

Output goes to `output/<brand>/`: `ads.csv` (all ads, ranked), `winners.csv`
(top N), and with `--download` also `videos/`, `frames/<ad_id>/`, and
`transcripts/`.

`--download` needs `ffmpeg` on PATH; transcripts also need the optional
`faster-whisper` dependency (the run degrades to frames-only without it).

## Building a report

```bash
python report.py --csv output/<brand>/winners.csv --title "<title>"
```

## Bundled skills

- **tiktok-ad-report** — scrape a brand and build a PDF report.
- **tiktok-ad-brief** — after a `--download` run, analyze the winners' frames and
  transcripts and write `output/<brand>/brief.md` plus a styled `brief.pdf`
  (creative patterns plus ready-to-shoot new-ad concepts). Render the PDF with
  `python brief_pdf.py --md output/<brand>/brief.md`.

## Data caveats (tell the user)

EU/EEA regions only, nothing before October 2022, no ad spend, no click-through
rate, reach only as broad buckets, and keyword search is fuzzy. Treat results as
directional competitive intelligence, not precise metrics. Scrape gently and
respect TikTok's Terms of Service.
