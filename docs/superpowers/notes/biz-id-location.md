# TikTok Ads Library: Where the Business ID Lives

**Date confirmed:** 2026-06-23  
**Verified by:** Task-6 live spike (headless Playwright, brand=gymshark, region=GB)

## Location

The numeric advertiser business id (`adv_biz_ids`) is exposed **exclusively on the ad detail page** (`/ads/detail/?ad_id=<id>`), in the href of the "See all ads" anchor link. It does NOT appear on the list page.

Example href found on a real detail page:

```
/ads?adv_name=carloshoyos1&region=all&query_type=2&adv_biz_ids=7394448526819852304
```

The same href also carries `adv_name=<handle>`, which is the exact TikTok advertiser handle.

## How `ADVERTISER_JS` Extracts It

`ADVERTISER_JS` runs on a detail page and queries `document.querySelectorAll('a[href]')`. It matches anchors whose href contains `adv_biz_ids=<5+ digits>` and pulls both the biz_id and adv_name URL parameters. A `<script>`-JSON fallback covers future layout changes.

## Spike Results (9 candidates found)

The list search for `adv_name=gymshark&query_type=1` returns ads whose **captions mention** "gymshark" — it is a keyword search, not an advertiser-name filter. Visiting the detail pages for those ads yielded real business ids:

| advertiser handle    | biz_id                |
|----------------------|-----------------------|
| carloshoyos1         | 7394448526819852304   |
| carlo.massimo.coac   | 7601933089027129361   |
| alfiehc23            | 7611434229989195793   |
| chloeeorose          | 7631294465713504272   |
| jacob.coys2          | 7591842573363232785   |
| baggers074           | 7336254342225444866   |
| een2857              | 7571050133391933441   |
| joeyjosephh          | 7570829625962659856   |
| ms.kabz              | 7463355829610135569   |

None of these handles match "gymshark" — they are user-generated content creators mentioning the brand, not the Gymshark corporate TikTok advertiser account.

## Implication for `resolve()`

When `search_advertisers('gymshark', 'GB')` is called, `choose_candidate` correctly returns `None` (no exact or substring match for "gymshark" in any handle) and `resolve()` returns `{"ambiguous": True, "candidates": [...]}`. This is correct behavior — the human must find one Gymshark-run ad and call `search_advertisers` on that detail page directly, or supply the biz_id manually via `save_brand()`.

To locate the official Gymshark account, an operator should:
1. Find an ad that is genuinely **run by** Gymshark (not UGC).
2. Visit its detail page; the "See all ads" link will carry Gymshark's real `adv_biz_ids`.
3. Call `save_brand(path, 'gymshark', <biz_id>, <exact_name>, 'GB')` to seed the cache.

After that, `resolve('gymshark', 'GB', browser, path)` returns the cached entry instantly.

## Video Download

**Date confirmed:** 2026-06-23  
**Verified by:** Task-7 live sanity check (headless Playwright, brand=gymshark, region=GB, 30-day window)

The `video_url` returned by `DETAIL_JS` on a real ad detail page is a **direct HTTPS URL** (not a `blob:` or streamed source). The URL points to a TikTok CDN proxy endpoint on `library.tiktok.com/api/v1/cdn/...`.

Calling `browser.fetch_bytes(video_url)` via the Playwright session request context:
- Returned **791,202 bytes**
- First 12 bytes (hex): `000000206674797069736f6d` — a valid ISO Base Media (MP4) **ftyp box**
- **Conclusion: the request-context GET approach works.** The session cookies/headers carried by the Playwright context are sufficient to download the video.

No follow-up network-capture fallback is needed for the current CDN format.

## Fields NOT Present in List Page HTML

Checked the full rendered HTML of the list page; none of the following appeared:  
`adv_biz_ids`, `advertiser_id`, `business_id`, `adv_id`, `biz_id`, `advId`.

The biz_id is only rendered server-side into the detail page's anchor href.
