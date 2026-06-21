"""CSV storage helpers: resume support and incremental append.

The scraper appends each ad to disk as soon as it is found, so a long run can
be interrupted and resumed without losing progress. On resume we read back the
ad_ids that are already saved and skip them.
"""

import csv
import os


LIST_COLUMNS = [
    "ad_id",
    "advertiser",
    "first_shown",
    "last_shown",
    "unique_users",
    "detail_url",
]

DETAIL_COLUMNS = [
    "caption_text",
    "active_for_days",
    "objective",
    "paid_for_by",
    "video_url",
    "mentions_brand",
]


def columns_for(detailed):
    """Return the ordered column list for the chosen mode."""
    if detailed:
        return LIST_COLUMNS + DETAIL_COLUMNS
    return list(LIST_COLUMNS)


def load_existing_ids(path):
    """Return a set of ad_ids already present in the CSV at path.

    Returns an empty set when the file does not exist yet.
    """
    existing = set()
    if not path or not os.path.exists(path):
        return existing
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            ad_id = (row.get("ad_id") or "").strip()
            if ad_id:
                existing.add(ad_id)
    return existing


class CsvWriter:
    """Incremental CSV writer that writes the header exactly once.

    The header is written when the target file is new or empty. Existing files
    are opened in append mode so a resumed run continues cleanly.
    """

    def __init__(self, path, fieldnames):
        self.path = path
        self.fieldnames = fieldnames
        parent = os.path.dirname(os.path.abspath(path))
        os.makedirs(parent, exist_ok=True)
        is_new = not os.path.exists(path) or os.path.getsize(path) == 0
        self._handle = open(path, "a", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._handle, fieldnames=fieldnames)
        if is_new:
            self._writer.writeheader()
            self._handle.flush()

    def write_row(self, row):
        """Write a single row, keeping only known columns, then flush to disk."""
        clean = {key: row.get(key, "") for key in self.fieldnames}
        self._writer.writerow(clean)
        self._handle.flush()

    def close(self):
        """Close the underlying file handle."""
        if self._handle:
            self._handle.close()
            self._handle = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
