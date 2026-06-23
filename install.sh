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

echo "==> Installing the bundled Claude Code skills"
for skill_dir in "$SCRIPT_DIR"/skills/*/; do
  skill_name="$(basename "$skill_dir")"
  skill_dest="$HOME/.claude/skills/$skill_name"
  mkdir -p "$skill_dest"
  cp -R "$skill_dir." "$skill_dest/"
  echo "    Installed skill: $skill_name -> $skill_dest"
done

echo ""
echo "==> Done. Next steps:"
echo "    1. Activate the environment:   source .venv/bin/activate"
echo "    2. Scrape and rank a brand:    python scraper.py --brand gymshark --region GB --top 20"
echo "    3. Build a PDF report:         python report.py --csv output/gymshark/winners.csv"
echo ""
echo "    Or open Claude Code in this folder and ask it to run a scrape for you."
