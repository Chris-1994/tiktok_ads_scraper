#!/usr/bin/env bash
# Set up the scraper and install the bundled Claude Code skill.
# Safe to run more than once: each step is idempotent.
set -euo pipefail

# Resolve the repo root so the script works from any working directory.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "==> Setting up virtual environment (.venv)"
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

echo "==> Installing Python dependencies"
pip install --upgrade pip >/dev/null
pip install -r requirements.txt

echo "==> Installing chromium for Playwright"
python -m playwright install chromium

echo "==> Installing the Claude Code skill"
SKILL_SRC="$SCRIPT_DIR/skills/tiktok-ad-report"
SKILL_DEST="$HOME/.claude/skills/tiktok-ad-report"
mkdir -p "$SKILL_DEST"
cp -R "$SKILL_SRC/." "$SKILL_DEST/"
echo "    Skill installed to $SKILL_DEST"

echo ""
echo "==> Done. Next steps:"
echo "    1. Activate the environment:   source .venv/bin/activate"
echo "    2. Run a scrape:               python scraper.py --brand nike --region GB"
echo "    3. Build a PDF report:         python report.py --csv output/tiktok_ads_GB_nike.csv"
