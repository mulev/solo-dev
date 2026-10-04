# SEO Playbook

Search Engine Optimization reference for Google (primary) and Bing. Covers ranking mechanics, a self-serve research pipeline using `/browser-use`, on-page optimization, technical SEO, content strategy, and monitoring.

---

## Contents

1. [How Google Ranking Works](#how-google-ranking-works)
2. [Research Pipeline](#research-pipeline) — Phases 1-6
3. [Output Schemas](#output-schemas)
4. [On-Page Optimization Reference](#on-page-optimization-reference)
5. [Technical SEO Reference](#technical-seo-reference)
6. [Monitoring](#monitoring)

---

## How Google Ranking Works

> **Freshness warning:** Google updates its ranking algorithm continuously (core updates, helpful content updates, spam updates). The signal weightings below reflect stable, long-observed patterns, but specific behaviors shift. Before relying on any specific ranking signal, check Google Search Central documentation and recent search industry analysis (Search Engine Journal, Search Engine Land, Google's own blog). When observed SERP behavior contradicts what's described here, trust the observation.

### Crawling and indexing
- Googlebot discovers pages via links, sitemaps, and direct submissions (Search Console)
- Pages must be crawlable (not blocked by robots.txt) and indexable (no `noindex` tag)
- Crawl budget matters at scale (10K+ pages) — for smaller sites, focus on content quality

### Ranking signals (weighted by impact)
1. **Content relevance and quality** — topical match to query, depth, accuracy, freshness. Google evaluates E-E-A-T (Experience, Expertise, Authoritativeness, Trustworthiness) especially for YMYL topics.
2. **Backlinks** — quantity and quality of external sites linking to the page. Domain authority of linking sites matters more than raw count. Anchor text relevance is a signal.
3. **User engagement signals** — click-through rate from SERPs, dwell time, pogo-sticking (returning to SERP immediately = negative). These are indirect — Google debates their direct use but the correlation is strong.
4. **Technical factors** — page speed (Core Web Vitals: LCP, INP, CLS), mobile-friendliness, HTTPS, clean URL structure, structured data markup.
5. **On-page optimization** — title tag, meta description, H1, header hierarchy, internal linking, keyword presence in content (natural, not stuffed).

### SERP features
Google SERPs are no longer 10 blue links. Common features that affect click-through and strategy:
- **Featured snippet** — position 0, pulled from page content. Owning this can double CTR.
- **People Also Ask (PAA)** — expandable questions. Appearing here drives discovery.
- **Image/video pack** — visual results interleaved in SERPs. Opportunity for visual content.
- **Knowledge panel** — entity-based. Relevant for branded searches.
- **Local pack** — for location-intent queries. Not relevant for purely digital products.

---

## Research Pipeline

Run this pipeline before writing content or optimizing pages. It replaces paid tools (Ahrefs, Semrush, Moz) by scraping SERPs and competitor sites directly with `/browser-use`.

**Startup:** follow the Pipeline Startup Protocol in `references/research-storage.md`. Read the product foundation to extract: value prop, features, audiences, positioning, existing SEO state, website URL, locale priorities.

All paths below are relative to the research run directory: `{project_root}/research/seo-{YYYY-MM-DDTHH-MM-SS}/`

---

### Phase 1 — Keyword Generation

Goal: a tiered shortlist of keywords with clear intent classification. Quality over quantity.

**Before generating:** read `product-foundation.json` → `learned` section. If `category_vocabulary` exists (from prior ASO or SEO runs) and is < 3 months old, use `user_search_terms` as seeds. If `search_landscape` exists from a prior SEO run, review its `demand_confirmed` and `topical_clusters` — focus on discovering new terms and validating whether the landscape has shifted.

**Generation sources (run in order):**

1. **Product-derived terms** — from `product-foundation.json`: feature names, use case descriptions, audience pain points, problem statements, outcome phrases. Generate both noun phrases ("photo editor") and question phrases ("how to edit photos"). If `learned.category_vocabulary` exists, add its terms as additional seeds.

2. **Google autocomplete scraping** — use `/browser-use` to type each seed term into Google search and capture all autocomplete suggestions. These reflect real search behavior. Also capture "Related searches" at the bottom of the first SERP for each seed.

3. **People Also Ask (PAA) extraction** — for each seed keyword, scrape the PAA questions from the Google SERP. These are gold for content ideation and featured snippet targeting.

4. **Competitor content mining** — from Phase 2 results, extract title tags and H1s from top-ranking competitor pages. Mine for keyword patterns you missed. (May require an iterative pass: run Phase 2 with seeds, return here, then re-run Phase 2 with the expanded list.)

**Tiering:**

| Tier | Profile | Content type |
|---|---|---|
| Tier 1 | High intent, commercial or transactional | Dedicated landing pages or core product pages |
| Tier 2 | Informational, moderate volume | Long-form guides, tutorials, comparison pages |
| Tier 3 | Longtail, question-based | Blog posts, FAQ sections, help articles |

**Intent classification** — assign one per keyword:
- **Transactional** — user wants to buy or sign up ("best photo editor app", "photo editor download")
- **Commercial** — user is comparing options ("snapseed vs vsco", "photo editor reviews")
- **Informational** — user wants to learn ("how to remove background from photo", "what is HDR photography")
- **Navigational** — user looking for a specific brand/page ("snapseed download", "vsco pricing")

**Save:** `phase1-keywords-raw.json`, `phase1-keywords-tiered.json`. Follow the Phase Transition Protocol in `references/research-storage.md` — present tiered keywords for user review before proceeding.

---

### Phase 2 — SERP Landscape

For each Tier 1 and Tier 2 keyword, search Google via `/browser-use` and extract the top 20 organic results.

**Per result, extract:**
- URL, domain
- Title tag (as shown in SERP)
- Meta description (as shown in SERP)
- Content type: landing page, blog post, listicle, comparison, tool/calculator, video, documentation
- Estimated content depth: short (<1000 words), medium (1000-3000), long (3000+) — infer from SERP snippet length and description

**Per keyword SERP, also extract:**
- SERP features present: featured snippet (and which domain owns it), PAA questions, image pack, video carousel, knowledge panel
- Number of ads above organic results (indicates commercial value)

**After collection:**
- Deduplicate domains across all keywords
- Score each domain: `appearance_frequency × average_position_inverse` (appearing often in high positions = strongest competitor)
- Rank all domains by score — this is your SEO competitive set

**Parallelization:** 3-5 concurrent SERP scrapes. Avoid more to prevent rate limiting / CAPTCHA triggers.

**Save:** `phase2-keyword-results.json`, `phase2-landscape.json`. Follow the Phase Transition Protocol — present top domains and confirm which to deep-dive before starting Phase 3.

---

### Phase 3 — Competitor Content Analysis

Take the top 15 domains by score from Phase 2. Analyze in two tiers.

**Tier A — top 5 domains (full analysis):**

For each domain, visit the site and analyze:

1. **Site structure** — main navigation categories, content organization, hub-and-spoke structure (topic hubs linking to related articles). Use `/browser-use` to navigate and map the structure.

2. **Content inventory** — blog/content section: estimate posting frequency (dates on recent posts), topics covered, content categories. Identify their highest-performing content (pages that rank for the most keywords from Phase 2).

3. **Top page deep-dive** — for the 3-5 pages from this domain that appear most in Phase 2 keyword results:
   - Full heading structure (H1, H2, H3)
   - Estimated word count
   - Content elements: images, videos, tables, interactive tools, downloadable resources
   - Internal linking pattern (how many internal links, to what pages)
   - Schema markup (check page source for structured data: Article, FAQ, HowTo, Product)
   - Featured snippet format (paragraph, list, table) if this page owns one

4. **Technical signals** — observe during browsing: page load speed (subjective fast/medium/slow), mobile rendering, HTTPS, clean URL patterns.

**Tier B — next 10 domains:**

Extract from SERP data only: domain, pages that rank, content types. No site visits.

**Save per domain:** `phase3/{domain-slug}/` with `structure.json`, `content-inventory.json`, `top-pages.json`. Update `_manifest.json` per completed domain. If any domains fail, follow the Failure Handling Protocol in `references/research-storage.md`.

---

### Phase 4 — Synthesis

**Keyword opportunity scoring:**

For each keyword, calculate:
- **Demand signal** = number of PAA questions + autocomplete variants + ads presence (ads = commercial value = demand)
- **Competition signal** = average domain authority proxy of top 5 (use appearance frequency as a proxy for authority) + content depth of top results
- **Opportunity score** = demand signal ÷ competition signal. High demand + thin/weak competition = best opportunity.
- **Featured snippet opportunity** = keyword has a featured snippet AND the current owner's content is thin or outdated

**Content gap analysis:**

Compare topics covered by top 5 competitor domains against the user's existing content:
- **Covered by competitors, not by user** = content creation opportunities
- **Covered poorly by competitors** (thin content, outdated, low depth) = content quality opportunities
- **Covered by user but not ranking** = optimization opportunities (content exists but needs improvement)

**Content format map:**

For each keyword cluster, identify which content type ranks:
- Long-form guides (informational keywords)
- Comparison pages (commercial keywords)
- Landing pages (transactional keywords)
- Tools/calculators (interactive intent)
- Listicles (discovery intent)

This tells you what to build for each keyword, not just which keywords to target.

**Topical authority map:**

Cluster related keywords into topic groups. Identify:
- Strong clusters (many related keywords, clear hub potential)
- Isolated keywords (no cluster, lower priority unless high volume)
- Topic areas where competitors have deep coverage but user has none (topical authority gaps)

**Save:** `phase4-synthesis.json`. Include the `assumptions` array listing key assumptions and their invalidation conditions. Follow the Phase Transition Protocol — present key findings for user review before proceeding to content strategy.

**Foundation writeback:** after saving phase4, update `product-foundation.json` → `learned` section (see `references/research-storage.md` → "Foundation Writeback"):

| Learned field | What this pipeline contributes | Mode |
|---|---|---|
| `competitive_set.content_competitors` | Top domains from SERP landscape | Merge |
| `category_vocabulary.user_search_terms` | Autocomplete, PAA, and related search terms | Merge |
| `search_landscape` | Demand-confirmed topics, topical clusters, content gaps, dominant formats | Replace |

---

### Phase 5 — Content Strategy

**Evidence requirement:** Every recommendation in this phase must cite the specific Phase 4 finding that supports it and carry a confidence level (confirmed / high / medium / low / needs research). Do not recommend creating a page or optimizing content without citing the keyword opportunity score, content gap, or competitor weakness that justifies it. If confidence is below High, state what additional research would raise it.

**Page recommendations:**

Prioritized list of pages to create or optimize, each with:
- Target page URL (existing or proposed)
- Action: `create` (new page), `optimize` (existing page needs work), `consolidate` (merge thin pages)
- Primary keyword + 2-3 secondary keywords
- Search intent
- Priority score (from Phase 4 opportunity score)

**Content briefs for top 10 priority pages:**

Each brief includes:
- Target keyword and secondary keywords
- Search intent classification
- Recommended word count (based on what ranks — match or exceed top competitors)
- Recommended heading structure (H1, key H2s, H3 sections — based on competitor top page analysis)
- Content elements to include (based on what top-ranking pages have: images, tables, examples, tools)
- Internal linking targets (which existing pages to link to/from)
- Featured snippet strategy (if applicable: target paragraph/list/table format)
- Competitor benchmark: what the current #1 page does and how to beat it

**Site structure recommendations:**

Based on topical authority map:
- Hub pages to create (topic clusters that need a central page)
- Internal linking improvements
- Navigation changes (if major topic areas are buried)

**Save:** `phase5-strategy.json`. Follow the Phase Transition Protocol — present content strategy recommendations for user approval before generating the report.

---

### Phase 6 — Report Generation

Generate `report.html` using `references/report-template.html` as the base template. Fill `{{TOKENS}}` from pipeline JSON outputs. See `references/research-storage.md` → "Final Report — HTML" for the full design spec.

**Sections specific to SEO report:**

| Section | Data source | Key elements |
|---|---|---|
| Executive Summary | phase4 + phase5 `_summary` fields | Top 5 keyword opportunities, biggest content gap, primary recommendation |
| Keyword Analysis | phase4 `keyword_opportunities` | Opportunity-scored table, intent breakdown, featured snippet opportunities |
| SERP Landscape | phase2 `landscape` | Top competing domains table, SERP feature distribution |
| Content Gaps | phase4 `content_gaps` | Gap table: topic, competitor coverage, user coverage, opportunity |
| Competitor Breakdown | phase3 Tier A domains | Per-domain: content depth, structure, top pages, posting cadence |
| Content Strategy | phase5 `page_recommendations` | Priority pages table, top 5 content briefs, site structure recommendations |
| Recommendations | phase5 top actions | Ordered action list with expected impact |

**Input:** read `phase4-synthesis.json`, `phase5-strategy.json`, and `phase2-landscape.json`.

**Save:** `report.html` — mark `phases.6_report` as `complete` and top-level `status` as `complete` in `_manifest.json`. Update `_index.json`. Write `actions.json` with all Phase 5 recommendations as `pending` (see `references/research-storage.md` → "Action Tracking").

---

## Output Schemas

**Authority:** `references/schema-seo.json` — JSON Schema (draft 2020-12) defining all pipeline output files. Validate every file against the schema before saving.

Infrastructure schemas (_manifest.json, _index.json, actions.json): see `references/schema-infrastructure.json`.
Product foundation schema: see `references/schema-foundation.json`.
Report template: see `references/report-template.html`.

Every JSON file must include a `_summary` field. After each file is written, validate per the Write Protocol in `references/research-storage.md`, then update both `_manifest.json` and `_index.json`.

### Files by phase

| Phase | File | Schema `$defs` key |
|---|---|---|
| 1 | `phase1-keywords-raw.json` | `phase1_keywords_raw` |
| 1 | `phase1-keywords-tiered.json` | `phase1_keywords_tiered` |
| 2 | `phase2-keyword-results.json` | `phase2_keyword_results` |
| 2 | `phase2-landscape.json` | `phase2_landscape` |
| 3 | `phase3/{domain-slug}/structure.json` | `phase3_structure` |
| 3 | `phase3/{domain-slug}/top-pages.json` | `phase3_top_pages` |
| 4 | `phase4-synthesis.json` | `phase4_synthesis` |
| 5 | `phase5-strategy.json` | `phase5_strategy` |

---

## On-Page Optimization Reference

Quick reference for page-level SEO elements.

### Title tag
- 50-60 characters (Google truncates at ~60)
- Primary keyword near the front
- Include brand name at the end for branded search capture: `Primary Keyword | Brand`
- Unique per page — no duplicates across the site

### Meta description
- 150-160 characters
- Not a ranking signal directly, but affects CTR from SERPs — which is a signal
- Include primary keyword (Google bolds matches)
- Write as a pitch: what the user will get if they click

### H1
- One per page
- Should match the page's primary topic and keyword
- Does not need to be identical to the title tag — can be more natural/longer

### Header hierarchy (H2-H6)
- Use H2 for major sections, H3 for subsections
- Include secondary keywords naturally in H2s
- Headers structure the content for both users and crawlers
- FAQ sections should use H2 or H3 for each question (aligns with FAQPage schema)

### Internal linking
- Every important page should be reachable within 3 clicks from the homepage
- Use descriptive anchor text (not "click here")
- Link from high-authority pages to new/important pages (passes link equity)
- Hub-and-spoke model: topic hub page links to all related articles, they link back

### Schema markup
- `Article` for blog posts (with `datePublished`, `author`)
- `FAQPage` for FAQ sections (can trigger FAQ rich results)
- `HowTo` for step-by-step guides (can trigger how-to rich results)
- `Product` for product pages (with `offers`, `review`)
- `BreadcrumbList` for navigation breadcrumbs
- Use JSON-LD format (Google's preferred method)

---

## Technical SEO Reference

### Core Web Vitals
- **LCP** (Largest Contentful Paint) < 2.5s — optimize images, server response time
- **INP** (Interaction to Next Paint) < 200ms — minimize JavaScript blocking
- **CLS** (Cumulative Layout Shift) < 0.1 — set dimensions on images/embeds, avoid dynamic content injection

### Crawlability
- `robots.txt` — do not block CSS/JS (Google needs them to render pages)
- XML sitemap — submit via Search Console, include only canonical URLs
- Canonical tags — use `rel="canonical"` to prevent duplicate content issues
- Pagination — use `rel="next"` / `rel="prev"` or load-more patterns
- Hreflang — for multi-locale sites, set `rel="alternate" hreflang="x"` per locale

### URL structure
- Descriptive, keyword-containing slugs: `/ai-photo-editor` not `/page?id=123`
- Hyphens between words (not underscores)
- Lowercase only
- Flat hierarchy preferred: `/blog/keyword` over `/blog/category/subcategory/keyword`

---

## Monitoring

Track weekly. Google Search Console is the authoritative source — third-party tools estimate.

| Metric | Signal | Source |
|---|---|---|
| Impressions by keyword | Discoverability | Search Console |
| Click-through rate by keyword | SERP effectiveness | Search Console |
| Average position by keyword | Ranking health | Search Console |
| Pages indexed | Crawl health | Search Console |
| Core Web Vitals | Technical health | Search Console, PageSpeed Insights |
| Organic traffic by page | Content performance | Analytics (GA4, Plausible, etc.) |
| Backlinks (new/lost) | Authority trajectory | Search Console, Ahrefs free backlink checker |

Segment by locale and device (mobile vs. desktop) for multi-market sites.

Rerun the research pipeline (Phase 2 onward) every 3-6 months or after a major algorithm update — the competitive landscape shifts.
