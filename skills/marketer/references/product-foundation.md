# Product Foundation

Shared intake protocol that runs once per product and feeds every downstream pipeline (ASO, SEO, competitive intelligence, pricing, GTM). Stored at `{project_root}/research/product-foundation.json` — outside any timestamped pipeline directory because it belongs to the product, not to a single research run.

---

## Contents

1. [When to Run](#when-to-run)
2. [Intake Process](#intake-process)
3. [Storage](#storage)
4. [Schema](#schema)
5. [`learned` Section](#learned-section)
6. [Field Notes](#field-notes)

---

## When to Run

**Before any pipeline.** Every playbook (ASO, SEO, competitive, etc.) has this as a prerequisite.

- If `{project_root}/research/product-foundation.json` does not exist → run the full intake
- If it exists → read it, check `updated_at`, ask the user: "Product foundation last updated {date}. Still current, or should we update anything?" Only update sections the user flags as stale.
- If the user provides new information during a pipeline (e.g., "we changed our pricing last week") → update the relevant section of the foundation and bump `updated_at`

---

## Intake Process

The intake combines two sources: **what you ask the user** (they know their product, audience, and goals) and **what you research** (you verify and supplement with observable data). Both are marked in the schema with their source.

### Step 1 — Gather from the user

Ask these questions in order. Accept whatever depth the user provides; do not force answers to optional questions. Mark unanswered fields as `null`.

**Product identity:**
- What is the product name?
- What does it do? (functional description in the user's words)
- What problem does it solve and for whom?
- What platform(s)? (iOS, Android, web, desktop, multi-platform)
- What stage? (idea, MVP, launched, growth, mature)
- Is it live? If yes, where? (app store URLs, website URL)

**Value proposition:**
- If a user had to explain your product to a friend in one sentence, what would they say?
- What can users do with this that they couldn't before (or couldn't do as well)?
- What are the product's features, ranked by importance?

**Audiences:**
- Who is the primary audience? Describe them.
- Is there a secondary audience?
- Who is this product NOT for? (Anti-audience — constrains positioning and prevents "everything for everyone" drift)

**Positioning:**
- How do you describe your product's category? (e.g., "photo editor", "project management tool", "meditation app")
- What makes your product different from the alternatives?
- What alternatives do your users currently use? (direct competitors, indirect substitutes, manual workarounds)
- Do you have a positioning statement? If so, share it.

**Business context:**
- What is the business model? (subscription, freemium, one-time purchase, ad-supported, free)
- Current pricing? (tiers, prices, trial structure)
- Revenue goals or growth targets? (optional — helps prioritize channels)
- Geographic scope? Which markets matter most?
- What locales does the product support?

**Existing marketing state:**
- What channels are you currently using? (SEO, ASO, paid, social, email, partnerships, none yet)
- What's working? What's not?
- Any current metadata? (app store title/subtitle/keywords, website meta tags, ad copy)
- Any past research, insights, or data you can share?

### Step 2 — Research and verify

After the user interview, use available tools to supplement:

- **If the app is live in a store**: use `/browser-use` to scrape the current store listing — title, subtitle, description, screenshots, ratings, ratings count, reviews sample (20 recent), IAP list. Compare with what the user said.
- **If a website exists**: visit it. Extract homepage headline, meta title, meta description, pricing page content, feature list, blog presence, about page.
- **If the project has code in the working directory**: read README, pubspec.yaml / package.json / build.gradle / equivalent to understand supported platforms, dependencies, and features.
- **Web search** the product name: check for existing press coverage, community mentions, competitor comparisons that mention it.

Record everything you find. Where it conflicts with what the user said, note the discrepancy and ask.

### Step 3 — Synthesize and confirm

Compose the product foundation JSON. Present a summary to the user before saving:

```
Product Foundation Summary:

  Product: FotoApp (iOS + Android, launched, growth stage)
  Value prop: AI-powered photo editing for social media creators
  Primary audience: Social media creators aged 18-35
  Anti-audience: Professional photographers needing RAW workflow
  Category frame: "AI photo editor"
  Differentiators: Speed (one-tap editing), AI background removal
  Main alternatives: Snapseed, VSCO, Lightroom Mobile
  Business model: Freemium + subscription ($6.99/mo)
  Current channels: ASO, Instagram organic
  Locales: en, es, pt_BR, de, fr, ja

  Does this look right? Anything to correct or add?
```

Save only after the user confirms.

---

## Storage

**Location:** `{project_root}/research/product-foundation.json`

This file lives at the research root, not inside any pipeline directory. All pipelines read from this single file. It has its own `version` counter — bumped on every update.

---

## Schema

The full field-level specification — required fields, types, enum constraints — lives in `references/schema-foundation.json`. That file is the authoritative contract. The example below illustrates the shape; the schema file defines the rules.

```json
{
  "_summary": "Product foundation for FotoApp. iOS, Android. Growth stage. Value prop: Professional photo edits in 3 seconds with AI. Primary audience: social media creators 18-35. Model: freemium.",
  "version": 1,
  "created_at": "2026-04-05T14:00:00Z",
  "updated_at": "2026-04-05T14:00:00Z",
  "identity": {
    "name": "FotoApp",
    "tagline": "AI-powered photo editing",
    "description": "Mobile photo editor that uses AI to deliver professional-quality edits in seconds",
    "problem_solved": "Social media creators need professional-looking photos but lack Photoshop skills and time",
    "platforms": ["ios", "android"],
    "stage": "growth",
    "is_live": true,
    "store_urls": { "app_store": "https://apps.apple.com/app/id123456789", "play_store": "https://play.google.com/store/apps/details?id=com.fotoapp" },
    "website_url": "https://fotoapp.com"
  },
  "value_proposition": {
    "one_sentence": "Professional photo edits in 3 seconds with AI — no skills needed",
    "mechanism": "AI models trained on professional editing styles apply complex adjustments in a single tap",
    "features": [
      { "name": "AI one-tap enhance", "importance": "primary", "description": "Automatically adjusts lighting, color, and sharpness" },
      { "name": "Background removal", "importance": "primary", "description": "AI-powered background removal and replacement" }
    ]
  },
  "audiences": {
    "primary": { "description": "Social media creators aged 18-35", "needs": "Professional-looking photos quickly", "current_behavior": "Currently use Snapseed or VSCO" },
    "secondary": { "description": "Small business owners needing product photos", "needs": "Consistent product photography", "current_behavior": "iPhone camera + basic auto-enhance" },
    "anti_audience": { "description": "Professional photographers needing RAW workflow", "reason": "Product optimizes for speed over precision" }
  },
  "positioning": {
    "category_frame": "AI photo editor",
    "category_strategy": "reframe",
    "positioning_statement": "For social media creators who need professional-looking photos fast, FotoApp is the AI photo editor that delivers pro-quality results in one tap.",
    "differentiators": [
      { "claim": "One-tap professional results", "evidence": "AI enhancement benchmarked against professional edits", "is_validated": false }
    ],
    "main_alternatives": [
      { "name": "Snapseed", "type": "direct", "positioning": "Professional photo editor (free, Google-backed)" }
    ]
  },
  "business": {
    "model": "freemium",
    "pricing": {
      "free_tier": "Basic editing, 10 filters, watermarked exports",
      "tiers": [{ "name": "Pro", "monthly": 6.99, "annual": 39.99, "features": "All filters, no watermark, AI tools, batch edit" }],
      "trial": { "duration_days": 7, "credit_card_required": true }
    },
    "revenue_target": null,
    "geographic_scope": ["US", "EU", "LATAM", "Japan"],
    "supported_locales": ["en", "es", "pt_BR", "de", "fr", "ja"]
  },
  "current_marketing": {
    "channels": [{ "channel": "ASO", "status": "active", "notes": "Current App Store listing, not recently optimized" }],
    "current_metadata": { "app_store_title": "FotoApp: Photo Editor", "app_store_subtitle": "Edit Photos Easily", "keyword_field": "photo,editor,filters,enhance,retouch", "website_meta_title": "FotoApp - AI Photo Editor", "website_meta_description": "Edit your photos with AI." },
    "whats_working": "App store search drives 60% of installs",
    "whats_not_working": "Website gets minimal organic traffic",
    "past_research": null
  },
  "observed_data": {
    "source": "store_scrape",
    "scraped_at": "2026-04-05T14:15:00Z",
    "app_store": { "rating": 4.3, "ratings_count": 8500, "last_updated": "2026-03-20", "current_version": "3.2.1" },
    "play_store": { "rating": 4.1, "ratings_count": 12000, "last_updated": "2026-03-22", "installs": "100K+" },
    "website": { "homepage_headline": "AI Photo Editor - Edit Photos in Seconds", "has_blog": true, "blog_post_count": 3, "has_pricing_page": true }
  }
}
```

### `learned` section

The `learned` section does not exist at intake time. It is created and updated by research pipelines after their synthesis phase. Each pipeline writes back durable findings — knowledge that is structural to the product and category, not ephemeral to a single research run.

The full field-level specification — required fields, types, enum constraints, pipeline ownership, update modes, and staleness rules — lives in `references/schema-foundation.json` → [learned](#learned). The compact example below illustrates the shape; the schema file defines the rules.

```json
"learned": {
  "competitive_set": {
    "updated_at": "2026-04-05T16:00:00Z",
    "source": "aso-2026-04-05T14-23-00",
    "direct": [{ "name": "Snapseed", "slug": "snapseed", "ratings_count": 892000, "rating": 4.6, "positioning": "Professional photo editor (free, Google-backed)" }],
    "indirect": [{ "name": "Canva", "slug": "canva", "ratings_count": 2100000, "rating": 4.7, "positioning": "All-in-one design tool with photo editing" }],
    "content_competitors": [{ "domain": "adobe.com", "positioning": "Dominates SEO for photo editing terms" }],
    "notes": "Verified from app store search across 30 keywords (127 unique apps)."
  },
  "category_vocabulary": {
    "updated_at": "2026-04-05T16:00:00Z",
    "source": "aso-2026-04-05T14-23-00",
    "user_search_terms": ["photo editor", "ai photo", "background remover"],
    "praise_language": ["professional quality", "quick edits", "easy to use"],
    "complaint_language": ["crashes after update", "subscription too expensive"],
    "notes": "From autocomplete scraping + review clustering across 10 competitors."
  },
  "feature_landscape": {
    "updated_at": "2026-04-05T16:00:00Z",
    "source": "aso-2026-04-05T14-23-00",
    "table_stakes": ["Filters", "Manual adjust", "Crop and rotate"],
    "differentiators": ["AI enhance", "RAW support", "Batch edit"],
    "gaps": ["Batch edit with AI", "Offline cloud sync"],
    "notes": "From feature matrix of top 10 apps by search ranking."
  },
  "validated_positioning": {
    "updated_at": "2026-04-05T16:00:00Z",
    "source": "competitive-2026-04-01T11-00-00",
    "differentiators_status": [
      { "claim": "One-tap professional results", "status": "validated", "evidence": "Only 2/10 competitors offer one-tap AI editing." }
    ],
    "positioning_gaps": [
      { "gap": "Speed as primary positioning", "evidence": "23% of praise reviews mention speed but only 2/10 apps lead with it", "opportunity": "high" }
    ],
    "notes": "Validated against competitive intelligence teardown of 15 competitors."
  },
  "search_landscape": {
    "updated_at": "2026-04-02T12:00:00Z",
    "source": "seo-2026-04-02T10-30-00",
    "demand_confirmed": ["ai photo editing", "background removal"],
    "demand_absent": ["photo editor blockchain"],
    "topical_clusters": [{ "cluster": "AI photo editing", "keywords_count": 12, "hub_potential": "high" }],
    "content_gaps_with_demand": ["AI photo editing tutorials"],
    "dominant_formats": { "transactional": "landing_page", "informational": "long_form_guide", "commercial": "comparison_page" },
    "notes": "From SERP analysis of 45 keywords."
  },
  "pricing_intelligence": {
    "updated_at": "2026-04-05T18:00:00Z",
    "source": "pricing-2026-04-05T16-00-00",
    "category_norms": { "dominant_model": "freemium", "median_monthly": 6.99, "median_annual": 39.99, "standard_free_features": ["Basic editing", "Limited filters"], "standard_paid_gates": ["Premium filters", "AI tools", "No watermark"] },
    "price_sensitivity_profile": { "acceptable_range_monthly": { "floor": 3.99, "ceiling": 9.99 }, "complaint_threshold_monthly": 9.99, "model_resistance_signals": "23 review mentions of subscription fatigue" },
    "recommended_value_metric": "feature_tier",
    "notes": "From pricing analysis of 10 competitors + review mining of 2500 reviews."
  },
  "audience_insights": {
    "updated_at": "2026-04-05T16:00:00Z",
    "source": "aso-2026-04-05T14-23-00",
    "observed_user_segments": [
      { "segment": "Casual social media posters", "signals": "Praise 'easy' and 'quick'. Low price tolerance.", "size_signal": "Largest segment in reviews" }
    ],
    "top_user_needs": ["Speed", "Professional-looking results", "No learning curve"],
    "top_user_frustrations": ["App instability", "Subscription cost", "Feature limitations in free tier"],
    "notes": "From review clustering across 10 competitors (5000 reviews)."
  }
}
```

#### Which pipelines write which fields

Pipeline ownership, update modes (replace/merge), and staleness rules are documented per-field in `references/schema-foundation.json` → [learned](#learned). Summary:

| `learned` field | Written by | Mode |
|---|---|---|
| `competitive_set` | ASO, SEO, competitive intelligence | Merge |
| `category_vocabulary` | ASO, SEO | Merge |
| `feature_landscape` | ASO, competitive intelligence | Replace |
| `validated_positioning` | Competitive intelligence, pricing | Merge |
| `search_landscape` | SEO | Replace |
| `pricing_intelligence` | Pricing (primary), competitive intelligence (partial) | Replace |
| `audience_insights` | ASO, competitive intelligence | Merge |

### Field notes

These constraints are also documented in the schema file as enum values. Quick reference:

- `positioning.category_strategy`: `own` · `reframe` · `replace`
- `positioning.differentiators[].is_validated`: `true` if backed by data, `false` if unvalidated. Pipelines should prioritize validating `false` entries.
- `positioning.main_alternatives[].type`: `direct` · `indirect` · `alternative`
- `observed_data`: null if the app/website is not live
- `audiences.anti_audience`: optional but strongly encouraged — sharpens positioning
- `current_marketing.past_research`: pointer to existing research, not embedded data
