# Plan Templates

Templates for plan markdown files. Every section is mandatory unless explicitly noted. Replace placeholders in `{braces}` with actual values.

For type values (Feature/Fix/Refactor/Tech/Docs/Epic) → `references/conventions.md` (Type Codes & Values).
For task decomposition → `references/task-decomposition.md`.
For bug rounds & completion formatting → `references/bug-and-completion.md`.

---

## Core Principle: Vertical Slices

Every plan is structured as one or more **vertical slices**. A vertical slice is an atomic deliverable — a feature, fix, or capability that can be shipped independently. Each slice contains the full stack of work needed to deliver it:

1. **Exploration** — read relevant code, docs, APIs
2. **Tests (TDD)** — write failing unit/widget tests
3. **Implementation** — make the tests pass
4. **Integration tests** — end-to-end verification
5. **Documentation** — update project docs
6. **Polish** — format, final test run

### How plan structure maps to file structure

| Plan size | Phases | File structure | Tracker structure |
|-----------|--------|----------------|-------------------|
| **Small** (1 phase) | 1 vertical slice | Single `.md` file | 1 standalone task |
| **Medium+** (2+ phases) | 2+ vertical slices | Folder: `plan.md` + `phase_N_{slug}.md` per slice | Epic + 1 task per slice |

### Plan sizing

Calibrate the number of phases to task scope:

**Small fix** (1-2 files): 1 phase → single file.
**Medium feature** (3-10 files): 2 phases → folder. Phase 1: core feature. Phase 2: enhancement or secondary concern.
**Large feature** (10+ files, multi-platform): 3+ phases → folder. Independent slices can be parallelized.

**Hard limits per phase:** ≤8 implementation steps, ≤5 unrelated files. If a drafted phase exceeds either threshold, split it into thinner slices. Better to have more phases in the epic than fat phases that are hard to execute and review.

#### Multi-platform projects

For libraries or apps that span multiple platforms, each platform is a natural slice boundary. Prefer one platform per phase rather than bundling all platforms into a single "thread it through everywhere" phase.

**Too fat (anti-pattern):**

| Phase | Scope | Steps | Files |
|-------|-------|-------|-------|
| 1: Interface | Abstract class + method channel + tests | 9 | 2 |
| 2: All platforms | Dart API, Android, iOS, Web, mock, docs, example app, integration test | 21 | 10+ |

Phase 2 is a marathon — too many unrelated files, too many context switches, hard to review.

**Right-sized:**

| Phase | Scope | Steps | Files |
|-------|-------|-------|-------|
| 1: Interface | Abstract class + method channel + tests | 9 | 2 |
| 2: Dart API | Public API, web stub, mock, Dart unit tests | 7 | 4 |
| 3: Android | Handler + native impl + Android unit tests | 5 | 2 |
| 4: iOS | Handler + native impl | 3 | 1 |
| 5: Docs & example | API docs, guide, example app, integration test | 7 | 5 |

Each phase is independently shippable, stays under the thresholds, and takes minutes to execute rather than being a long session.

#### Common split patterns

- **Multi-platform:** one phase per platform (Dart, Android, iOS, Web).
- **API + consumers:** one phase for the interface/API layer, one per major consumer.
- **Core + periphery:** one phase for the core logic, one for docs/example/integration tests.

---

## Substitution rules

Templates use shorthand placeholders inside braces — `{max_file_loc}`, `{plans_dir}`, `{project}`, `{system_plan_dir}`, `{tracker_cli}`, `{formatter}`, `{test_command}`, `{skills_dir}`. These resolve from `skill.config.md` at write time. **Substitute every placeholder when writing a real plan file.** A rendered plan must not contain literal `{...}` shorthand outside of fenced code blocks where the shorthand is the subject of explanation. If you find yourself writing `{max_file_loc}` into a plan file's body, stop and replace it with the resolved integer.

---

## Single-Phase Plan Template

For plans with exactly one vertical slice. Produces a single `.md` file, not a folder.

```markdown
# {Project} {Type}: {Title}

**Status:** 🔄 IN PROGRESS
**System plan file:** {path to {system_plan_dir}/slug.md}

## Background

<!-- OMIT this section when the plan was NOT created from an investigation. -->
<!-- INCLUDE it when an investigation file was detected in Step 2. -->
**Investigation:** {absolute path to {plans_dir}/{project}/investigations/{file}.md}
**Root cause (1 sentence):** {copy verbatim from investigation Root Cause section}
**Approved fix (1 sentence):** {copy verbatim from investigation Approved Fix → Summary}

Read the investigation file for the full execution chain, supporting evidence, ruled-out hypotheses, and side-effect notes. Do not duplicate that content here.

## Component Decomposition

Atomic units this plan creates or modifies. Each component owns one logical action, passes the Meaningfulness Test, and is unit-testable in isolation. The smell threshold is ≤`{max_file_loc}` LOC — beyond that, either split (if every candidate split passes the Meaningfulness Test) or take a `**LOC waiver:**`. See `../_shared/architecture-principles.md`.

| Component | Responsibility (one sentence, no "and") | Public API | Callers (≥2 OR single-caller + own test) | Foreign modules touched | Projected LOC | Test approach |
|-----------|------------------------------------------|------------|------------------------------------------|-------------------------|---------------|---------------|
| `{path/to/module.ext}` | {single responsibility} | `{exported symbols}` | `{caller A}`, `{caller B}` | `{module X}`, `{module Y}` | {N} | {how to unit-test in isolation} |

**LOC waivers** (when a component legitimately exceeds `{max_file_loc}` and every candidate split fails the Meaningfulness Test):
- `{path/to/file}` — projected {N} LOC. Reason: {generated parser / exhaustive enum / cohesive state machine}. Alternatives considered: {list}.

**Coupling waivers** (when behavior legitimately spans >5 foreign feature modules):
- `{path/to/file}` — touches {N} foreign modules: {list}. Reason: {orchestration boundary / integration shim with no further decomposition}. Splits ruled out because: {failed Meaningfulness Test condition}.

## Implementation Progress

### Phase 1: {Slice Name} — {Brief Description}

---

#### Step 1.1: Exploration

> **Read before starting:** `{path/to/relevant/file}`, `{project}/docs/{relevant-doc}.md`. Understand how {X} works before touching anything.

- [ ] Read `{path/to/existing_feature.dart}` — understand how {X} is currently implemented. Done when you can describe what each method does.
- [ ] Read `{test/path/to/existing_test.dart}` — understand what's already tested. Done when you know which test cases exist.

---

#### Step 1.2: Tests (write before implementation)

> **Read before starting:** Step 1.1 results, plus `{project}/docs/05-testing/unit-tests.md` for test conventions.

- [ ] Create `{test/path/to/new_test.dart}` — add a test for `{behavior}`. Use `{nearby_test.dart}` as reference. Done when test **fails** (red). Run: `{test command}`.
- [ ] Add regression test for `{edge case}` in `{existing_test.dart}`. Done when **fails**.

---

#### Step 1.3: Implementation

> **Read before starting:** Step 1.2 tests, plus `{path/to/file_to_modify.dart}`.

- [ ] Add `{methodName}` to `{file.dart}` — implement `{behavior}`. Reuse `{existing_helper}` (DRY). Done when Step 1.2 unit test passes.
- [ ] Run `{test command}` — all tests green. Done when "TESTS PASSED".

---

#### Step 1.4: Integration Tests

> **Read before starting:** `{path/to/existing_integration_test.dart}` for test patterns.

- [ ] Add integration test for `{user flow}` in `{integration_test.dart}`. Done when test compiles.

---

#### Step 1.5: Documentation

> **Read before starting:** `{project}/docs/{relevant-doc}.md` for existing doc style.

- [ ] Update `{project}/docs/{relevant-doc}.md` — add section for `{feature}`. Done when saved.

---

#### Step 1.6: Polish

- [ ] Run the configured formatter (`{formatter}`). Done when no changes.
- [ ] Run `{test command}` one final time. Done when "TESTS PASSED".
- [ ] Run the architecture gate on every changed file (`git diff --name-only`) and write the `## Architecture Gate Results` block into this plan file. See execute skill `references/update-format.md` (Adding the Architecture Gate Results). Done when the block exists with **Overall: PASS** and every row PASS.

---

## Objective

{1-3 sentences. What are we building or fixing and why it matters.}

---

## Requirements

{Numbered list of concrete requirements. Include constraints, prerequisites, platform considerations.}

1. {Requirement}
2. {Requirement}

## Implementation

{Numbered steps with file paths and code snippets. This is the technical blueprint.}

### {Step N}: {Description}

**Files:**
- `{path/to/file}` — {what changes}

{Code snippet showing the key change or new API}

{Explain what this code does and why this approach was chosen.}

## Testing

Describe all tests BEFORE writing any implementation code. TDD red-green cycle is mandatory: write test → run to confirm it fails → implement → run to confirm it passes.

### Unit Tests

**New file:** `{test/path/to/test_file}`
- {Test case 1: what behavior it verifies}
- {Test case 2: what behavior it verifies}

**Existing file to update:** `{test/path/to/existing_test}`
- {Regression: existing behavior that must keep passing}
- {New test: what to add}

### Integration Tests

{Cover at least one complete app-level flow per feature added or changed.}

- {Scenario: describe the full user flow being tested end-to-end}

**Coverage requirement:** 100% — no untested code paths, no exceptions.

## Localization

{Skip this section entirely if the project has no localization files. Otherwise, list all supported locales and what must be translated.}

**Baseline — always update first:** English (`{path/to/en.arb}` or equivalent)

| Locale | File | Strings to add/update |
|--------|------|-----------------------|
| en | `{path}` | {list of keys} |
| {locale} | `{path}` | {list of keys} |

For each non-English locale: adopt the role of a native speaker to produce natural, idiomatic translation — not word-for-word from English.

## Verification

### Automated
- Run: `{test command}`
- Expected: all tests pass

### Manual
- [ ] {Manual verification step 1}
- [ ] {Manual verification step 2}

### Phase exit
- Run from the repo root: `./validate run phase-exit` — every row PASS, then `./validate verify phase-exit` (no file argument) exits 0. The run writes the repo's `ledger`; record the verdict line and the ledger's commit in the `### Validation` block of this file's `## Architecture Gate Results`, and stage `ledger` with the phase commit. See `../_shared/validators.md`.

## Success Criteria

- [ ] {Measurable outcome 1}
- [ ] {Measurable outcome 2}
- [ ] All unit and regression tests pass
- [ ] Integration tests pass
- [ ] Test coverage is 100%
- [ ] Documentation updated
- [ ] Localization updated for all supported locales (if applicable)

## Files Created

{Leave empty initially. Fill in during Update workflow as files are created. Always record LOC — every entry must show a count and stay ≤ `{max_file_loc}` unless explicitly waived.}

- `{path}` ({line count} lines) — {brief description}
- `{path}` ({line count} lines) — {description}. **LOC waiver:** {reason} — alternatives considered: {list}

## Files Modified

{Leave empty initially. Fill in during Update workflow as files are modified.}

- `{path}` — {what changed}

## Beads

{Leave empty initially. Populated during Step 8 decomposition.}

| Role | ID | Title |
|------|----|-------|
| Task | {id} | {title} |
```

---

## Multi-Phase Plan Templates

For plans with 2+ vertical slices. Produces a **folder** containing a master plan and one slice file per phase. See `references/conventions.md` for folder naming.

### Master Plan (`plan.md`)

The master plan holds shared context — objective, requirements, dependency table, cross-cutting concerns, and a progress dashboard linking to each slice. It is referenced by the tracker epic. It does NOT contain implementation detail or code snippets — those live in the slice files.

```markdown
# {Project} {Type}: {Title}

**Status:** 🔄 IN PROGRESS
**System plan file:** {path to {system_plan_dir}/slug.md}

{Brief paragraph describing the overall epic scope and how slices relate to each other.}

## Background

<!-- OMIT this section when the plan was NOT created from an investigation. -->
<!-- INCLUDE it when an investigation file was detected in Step 2. -->
**Investigation:** {absolute path to {plans_dir}/{project}/investigations/{file}.md}
**Root cause (1 sentence):** {copy verbatim from investigation Root Cause section}
**Approved fix (1 sentence):** {copy verbatim from investigation Approved Fix → Summary}

Read the investigation file for the full execution chain, supporting evidence, ruled-out hypotheses, and side-effect notes. Slice files do not need to re-quote this — link back to the investigation when relevant.

## Dependency Table

| Phase | Scope | Depends on | Slice |
|-------|-------|------------|-------|
| **1: {Slice name}** | {Brief scope} | — | [phase_1_{slug}.md](phase_1_{slug}.md) |
| **2: {Slice name}** | {Brief scope} | Phase 1 | [phase_2_{slug}.md](phase_2_{slug}.md) |
| **N: {Slice name}** | {Brief scope} | Phase 1 | [phase_N_{slug}.md](phase_N_{slug}.md) |

## Architecture Boundaries

Modular-monolith placement for code introduced by this epic. See `../_shared/architecture-principles.md`.

- **Feature/domain modules touched:** {e.g., `lib/features/reader/`, `lib/features/library/`}
- **New modules introduced:** {list, with single-sentence responsibility each — or "None"}
- **Public APIs added or changed:** {symbol → consumer module}
- **Existing helpers reused (DRY):** {symbol → location} — confirms no duplication
- **Smell thresholds:** every component ≤ `{max_file_loc}` LOC and ≤5 foreign feature modules touched. Waivers listed per slice. Splits driven only by metrics — without passing the Meaningfulness Test — are rejected.

## Cross-Cutting Concerns

{Constraints, conventions, and rules that every phase must follow:}
- Commit discipline: {e.g., "Keep X/ and Y/ changes in separate commits"}
- Platform constraints: {e.g., "no serializer() calls"}
- Naming conventions: {e.g., "All new methods follow the tts* prefix pattern"}
- {Other project-specific constraints}

## Progress

- [ ] [Phase 1: {Slice name}](phase_1_{slug}.md) — `{task-id}`
- [ ] [Phase 2: {Slice name}](phase_2_{slug}.md) — `{task-id}`
- [ ] [Phase N: {Slice name}](phase_N_{slug}.md) — `{task-id}`

## Dispatch Log

{Filled during execution when phases are delegated. This table is the epic's state on disk — after a compaction it is how the main session knows where it is, instead of guessing. Baseline row first. `Dispatched` and `Returned` are UTC timestamps to the second (`date -u +%Y-%m-%dT%H:%M:%SZ`), never bare dates or wall-clock times: the row exists to be lined up against that bead's validator ledger header in git (`git show <sha>:ledger`), not against a block pasted into a plan file, and only a full stamp answers whether the ledger was earned after the dispatch it claims.}

| Bead | Worker | Dispatched | Returned | Commits | Gate | Ledger | Bead state |
|------|--------|------------|----------|---------|------|--------|------------|
| — | baseline | `2026-08-19T19:41:27Z` | `2026-08-19T19:50:33Z` | — | — | {verdict line verbatim} @ `aaf13fe` | — |

## Objective

{1-3 sentences. What are we building or fixing and why it matters.}

## Requirements

{Numbered list of concrete requirements. Include constraints, prerequisites, platform considerations.}

1. {Requirement}
2. {Requirement}

## {Optional shared context sections}

{Root cause analysis, architecture decisions, or other context that multiple phases need. Include only sections relevant to the plan. Title them descriptively — e.g., "## Root Cause Analysis", "## Architecture Decision". Omit this entirely if no shared context is needed beyond the objective and requirements.}

## Success Criteria

{Cross-cutting criteria that apply to the overall epic, not a single phase:}

- [ ] {Measurable outcome 1}
- [ ] {Measurable outcome 2}
- [ ] All unit and regression tests pass
- [ ] Integration tests pass
- [ ] Test coverage is 100%
- [ ] Documentation updated
- [ ] Localization updated for all supported locales (if applicable)

## Localization

{Skip if no localization files exist. Otherwise, list all locales and what to translate. This section lives in the master because localization typically spans phases.}

**Baseline — always update first:** English (`{path/to/en.arb}` or equivalent)

| Locale | File | Strings to add/update |
|--------|------|-----------------------|
| en | `{path}` | {list of keys} |
| {locale} | `{path}` | {list of keys} |

## Beads

{Leave empty initially. Populated during Step 8 decomposition.}

| Role | ID | Title | Slice |
|------|----|-------|-------|
| Epic | {id} | {title} | — |
| Task (Phase 1) | {id} | Phase 1: {slice name} | [phase_1_{slug}.md](phase_1_{slug}.md) |
| Task (Phase 2) | {id} | Phase 2: {slice name} | [phase_2_{slug}.md](phase_2_{slug}.md) |

## Files Created

{Consolidated across all phases — updated during Update workflow.}

- `{path}` ({line count} lines) — {brief description}

## Files Modified

{Consolidated across all phases — updated during Update workflow.}

- `{path}` — {what changed}
```

### Slice File (`phase_N_{slug}.md`)

Each slice file is self-contained for execution — a tracker task points to this file and nothing else is needed to begin work. The prerequisites section provides just enough cross-phase context to orient without duplicating implementation detail from other phases.

```markdown
# Phase {N}: {Slice Name} — {Brief Description}

**Parent plan:** [plan.md](plan.md)
**Beads task:** `{task-id}`
**Status:** 🔄 IN PROGRESS

## Prerequisites

{What prior phases deliver and why it matters for this phase. 2-3 sentences max. Do not duplicate implementation detail — reference the parent plan or prior slice files for full context. For Phase 1 or independent phases, write "None — this phase has no dependencies."}

## Component Decomposition

Atomic units this phase creates or modifies. Each component owns one logical action, passes the Meaningfulness Test, and is unit-testable in isolation. The smell threshold is ≤`{max_file_loc}` LOC — beyond that, either split (if every candidate split passes the Meaningfulness Test) or take a `**LOC waiver:**`. See `../_shared/architecture-principles.md`.

| Component | Responsibility (one sentence, no "and") | Public API | Callers (≥2 OR single-caller + own test) | Foreign modules touched | Projected LOC | Test approach |
|-----------|------------------------------------------|------------|------------------------------------------|-------------------------|---------------|---------------|
| `{path/to/module.ext}` | {single responsibility} | `{exported symbols}` | `{caller A}`, `{caller B}` | `{module X}`, `{module Y}` | {N} | {how to unit-test in isolation} |

**LOC waivers** (when a component legitimately exceeds `{max_file_loc}` and every candidate split fails the Meaningfulness Test):
- `{path/to/file}` — projected {N} LOC. Reason: {generated parser / exhaustive enum / cohesive state machine}. Alternatives considered: {list}.

**Coupling waivers** (when behavior legitimately spans >5 foreign feature modules):
- `{path/to/file}` — touches {N} foreign modules: {list}. Reason: {orchestration boundary / integration shim}. Splits ruled out because: {failed Meaningfulness Test condition}.

## Implementation Progress

- [ ] Read `{file}` — understand {what}. Done when you can describe {specific knowledge}.
- [ ] Create `{test_file}` — test for `{behavior}`. Run: `{command}`. Done when test **fails**.
- [ ] {Implementation task} in `{file}`. Done when test passes. Run: `{command}`.
- [ ] Add integration test for `{flow}` in `{file}`. Done when test compiles.
- [ ] Update `{doc_file}` — add section on `{topic}`. Done when saved.
- [ ] Run `{formatter}` + `{test command}`. Done when clean + "TESTS PASSED".
- [ ] Run the architecture gate on every changed file (`git diff --name-only`) and write the `## Architecture Gate Results` block into this slice file. See execute skill `references/update-format.md` (Adding the Architecture Gate Results). Done when the block exists with **Overall: PASS** and every row PASS.

## Implementation

### File: `{path/to/file}`

{What changes and why this approach was chosen.}

```{lang}
{Code snippet showing the key change or new API}
```

### File: `{path/to/another_file}`

{More changes...}

## Testing

Describe all tests BEFORE writing any implementation code. TDD red-green cycle is mandatory.

### Unit Tests

**New file:** `{test/path/to/test_file}`
- {Test case 1: what behavior it verifies}
- {Test case 2: what behavior it verifies}

**Existing file to update:** `{test/path/to/existing_test}`
- {Regression: existing behavior that must keep passing}

### Integration Tests

- {Scenario: describe the full user flow being tested end-to-end}

**Coverage:** 100% of code paths introduced or modified in this phase.

## Documentation

- Update `{doc_file}` — {what to add or change}

## Verification

- TDD inner loop: `{test command}` on the changed test files.
- Phase exit, run from the repo root: `./validate run phase-exit` — every row PASS, then `./validate verify phase-exit` (no file argument) exits 0. The run writes the repo's `ledger`; record the verdict line and the ledger's commit in this file's `### Validation` block, and stage `ledger` with the phase commit. See `../_shared/validators.md`.

## Files Created

{Leave empty initially. Updated during execution.}

- `{path}` ({line count} lines) — {brief description}

## Files Modified

{Leave empty initially. Updated during execution.}

- `{path}` — {what changed}
```
