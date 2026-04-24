# Pipeline Orchestration

How pipelines relate, what order to run them, and how to choose the right engagement depth for a given request.

---

## Contents

1. [Engagement Depth](#engagement-depth)
2. [Pipeline Dependency Graph](#pipeline-dependency-graph)
3. [Goal-to-Sequence Mapping](#goal-to-sequence-mapping)
4. [Cross-Pipeline Data Contracts](#cross-pipeline-data-contracts)
5. [Multi-Locale Research](#multi-locale-research)

---

## Engagement Depth

Not every question needs a pipeline. Match the response depth to the question.

| Depth | When | What you do |
|---|---|---|
| **Quick answer** | User needs a specific tactical answer ("What should my title be?", "Is $9.99 too high?") | Use product foundation + any existing research. State confidence level. Offer to go deeper if confidence is below High. |
| **Advisory** | User needs strategic guidance ("How should I position against X?", "What channels should I prioritize?") | Use strategy frameworks + product foundation. No pipeline needed. Cite what research would strengthen the recommendation. |
| **Single pipeline** | User needs comprehensive research on one domain ("Optimize my App Store listing", "Analyze my competitors") | Run the appropriate pipeline end-to-end. |
| **Multi-pipeline** | User needs a complete marketing strategy or the question spans domains ("Launch strategy for my app", "Full marketing audit") | Run pipelines in the sequence defined below. |

**Default to the lightest engagement that serves the question.** Escalate only when confidence is insufficient or the user explicitly asks for depth. When giving a quick answer or advisory response, always state what pipeline would improve confidence and offer to run it.

---

## Pipeline Dependency Graph

```
                    ┌──────────────────┐
                    │     Product      │
                    │   Foundation     │
                    │  (prerequisite   │
                    │   for all)       │
                    └────────┬─────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
     ┌────────────┐  ┌────────────┐  ┌────────────┐
     │    ASO     │  │    SEO     │  │Competitive │
     │  Pipeline  │  │  Pipeline  │  │Intelligence│
     └──────┬─────┘  └──────┬─────┘  └──────┬─────┘
            │               │               │
            │   writes to   │   writes to   │  writes to
            │   learned:    │   learned:    │  learned:
            │  competitive  │  search       │  competitive
            │  vocabulary   │  vocabulary   │  features
            │  features     │              │  positioning
            │  audience     │              │  pricing (partial)
            │               │              │  audience
            └───────────┬───┴──────────────┘
                        │
                        ▼
               ┌────────────────┐
               │    Pricing     │
               │   Pipeline     │
               │ (consumes data │
               │  from above)   │
               └────────────────┘
```

### Dependencies

| Pipeline | Hard prerequisite | Soft prerequisites (improves quality) |
|---|---|---|
| ASO | Product foundation | Competitive intelligence (provides validated competitor set) |
| SEO | Product foundation | ASO (shares category vocabulary), competitive intelligence (provides content competitor set) |
| Competitive intelligence | Product foundation | None — can run first |
| Pricing | Product foundation | Competitive intelligence (pricing landscape), ASO (IAP data, review sentiment) |

**Hard prerequisite** = pipeline will not start without it.
**Soft prerequisite** = pipeline works without it but produces better results with it. When a soft prerequisite hasn't been run, the pipeline discovers its own data (slower, potentially less complete). When it has been run, the pipeline reads from `learned` and skips redundant work.

### Independence

ASO, SEO, and competitive intelligence are **independent** — they can run in parallel or in any order. Each writes different fields to the `learned` section. Running competitive intelligence first gives the other two a head start (validated competitor set, feature landscape), but it's not required.

Pricing is the **downstream consumer** — it reads from all other pipelines. Running it last maximizes data quality. Running it standalone is possible but requires its own competitor pricing scraping (Phase 1 gap-filling).

---

## Goal-to-Sequence Mapping

Common user goals mapped to the recommended pipeline sequence.

### "Launch my app" / "Full marketing strategy"

```
1. Product foundation (if missing or stale)
2. Competitive intelligence
3. ASO + SEO (can run in parallel — they're independent)
4. Pricing (reads from all above)
```

Estimated effort: 4 pipeline runs. Competitive intelligence should complete before ASO/SEO start for best results, but parallel execution is acceptable if time-constrained.

### "Optimize my App Store listing"

```
1. Product foundation (if missing or stale)
2. ASO pipeline
```

If competitive intelligence exists and is < 3 months old, ASO will use it automatically via `learned`. If not, ASO discovers competitors independently during Phase 2.

### "Analyze my competitors"

```
1. Product foundation (if missing or stale)
2. Competitive intelligence pipeline
```

Standalone. No other pipeline needed unless the user wants to act on the findings (in which case, follow up with the relevant pipeline).

### "Improve my SEO / content strategy"

```
1. Product foundation (if missing or stale)
2. SEO pipeline
```

If ASO research exists, SEO will reuse `category_vocabulary` from `learned`. If competitive intelligence exists, SEO will reuse `competitive_set.content_competitors`.

### "Set my pricing" / "Optimize pricing"

```
1. Product foundation (if missing or stale)
2. Competitive intelligence (if none exists or > 3 months old)
3. Pricing pipeline
```

Pricing without competitive data is possible but significantly weaker. Always recommend running competitive intelligence first if no recent run exists.

### "Quick audit" / "What should I focus on?"

```
1. Product foundation (if missing or stale)
2. Advisory response using strategy frameworks — no pipeline
```

Review the product foundation, identify the most obvious gaps (no ASO optimization? no content strategy? pricing not researched?), and recommend which pipeline to run first. Prioritize by expected impact.

---

## Cross-Pipeline Data Contracts

Each pipeline reads from and writes to `product-foundation.json` → `learned`. This table defines **what each pipeline expects to find** (reads) and **what it guarantees to produce** (writes).

### Reads (what pipelines consume from `learned`)

| Pipeline | Field it reads | What it uses it for | Behavior if absent |
|---|---|---|---|
| ASO | `competitive_set` | Seed competitor list for Phase 2 | Discovers competitors from scratch via store search |
| ASO | `category_vocabulary` | Seed keywords for Phase 1 | Generates keywords from product foundation only |
| SEO | `competitive_set.content_competitors` | Seed domain list for Phase 2 | Discovers domains from scratch via SERP scraping |
| SEO | `category_vocabulary` | Seed keywords for Phase 1 | Generates keywords from product foundation only |
| SEO | `search_landscape` (from prior SEO run) | Baseline to detect shifts | Runs full discovery |
| Pricing | `competitive_set` | Full competitor list for pricing scraping | Discovers competitors independently (slower) |
| Pricing | `feature_landscape` | Feature matrix for tier design | Scrapes feature data during Phase 1 |
| Pricing | `pricing_intelligence` (from prior pricing run) | Baseline to detect changes | Runs full analysis |
| Competitive | `competitive_set` (from prior run) | Known competitors to verify + expand | Discovers from scratch |

### Writes (what pipelines produce into `learned`)

See the "Foundation Writeback" section in each playbook and in `references/research-storage.md` for the full field ownership table, update modes (replace vs. merge), and staleness rules.

---

## Multi-Locale Research

When a product supports multiple locales, research scope must be managed explicitly.

### When to run multi-locale research

- **ASO:** always consider it — each App Store locale has independent keyword fields and rankings. A single-locale run misses opportunities in other markets.
- **SEO:** consider it when the website targets multiple languages/regions with separate content (hreflang setup, country-specific domains or subdirectories).
- **Competitive intelligence:** usually single-locale is sufficient — competitors are mostly the same across markets. Run multi-locale only if the competitive set differs significantly by region.
- **Pricing:** always consider localized pricing — purchasing power parity varies. The pricing pipeline's Phase 5 includes localized pricing recommendations.

### Locale prioritization

When the product supports many locales, research them in priority order:

1. **Primary market** — the locale generating the most revenue or installs. Always research first.
2. **Growth markets** — locales with high potential but low current penetration. Research next.
3. **Maintenance markets** — locales with stable performance. Research only when stale or when the user flags an issue.

Ask the user to rank their locales by priority if not obvious from the product foundation.

### Multi-locale pipeline execution

For ASO and SEO, run **one pipeline instance per locale** (or per locale group if locales share a language, e.g., `es` covers Spain and most of Latin America). Each instance gets its own timestamped directory: `aso-2026-04-05T14-23-00-en`, `aso-2026-04-05T16-00-00-es`.

The product foundation is shared across all locale runs. Each run writes locale-specific findings to its own output files, not to the shared `learned` section (which remains locale-agnostic for structural knowledge like competitive set and feature landscape).
