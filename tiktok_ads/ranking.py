"""Deterministic winner ranking for scraped ads.

No AI in this path. A winning ad is approximated by longevity (how many days
it ran), because advertisers keep paying for ads that convert. Reach acts as a
tie breaker so an equally old ad seen by more people ranks higher.

    winner_score = active_days * log10(reach_midpoint + 10)

The reach value is a bucketed range like "700K-800K"; it is reduced to a
numeric midpoint before scoring.
"""

import math
import re

from . import extract

_SUFFIX = {"": 1, "K": 1_000, "M": 1_000_000, "B": 1_000_000_000}


def parse_reach_bucket(bucket):
    """Return the numeric midpoint of a reach range like "700K-800K".

    Returns 0 when no numbers can be read (for example "N/A" or "").
    """
    if not bucket:
        return 0
    numbers = []
    for value, suffix in re.findall(r"([\d.]+)\s*([KMB]?)", bucket.upper()):
        try:
            numbers.append(float(value) * _SUFFIX[suffix])
        except (ValueError, KeyError):
            continue
    if not numbers:
        return 0
    return int(sum(numbers) / len(numbers))


def compute_score(active_days, reach_midpoint):
    """Longevity weighted score. Invalid or negative days score 0.0."""
    try:
        days = int(active_days)
    except (ValueError, TypeError):
        return 0.0
    if days < 0:
        days = 0
    return round(days * math.log10(reach_midpoint + 10), 4)


def rank_rows(rows):
    """Add a winner_score to each row and return rows sorted high to low."""
    for row in rows:
        active_days = extract.parse_active_days(
            row.get("first_shown", ""), row.get("last_shown", "")
        )
        reach = parse_reach_bucket(row.get("unique_users", ""))
        row["winner_score"] = compute_score(active_days, reach)
    return sorted(rows, key=lambda r: r["winner_score"], reverse=True)


def select_top(rows, top):
    """Rank rows and return the top N. A non-positive top returns all rows."""
    ranked = rank_rows(rows)
    if top and top > 0:
        return ranked[:top]
    return ranked
