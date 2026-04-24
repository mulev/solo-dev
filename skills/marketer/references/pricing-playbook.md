# Pricing Playbook

Research pipeline for pricing decisions — model selection, tier design, price points, and go-to-market pricing strategy. Covers one-time purchases, subscriptions, freemium, and hybrid models. Uses data from other pipelines (competitive intelligence, ASO, SEO) as primary inputs, then layers pricing-specific research on top.

This is the first pipeline designed to **consume outputs from other pipelines**. Phase 1 aggregates what already exists. New scraping only fills gaps.

---

## Contents

1. [Pricing Fundamentals](#pricing-fundamentals)
2. [Research Pipeline](#research-pipeline) — Phases 1-6
3. [Output Schemas](#output-schemas)
4. [Pricing Page Reference](#pricing-page-reference)

---

## Pricing Fundamentals

### Models

| Model | Revenue pattern | Fits when | Risks |
|---|---|---|---|
| One-time purchase | Front-loaded, no recurrence | Value is delivered once (utilities, tools, games), user resists recurring payments | No recurring revenue; must sell new versions or features to grow |
| Subscription (auto-renew) | Recurring, predictable | Ongoing value delivery, content updates, cloud features | Churn is existential; must justify recurring cost every billing cycle |
| Freemium + subscription | Free acquisition, paid conversion | Large addressable market, low marginal cost per free user, clear upgrade trigger | Free tier can cannibalize paid if too generous |
| Freemium + one-time IAP | Free acquisition, one-time upsell | Features or content that don't need ongoing delivery (filters, level packs, tools) | Revenue per user is capped; need large volume |
| Consumable IAP | Per-use revenue | AI credits, exports, tokens, prints — value scales with usage | Unpredictable revenue; users may hoard or churn between purchases |
| Tiered one-time | Multiple price points | Different user segments with different needs | Complex to communicate; risk of cannibalizing higher tiers |

### Platform economics

> **Freshness warning:** Platform commission rates and policies change. Apple introduced the Small Business Program in 2021 and has adjusted terms since. Google has made similar changes. Before using these rates in revenue calculations, verify against the current Apple Developer Program agreement and Google Play Developer documentation.

| Platform | Commission | Reduced rate | Notes |
|---|---|---|---|
| Apple App Store | 30% | 15% after Year 1 for auto-renewing subs; 15% for Small Business Program (<$1M/yr) | Subscriptions must use Apple's billing; no linking to external payment |
| Google Play Store | 30% | 15% on first $1M/yr revenue; 15% after Year 1 for subs | Similar restrictions to Apple |
| Web direct | 0% (payment processor fee only, ~3%) | — | No platform commission; can offer lower prices or keep margin; must handle billing |

When deciding between app store pricing and web direct: app store has distribution and trust but 30% fee. Web direct has full margin but requires driving traffic and handling billing. Many products use both: app store for acquisition, web for upgrades/renewals at better margin.

---

## Research Pipeline

**Startup:** follow the Pipeline Startup Protocol in `references/research-storage.md`. Read the product foundation to extract: business model, current pricing, audiences, positioning, geographic scope.

**Cross-pipeline data:** this pipeline aggregates pricing data from other completed pipelines. Before starting, check what exists:
- `competitive-*/phase4-synthesis.json` → `pricing_landscape` section
- `competitive-*/phase2/*/website.json` → pricing page data
- `aso-*/phase3/*/website.json` → subscription tiers, trial structure
- `aso-*/phase3/*/metadata.json` → IAP list with prices
- `aso-*/phase3/*/reviews.json` → reviews (mined for price sentiment in Phase 3)

If no competitive or ASO pipeline has been run, ask the user: "Competitor pricing data improves this analysis significantly. Run competitive intelligence first, or collect pricing data standalone within this pipeline?" If standalone, Phase 1 includes targeted competitor pricing scraping.

All paths below are relative to the research run directory: `{project_root}/research/pricing-{YYYY-MM-DDTHH-MM-SS}/`

---

### Phase 1 — Pricing Data Aggregation

Collect all available pricing data from existing pipeline outputs and fill gaps.

**Before starting:** read `product-foundation.json` → `learned` section. If `pricing_intelligence` exists and is < 3 months old, use it as the baseline and focus on what's changed. If `competitive_set` exists, use it to identify all competitors that need pricing data. If `feature_landscape` exists, use it to inform tier design in later phases.

**From existing pipelines (read, do not re-scrape):**
- Competitor pricing from competitive intelligence pipeline
- App IAP structures and pricing from ASO pipeline
- Competitor website pricing from any pipeline that visited competitor sites

**Gap identification:**
- Which competitors in the product foundation have NO pricing data?
- Which have partial data (e.g., app store IAP but not website pricing page)?
- Are there competitors discovered in other pipelines that aren't in the foundation?

**Gap filling (only for missing data):**
- Use `/browser-use` to visit pricing pages of competitors with no data
- For mobile apps without website pricing: scrape app store IAP listing
- Extract: tiers, prices (monthly/annual/one-time), features per tier, trial structure, free tier details

**Save:** `phase1-aggregated-pricing.json`. Follow the Phase Transition Protocol in `references/research-storage.md`.

---

### Phase 2 — Pricing Architecture Mapping

For each competitor with pricing data, map the full architecture — not just "what's the price" but "how does the pricing work."

**Per competitor, analyze:**

*Tier structure:*
- How many tiers? What are they called?
- What feature or limit differentiates each tier?
- What is the upgrade trigger? (The specific limitation in the lower tier that forces users to upgrade — storage limit, user count, feature lock, watermark, export quality)
- Is there a clear "recommended" tier? How is it signaled?

*Free tier / freemium (if exists):*
- What's included for free?
- What's the most painful limitation? (This is the conversion driver)
- Can a user get real value from the free tier, or is it essentially a trial?
- Is free time-limited or permanently free with limitations?

*Trial structure:*
- Duration (3-day, 7-day, 14-day, 30-day, none)
- What's available during trial? (Full product? Limited features?)
- Credit card required upfront?
- Conversion mechanism: what happens when trial ends? (Paywall, grace period, downgrade to free)

*Pricing signals:*
- Annual discount percentage: (1 - (annual_monthly_equivalent / monthly)) × 100
- Whether annual is presented first or monthly
- Savings messaging ("Save $X/year", "2 months free", percentage)
- Currency and localization (one price globally, or localized)
- Student/education/nonprofit pricing
- Enterprise "contact us" vs. published enterprise pricing

*Platform strategy:*
- Same price on app store and web, or different?
- Does web bypass the app store commission? (Lower price on web = margin play)
- Subscription management: app store billing only, or also direct billing?

**Identify category patterns:**
- Most common model in the category (subscription? freemium? one-time?)
- Most common tier count (2? 3? 4?)
- Most common trial duration
- Average annual discount percentage
- Standard feature gates (what's always free, what's always paid)

**Save:** `phase2-architectures.json`. Follow the Phase Transition Protocol.

---

### Phase 3 — Price Sensitivity Research

New research the other pipelines don't perform. Three data sources:

**3a. Review mining for price sentiment**

Search existing review data from ASO or competitive pipelines. If reviews aren't available, scrape the top 5 competitors' app store reviews (200 each) filtered for pricing keywords.

Search terms: "price", "expensive", "cheap", "worth", "overpriced", "free", "subscription", "pay", "cost", "money", "refund", "cancel", "renewal", "billing"

Classify each mention:
- **Positive price perception** — "worth every penny", "great value", "cheap for what you get"
- **Negative price perception** — "too expensive", "not worth the subscription", "overpriced"
- **Comparison** — "cheaper than X", "same price as Y but worse"
- **Feature-price alignment** — "would pay more for X", "not enough features for the price"
- **Model resistance** — "hate subscriptions", "just let me buy it once", "subscription fatigue"

Quantify: what percentage of negative reviews across the category mention price? Do price complaints concentrate at specific price points?

**3b. Community pricing discussions**

Use `/browser-use` to search:
- Reddit: `"[category] pricing" site:reddit.com`, `"[category] worth it" site:reddit.com`, `"[competitor] too expensive site:reddit.com"`
- Twitter/X: `[category] subscription expensive`, `[category] free alternative`
- Forum/community: any category-specific communities

Extract: stated price expectations, willingness-to-pay signals, model preferences (subscription vs. one-time), deal-breaker prices.

**3c. Price comparison content**

Search Google for:
- "best free [category] app"
- "[category] pricing comparison"
- "[product] vs [competitor] price"
- "[category] lifetime deal"

Scrape the top 3-5 results for each. Extract: how price-sensitive searchers evaluate options, what price points are mentioned as reasonable, what features they expect at each price point.

**Save:** `phase3-sensitivity.json`. Follow the Phase Transition Protocol.

---

### Phase 4 — Synthesis

**Pricing landscape:**
- Full competitive pricing table with architectures from Phase 2
- Category pricing patterns (dominant model, median prices, standard gates)
- Price distribution: min, median, max at each tier level

**Price sensitivity findings:**
- Review sentiment summary: percentage of reviews mentioning price, net sentiment, threshold price points
- Community signals: stated willingness to pay, model preferences
- Comparison content: what searchers expect at each price point

**Value metric recommendation:**
Based on product features (from foundation) + competitive patterns (Phase 2) + audience behavior (Phase 3):
- What should the price be tied to? (Users, usage, features, time, content)
- Why this metric? (Evidence from competitive patterns and user expectations)

**Model recommendation:**
- Recommended model with evidence trail
- If subscription: recommended billing periods and annual discount
- If one-time: recommended base price and optional premium tiers
- If hybrid: recommended combination and how they interact
- If freemium: recommended free tier scope and upgrade trigger

**Tier structure recommendation:**
- Recommended number of tiers
- Feature allocation per tier (using feature matrix from competitive/ASO pipelines if available)
- Naming convention (aligned with category patterns or deliberately differentiated)
- Upgrade trigger for each tier boundary

**Price point analysis:**
For each recommended tier:
- **Floor** — minimum viable price: below this signals "too cheap to trust" (Van Westendorp theory) or undercuts positioning
- **Target** — value-based price: anchored to competitive alternatives + perceived value + audience willingness to pay
- **Ceiling** — maximum before significant demand reduction: price complaints spike above this in reviews
- Confidence level for each point (confirmed / high / medium / low / needs primary research)

**Revenue scenarios:**
Three models using the target price:
- **Conservative:** low conversion rate (25th percentile of category), moderate churn (if subscription)
- **Target:** expected conversion, expected churn, based on category benchmarks
- **Optimistic:** high conversion (75th percentile), low churn

**Important:** The conversion and churn percentiles above are approximate industry ranges commonly cited in app economy reports (RevenueCat State of Subscription Apps, Adapty benchmarks, Sensor Tower market reports). They vary significantly by category, geography, and product maturity. Before using these in recommendations:
- Search for recent benchmark reports specific to the product's category
- Label which source and year each benchmark comes from
- If no category-specific benchmark exists, state this explicitly and widen the confidence interval

For each: monthly revenue estimate, annual revenue estimate, Year 1 and Year 2 projections. For subscriptions: estimated LTV per user (ARPU ÷ monthly churn rate).

Note: these are estimates based on category benchmarks and competitive data. They are not forecasts. Label as hypotheses requiring validation.

**Save:** `phase4-synthesis.json`. Include the `assumptions` array listing key assumptions and their invalidation conditions. Follow the Phase Transition Protocol — present pricing findings for user review before proceeding to strategy.

**Foundation writeback:** after saving phase4, update `product-foundation.json` → `learned` section (see `references/research-storage.md` → "Foundation Writeback"):

| Learned field | What this pipeline contributes | Mode |
|---|---|---|
| `pricing_intelligence` | Category norms, price sensitivity profile, value metric recommendation | Replace |
| `validated_positioning` | Pricing-related positioning gaps (e.g., underserved price points) | Merge |
| `audience_insights` | Price sensitivity by user segment, model preferences | Merge |

---

### Phase 5 — Pricing Strategy

The actionable deliverable.

**Evidence requirement:** Every recommendation must cite the specific Phase 2-4 finding that supports it. Price point recommendations must reference the competitive range (Phase 2), sensitivity signals (Phase 3), and the floor/target/ceiling analysis (Phase 4). Do not recommend a price without stating its confidence level and what validation is needed before committing.

**Recommended pricing model** — with rationale citing specific research findings from Phases 2-4.

**Recommended tiers:**
For each tier:
- Name
- Price (monthly, annual, or one-time)
- Key features included
- Upgrade trigger (what limitation drives users to the next tier)
- Positioning (who this tier is for)

**Trial/freemium structure:**
- Recommended trial duration with evidence (competitive analysis of what works in the category)
- What's available during trial
- Credit card upfront: yes/no with rationale
- Conversion optimization: what to show at trial end, reminder strategy

**Platform pricing strategy:**
- App Store and Play Store pricing (using available price tiers)
- Web direct pricing (if applicable) — same or lower than app store?
- Cross-platform considerations (users who buy on one platform and use on another)

**Localized pricing:**
- Recommended local prices for each priority market from product foundation
- Purchasing power parity adjustments (lower prices in lower-PPP markets)
- Which markets justify different pricing vs. currency-converted equivalents

**Pricing page guidance:**
- Recommended page structure (tier order, emphasis, CTA placement)
- Messaging: how to frame each tier, how to communicate the annual discount
- What NOT to include (complexity, ambiguous features, hidden costs)

**A/B testing plan:**
- What to test: price points, tier structure, annual discount, trial duration, free tier scope
- Recommended first test (highest-leverage variable)
- Minimum sample size for significance
- Test duration recommendation

**Primary research design** (for user to execute):
If confidence on price points is Medium or Low, design a validation study:
- **Van Westendorp survey:** 4 questions adapted to the specific product, recommended sample size (minimum n=50, ideal n=200), target respondent profile, recommended distribution channels
- **Gabor-Granger study:** price points to test (based on the floor-to-ceiling range from Phase 4), recommended sample size, structure
- **Pricing page A/B test:** control (current or recommended) vs. variant, primary metric (trial start rate or purchase rate), required traffic volume for 95% confidence

**Save:** `phase5-strategy.json`. Follow the Phase Transition Protocol — present pricing recommendations for user approval before generating the report.

---

### Phase 6 — Report Generation

Generate `report.html` using `references/report-template.html` as the base template. Fill `{{TOKENS}}` from pipeline JSON outputs. See `references/research-storage.md` → "Final Report — HTML" for the full design spec.

**Sections specific to pricing report:**

| Section | Data source |
|---|---|
| Executive Summary | phase4 + phase5 `_summary` fields |
| Competitive Pricing Landscape | phase2 architectures + phase4 landscape table |
| Category Patterns | phase2 category patterns (dominant model, median prices, standard gates) |
| Price Sensitivity | phase3 review sentiment, community signals, comparison content |
| Pricing Architecture Analysis | phase2 per-competitor architecture cards |
| Revenue Scenarios | phase4 revenue modeling table |
| Pricing Recommendation | phase5 tiers, prices, trial structure |
| Platform & Localization | phase5 platform strategy, localized pricing |
| Validation Plan | phase5 A/B test plan, survey design |

**Save:** `report.html` — mark `phases.6_report` and top-level `status` as `complete`. Update `_index.json`. Write `actions.json` with all Phase 5 recommendations as `pending` (see `references/research-storage.md` → "Action Tracking").

---

## Output Schemas

**Authority:** `references/schema-pricing.json` — JSON Schema (draft 2020-12) defining all pipeline output files. Validate every file against the schema before saving.

Infrastructure schemas (_manifest.json, _index.json, actions.json): see `references/schema-infrastructure.json`.
Product foundation schema: see `references/schema-foundation.json`.
Report template: see `references/report-template.html`.

Every JSON file must include a `_summary` field. After each file is written, validate per the Write Protocol in `references/research-storage.md`, then update both `_manifest.json` and `_index.json`.

### Files by phase

| Phase | File | Schema `$defs` key |
|---|---|---|
| 1 | `phase1-aggregated-pricing.json` | `phase1_aggregated_pricing` |
| 2 | `phase2-architectures.json` | `phase2_architectures` |
| 3 | `phase3-sensitivity.json` | `phase3_sensitivity` |
| 4 | `phase4-synthesis.json` | `phase4_synthesis` |
| 5 | `phase5-strategy.json` | `phase5_strategy` |

### Compact examples

One example per file for human illustration. The schema file is the authority for all field types, enums, and constraints.

### `phase1-aggregated-pricing.json`

```json
{
  "_summary": "{N} competitors with pricing data. {M} from existing pipelines, {P} newly scraped. Price range: {min}-{max}/mo. {Q} offer free tiers.",
  "sources": { "competitive_pipeline": "competitive-2026-04-05T14-23-00", "aso_pipeline": "aso-2026-04-04T09-00-00", "fresh_scrapes": ["competitor-d"] },
  "competitors": [
    { "name": "Snapseed", "slug": "snapseed", "data_source": "aso_pipeline", "model": "free", "has_iap": false, "has_subscription": false, "website_pricing_url": null, "app_store_price": "Free", "notes": "Fully free, Google-subsidized" },
    { "name": "VSCO", "slug": "vsco", "data_source": "competitive_pipeline", "model": "freemium", "has_iap": true, "has_subscription": true, "website_pricing_url": "https://vsco.co/subscribe", "tiers": [{ "name": "Free", "monthly": 0, "features_summary": "Basic filters" }, { "name": "VSCO Pro", "monthly": 12.99, "annual": 59.99, "features_summary": "All filters, video editing" }], "trial": { "duration_days": 7, "credit_card_required": true }, "notes": null }
  ],
  "gaps": ["competitor-f has no pricing data — website requires login"]
}
```

### `phase2-architectures.json`

```json
{
  "_summary": "{N} competitor pricing architectures mapped. Dominant model: {model} ({X}/{N}). Median price: ${Y}/mo. Most common upgrade trigger: {trigger}.",
  "architectures": [
    {
      "name": "VSCO", "slug": "vsco", "model": "freemium", "tier_count": 2,
      "tiers": [
        { "name": "Free", "price_monthly": 0, "price_annual": 0, "key_features": ["Basic filters", "Photo import"], "key_limitations": ["Limited filter library", "No video editing"] },
        { "name": "VSCO Pro", "price_monthly": 12.99, "price_annual": 59.99, "key_features": ["All 200+ filters", "Video editing"], "annual_discount_pct": 61.5 }
      ],
      "upgrade_trigger": "Filter library limitation — free users see locked filters",
      "trial": { "duration_days": 7, "full_access": true, "credit_card_required": true },
      "platform_strategy": "Same price app store and web.",
      "pricing_signals": { "annual_presented_first": true, "savings_messaging": "Save over 60%", "student_pricing": false, "enterprise_pricing": false }
    }
  ],
  "category_patterns": { "dominant_model": "freemium", "dominant_model_count": 7, "median_price_monthly": 6.99, "median_price_annual": 39.99, "average_tier_count": 2.3, "most_common_trial_duration_days": 7, "average_annual_discount_pct": 45, "standard_free_features": ["Basic editing", "Limited filters"], "standard_paid_gates": ["Premium filters", "AI tools", "No watermark"] }
}
```

### `phase3-sensitivity.json`

```json
{
  "_summary": "{N} reviews analyzed for price sentiment. {X}% of negative reviews mention price. Net sentiment: {positive/negative}. Strongest signal: '{finding}'.",
  "review_sentiment": {
    "total_reviews_analyzed": 2500, "reviews_mentioning_price": 312, "price_mention_rate_pct": 12.5,
    "sentiment_breakdown": {
      "positive": { "count": 89, "pct": 28.5, "example_quotes": ["Worth every penny for the AI tools"] },
      "negative": { "count": 178, "pct": 57.1, "example_quotes": ["$13/month is insane for a photo editor"] },
      "comparison": { "count": 31, "pct": 9.9, "example_quotes": ["Same price as VSCO but fewer features"] },
      "feature_price": { "count": 14, "pct": 4.5, "example_quotes": ["Would pay $20/month if they added RAW support"] }
    },
    "model_resistance": { "subscription_fatigue_mentions": 47, "want_one_time_purchase_mentions": 23, "examples": ["Stop making everything a subscription"] },
    "price_threshold_signals": "Complaints spike above $9.99/month. Below $6.99/month, few complaints."
  },
  "community_signals": {
    "sources_scraped": ["reddit", "twitter"], "threads_analyzed": 15,
    "key_findings": [{ "finding": "Reddit consensus: $5-7/mo reasonable for a photo editor", "source": "reddit", "confidence": "medium" }]
  },
  "comparison_content": {
    "pages_analyzed": 8,
    "key_findings": [{ "finding": "Comparison sites highlight $4.99/mo as 'affordable' benchmark", "source": "top_comparison_articles" }]
  }
}
```

### `phase4-synthesis.json`

```json
{
  "_summary": "Pricing analysis for {app}. Recommended model: {model}. Target price: ${X}/mo. Competitive range: ${min}-${max}/mo. Key insight: {one line}.",
  "pricing_landscape": {
    "competitors_analyzed": 10,
    "models_distribution": { "freemium": 7, "free": 1, "subscription_only": 2 },
    "price_distribution": {
      "monthly": { "min": 2.99, "max": 12.99, "median": 6.99 },
      "annual": { "min": 19.99, "max": 69.99, "median": 39.99 },
      "one_time": { "min": 4.99, "max": 29.99, "median": 9.99 }
    }
  },
  "sensitivity_summary": "12.5% of negative reviews mention price. Complaints spike above $9.99/mo. Community consensus: $5-7/mo is reasonable. Strong minority wants one-time purchase option.",
  "value_metric": {
    "recommended": "feature_tier",
    "rationale": "Category standard is feature-gated tiers. Users expect free basic editing with paid premium tools. Usage-based (per-export) would create friction in a high-frequency use case.",
    "alternatives_considered": ["per_usage", "per_user"],
    "why_rejected": "Per-usage creates anxiety for creators who edit 20+ photos/day. Per-user irrelevant for solo-use product."
  },
  "model_recommendation": {
    "primary": "freemium_subscription",
    "rationale": "7/10 competitors use freemium. Audience expects free entry. Subscription justified by ongoing AI model updates and cloud features. Add one-time purchase option for premium filters to address subscription fatigue (23 review mentions).",
    "secondary": "one_time_iap_for_extras",
    "confidence": "high"
  },
  "tier_recommendation": {
    "tiers": [
      {
        "name": "Free",
        "features": ["Basic editing", "10 filters", "Standard export"],
        "upgrade_trigger": "Watermark on AI-edited photos + limited AI uses per day (3)",
        "rationale": "Watermark creates visible limitation. Daily AI limit creates repeated friction."
      },
      {
        "name": "Pro",
        "features": ["All AI tools unlimited", "200+ filters", "No watermark", "Batch edit", "Cloud sync"],
        "rationale": "Bundles all premium features. Single tier simplifies decision."
      }
    ],
    "tier_count_rationale": "Category median is 2.3 tiers. Adding a third tier risks decision paralysis for an impulse-category product. Two tiers = simple choice."
  },
  "price_points": {
    "pro_monthly": {
      "floor": 3.99,
      "target": 6.99,
      "ceiling": 9.99,
      "rationale": "Floor: below $4 signals 'too cheap' for AI-powered tool. Target: matches category median, below complaint threshold. Ceiling: $9.99 is the spike point for price complaints.",
      "confidence": "high"
    },
    "pro_annual": {
      "target": 39.99,
      "annual_discount_pct": 52,
      "savings_messaging": "Save $44/year",
      "rationale": "Matches category median annual. 52% discount is above average (45%) — incentivizes annual commitment."
    },
    "one_time_filter_packs": {
      "target": 4.99,
      "rationale": "Optional non-consumable IAP for curated filter packs. Addresses one-time purchase preference without undermining subscription."
    }
  },
  "revenue_scenarios": {
    "assumptions": {
      "monthly_new_users": 5000,
      "source": "current install rate from product foundation"
    },
    "conservative": {
      "trial_to_paid_pct": 3,
      "monthly_churn_pct": 8,
      "monthly_revenue": 1048,
      "annual_revenue": 12576,
      "ltv_per_subscriber": 87.38,
      "notes": "3% conversion is 25th percentile for freemium apps (approximate industry range — verify against category-specific benchmarks)"
    },
    "target": {
      "trial_to_paid_pct": 6,
      "monthly_churn_pct": 5,
      "monthly_revenue": 2097,
      "annual_revenue": 25164,
      "ltv_per_subscriber": 139.80,
      "notes": "6% conversion is median for well-optimized freemium apps (approximate industry range — verify against category-specific benchmarks)"
    },
    "optimistic": {
      "trial_to_paid_pct": 10,
      "monthly_churn_pct": 3,
      "monthly_revenue": 3495,
      "annual_revenue": 41940,
      "ltv_per_subscriber": 233.00,
      "notes": "10% conversion is 75th percentile, requires strong onboarding (approximate industry range — verify against category-specific benchmarks)"
    }
  }
}
```

### `phase5-strategy.json`

```json
{
  "_summary": "Pricing strategy for {app}. {N} tiers. Pro at ${X}/mo (${Y}/yr). {trial_duration}-day trial. Validation: {A/B test or survey plan}.",
  "recommended_model": {
    "model": "freemium_subscription",
    "rationale": "Matches category convention. Free tier drives acquisition. Subscription justified by ongoing AI model improvements and cloud sync."
  },
  "recommended_tiers": [
    {
      "name": "Free",
      "price": 0,
      "features": ["Basic editing tools", "10 curated filters", "Standard quality export", "3 AI edits per day"],
      "limitations": ["Watermark on AI-edited exports", "No batch editing", "No cloud sync"],
      "upgrade_trigger": "Watermark on AI exports + daily AI limit",
      "target_audience": "Casual users, first-time installers evaluating the app"
    },
    {
      "name": "Pro",
      "price_monthly": 6.99,
      "price_annual": 39.99,
      "annual_discount_pct": 52,
      "features": ["Unlimited AI edits", "200+ filters", "No watermark", "Batch editing", "Cloud sync", "Priority processing"],
      "target_audience": "Active creators posting regularly, small business owners"
    }
  ],
  "one_time_iaps": [
    {
      "name": "Premium Filter Packs",
      "price": 4.99,
      "type": "non_consumable",
      "rationale": "Addresses subscription fatigue. Revenue supplement. Does not cannibalize Pro tier (Pro includes all filters)."
    }
  ],
  "trial_structure": {
    "duration_days": 7,
    "access_level": "Full Pro features",
    "credit_card_required": true,
    "rationale": "7 days is category standard. Full access maximizes feature discovery. CC required increases intent quality — conversion rate is lower but revenue per converted user is higher.",
    "conversion_optimization": [
      "Day 1: Welcome email highlighting Pro-only features",
      "Day 5: Reminder with usage stats (You used AI editing 23 times this week)",
      "Day 7: Trial ending notification with annual plan savings emphasis",
      "Post-trial: Downgrade to Free, show watermark on next AI edit as re-conversion trigger"
    ]
  },
  "platform_pricing": {
    "app_store": {
      "monthly_tier": "$6.99 (Tier 5)",
      "annual_tier": "$39.99 (Tier 30)",
      "introductory_offer": "7-day free trial → auto-renew monthly",
      "notes": "Use subscription group to make monthly and annual mutually exclusive"
    },
    "play_store": {
      "monthly": "$6.99",
      "annual": "$39.99",
      "trial": "7-day free trial",
      "notes": "Match App Store pricing for consistency"
    },
    "web_direct": {
      "recommended": false,
      "rationale": "Product is mobile-first. Most users discover via app store. Web billing adds complexity without sufficient volume to justify."
    }
  },
  "localized_pricing": [
    { "market": "US", "monthly": 6.99, "annual": 39.99, "currency": "USD" },
    { "market": "EU", "monthly": 6.99, "annual": 39.99, "currency": "EUR", "notes": "Parity with USD" },
    { "market": "Brazil", "monthly": 14.90, "annual": 79.90, "currency": "BRL", "notes": "PPP-adjusted: ~40% below USD equivalent" },
    { "market": "Japan", "monthly": 800, "annual": 4800, "currency": "JPY", "notes": "Round to psychologically clean number" }
  ],
  "ab_testing_plan": {
    "first_test": {
      "variable": "Price point: $4.99 vs $6.99 vs $9.99/month",
      "hypothesis": "If we price at $6.99/mo, trial-to-paid conversion will be within 15% of $4.99/mo while generating 40% more revenue per user",
      "primary_metric": "Revenue per install (not conversion rate — higher conversion at lower price can yield less revenue)",
      "minimum_sample": 5000,
      "duration": "14 days minimum",
      "traffic_split": "33/33/33"
    },
    "second_test": {
      "variable": "Trial duration: 3-day vs 7-day vs 14-day",
      "hypothesis": "7-day trial maximizes conversion because users need a full week to build a habit",
      "primary_metric": "Trial-to-paid conversion rate",
      "minimum_sample": 3000,
      "duration": "30 days (must capture full trial period for 14-day variant)"
    }
  },
  "primary_research_design": {
    "method": "van_westendorp",
    "when_to_run": "If A/B test results are inconclusive or if launching in a new market",
    "questions": [
      "At what monthly price would FotoApp Pro be so cheap that you'd question its quality?",
      "At what monthly price would FotoApp Pro be a bargain — a great deal for the money?",
      "At what monthly price would FotoApp Pro start to feel expensive, but you'd still consider it?",
      "At what monthly price would FotoApp Pro be too expensive to consider?"
    ],
    "target_respondents": "Social media creators who currently use a photo editing app, aged 18-35",
    "sample_size": "Minimum 100, ideal 200",
    "distribution": "In-app survey to existing Free tier users + social media polling"
  }
}
```

---

## Pricing Page Reference

Principles for designing the pricing page or in-app paywall. Informed by Phase 5 recommendations.

### Structure
- Lead with the recommended tier (visual hierarchy, pre-selected, "Most Popular" label)
- Show annual pricing by default with monthly as secondary toggle
- Make savings concrete and specific: "Save $44/year" beats "Save 52%"
- Feature comparison table below the pricing cards — let curious users compare, but don't front-load complexity
- 2-3 tiers maximum for consumer products; 3-4 for B2B SaaS
- CTA button text: action-oriented ("Start Free Trial", "Get Pro") not passive ("Learn More")

### In-app paywall (mobile)
- Show paywall at a moment of desire, not a moment of frustration
- Best triggers: after the user completes their first edit (positive experience), after they hit the AI limit (motivation is high), after they see the watermark on a photo they want to share (conversion urgency)
- Worst triggers: immediately after install (no value demonstrated), after a crash or error (negative association)
- Show social proof on the paywall: "Join 50K+ creators", star rating, review quote
- Always show the annual option first — mobile users decide quickly and the first option gets the most conversions

### Anti-patterns to avoid
- Hidden costs or surprise billing
- Making cancellation difficult (damages trust and generates negative reviews)
- Dark patterns on trial conversion (auto-upgrading without clear warning)
- Too many tiers or confusing feature differences
- Pricing that differs between app store and website without explanation
