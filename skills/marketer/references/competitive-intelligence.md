# Competitive Intelligence

Framework and research pipeline for competitor analysis. Covers identification, scraping, review analysis, synthesis, and strategic implications. Uses `/browser-use` for direct data collection instead of paid tools.

---

## Contents

1. [Research Pipeline](#research-pipeline) — Phases 1-6
2. [Framework Reference](#framework-reference)
   - [What to Research](#what-to-research)
   - [Research Sources by Type](#research-sources-by-type)
   - [Competitor Teardown Structure](#competitor-teardown-structure)
   - [Identifying Strategic Gaps](#identifying-strategic-gaps)
   - [Avoiding Intelligence Failures](#avoiding-intelligence-failures)

---

## Research Pipeline

**Startup:** follow the Pipeline Startup Protocol in `references/research-storage.md`. Read the product foundation to extract: known competitors, main alternatives, positioning hypothesis, business model, geographic scope.

All paths below are relative to the research run directory: `{project_root}/research/competitive-{YYYY-MM-DDTHH-MM-SS}/`

---

### Phase 1 — Competitor Identification

Gather candidates from multiple sources, then score and prioritize.

**Before starting:** read `product-foundation.json` → `learned` section. If `competitive_set` exists and is < 3 months old, start with this as the known set and focus on discovering new or changed competitors. If `feature_landscape` or `pricing_intelligence` exist, use them to inform which dimensions to analyze more deeply.

**Sources:**
1. **Product foundation** — `positioning.main_alternatives` gives the user's known competitors. `learned.competitive_set` adds empirically discovered competitors from prior pipeline runs.
2. **Web search** — search category terms from the product foundation: `"[category] app"`, `"best [category]"`, `"[category] alternatives"`. Capture the first 3 pages of results.
3. **App store search** (if mobile product) — use results from any existing ASO research, or search the primary category keywords
4. **Review platforms** — search G2, Capterra, Product Hunt for the category. Extract apps listed in "alternatives" and "competitors" sections.
5. **Community** — search Reddit, Hacker News for category discussions. Users mention tools by name.

**Per competitor, record:**
- Name, website URL, app store URLs (if applicable)
- One-line description of what they do
- Relevance classification:
  - `direct` — same category, same audience, same core problem
  - `indirect` — adjacent category, overlapping audience or overlapping problem
  - `alternative` — different solution to the same underlying problem (e.g., hiring a photographer vs. using a photo editing app)

**Scoring:** prioritize by relevance × visibility (how often they appear across sources). Take the top 10-15 for deep research.

**Save:** `phase1-competitors.json`. Follow the Phase Transition Protocol in `references/research-storage.md` — present the prioritized competitor list for user review before proceeding to deep scraping.

---

### Phase 2 — Per-Competitor Scraping

For each competitor (top 10-15 from Phase 1), use `/browser-use` to collect data across multiple surfaces.

**2a. Website** — visit the site:
- Homepage headline and subheadline (their positioning bet)
- About page (founding story, team size, mission statement)
- Features page (feature list, how they organize and prioritize features)
- Pricing page (tiers, prices, trial structure, free tier, enterprise "contact us" vs. published pricing)
- Careers page (open roles, team size signals, investment areas)

**2b. App stores** (if applicable):
- Title, subtitle, description, screenshots
- Rating, ratings count, last updated date
- IAP list with prices
- "What's New" section (recent product direction)

**2c. Social presence:**

> **Scraping limitations:** Twitter/X increasingly restricts automated access. LinkedIn may require authentication. If a platform blocks scraping, record `null` for that channel's metrics and note the gap — do not infer low social presence from a scraping failure. Focus data collection effort on platforms that return reliable results.

- Twitter/X: follower count, posting frequency, engagement (likes/replies on recent posts)
- LinkedIn company page: employee count, recent posts, growth signals
- YouTube (if relevant): subscriber count, video frequency, view counts

**2d. Job postings:**
- Check careers page, Greenhouse, Lever, Ashby, LinkedIn Jobs
- Extract: open roles by department (engineering, sales, marketing, product, support)
- Hiring patterns signal investment areas: heavy engineering hiring = product push; heavy sales = growth mode; heavy content = SEO bet

**Process competitors sequentially** or 2-3 in parallel. Sub-tasks within each competitor (website, app store, social, jobs) are independent and can run in parallel.

**Save per competitor:** `phase2/{competitor-slug}/website.json`, `app-store.json`, `social.json`, `jobs.json`. Update manifest per completed task per competitor. If any competitors fail, follow the Failure Handling Protocol in `references/research-storage.md`.

---

### Phase 3 — Review and Sentiment Analysis

For the top 5-8 competitors by relevance score:

**Sample size discipline:**
- Per-competitor sentiment analysis requires at least 100 reviews to be directional and at least 500 to be reliable. State the actual count when reporting: "Net sentiment based on 312 reviews (directional)" vs. "Net sentiment based on 2100 reviews (reliable)".
- Cross-competitor clusters (aggregated across all competitors) need at least 500 total reviews for the aggregate to be meaningful.
- When a competitor has fewer than 50 reviews on a platform, skip that platform for that competitor and note the gap rather than drawing conclusions from insufficient data.

**Sources to scrape:**
- **G2 / Capterra** — scrape the 100 most recent reviews. Focus on 1-3 star reviews (pain points) and 5-star reviews (value drivers).
- **App store reviews** (if applicable) — 200 most recent reviews per store.
- **Reddit** — search `[competitor name] site:reddit.com` in relevant subreddits. Capture top 10 threads mentioning the competitor.
- **Trustpilot** (if B2C) — 100 most recent reviews.

**Per competitor, produce:**
- Complaint clusters (from 1-3 star reviews): theme, frequency, example quotes
- Praise clusters (from 4-5 star reviews): theme, frequency, example quotes
- Net sentiment summary: overall positive/negative ratio, trending direction if visible from dates

**Save per competitor:** `phase3/{competitor-slug}/reviews.json`, `sentiment.json`. Update manifest per completed competitor. If any competitors fail, follow the Failure Handling Protocol.

---

### Phase 4 — Synthesis

Run after Phase 2 and Phase 3 are complete. Use the teardown structure and gap analysis frameworks below.

**Positioning map:**
- Choose 2 axes relevant to the category from Phase 2 website data (e.g., price vs. depth, SMB vs. enterprise, broad vs. niche, self-serve vs. high-touch)
- Place every competitor on the map using a 1-10 scale for each axis, where 1 is lowest and 10 is highest. This provides enough resolution to distinguish between closely-positioned competitors.
- Identify empty quadrants and crowded zones

**Feature comparison matrix:**
- Build from Phase 2 features page data
- Apps as rows, features as columns
- Classify each feature: table stakes / differentiator / gap (same logic as ASO playbook)

**Pricing landscape:**
- From Phase 2 pricing data
- Summary table: competitor, model, tiers, monthly/annual prices, trial, free tier
- Price distribution: min, max, median at comparable tiers
- Identify pricing gaps (underserved price points)

**Per-competitor teardown** (use the teardown structure defined below):
- Summary, positioning, strengths, weaknesses, strategic bets, implications
- Source all claims from Phase 2/3 data

**Strategic gaps** (use the three-criteria test defined below):
- Demand exists + competitors underserve + we can credibly fill = true opportunity
- Rank gaps by impact potential

**Save:** `phase4-synthesis.json`. Include the `assumptions` array listing key assumptions and their invalidation conditions. Follow the Phase Transition Protocol — present key findings for user review before proceeding to strategic implications.

**Foundation writeback:** after saving phase4, update `product-foundation.json` → `learned` section (see `references/research-storage.md` → "Foundation Writeback"):

| Learned field | What this pipeline contributes | Mode |
|---|---|---|
| `competitive_set` | Full competitive taxonomy: direct, indirect, alternative | Merge |
| `feature_landscape` | Feature matrix from website feature pages | Replace |
| `validated_positioning` | Differentiator validation status, positioning gaps | Merge |
| `pricing_intelligence` | Pricing landscape (only if no pricing pipeline run exists) | Replace (conditional) |
| `audience_insights` | User segments from review sentiment analysis | Merge |

---

### Phase 5 — Strategic Implications

The deliverable that tells the user what to do with the research.

**Evidence requirement:** Every recommendation in this phase must cite specific Phase 4 data (positioning map placement, feature matrix gap, pricing landscape gap, teardown finding, or strategic gap) and carry a confidence level. Inferences from indirect signals (job postings, content investment) must be labeled as inferences, not facts. If a recommendation relies on a single data point, state this limitation.

**Where to compete directly:**
- Areas where our product has a clear advantage (features, price, positioning)
- Evidence from Phase 4 feature matrix and gap analysis

**Where to avoid:**
- Areas where an incumbent is too strong and our differentiation is too weak
- Evidence from Phase 4 positioning map and feature matrix

**Positioning opportunities:**
- Gaps no competitor is filling (from gap analysis)
- Messaging angles competitors are not using (from review praise clusters — what users value but competitors don't emphasize)

**Pricing opportunities:**
- Underserved price points
- Business model alternatives (e.g., competitors are all subscription, opportunity for a one-time purchase option)

**Messaging opportunities:**
- What competitors claim vs. what their customers actually say (Phase 2 positioning vs. Phase 3 sentiment)
- Competitor weaknesses in their own customers' words — direct copywriting source

**Save:** `phase5-implications.json`. Follow the Phase Transition Protocol — present strategic implications for user approval before generating the report.

---

### Phase 6 — Report Generation

Generate `report.html` using `references/report-template.html` as the base template. Fill `{{TOKENS}}` from pipeline JSON outputs. See `references/research-storage.md` → "Final Report — HTML" for the full design spec.

**Sections specific to competitive intelligence report:**

| Section | Data source |
|---|---|
| Executive Summary | phase4 + phase5 `_summary` fields |
| Competitor Overview | phase1 competitors table with relevance scores |
| Positioning Map | phase4 `positioning_map` — visual representation |
| Feature Comparison | phase4 `feature_matrix` |
| Pricing Landscape | phase4 `pricing_landscape` |
| Review Intelligence | phase3 complaint + praise clusters per competitor |
| Individual Teardowns | phase4 `teardowns` — one section per competitor |
| Strategic Gaps | phase4 `strategic_gaps` |
| Recommendations | phase5 — where to compete, avoid, opportunity areas |

**Save:** `report.html` — mark `phases.6_report` and top-level `status` as `complete`. Update `_index.json`. Write `actions.json` with all Phase 5 recommendations as `pending` (see `references/research-storage.md` → "Action Tracking").

---

## Output Schemas

**Authority:** `references/schema-competitive.json` — JSON Schema (draft 2020-12) defining all pipeline output files. Validate every file against the schema before saving.

Infrastructure schemas (_manifest.json, _index.json, actions.json): see `references/schema-infrastructure.json`.
Product foundation schema: see `references/schema-foundation.json`.
Report template: see `references/report-template.html`.

Every JSON file must include a `_summary` field. After each file is written, validate per the Write Protocol in `references/research-storage.md`, then update both `_manifest.json` and `_index.json`.

### Files by phase

| Phase | File | Schema `$defs` key |
|---|---|---|
| 1 | `phase1-competitors.json` | `phase1_competitors` |
| 2 | `phase2/{slug}/website.json` | `phase2_website` |
| 2 | `phase2/{slug}/app-store.json` | `phase2_app_store` |
| 2 | `phase2/{slug}/social.json` | `phase2_social` |
| 2 | `phase2/{slug}/jobs.json` | `phase2_jobs` |
| 3 | `phase3/{slug}/reviews.json` | `phase3_reviews` |
| 3 | `phase3/{slug}/sentiment.json` | `phase3_sentiment` |
| 4 | `phase4-synthesis.json` | `phase4_synthesis` |
| 5 | `phase5-implications.json` | `phase5_implications` |

---

## Framework Reference

The following frameworks are used by the pipeline phases above and can also be applied as standalone analysis tools.

---

### What to Research

A complete competitive picture covers six dimensions. Prioritize based on the decision being made.

**1. Product and Feature Coverage**
- What the product does, what it does not do
- Pricing tiers and what each unlocks
- Platform availability (iOS, Android, web, desktop)
- Integrations and ecosystem plays
- Recent product changes (changelog pages, release notes, app store "What's New")

**2. Positioning and Messaging**
- Homepage headline — this is their positioning bet
- Tagline, product naming conventions, tone of voice
- Who they claim their product is for (ICP signals in copy)
- What pain points they lead with vs. bury
- Differentiators they claim (and whether credible)

**3. Pricing**
- Published pricing page
- Trial structure: duration, freemium limitations, credit card required
- Pricing model: per-seat, usage-based, flat, tiered, hybrid
- Discount signals: year/month ratio, visible coupons, sale frequency
- Enterprise: published vs. "contact sales" (contact sales = they negotiate, higher ACV likely)

**4. Marketing Channels and Spend**
- **SEO presence**: estimate organic traffic and keyword coverage via web search (scrape SERPs for their domain)
- **Paid search**: Google Ads Transparency Center shows active ads
- **Content strategy**: blog posting frequency, topics, depth — signals their SEO investment
- **Social**: engagement rate matters more than follower count
- **PR**: Google News search `[company] site:techcrunch.com OR site:forbes.com`
- **App store**: ratings volume trajectory as a download growth proxy

**5. Customer Sentiment**
- **Review platforms**: G2, Capterra, Trustpilot, Product Hunt — read the 3-star reviews (most honest) and 1-star reviews (pain points)
- **App store reviews**: recurring complaints and praised features
- **Reddit / communities**: `[competitor name]` on relevant subreddits — unfiltered opinions
- **Social listening**: Twitter/X and LinkedIn mentions

**6. Organizational Signals**
- **Job postings**: engineering hires = product investment; sales hires = growth mode; content hires = SEO push
- **Leadership changes**: C-suite movement signals strategic shifts
- **Funding and acquisitions**: resources and direction

---

### Research Sources by Type

| Data type | Free sources | Paid sources |
|---|---|---|
| Organic traffic / keywords | SERP scraping (browser-use), Google Search Console (own site) | Ahrefs, Semrush Pro |
| Paid search | Google Ads Transparency Center | SpyFu Pro, SimilarWeb |
| App store data | Store scraping (browser-use) | Sensor Tower, AppFollow |
| Web traffic estimates | SimilarWeb free (limited accuracy) | SimilarWeb Pro |
| Customer reviews | G2, Capterra, Trustpilot, app stores | No paid source needed |
| Job postings | LinkedIn, careers pages, Greenhouse, Lever | LinkedIn Recruiter |
| Funding / company data | Crunchbase (limited free) | Crunchbase Pro, PitchBook |
| PR / news | Google News | Muck Rack Pro |

Verify free-tier data against at least one other source before using as a benchmark. SimilarWeb estimates can be 30-50% off for smaller sites.

---

### Competitor Teardown Structure

Use this for each competitor in Phase 4:

**1. Summary** (3-5 sentences) — who they are, what they've built, who they serve, single most important observation.

**2. Positioning map** — where they sit on the category's relevant axes. Where they are NOT competing.

**3. Strengths** (evidence-backed) — only claims supported by data from Phase 2/3. No generic strengths.

**4. Weaknesses** (evidence-backed) — customer complaints from Phase 3, features not built, positioning gaps.

**5. Strategic bets** — inferred from hiring patterns, content investment, product changes. Label as inferences.

**6. Implications** — what this means for our strategy: gaps, threats, what to avoid competing on directly.

---

### Identifying Strategic Gaps

A gap is valuable only if all three criteria are met:

1. **Real demand exists** — customers are asking for it (search volume, review complaints, community requests)
2. **Competitors are not serving it well** — confirmed by absence or weak execution
3. **We can credibly serve it** — we have or can build the capability in a meaningful time horizon

Avoid gaps that are gaps for a reason: low willingness to pay, regulatory barriers, technical infeasibility.

---

### Avoiding Intelligence Failures

- **Do not generalize from reviews** — sample size matters. 10K reviews at 4.2 with a "slow support" pattern is different from 200 reviews with the same average.
- **Do not treat traffic estimates as precise** — SimilarWeb can be 30-50% off. Directional signal only.
- **Verify recency** — a cached pricing page from 18 months ago is wrong data. Always check the live page, note the date.
- **Separate claims from reality** — positioning copy is aspirational; review data is closer to lived experience.
- **Survivorship bias** — competitors you can easily research are the successful ones. Ask: "who tried this before and failed?"
