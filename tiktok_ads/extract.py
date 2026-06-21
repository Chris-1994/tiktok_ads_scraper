"""DOM extraction logic for the TikTok Ads Library.

The TikTok Ads Library renders with obfuscated, randomized CSS class names, so
class selectors are unreliable. The JavaScript snippets below walk the DOM by
stable signals instead: anchor hrefs that carry an "ad_id=" parameter, and the
visible text of each ad card. Keep these snippets as is unless the site changes.
"""

from datetime import datetime


# JavaScript that runs in the page context and returns a list of ad rows.
LIST_JS = r"""
() => {
  const links = [...document.querySelectorAll('a[href*="ad_id="]')];
  const seen = new Set();
  const rows = [];
  for (const link of links) {
    const href = link.getAttribute('href');
    const id = (href.match(/ad_id=(\d+)/) || [])[1] || '';
    if (!id || seen.has(id)) continue;
    seen.add(id);
    let card = link;
    for (let i = 0; i < 8 && card.parentElement; i++) {
      card = card.parentElement;
      if (/First shown/i.test(card.innerText) && /Last shown/i.test(card.innerText)) break;
    }
    const t = card.innerText || '';
    const g = re => ((t.match(re) || [,''])[1] || '').trim();
    const advertiser = (t.split('\n').map(s=>s.trim()).filter(Boolean)
      .find(l => l !== 'Ad' && !/^(First shown|Last shown|Unique users seen)/i.test(l)) || '');
    rows.push({
      ad_id: id, advertiser,
      first_shown: g(/First shown:\s*([0-9/]+)/i),
      last_shown: g(/Last shown:\s*([0-9/]+)/i),
      unique_users: g(/Unique users seen:\s*([^\n]+)/i),
      detail_url: 'https://library.tiktok.com' + href
    });
  }
  return rows;
}
"""


# JavaScript that finds and clicks the "View more" control. Returns true if a
# button was clicked, false if it fell back to scrolling the page.
VIEW_MORE_JS = r"""
() => {
  const els = [...document.querySelectorAll('button, div, span, a')];
  const btn = els.find(e => /view more/i.test(e.innerText || '') && (e.innerText || '').length < 30);
  if (btn) { btn.scrollIntoView({block:'center'}); btn.click(); return true; }
  window.scrollTo(0, document.body.scrollHeight);
  return false;
}
"""


# JavaScript that runs on a single ad detail page and returns richer fields.
DETAIL_JS = r"""
() => {
  const t = document.body.innerText || '';
  const g = re => ((t.match(re) || [,''])[1] || '').trim();
  const v = document.querySelector('video');
  return {
    caption_text: g(/Ad caption\s*\n?\s*([^\n]+)/i),
    objective: g(/(?:Advertising objectives?|Objective)s?:?\s*([^\n]+)/i),
    paid_for_by: g(/paid for by:?\s*([^\n]+)/i),
    video_url: v ? (v.getAttribute('src') || '') : ''
  };
}
"""


def parse_active_days(first_shown, last_shown):
    """Return whole days between two MM/DD/YYYY dates.

    Same day returns 0. Unparseable input returns an empty string so the CSV
    cell stays blank rather than showing a misleading number.
    """
    fmt = "%m/%d/%Y"
    try:
        start = datetime.strptime(first_shown.strip(), fmt)
        end = datetime.strptime(last_shown.strip(), fmt)
    except (ValueError, AttributeError):
        return ""
    return (end - start).days


def mentions_brand(brand, advertiser, caption_text):
    """Return True when the brand keyword appears in the advertiser or caption.

    Comparison is case insensitive. Returns False when no brand is supplied.
    """
    if not brand:
        return False
    needle = brand.lower()
    haystack = ((advertiser or "") + " " + (caption_text or "")).lower()
    return needle in haystack
