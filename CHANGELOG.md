# Changelog

All notable changes to this project are documented in this file.

## v0.1.0 (2026-06-21)

Initial release.

### Added

- Standalone `scraper.py` command line tool that scrapes the public TikTok Ads
  Library by advertiser keyword, region, and look-back window.
- Quick list mode and an optional `--detailed` mode that visits each ad's detail
  page for the caption, objective, "paid for by" line, and video URL.
- Safe resume: every ad is written the moment it is found, and re-running skips
  ads already saved.
- Headless by default, with a `--headful` flag for watching the run.
- `report.py`, which turns any scraped CSV into a styled A4 PDF report with reach
  badges, clickable detail links, and an honest caveats note.
- A bundled Claude Code skill, `tiktok-ad-report`.
- `install.sh`, which sets up the virtual environment, installs Playwright
  chromium, and installs the Claude Code skill.
- An optional Dockerfile for running fully isolated from the host machine.
