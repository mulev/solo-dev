# ASO Playbook

App Store Optimization reference for Apple App Store and Google Play Store. Covers store algorithm mechanics, a self-serve research pipeline using `/browser-use`, metadata optimization, creative strategy, ratings, A/B testing, and monitoring.

---

## Contents

1. [How the Algorithms Work](#how-the-algorithms-work)
2. [Research Pipeline](#research-pipeline) — Phases 1-6
3. [Output Schemas](#output-schemas)
4. [Metadata Optimization Reference](#metadata-optimization-reference)
5. [Creative Optimization](#creative-optimization)
6. [Ratings and Reviews](#ratings-and-reviews)
7. [A/B Testing on Stores](#ab-testing-on-stores)
8. [Monitoring](#monitoring)

---

## How the Algorithms Work

> **Freshness warning:** Algorithm behavior and field limits change. Apple and Google update ranking signals, character limits, and indexing rules without public announcement. Before building a strategy on the mechanics below, verify against current platform documentation (Apple Developer — App Store, Google Play Console Help) or recent ASO community reports. When a mechanic described here conflicts with observed store behavior, trust the observation.

### Apple App Store
- Indexed fields: app name (30 chars), subtitle (30 chars), keyword field (100 chars, comma-separated, hidden from users), in-app purchase names
- NOT indexed: long description, developer name (minimal weight)
- Ranking signals: install rate from search impressions, ratings volume, ratings average, ratings recency
- Velocity: a spike in downloads for a keyword improves rank for that keyword; sustained performance is required to hold it
- Localization: each country storefront has its own independent keyword field — full 100-char capacity per locale, not shared

### Google Play Store
- Indexed fields: app title (30 chars), short description (80 chars), long description (4000 chars, first ~250 chars weighted most), developer name
- No hidden keyword field — all optimization is in visible copy
- Keyword density in long description: 3–5 mentions of the primary keyword is the practical ceiling before spam penalty risk
- Ranking signals: install rate, uninstall rate, ratings, session length, retention

---

## Research Pipeline

Run this pipeline before writing any metadata. It replaces paid tools (Sensor Tower, AppFollow, MobileAction) by doing the same scraping directly with `/browser-use`.

**Startup:** follow the Pipeline Startup Protocol in `references/research-storage.md`. Read the product foundation to extract: product identity, value prop, features, audiences, positioning, existing ASO metadata, app store URLs, locale priorities.

All paths below are relative to the research run directory: `{project_root}/research/aso-{YYYY-MM-DDTHH-MM-SS}/`

---

### Phase 1 — Keyword Generation

Goal: produce a **tiered shortlist** of the best keywords, not the longest list. The App Store keyword field is 100 characters — quality beats quantity.

**Before generating:** read `product-foundation.json` → `learned` section. If `category_vocabulary` or `competitive_set` exist and are < 3 months old, use them as seed input and focus on discovering NEW terms. If > 6 months old or absent, generate from scratch.

**Generation sources (run in order):**

1. **Product-derived terms** — extract from `product-foundation.json`: feature names, use case verbs ("track", "scan", "manage"), audience descriptors ("for teams", "for students"), outcome statements ("lose weight", "learn faster"), problem descriptions. If `learned.category_vocabulary` exists, add its `user_search_terms` as additional seeds.
2. **Autocomplete scraping** — use `/browser-use` to open the App Store (and Play Store) search, type each seed term from step 1, and capture every autocomplete suggestion. These are real user queries. This is the highest-signal source.
3. **Competitor metadata** — collect titles and subtitles of the top apps found in Phase 2 and mine them for keyword candidates. (Run Phase 2 with a small seed set first if needed, then return here.)

**Tiering:**

| Tier | Profile | Role |
|---|---|---|
| Tier 1 | High-intent, moderate competition | Anchor in title and subtitle; primary ranking targets |
| Tier 2 | Specific use cases, lower competition | Secondary targets; fill keyword field and description |
| Tier 3 | Longtail, niche | Keyword field fill; often convert better due to query specificity |

**Apple App Store keyword field rules:**
- 100 characters maximum, commas as separators, no spaces after commas
- No words already in the title or subtitle (redundant — Apple indexes them separately)
- No competitor brand names (policy violation)
- No plurals and singulars of the same word — Apple indexes both from one form
- Use every character — unused capacity is wasted ranking potential
- Commas separate terms; spaces within a term create phrase matching

**Save:** `phase1-keywords-raw.json` (full list, each entry annotated with source), `phase1-keywords-tiered.json` (tiered shortlist with `tier1`, `tier2`, `tier3` arrays). Follow the Phase Transition Protocol in `references/research-storage.md` — present tiered keywords for user review before proceeding.

---

### Phase 2 — Search Landscape

For each Tier 1 and Tier 2 keyword, search the store and collect the top 20 results. Also browse Top Free and Top Grossing charts for every relevant category to catch high-volume apps that rank through browse traffic rather than keyword search.

**Per app, extract:**
- App name, developer name
- Ratings average and ratings count
- Category
- Price and whether in-app purchases exist
- Rank position for this keyword
- App store URL

**After collection:**
- Deduplicate apps across all keywords
- Score each unique app: `appearance_frequency × ratings_count`
- Rank all unique apps by this score — this is your competitive priority list

**Parallelization:** safe to run multiple keyword searches concurrently (3–5 at a time). Avoid more than 5 simultaneous requests to the same store.

**Save:** `phase2-keyword-results.json` (object keyed by keyword, each value = ordered array of top 20 apps), `phase2-landscape.json` (deduplicated app array sorted by opportunity score). Follow the Phase Transition Protocol — present the top 20 apps and confirm which to deep-dive before starting Phase 3.

---

### Phase 3 — App Deep Research

Take the top 20 apps by score from Phase 2. Research them in two tiers of depth.

**Tier A — top 10 apps (full research):**

Run all four tasks per app. Tasks within each app are independent — parallelize them:

1. **Reviews** — use `/browser-use` to scrape the 500 most recent reviews from the store listing. Extract: text, star rating, date, "helpful" count. Save to `phase3/{app-slug}/reviews.json`.

2. **Metadata extraction** — scrape the store listing page: full description, developer name, in-app purchases list with prices, last updated date, version history if visible, content rating, size.

3. **Screenshot analysis** — capture or load the first 3 screenshots. For each: extract the headline/callout text, identify the UI element shown, note the primary claim being made. Save to `phase3/{app-slug}/screenshots.json`.

4. **Website visit** — find and visit the app's marketing website. Extract: homepage headline, pricing page (URL: usually `/pricing`), subscription tiers and prices, trial structure (free trial duration, credit card required, freemium tier), any visible promotional pricing.

**Tier B — next 10 apps (metadata only):**

Scrape description and IAP structure. No reviews, no screenshots, no website visit.

**Process apps sequentially** (one at a time, or max 2–3 in parallel) to avoid store rate limiting.

**Save per app:** write each completed task file to `phase3/{app-slug}/{task}.json`, then immediately update `_manifest.json` → `phase3.items.{slug}.{task}` to `complete`. Update `phase3.complete` count after all four tasks for an app are done. Mark `phases.3_app_research` as `complete` only after all apps are finished. If any apps fail, follow the Failure Handling Protocol in `references/research-storage.md`.

App slug convention: see `references/research-storage.md` → "App Slug Convention".

---

### Phase 4 — Synthesis

Run after Phase 2 and Phase 3 are complete.

**Keyword opportunity scoring:**

For each keyword, calculate:
- **Demand proxy** = average ratings count of the top 10 ranking apps (more ratings = more downloads = more search volume)
- **Competition proxy** = number of distinct apps in the top 20 + average ratings count of the top 3 (high ratings = strong incumbents)
- **Opportunity score** = demand proxy ÷ competition proxy (high demand, fragmented/weak competition = best opportunity)

Rank keywords by opportunity score. Your Tier 1 targets should be the highest-scoring keywords where you can credibly compete.

**Review clustering:**

Pool all reviews across Tier A apps. Cluster by theme separately:

**Sample size discipline:**
- A cluster must contain at least 10 reviews AND represent at least 2% of the total sample to be reported as a pattern. Below this, it is an anecdote, not a signal.
- Always report cluster statistics with the sample size: "Crash complaints: 12.3% of 5000 reviews (n=615)" — never just "12.3%".
- If the total review pool is below 500, note this limitation in the `_summary` and reduce confidence in cluster-level findings from High to Medium.
- Do not rank clusters by percentage alone when sample sizes differ significantly across apps. A 15% complaint rate across 200 reviews is weaker evidence than a 10% rate across 5000 reviews.

- **Complaint clusters** (1–2 star reviews) — rank by frequency. Top clusters are your competitors' weakest points and your product's positioning opportunities.
- **Praise clusters** (4–5 star reviews) — rank by frequency. The language users use to praise these apps is your metadata copy source. These phrases convert because they match what buyers want to hear.

**Feature comparison matrix:**

Build a table: apps as rows, features as columns. Mark presence/absence. Identify:
- Features every top app has (table stakes — must have, not differentiating)
- Features only some apps have (potential differentiators)
- Features no app has but reviews suggest users want (gaps)

**Value prop map:**

From screenshot analysis, extract every unique value proposition headline across Tier A apps. Cluster by theme. Identify:
- Category conventions (what everyone says — signals expectations, not differentiation)
- Gaps (what nobody is saying but complaint clusters suggest users want)

**Pricing landscape:**

Summarize across all websites visited: pricing models present, price points per tier, trial structures, average monthly and annual prices at comparable tiers.

**Save:** `phase4-synthesis.json` (see "Output Schemas" section below for the full schema). Include the `assumptions` array listing key assumptions and their invalidation conditions. Follow the Phase Transition Protocol — present key findings for user review before proceeding to metadata drafting.

**Foundation writeback:** after saving phase4, update `product-foundation.json` → `learned` section (see `references/research-storage.md` → "Foundation Writeback"):

| Learned field | What this pipeline contributes | Mode |
|---|---|---|
| `competitive_set.direct` | Top 20 apps from landscape, empirically verified | Merge |
| `category_vocabulary.user_search_terms` | Autocomplete-derived search terms | Merge |
| `category_vocabulary.praise_language` | Praise clusters from review mining | Merge |
| `category_vocabulary.complaint_language` | Complaint clusters from review mining | Merge |
| `feature_landscape` | Feature matrix classification: table stakes, differentiators, gaps | Replace |
| `audience_insights` | User segments, needs, and frustrations from review clustering | Merge |

---

### Phase 5 — Metadata Draft

The pipeline culminates in a concrete deliverable.

**Draft for each platform:**

*Apple App Store:*
- Title (30 chars): lead with primary keyword, then brand name if space allows — format: `[Keyword]: Brand` or `Brand — [Keyword]`
- Subtitle (30 chars): secondary keyword + benefit statement
- Keyword field (100 chars): Tier 2 and 3 keywords, comma-separated, no spaces after commas, no words already in title/subtitle
- Long description: conversion copy only (not indexed) — hook → primary use cases → key features → social proof → call to action

*Google Play Store:*
- Title (30 chars): same logic as above
- Short description (80 chars): primary keyword + primary benefit — this is both a ranking signal and the first copy a searcher sees
- Long description (4000 chars): keyword-rich and readable — primary keyword 3–5 times, first 250 chars visible without expanding, same structure as App Store description

**For each field:** cite which research finding informed the choice.

**Draft 3 screenshot concepts:**
- Screenshot 1: headline claim (from praise clusters / gap analysis) + hero UI
- Screenshot 2–3: top 2 differentiating features
- Note visual conventions to follow or break based on competitor screenshot analysis

**Save:** `phase5-metadata.json` (see "Output Schemas" section below for the full schema). Follow the Phase Transition Protocol — present metadata recommendations for user approval before generating the report.

---

### Phase 6 — Report Generation

Generate `report.html` using `references/report-template.html` as the base template. Fill `{{TOKENS}}` from pipeline JSON outputs. See `references/research-storage.md` → "Final Report — HTML" for the full design spec.

**Input:** read `phase4-synthesis.json`, `phase5-metadata.json`, and `phase2-landscape.json`.

**Output:** a single HTML file with inline CSS, system fonts, no external dependencies. Sections: executive summary, keyword analysis, competitive landscape, feature comparison, review intelligence, messaging analysis, pricing landscape, and recommendations. Fixed sidebar navigation with jump links.

**Save:** `report.html` — mark `phases.6_report` as `complete` and top-level `status` as `complete` in `_manifest.json`. Update `_index.json`. Write `actions.json` with all Phase 5 recommendations as `pending` (see `references/research-storage.md` → "Action Tracking").

---

## Output Schemas

**Authority:** `references/schema-aso.json` — JSON Schema (draft 2020-12) defining all pipeline output files. Validate every file against the schema before saving.

Infrastructure schemas (_manifest.json, _index.json, actions.json): see `references/schema-infrastructure.json`.
Product foundation schema: see `references/schema-foundation.json`.
Report template: see `references/report-template.html`.

Every JSON file must include a `_summary` field (see `references/research-storage.md` → "Intermediary Files — LLM Optimization"). After each file is written, validate per the Write Protocol in `references/research-storage.md`, then update both `_manifest.json` and `_index.json`.

### Files by phase

| Phase | File | Schema `$defs` key |
|---|---|---|
| 1 | `phase1-keywords-raw.json` | `phase1_keywords_raw` |
| 1 | `phase1-keywords-tiered.json` | `phase1_keywords_tiered` |
| 2 | `phase2-keyword-results.json` | `phase2_keyword_results` |
| 2 | `phase2-landscape.json` | `phase2_landscape` |
| 3 | `phase3/{slug}/reviews.json` | `phase3_reviews` |
| 3 | `phase3/{slug}/metadata.json` | `phase3_metadata` |
| 3 | `phase3/{slug}/screenshots.json` | `phase3_screenshots` |
| 3 | `phase3/{slug}/website.json` | `phase3_website` |
| 4 | `phase4-synthesis.json` | `phase4_synthesis` |
| 5 | `phase5-metadata.json` | `phase5_metadata` |

---

## Metadata Optimization Reference

Quick reference for field rules — detail is in the pipeline above.

| Field | App Store | Google Play |
|---|---|---|
| Title | 30 chars, most heavily weighted | 30 chars, most heavily weighted |
| Subtitle / Short desc | 30 chars, second-highest weight | 80 chars, ranking signal + first impression |
| Keyword field | 100 chars, hidden, not indexed from description | Does not exist — use description |
| Long description | Not indexed, conversion only | Indexed, first 250 chars weighted most |
| In-app purchase names | Indexed | Not significantly indexed |

Title format when brand is not yet known: `[Primary Keyword]: [Brand Name]`
Title format when brand is strong: `[Brand Name] — [Primary Keyword]`

---

## Creative Optimization

Creative assets affect conversion rate from page visit to download. Conversion rate is a ranking signal — creative indirectly affects ranking.

### Icon
- Must be legible at 60×60pt (primary display size in search results)
- No text — unreadable at scale
- Differentiation: if every competitor uses a blue icon, a contrasting color creates visual distinction in search results. Check this during Phase 3 screenshot analysis.
- Test with Apple Product Page Optimization or Google Play Experiments before committing

### Screenshots
- Most users do not scroll past screenshot 3 — the first three carry almost all conversion weight
- Screenshot 1: primary value prop headline + hero UI. This is an ad, not a product tour.
- Screenshots 2–3: key features or social proof (ratings, press mentions, user counts)
- Screenshots 4+: secondary features for the minority of users who scroll
- Portrait fills more screen in App Store search results than landscape — default to portrait unless UI demands landscape
- Captions are mandatory — never rely on UI alone to communicate value; add callout text to every screenshot

### Preview Video (App Store) / Promo Video (Google Play)
- Auto-plays muted in App Store search results — first 5 seconds must work without audio
- Only include if the product experience is inherently visual and dynamic
- A poor video hurts conversion more than no video

---

## Ratings and Reviews

### How ratings affect ranking
- Volume and average are direct signals in both stores
- Recency is weighted more heavily than historical average — a recent dip overrides a strong historical score
- Google Play rewards review response rate as a quality signal

### Review acquisition
- Prompt at peak-engagement moments: after task completion, after a positive outcome, never on launch or after an error
- iOS: use `SKStoreReviewRequest` API only — custom prompts that gate the store redirect behind a positive-only path are a policy violation
- Android: use the Google Play In-App Review API
- Respond to 1-star reviews promptly — converts some reviewers and signals quality to prospective users reading the review section

---

## A/B Testing on Stores

### Apple Product Page Optimization
- Test up to 3 treatments vs. control
- Testable elements: icon, screenshots, preview video (not title, subtitle, or keyword field)
- Minimum 7 days (captures weekly seasonality); recommended 14–28 days for significance
- Only new visitors are exposed to treatments
- Traffic split managed by Apple — you cannot control allocation precisely

### Google Play Store Listing Experiments
- Testable: icon, feature graphic, short description, screenshots, promo video, full description
- Minimum 2 weeks; run until 95% confidence
- You control traffic split — 50/50 is recommended for fastest results

### Test priority order
1. Icon — affects every impression across search and browse
2. First screenshot — primary driver of conversion on the detail page
3. Title and subtitle — highest reward but triggers re-review; higher risk
4. Remaining screenshots
5. Description copy

---

## Monitoring

Track weekly. Your own console data (App Store Connect, Play Console) is the only authoritative source — do not rely on third-party traffic estimates for your own app.

| Metric | Signal | Source |
|---|---|---|
| Keyword rank by keyword | Discoverability health | App Store Connect Search Popularity, Play Console, or manual search checks |
| Impressions | Reach | App Store Connect, Play Console |
| Conversion rate (impression → download) | Page effectiveness | App Store Connect, Play Console |
| Download source (search / browse / referral) | Channel mix | App Store Connect, Play Console |
| Average rating last 30 days | Recent quality signal | Both consoles |
| Ratings volume last 30 days | Rating velocity | Both consoles |

Segment all metrics by locale when running multi-market. A global average masks local problems and missed opportunities.

Rerun the research pipeline (Phase 2 onward) every 3–6 months or after a major competitor launch — the competitive landscape shifts.
