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
