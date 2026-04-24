# Research Storage Convention

Defines how marketing research is stored, versioned, and resumed. All research pipelines (ASO, SEO, competitive intelligence, etc.) follow this convention.

Two audiences, two formats:
- **Intermediary results (Phases 0–5):** JSON — optimized for LLM consumption and programmatic access
- **Final report (Phase 6):** single-file HTML — optimized for humans: navigable, structured, shareable

---

## Contents

1. [Directory Layout](#directory-layout)
2. [Directory Naming](#directory-naming)
3. [Manifest File](#manifest-file-_manifestjson)
4. [Write Protocol](#write-protocol)
5. [Foundation Writeback](#foundation-writeback)
6. [Intermediary Files — LLM Optimization](#intermediary-files--llm-optimization)
7. [`_index.json` — Research Navigation](#_indexjson--research-navigation)
8. [Pipeline Startup Protocol](#pipeline-startup-protocol)
9. [Phase Transition Protocol](#phase-transition-protocol)
10. [Context Recovery Protocol](#context-recovery-protocol)
11. [Failure Handling Protocol](#failure-handling-protocol)
12. [Action Tracking](#action-tracking)
13. [Starting a Pipeline](#starting-a-pipeline)
14. [Listing Past Researches](#listing-past-researches)
15. [App Slug Convention](#app-slug-convention)
16. [File Format Rules](#file-format-rules)
17. [Final Report — HTML](#final-report--html)

---

## Directory Layout

```
{project_root}/research/
  product-foundation.json          # shared product data — read by all pipelines
  aso-2026-04-05T14-23-00/
    _manifest.json                 # pipeline status — resume logic
    _index.json                    # content summaries — LLM navigation
    phase0-intake.json
    phase1-keywords-raw.json
    phase1-keywords-tiered.json
    phase2-keyword-results.json
    phase2-landscape.json
    phase3/
      {app-slug}/
        metadata.json
        reviews.json
        screenshots.json
        website.json
    phase4-synthesis.json
    phase5-metadata.json
    report.html                    # final human-readable report
  aso-2026-03-10T09-15-00/        # previous run — untouched
  competitive-2026-04-01T11-00-00/ # different pipeline, same project
  seo-2026-04-02T10-30-00/        # SEO research run
  pricing-2026-04-05T16-00-00/    # pricing research — reads from other pipeline outputs
```

`{project_root}` is the root of the project being researched. Research lives with the project, not inside the skill.

`product-foundation.json` lives at the research root — it belongs to the product, not to any pipeline. All pipelines read from it. See `references/product-foundation.md` for the full schema and intake protocol.

---

## Directory Naming

Format: `{type}-{YYYY-MM-DDTHH-MM-SS}`

- `{type}` identifies the pipeline: `aso`, `seo`, `competitive`, `pricing`, etc.
- Timestamp uses dashes instead of colons for filesystem compatibility
- Always UTC
- Generated at the moment the pipeline starts

If the user provides an optional label, append it: `aso-2026-04-05T14-23-00-post-rebrand`

---

## Manifest File (`_manifest.json`)

The manifest tracks pipeline status for resume logic. Updated immediately after each unit of work completes.

### Schema

```json
{
  "version": "1",
  "id": "aso-2026-04-05T14-23-00",
  "label": null,
  "type": "aso",
  "platform": "ios",
  "created_at": "2026-04-05T14:23:00Z",
  "updated_at": "2026-04-05T16:45:22Z",
  "status": "in_progress",
  "phases": {
    "0_intake":       { "status": "complete",     "completed_at": "2026-04-05T14:31:00Z" },
    "1_keywords":     { "status": "complete",     "completed_at": "2026-04-05T14:45:00Z" },
    "2_landscape":    { "status": "complete",     "completed_at": "2026-04-05T15:30:00Z" },
    "3_app_research": { "status": "in_progress",  "started_at":   "2026-04-05T15:31:00Z" },
    "4_synthesis":    { "status": "pending" },
    "5_metadata":     { "status": "pending" },
    "6_report":       { "status": "pending" }
  },
  "phase3": {
    "total": 20,
    "complete": 14,
    "items": {
      "spotify":     { "reviews": "complete", "metadata": "complete", "screenshots": "complete",    "website": "complete" },
      "apple-music": { "reviews": "complete", "metadata": "complete", "screenshots": "in_progress", "website": "pending"  }
    }
  }
}
```

### Status values

| Value | Meaning |
|---|---|
| `pending` | Not started |
| `in_progress` | Started, not complete |
| `complete` | Finished, output file written |
| `failed` | Errored — check `"error"` field for details |
| `skipped` | Intentionally omitted (e.g., Tier B app, no screenshot analysis) |

Top-level `status` is `complete` only when all phases including `6_report` are done.

---

## Write Protocol

1. Write the output file to its final path
2. **Validate** — before saving any JSON file, verify:
   - All required fields are present (see the relevant JSON Schema file: `references/schema-foundation.json` for product foundation, `references/schema-infrastructure.json` for manifest/index/actions, or the pipeline-specific schema in `references/schema-{pipeline}.json`)
   - All enum fields contain a valid value from the defined set
   - All arrays have consistent item shapes (every object in an array has the same keys)
   - `_summary` is present and ≤200 characters for per-phase and per-file summaries; the top-level `_summary` in `_index.json` allows up to 300 characters because it summarizes an entire pipeline run
   - `null` is used for missing optional values — never omit the key
3. Immediately update `_manifest.json` to mark that unit as `complete`
4. Update `_index.json` with the `_summary` from the newly written file

Never mark a unit `complete` before its output file exists. For Phase 3, granularity is per-task per-app — each of reviews, metadata, screenshots, website is tracked independently.

---

## Foundation Writeback

After Phase 4 (synthesis) of any pipeline, write durable findings back to the `learned` section of `{project_root}/research/product-foundation.json`. This creates a learning flywheel: each research run enriches the foundation, and each subsequent run starts with better context.

### When to write back

Immediately after Phase 4 synthesis is saved and before Phase 5 begins. The writeback is part of the Phase 4 completion step.

### What to write back

Only **durable, structural knowledge** — findings that are fundamental to the product and category, not ephemeral to a single run. See `references/product-foundation.md` → "`learned` section" for the full schema, field ownership, update modes (replace vs. merge), and staleness rules.

### How to write back

1. Read `product-foundation.json`
2. Check the `learned` field (create it if it does not exist)
3. For each field this pipeline owns (see the ownership table in `product-foundation.md`):
   - **Replace mode:** overwrite the section with new data, update `updated_at` and `source`
   - **Merge mode:** add new entries, update existing entries with newer data, never remove entries. Update `updated_at` and `source`.
4. Bump `product-foundation.json` → `version` and `updated_at`
5. Write the file back

### How pipelines read it

At the start of every pipeline (Phase 1), read `product-foundation.json` including the `learned` section. Check staleness of each field you intend to use:
- **< 3 months:** use as reliable input, note in output
- **3–6 months:** use as starting point, verify during the run
- **> 6 months:** treat as stale, re-research

If a learned field exists and is fresh, use it to skip redundant work. For example: if `competitive_set` is 1 month old and the ASO pipeline needs competitor names for keyword research, use the cached set instead of re-discovering from scratch.

---

## Intermediary Files — LLM Optimization

All JSON output files (Phases 0–5) follow these rules:

### `_summary` field (required)

Every JSON file starts with a `_summary` field: a natural-language paragraph summarizing the file's contents, key stats, and notable findings. This is the single most impactful LLM optimization — it lets the LLM decide whether to load the full file without reading it.

```json
{
  "_summary": "47 keywords across 3 tiers. Tier 1 (8): photo editor, ai photo, image enhance, ... Tier 2 (22): background remover, portrait retouch, ... Top opportunity: 'ai photo editor' (low competition, high demand proxy).",
  "tier1": [...],
  "tier2": [...],
  "tier3": [...]
}
```

**What makes a good `_summary`:**
- Total count of items in the file
- Top 3–5 most important entries by name
- The single most notable finding or outlier
- Enough context that the LLM can answer basic questions without reading deeper

### `assumptions` field (required in Phase 4 synthesis files)

Every Phase 4 synthesis file must include an `assumptions` array listing the key assumptions underlying the analysis. Each entry states: what is assumed, the confidence level, and what would invalidate it.

This serves two purposes:
1. Phase 5 can check whether the assumptions hold before building strategy on top of the synthesis
2. Future pipeline runs can verify whether prior assumptions are still valid before reusing cached `learned` data

Example:
```json
"assumptions": [
  {
    "assumption": "Ratings count is a reliable proxy for search volume in this category",
    "confidence": "medium",
    "invalidation_condition": "A keyword with top apps having high ratings_count but demonstrably low search impressions (verifiable via App Store Connect)"
  },
  {
    "assumption": "Competitor pricing pages reflect actual prices (no hidden discounts or dynamic pricing)",
    "confidence": "high",
    "invalidation_condition": "Evidence of competitor A/B testing pricing pages or offering personalized pricing"
  }
]
```

### Schema consistency

Every object of the same type must have the same fields in the same order. No surprise fields, no missing fields. If a value is unavailable, use `null` — never omit the key.

### Self-describing field names

Field names must be meaningful without consulting a schema reference. Use `ratings_count` not `rc`. Use `opportunity_score` not `score`. Use `rationale` not `r`.

### Denormalization over joins

When an app appears in multiple files, include the app name and slug in each reference. The LLM should never need to cross-reference files to understand a single entry:

```json
{ "keyword": "photo editor", "position": 1, "app_name": "Snapseed", "app_slug": "snapseed", "rating": 4.6, "ratings_count": 892000 }
```

---

## `_index.json` — Research Navigation

The index is the LLM's table of contents. It is updated after every phase completes by pulling the `_summary` from each output file.

An LLM starting a new conversation about this research should read `_index.json` first and then load only the files it needs.

### Schema

```json
{
  "_summary": "ASO research for FotoApp (iOS), completed 2026-04-05. 47 keywords analyzed, 127 apps found, top 20 researched in depth. Key finding: 'ai photo editor' has highest opportunity score. Top competitor weakness: crash complaints across 6/10 top apps.",
  "phases": {
    "0_intake": {
      "files": ["phase0-intake.json"],
      "summary": "Product intake for FotoApp. iOS. Live app, current title: 'FotoApp: Photo Editor'."
    },
    "1_keywords": {
      "files": ["phase1-keywords-raw.json", "phase1-keywords-tiered.json"],
      "summary": "63 raw keywords from 3 sources → 47 tiered. Tier 1: 8 keywords."
    },
    "2_landscape": {
      "files": ["phase2-keyword-results.json", "phase2-landscape.json"],
      "summary": "Search results for 30 keywords. 127 unique apps. Top 5 by score: Snapseed, VSCO, Lightroom, PicsArt, Pixlr."
    },
    "3_app_research": {
      "directory": "phase3/",
      "apps_researched": 20,
      "tier_a": ["snapseed", "vsco", "lightroom", "picsart", "pixlr", "darkroom", "afterlight", "prisma", "photoleap", "facetune"],
      "tier_b": ["canva", "polish", "airbrush", "befunky", "pho-to", "fotor", "inshot", "remini", "lensa", "prequel"],
      "summary": "Full research (reviews, metadata, screenshots, website) on 10 Tier A apps. Metadata only on 10 Tier B apps."
    },
    "4_synthesis": {
      "files": ["phase4-synthesis.json"],
      "summary": "Keyword opportunity scores, complaint clusters (top: crashes 12.3%, missing features 9.1%), praise clusters (top: professional quality 23.4%), feature matrix, value prop map, pricing landscape."
    },
    "5_metadata": {
      "files": ["phase5-metadata.json"],
      "summary": "Metadata draft for App Store and Play Store. Proposed title: 'FotoApp: AI Photo Editor' (24 chars). Keyword field: 98/100 chars. 3 screenshot concepts."
    },
    "6_report": {
      "files": ["report.html"],
      "summary": "Complete HTML report with all findings, tables, and recommendations."
    }
  }
}
```

---

## Starting a Pipeline

At the beginning of every research pipeline run:

1. **Check for `research/`** in the project root. Create it if absent.
2. **List existing directories** of the same type (e.g., all `aso-*/`).
3. **Check each `_manifest.json`** for `status: "in_progress"` or `"failed"`.
4. **If incomplete research exists**, present the user with:
   ```
   Found incomplete ASO research from 2026-04-05 14:23 (14/20 apps complete).
   Options:
     [R] Resume from where it stopped
     [N] Start a new research run
     [L] List all past researches for this project
   ```
5. **If resuming**: read the manifest, skip all `complete` units, continue from `pending` / `in_progress`.
6. **If starting fresh**: generate a new timestamped directory, create `_manifest.json` with all phases set to `pending`, create an empty `_index.json`.

---

## Listing Past Researches

```
Research runs for this project:

  ID                              Type   Platform  Status       Progress
  aso-2026-04-05T14-23-00         ASO    iOS       in_progress  Phase 3 (14/20 apps)
  aso-2026-03-10T09-15-00         ASO    iOS       complete     —
  competitive-2026-04-01T11-00-00 Comp.  —         complete     —
```

---

## Pipeline Startup Protocol

Shared steps that every pipeline runs before Phase 1. Individual playbooks should reference this section instead of repeating these steps.

1. **Product foundation check** — read `{project_root}/research/product-foundation.json`. If absent, run the product foundation intake first (see `references/product-foundation.md`). If present, check `updated_at` and confirm with the user it's still current.
2. **Read `learned` section** — check which fields exist and their staleness (< 3 months: use as-is; 3-6 months: verify during run; > 6 months: re-research). Note staleness in pipeline output.
3. **Ask the user:** "Run fast (parallel agents, higher cost) or lean (sequential, slower)?" Default: task-level parallelism within phases.
4. **Confirm project root path** with the user.
5. **Check for incomplete runs** — list existing directories of the same pipeline type, check each `_manifest.json` for `status: "in_progress"` or `"failed"`. If found, offer Resume / New / List (see "Starting a Pipeline" below).
6. **Create run directory** — if starting fresh: generate timestamped directory, create `_manifest.json` with all phases `pending`, create empty `_index.json`.

---

## Phase Transition Protocol

Run this checklist between every phase. Do not skip steps — context compaction can happen mid-pipeline, and the manifest + index are how you recover.

```
After completing Phase N:
1. Save the phase output file to its final path
2. Update _manifest.json → mark phase N as "complete" with completed_at timestamp
3. Update _index.json → add the _summary from the newly written file
4. Foundation writeback (Phase 4 only) → see "Foundation Writeback" section
5. USER CHECKPOINT → present a 3-5 line phase summary, ask "Continue to Phase N+1?"
6. Before starting Phase N+1 → re-read _manifest.json to confirm current state
```

### User Checkpoints

Pause for user review at these points. Present findings and ask for confirmation before proceeding.

| After phase | What to present | Why |
|---|---|---|
| Phase 1 (keywords / competitor identification) | Tiered keyword list or prioritized competitor list | Wrong targets waste hours of deep research in Phase 3 |
| Phase 2 (landscape) | Top apps/domains by score, recommended deep-dive list | Phase 3 is the most time-intensive — user should confirm which targets to research |
| Phase 4 (synthesis) | Key findings: top opportunities, biggest gaps, notable insights | Strategy (Phase 5) is built on these findings — user should validate before committing |
| Phase 5 (strategy / metadata / recommendations) | Recommended actions with rationale | Report (Phase 6) locks recommendations into a deliverable — last chance to adjust |

If the user says "just go" or "run the whole thing," skip the checkpoints — but still save the manifest and index at each transition.

---

## Context Recovery Protocol

When resuming a pipeline in a new conversation (after the previous conversation ended or was compacted), read files in this exact order to rebuild context efficiently:

```
1. Read _manifest.json
   → Understand: which phases are complete, which are in-progress, which are pending
   → For Phase 3 (per-item): which items are complete, which remain

2. Read _index.json
   → Get summaries of all completed phases without loading full files
   → Decide which full files you need based on the current phase

3. Read product-foundation.json (including learned section)
   → Restore full product context and cross-pipeline knowledge

4. Read the output file of the LAST COMPLETED phase
   → This is your current state — the data the next phase builds on

5. If current phase is partially complete (e.g., Phase 3 with 14/20 apps):
   → Read the manifest's per-item status to identify remaining work
   → Do NOT re-read completed items unless needed for the current task

6. Resume from the first incomplete unit in the current phase
```

Do not read all phase output files — read only what the current phase needs. The `_index.json` summaries are sufficient context for earlier phases.

---

## Failure Handling Protocol

### Scrape failures

When `/browser-use` or web search fails (CAPTCHA, rate limit, timeout, dynamic content requiring login):

1. **Retry once** after a 30-second pause
2. If retry fails, mark the unit as `failed` in `_manifest.json` with an `"error"` field describing the failure
3. **Do not block the pipeline.** Move to the next item and continue
4. Note the failure in the phase's `_summary` field: "15/20 apps complete. Failed: {app} (CAPTCHA), {app} (timeout)"

### Partial completion thresholds

Phases can proceed to the next phase with incomplete data if they meet the minimum threshold:

| Phase | Minimum to proceed | What to do with gaps |
|---|---|---|
| Phase 1 (keywords) | At least 10 keywords tiered | Note limited seed set in _summary. Phase 2 results may surface more. |
| Phase 2 (landscape) | At least 60% of Tier 1 keywords searched | Note missing keywords. Proceed with available data. |
| Phase 3 (deep research) | At least 70% of target items complete | Note missing items in _summary. Synthesis works with available data. |
| Phase 4 (synthesis) | All prerequisite phases meet their thresholds | N/A — synthesis uses whatever data exists |
| Phase 5 (strategy) | Phase 4 complete | N/A |

If a phase falls below its threshold, pause and ask the user: "Phase 3 completed only 50% of targets (10/20 apps). Options: [R] Retry failed items, [C] Continue with partial data (lower confidence), [S] Stop and investigate."

### Missing data propagation

When a data field is unavailable for a specific item (e.g., no pricing page, no reviews, competitor app removed from store):

- Use `null` for the missing field — never omit the key
- Add a note in the item's `notes` field explaining why it's missing
- Downstream phases should work with partial data, adjusting confidence levels accordingly
- In synthesis (`_summary`), note which findings are based on incomplete data: "Pricing landscape based on 8/10 competitors (2 had no public pricing)"

---

## Action Tracking

After Phase 5 (strategy/recommendations), write an `actions.json` file in the research run directory. This tracks whether recommendations are implemented and their outcomes.

### Schema

```json
{
  "_summary": "{N} recommended actions. {X} implemented, {Y} pending, {Z} deferred.",
  "actions": [
    {
      "id": 1,
      "action": "Update App Store title to 'FotoApp: AI Photo Editor'",
      "source_phase": "phase5",
      "priority": "high",
      "status": "pending",
      "implemented_at": null,
      "outcome": null,
      "notes": null
    }
  ],
  "follow_up_date": "2026-05-03T00:00:00Z",
  "follow_up_note": "Check App Store Connect for keyword ranking changes and conversion rate impact 4 weeks after implementation."
}
```

### Status values

| Status | Meaning |
|---|---|
| `pending` | Not yet implemented |
| `implemented` | Done — record `implemented_at` date |
| `deferred` | User decided to postpone — record reason in `notes` |
| `rejected` | User decided not to do this — record reason in `notes` |

### When to update

- After the pipeline completes: create `actions.json` with all recommendations from Phase 5 as `pending`
- When the user reports implementing a recommendation: update status to `implemented` with date
- When the user asks for a follow-up review: read `actions.json`, check what was implemented, and compare against monitoring metrics

---

## Slug Conventions

### App slugs (ASO, competitive intelligence)

App slugs are directory names inside `phase3/`:

- Lowercase
- Spaces and special characters replaced with hyphens
- Truncated to 50 characters
- Unique within a run (append `-2`, `-3` on collision)

Examples: `Spotify` → `spotify`, `Google Maps` → `google-maps`, `1Password – Password Manager` → `1password-password-manager`

### Domain slugs (SEO)

Domain slugs are directory names inside `phase3/` for SEO pipeline:

- Strip protocol (`https://`) and `www.` prefix
- Replace dots and special characters with hyphens
- Lowercase
- Truncated to 50 characters
- Unique within a run (append `-2`, `-3` on collision)

Examples: `adobe.com` → `adobe-com`, `blog.hubspot.com` → `blog-hubspot-com`, `searchengineland.com` → `searchengineland-com`

---

## File Format Rules

| File | Format | Audience | Notes |
|---|---|---|---|
| `product-foundation.json` | JSON | LLMs + all pipelines | Shared product data at research root, not inside a pipeline dir |
| `_manifest.json` | JSON | Pipeline engine | Status tracking and resume logic |
| `_index.json` | JSON | LLMs | Content summaries — read first to decide what to load |
| `phase0-intake.json` | JSON | LLMs | Product data from user intake |
| `phase1-keywords-raw.json` | JSON | LLMs | Array of `{ keyword, source, notes }` |
| `phase1-keywords-tiered.json` | JSON | LLMs | `{ tier1, tier2, tier3 }` arrays |
| `phase2-keyword-results.json` | JSON | LLMs | Keyed by keyword → array of top 20 apps |
| `phase2-landscape.json` | JSON | LLMs | Deduplicated apps sorted by score |
| `phase3/{slug}/metadata.json` | JSON | LLMs | Store listing data |
| `phase3/{slug}/reviews.json` | JSON | LLMs | Review array with sentiment summary |
| `phase3/{slug}/screenshots.json` | JSON | LLMs | Position, headline, feature, claim per screenshot |
| `phase3/{slug}/website.json` | JSON | LLMs | Pricing, tiers, trial, homepage headline |
| `phase4-synthesis.json` | JSON | LLMs | Keyword scores, clusters, feature matrix, pricing |
| `phase5-metadata.json` | JSON | LLMs | Metadata draft with rationale per field |
| `report.html` | HTML | Humans | Self-contained final report |

All JSON files must include a `_summary` field. No Markdown intermediary files — all structured data is JSON; all human-facing output is HTML.

---

## Final Report — HTML

Phase 6 generates `report.html`: a single-file, self-contained HTML document that renders the complete research for human consumption. Use `references/report-template.html` as the base template — fill `{{TOKENS}}` with data from pipeline JSON outputs.

### Design Principles

- **Self-contained** — all CSS in a `<style>` tag, no external stylesheets, fonts, or scripts. Opens in any browser, can be emailed or printed.
- **System fonts** — use the system font stack: `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`. No web font dependencies.
- **No JavaScript required** — the core reading experience works without JS. Optional JS may be added for enhancements (collapsible sections, sortable tables) but the report must be fully readable with JS disabled.
- **Print-friendly** — include a `@media print` stylesheet that hides navigation, adjusts margins, and prevents table breaks.
- **Responsive** — readable from 320px mobile to full desktop. Sidebar navigation collapses to a top bar on narrow screens.

### Color System

Use CSS custom properties for consistency:

| Token | Usage | Value (light theme) |
|---|---|---|
| `--color-opportunity` | Positive signals, gaps to exploit | `#16a34a` (green) |
| `--color-risk` | Negative signals, threats | `#dc2626` (red) |
| `--color-info` | Neutral data, informational | `#2563eb` (blue) |
| `--color-muted` | Secondary text, borders | `#6b7280` (gray) |
| `--color-bg` | Page background | `#ffffff` |
| `--color-surface` | Card/section background | `#f9fafb` |
| `--color-text` | Primary text | `#111827` |

### Report Structure

The HTML body has a fixed sidebar navigation and a scrollable main content area. Each section corresponds to a pipeline phase and is built from the JSON output of that phase.

```
┌──────────────────────────────────────────────────────┐
│ Header: App Name • Platform • Date • Research ID     │
├──────────┬───────────────────────────────────────────┤
│ Sidebar  │ Main content                              │
│          │                                           │
│ Summary  │ ┌─ Executive Summary ───────────────────┐ │
│ Keywords │ │ 5–7 bullet findings + recommendation  │ │
│ Compete  │ └───────────────────────────────────────┘ │
│ Features │                                           │
│ Reviews  │ ┌─ Keyword Analysis ────────────────────┐ │
│ Message  │ │ Opportunity-scored table, color-coded  │ │
│ Pricing  │ │ Tier recommendations                  │ │
│ Recs     │ │ Proposed keyword field (App Store)     │ │
│          │ └───────────────────────────────────────┘ │
│          │                                           │
│          │ ┌─ Competitive Landscape ───────────────┐ │
│          │ │ Top 20 apps table (name, rating,      │ │
│          │ │ ratings count, score)                  │ │
│          │ │ Positioning observations               │ │
│          │ └───────────────────────────────────────┘ │
│          │                                           │
│          │ ┌─ Feature Comparison ──────────────────┐ │
│          │ │ Matrix: apps × features               │ │
│          │ │ Color: green=has, empty=missing        │ │
│          │ │ Legend: table stakes / differentiator  │ │
│          │ │         / gap                          │ │
│          │ └───────────────────────────────────────┘ │
│          │                                           │
│          │ ┌─ Review Intelligence ─────────────────┐ │
│          │ │ Complaint clusters: bar + quotes       │ │
│          │ │ Praise clusters: bar + quotes          │ │
│          │ └───────────────────────────────────────┘ │
│          │                                           │
│          │ ┌─ Messaging Analysis ──────────────────┐ │
│          │ │ Screenshot value props clustered       │ │
│          │ │ Category conventions vs. gaps          │ │
│          │ └───────────────────────────────────────┘ │
│          │                                           │
│          │ ┌─ Pricing Landscape ───────────────────┐ │
│          │ │ Competitor pricing table               │ │
│          │ │ Model distribution, price ranges       │ │
│          │ └───────────────────────────────────────┘ │
│          │                                           │
│          │ ┌─ Recommendations ─────────────────────┐ │
│          │ │ Proposed metadata per platform         │ │
│          │ │ Character counts + rationale           │ │
│          │ │ Screenshot concepts with direction     │ │
│          │ │ Next steps                             │ │
│          │ └───────────────────────────────────────┘ │
└──────────┴───────────────────────────────────────────┘
```

### Section Details

**Executive Summary** — pull the top-level `_summary` from `phase4-synthesis.json` and `phase5-metadata.json`. Present as 5–7 bullet points: the biggest keyword opportunity, the biggest competitor weakness, the clearest positioning gap, the pricing insight, and the recommended metadata direction. End with a single recommended action.

**Keyword Analysis** — render `keyword_opportunities` from `phase4-synthesis.json` as a sortable table. Columns: keyword, demand proxy, competition proxy, opportunity score, tier, rationale. Color-code opportunity score (green = high, yellow = medium, gray = low). Below the table, show the proposed keyword field text from `phase5-metadata.json` with character count.

**Competitive Landscape** — render `phase2-landscape.json` as a table: rank, app name, developer, rating, ratings count, score. Top 10 get a highlight row. Include a text paragraph summarizing competitive density and notable gaps.

**Feature Comparison** — render `feature_matrix` from `phase4-synthesis.json`. Apps as rows, features as columns. Checkmark for present, empty for absent. Color-code the column header: green = differentiator, gray = table stakes, red outline = gap. Include a legend.

**Review Intelligence** — two sub-sections from `phase4-synthesis.json`:
- Complaint clusters: horizontal bar showing frequency percentage, theme name, affected apps, 2 example quotes per cluster
- Praise clusters: same format. Praise quotes are highlighted as messaging source material.

**Messaging Analysis** — render `value_prop_map` from `phase4-synthesis.json`. Show conventions as a list with usage count. Show gaps as highlighted cards with the evidence that suggests demand.

**Pricing Landscape** — render `pricing_landscape` from `phase4-synthesis.json`. Table of apps with pricing model, monthly price, annual price, trial structure. Summary row with median, min, max. Highlight where the user's product sits (or should sit).

**Recommendations** — render `phase5-metadata.json`. For each platform (App Store, Play Store), show every field: proposed text, character count vs. limit, and the rationale citing specific research findings. Screenshot concepts: show position, headline, feature, rationale, and visual direction.

### Generation Process

Phase 6 reads `phase4-synthesis.json` and `phase5-metadata.json` (and optionally `phase2-landscape.json` for the competitive table). It generates HTML by embedding the data directly into the markup — no template engine, no build step. The LLM writes the complete HTML string and saves it as `report.html`.
