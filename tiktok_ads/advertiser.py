"""Resolve a brand name to its exact TikTok advertiser business id.

The resolved ids are cached in a brands.json file so a brand is only looked up
once. This module holds the pure cache and candidate-selection logic; the live
browser search is added as resolve() in a later step.
"""

import json
import os


def load_brands(path):
    """Return the cached brand map, or an empty dict if missing or invalid."""
    if not path or not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as handle:
        try:
            return json.load(handle)
        except json.JSONDecodeError:
            return {}


def cached_biz_id(path, brand):
    """Return the cached business id for a brand, or None."""
    entry = load_brands(path).get((brand or "").strip().lower())
    return entry.get("biz_id") if entry else None


def save_brand(path, brand, biz_id, exact_name, region):
    """Write or update one brand entry in the cache file."""
    data = load_brands(path)
    data[(brand or "").strip().lower()] = {
        "biz_id": biz_id,
        "exact_name": exact_name,
        "region": region,
    }
    parent = os.path.dirname(os.path.abspath(path))
    os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)


def choose_candidate(brand, candidates):
    """Pick the single best advertiser candidate, or None when ambiguous.

    Each candidate is {"advertiser": str, "biz_id": str}. Preference order:
    one exact (case-insensitive) name match, then one substring match, then a
    single distinct id across all candidates. Anything else is ambiguous.
    """
    needle = (brand or "").strip().lower()
    valid = [c for c in candidates if c.get("biz_id")]
    if not valid:
        return None

    exact = [c for c in valid if c["advertiser"].strip().lower() == needle]
    if exact:
        ids = {c["biz_id"] for c in exact}
        return exact[0] if len(ids) == 1 else None

    contains = [c for c in valid if needle and needle in c["advertiser"].strip().lower()]
    if len(contains) == 1:
        return contains[0]

    ids = {c["biz_id"] for c in valid}
    if len(ids) == 1:
        return valid[0]
    return None
