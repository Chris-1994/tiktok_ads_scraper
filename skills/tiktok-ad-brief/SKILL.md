---
name: tiktok-ad-brief
description: Analyze a scraped competitor's winning TikTok ads and write a per-brand brief.md of creative patterns plus ready-to-shoot new-ad concepts. Use after running scraper.py with --download for a brand, when the user asks to "find patterns", "analyze the winners", or "make a brief" for a scraped brand.
---

# TikTok Ad Brief

Turn a scraped brand's winning ads into one `brief.md` a video-generation AI can build from.

## Inputs

Everything lives under `output/<brand>/` (produced by `scraper.py --download`):
- `winners.csv` — the top-ranked ads with `winner_score`, `caption_text`, `objective`, dates, `unique_users`.
- `frames/<ad_id>/*.jpg` — keyframes (hook, middle, end) for each winner.
- `transcripts/<ad_id>.txt` — spoken transcript when available (may be absent).

## Steps

1. Read `winners.csv`. Work through the ads in `winner_score` order (highest first).
2. For each ad: read its keyframes (look at hook frame, middle, end) and its transcript if present. Note the hook style, format (talking-head, demo, UGC, text-on-screen), pacing, on-screen text, copy angle, and CTA.
3. Find what the top winners share. Back every pattern with the specific `ad_id`s that show it. State plainly when transcripts were missing so the spoken-hook analysis is known to be partial.
4. Write `output/<brand>/brief.md` with exactly these two sections.

## brief.md structure

```
# <Brand> — Winning Ad Patterns

## Patterns
For each pattern: a name, a one-line description, the ad_ids that evidence it,
and why it likely works. Cover hooks, formats, pacing, on-screen text, copy
angles, and CTAs.

## New Ad Concepts
3 to 5 ready-to-shoot concepts built from the patterns above. Each concept:
- Hook line (first 2 seconds)
- Beats (shot-by-shot, 4 to 8 lines)
- On-screen text
- CTA
```

## Rules

- Ground every claim in the actual frames, transcripts, and CSV. Do not invent metrics; this data has no spend, CTR, or conversions.
- Keep concepts concrete enough that a video-generation tool (for example the higgsfield skills) can shoot them directly.
- Write one `brief.md` per brand. Do not overwrite another brand's folder.
