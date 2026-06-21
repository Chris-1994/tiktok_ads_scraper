# TikTok Ads Scraper

A small, standalone Python and Playwright tool that scrapes the public TikTok
Ads Library and turns the results into a clean PDF report. It runs on its own
from the command line, and it also ships with a Claude Code skill and a one-step
installer.

## Important: what this data is (and is not)

The TikTok Ads Library is a transparency tool that exists because of the EU
Digital Services Act (DSA). Keep these limits in mind before you rely on it:

- It covers EU and EEA regions only. There is no global data.
- It holds nothing from before October 2022.
- It does not contain ad spend, and it does not contain click-through rate.
- Reach is shown only as broad buckets (for example "10K-100K"), never exact
  numbers.
- Keyword search is fuzzy, so a brand search can return some unrelated ads.

Treat the output as directional competitive intelligence, not precise metrics.

## Features

- Scrape ads by advertiser keyword, region, and look-back window.
- Resume safely: each ad is written to disk the moment it is found, and a second
  run skips ads already saved.
- Optional detailed mode visits each ad's detail page for the caption,
  objective, "paid for by" line, and a video URL.
- Generate a styled, professional A4 PDF report from any scraped CSV, complete
  with reach badges, clickable detail links, and an honest caveats note.
- Headless by default, with a `--headful` flag when you want to watch.

## Quick start

Clone the repository, then run the installer:

```bash
git clone https://github.com/Chris-1994/tiktok_ads_scraper.git
cd tiktok_ads_scraper
./install.sh
```

The installer creates a virtual environment, installs the dependencies, downloads
chromium for Playwright, and installs the bundled Claude Code skill.

Prefer to do it by hand? Run these steps instead:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
```

## Usage

Activate the environment first (`source .venv/bin/activate`), then:

### Scrape a brand

```bash
python scraper.py --brand nike --region GB --limit 50
```

### Scrape everything in a region

```bash
python scraper.py --region FR --days 14 --limit 100
```

### Detailed scrape (richer fields, slower)

```bash
python scraper.py --brand adidas --region DE --detailed --limit 25
```

### Flags

| Flag         | Default | Meaning                                                   |
| ------------ | ------- | --------------------------------------------------------- |
| `--brand`    | (all)   | Advertiser keyword. Omit to scrape all advertisers.       |
| `--region`   | `GB`    | ISO country code, EU/EEA only (GB, FR, DE, AT, and more). |
| `--days`     | `30`    | Look-back window in days.                                 |
| `--limit`    | `50`    | Target number of ads to collect.                          |
| `--detailed` | off     | Also visit each ad's detail page for richer fields.       |
| `--headful`  | off     | Show the browser window instead of running headless.      |
| `--out`      | (auto)  | Output CSV path.                                          |

### Build a PDF report

```bash
python report.py --csv output/tiktok_ads_GB_nike.csv
python report.py --csv output/tiktok_ads_GB_nike.csv --title "Nike on TikTok"
```

The PDF lands next to the CSV by default. Try it against the bundled sample:

```bash
python report.py --csv examples/sample_ads.csv --out output/sample_report.pdf
```

## Claude Code skill

The repository bundles a Claude Code skill named `tiktok-ad-report`. Once
`install.sh` has run, you can simply ask Claude Code to scrape a brand from the
TikTok Ads Library and build a PDF report, and it will walk through the steps
for you. The skill lives in `skills/tiktok-ad-report/` and is copied into your
Claude Code skills folder during install.

## Output

- CSV data is written to `output/tiktok_ads_<REGION>_<brand-or-all>.csv`.
  - List mode columns: `ad_id, advertiser, first_shown, last_shown,
    unique_users, detail_url`.
  - Detailed mode adds: `caption_text, active_for_days, objective, paid_for_by,
    video_url, mentions_brand`.
- PDF reports are written next to their CSV with a `.pdf` extension.

The `output/` folder is git-ignored except for a `.gitkeep` placeholder, so your
scraped data stays local.

## Run in Docker (optional)

A Dockerfile is included for full isolation from your host machine. It builds on
the official Playwright Python image, so chromium is already present:

```bash
docker build -t tiktok-ads-scraper .
docker run --rm -v "$PWD/output:/app/output" tiktok-ads-scraper \
  --brand nike --region GB --limit 50
```

## Use responsibly

This tool reads public transparency data that TikTok itself publishes for the
EU and EEA. Please respect TikTok's Terms of Service, scrape gently (modest
limits, reasonable pauses), and use the data for legitimate research and
competitive analysis. You are responsible for how you use what you collect.

## License

MIT. See [LICENSE](LICENSE).
