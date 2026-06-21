# Minimal container that ships the scraper with chromium already installed.
# The Playwright base image bundles the browser and its system dependencies,
# which keeps the host machine clean.
FROM mcr.microsoft.com/playwright/python:v1.48.0-jammy

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Default to the scraper. Override the command to run report.py instead, e.g.
#   docker run --rm -v "$PWD/output:/app/output" IMAGE python report.py --csv output/your.csv
ENTRYPOINT ["python", "scraper.py"]
