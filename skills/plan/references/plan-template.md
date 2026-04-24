# Plan Template

Use this template for all new plans. Every section is mandatory. Replace placeholders in `{braces}` with actual values.

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

## Single-Phase Plan Template

For plans with exactly one vertical slice. Produces a single `.md` file, not a folder.

```markdown
# {Project} {Type}: {Title}

**Status:** 🔄 IN PROGRESS
**System plan file:** {path to {system_plan_dir}/slug.md}

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

## Success Criteria

- [ ] {Measurable outcome 1}
- [ ] {Measurable outcome 2}
- [ ] All unit and regression tests pass
- [ ] Integration tests pass
- [ ] Test coverage is 100%
- [ ] Documentation updated
- [ ] Localization updated for all supported locales (if applicable)

## Files Created

{Leave empty initially. Fill in during Update workflow as files are created.}

- `{path}` ({line count} lines) — {brief description}

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

## Dependency Table

| Phase | Scope | Depends on | Slice |
|-------|-------|------------|-------|
| **1: {Slice name}** | {Brief scope} | — | [phase_1_{slug}.md](phase_1_{slug}.md) |
| **2: {Slice name}** | {Brief scope} | Phase 1 | [phase_2_{slug}.md](phase_2_{slug}.md) |
| **N: {Slice name}** | {Brief scope} | Phase 1 | [phase_N_{slug}.md](phase_N_{slug}.md) |

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

## Implementation Progress

- [ ] Read `{file}` — understand {what}. Done when you can describe {specific knowledge}.
- [ ] Create `{test_file}` — test for `{behavior}`. Run: `{command}`. Done when test **fails**.
- [ ] {Implementation task} in `{file}`. Done when test passes. Run: `{command}`.
- [ ] Add integration test for `{flow}` in `{file}`. Done when test compiles.
- [ ] Update `{doc_file}` — add section on `{topic}`. Done when saved.
- [ ] Run `{formatter}` + `{test command}`. Done when clean + "TESTS PASSED".

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

- Run: `{test command}`
- Expected: all phase tests pass

## Files Created

{Leave empty initially. Updated during execution.}

- `{path}` ({line count} lines) — {brief description}

## Files Modified

{Leave empty initially. Updated during execution.}

- `{path}` — {what changed}
```

---

## Type Values

Use these labels in the plan header `# {Project} {Type}: {Title}`:

| Type | When to use |
|------|-------------|
| Feature | New user-facing capability |
| Fix | Bug fix |
| Refactor | Code restructuring without behavior change |
| Tech | Infrastructure, CI/CD, tooling, dependencies |
| Docs | Documentation-only changes |
| Epic | Multi-slice plan spanning multiple independent deliverables |

---

## Task Decomposition Template

After the user approves the plan, decompose it into tracker tasks. The plan files remain the source of truth — tracker tasks reference them, not duplicate them.

### Epic (multi-phase plans only)

The epic references the **master plan file** (`plan.md` inside the folder):

```
{tracker_cli} create "{Plan title}" \
  --type epic \
  --priority {0-4} \
  --description "{1-3 sentence summary of the epic scope}" \
  --labels {relevant labels} \
  --notes "Plan: {absolute path to folder/plan.md}
This epic's master plan contains the dependency table, cross-cutting concerns, and success criteria. Each child task has its own slice file with full implementation detail. Use the execution skill to implement."
```

### Task per phase

Each task references its **slice file** (`phase_N_{slug}.md`):

```
{tracker_cli} create "Phase {N}: {Slice name}" \
  --type {feature|task|bug|chore} \
  --priority {0-4} \
  --parent {epic-id} \
  --labels {relevant labels} \
  --deps "{dependency-task-id}" \
  --description "{Summary of what this phase delivers}

Step {N}.1: Exploration
- [ ] Read {file} — understand {what}

Step {N}.2: Tests (TDD)
- [ ] Create/update {test file} — {test description}
- [ ] Run tests — confirm new tests fail

Step {N}.3: Implementation
- [ ] {Implementation task} in {file}
- [ ] Run tests — confirm all pass

Step {N}.4: Integration Tests
- [ ] Add {integration test} in {file}

Step {N}.5: Documentation
- [ ] Update {doc file}

Step {N}.6: Polish
- [ ] Run formatter
- [ ] Run full test suite" \
  --notes "Slice: {absolute path to folder/phase_N_{slug}.md}
Master: {absolute path to folder/plan.md}
Full implementation detail (code snippets, insertion points, done-when criteria) is in the slice file. Use the execution skill to implement."
```

### Single-phase plans (no epic)

For plans with only one phase, create a single tracker task (not an epic):

```
{tracker_cli} create "{Plan title}" \
  --type {feature|task|bug|chore} \
  --priority {0-4} \
  --labels {relevant labels} \
  --description "{Same step checklist format as above}" \
  --notes "Plan: {absolute path to plan .md}
Full detail: see plan file. Use the execution skill when implementing."
```

### Key rules

- **Master plan** (`plan.md`) is the source of truth for shared context — objective, requirements, dependency table, cross-cutting concerns. Referenced by the epic.
- **Slice files** (`phase_N_{slug}.md`) are the source of truth for implementation detail — code snippets, insertion points, test cases. Referenced by individual tasks.
- Task descriptions contain **step checklists** — enough to orient from `{tracker_cli} show`, with the slice file pointer for deep detail.
- Dependencies between tasks must match the dependency table in the master plan.
- Labels should include the relevant technology/platform (e.g., `ios`, `android`, `web`, `dart`).

---

## Bug Round Format

When bugs are discovered during implementation, add a bug round section to the **slice file** of the affected phase (for multi-phase plans) or directly in the plan file (for single-phase plans):

```markdown
## Bug Round 1: {Short description} — {YYYY-MM-DD}

### Root Cause
{Explain what went wrong and why.}

### Fix
- [x] {What was changed}
- [x] {File modified}
- [x] {Test added to prevent regression}

### Verification
- [x] {How the fix was verified}
```

Multiple rounds are numbered sequentially (Bug Round 1, Bug Round 2, etc.).

---

## Completion Format

### Single-phase plans

Update the status line:

```markdown
**Status:** ✅ COMPLETED — {YYYY-MM-DD}
```

### Multi-phase plans

Update the **master plan** status:

```markdown
**Status:** ✅ COMPLETED — {YYYY-MM-DD}
```

Update each **slice file** status:

```markdown
**Status:** ✅ COMPLETED — {YYYY-MM-DD}
```

Mark progress lines in the master plan:

```markdown
- [x] [Phase 1: {Slice name}](phase_1_{slug}.md) — `{task-id}` ✅ {YYYY-MM-DD}
```
