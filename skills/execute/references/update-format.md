# Plan Update Format

Rules for updating plan files during execution. The execute skill modifies plan files directly for routine updates. For major changes (new phases, restructuring), invoke the planning skill (`{plan_skill}`) instead.

Plans come in two shapes — apply the matching rules:
- **Single-phase plan**: one `.md` file with `### Phase 1:` and `#### Step 1.1–1.6` sub-headers
- **Multi-phase plan**: a folder with `plan.md` (master) + `phase_N_{slug}.md` (slice files)

---

## Marking Tasks Complete

Change `- [ ]` to `- [x]` for completed tasks.

**Single-phase plan** (tasks live under `#### Step N.M` sub-headers):
```markdown
#### Step 1.2: Tests (write before implementation)
- [x] Create `test/reader_test.dart` — test for pagination. Done when test **fails**.
- [ ] Add regression test for empty list. Done when **fails**.
```

**Multi-phase slice file** (flat checklist under `## Implementation Progress`):
```markdown
## Implementation Progress
- [x] Read `lib/services/reader.dart` — understand pagination. Done when you can describe the flow.
- [x] Create `test/reader_test.dart` — test for pagination. Done when test **fails**.
- [ ] Implement pagination in `reader.dart`. Done when test passes.
```

---

## Completing a Phase

### Single-phase plans

Add ` ✅ COMPLETED — {YYYY-MM-DD}` to the `### Phase 1:` header:

```markdown
### Phase 1: Reader Pagination — Add page-based navigation ✅ COMPLETED — 2026-02-19
```

All `#### Step 1.1–1.6` sub-headers remain as-is — they don't get individual completion markers. The `### Phase 1:` marker covers them all.

### Multi-phase slice files

Update **two places**:

1. **Slice file** — change the `**Status:**` line:
```markdown
**Status:** ✅ COMPLETED — 2026-02-19
```

2. **Master plan** — mark the corresponding line `[x]` in `## Progress` and append the date:
```markdown
- [x] [Phase 1: Awaitable Disposal](phase_1_awaitable_disposal.md) — `EP-12` ✅ 2026-02-19
```

---

## Adding a Bug Round

Insert in the **working file** — the slice file for multi-phase plans, the plan file for single-phase plans. Never add bug rounds to the master plan. Number sequentially.

```markdown
## Bug Round 1: {Short description} — {YYYY-MM-DD}

### Root Cause
{What went wrong and why.}

### Fix
- [x] {What was changed}
- [x] {File modified}
- [x] {Regression test added}

### Verification
- [x] {How the fix was verified}
```

---

## Adding the Architecture Gate Results

Required artifact for every phase. Insert in the **working file** (slice file for multi-phase, plan file for single-phase) after Step 2.3 of execute and before flipping the phase status to `✅ COMPLETED`. Phase cannot end without it.

Scope: every file returned by `git diff --name-only` for this phase, including test files. If a Refactoring Round was opened, this block records the **post-refactor final pass** — every row must be PASS.

```markdown
## Architecture Gate Results — Phase {N} — {YYYY-MM-DD}

Banner (one line per file, captured from `run_arch_gate.py` or manual run):

\```
[arch-gate] file={path} LOC=PASS({n}+{d}doc) SHIM=PASS({exp}/{code}) DEPS=MANUAL SRP=MANUAL DRY=MANUAL TEST=MANUAL
\```

LOC and SHIM are automated (helper script). The LOC field carries a `+{d}doc` suffix only when the file spends lines on doc prose — a Python docstring — so a file with none reads `LOC=PASS({n})`, and over the limit the forms are `FAIL({n}+{d}doc>{max})` and `FAIL({n}>{max})`. `{n}` is code either way, and so is `{code}` in the SHIM field; a file with no code lines at all — a package `__init__.py` holding only a module docstring — reports a bare `SHIM=PASS` with no parenthetical. DEPS, SRP, DRY, TEST are model/human judgments — fill the table below with the reasoning. The banner stays as the script emits it; the table carries the conclusions.

| File | LOC | SHIM | SRP | DRY | DEPS (foreign modules touched) | TEST | Overall |
|------|-----|------|-----|-----|-------------------------------|------|---------|
| `{path}` | PASS({n}) | PASS | PASS — {one-sentence responsibility, no "and"} | PASS — checked: `{grep terms}` | PASS — {≤5 distinct foreign feature/domain modules: list them} | PASS — {test strategy: isolated / fixtures / DI} | PASS |

If any new file in the table fails the Meaningfulness Test (independent name, ≥2 unrelated callers OR independent test, real coupling reduction, survives inline-back), record it as a SHIM or DEPS FAIL with the failing condition — do not paper over the smell with a "PASS" annotation.

**Companion-skill status:**
- `{code_simplifier}`: ran (roster: `{agent name}`) / ran (briefed worker) / skipped — {empty config / no subagent mechanism / quoted rung-2 spawn error}
- `{code_reviewer}`: deferred to Step 5 / ran (roster: `{agent name}`) / ran (briefed worker) / skipped — {reason}

Name the rung, not just the outcome (execute `SKILL.md`, *Dispatching companion agents*): `ran` on its own hides whether a registered agent or a briefed generic worker did the work. When the rung is the local checklist, record below which manual checks compensated.

### Validation

Two lines, recorded after `./validate run phase-exit` wrote `{repo root}/ledger` and `./validate verify phase-exit` exited 0 (see `../../_shared/validators.md`):

\```
verify: {the verdict line `./validate verify phase-exit` printed, verbatim}
ledger: {sha} — the commit carrying `ledger`; full rows: `git show {sha}:ledger`
\```

The ledger itself is a file in the repo, committed with the source it proves, so this block is a pointer rather than a copy. `git show {sha}:ledger` is where every row, its stamp and the provenance header live.

Every row must be PASS. A FAIL opens a Bug Round or Refactoring Round and the **whole stage** re-runs afterwards. `user`-stage rows appear as `PENDING-USER` and are handed to the user in the close-out. If the repo has no `validators.conf` (runner exits 2), this section reads `validators: none — {reason}` and the report says so.

A later phase may add a validator row. From then on `verify` reports it as `DRIFT` against the ledger — expected, not a failure, and never a reason to re-run the stage. Record the line and leave the ledger alone:

\```
validate: DRIFT static-plugin — the stage gained this row after this ledger ran
\```

**Overall:** PASS

If any row is FAIL → open a Refactoring Round, do not flip the phase status. After the refactor, regenerate this block in full from the post-refactor file set.
```

---

## Adding a Refactoring Round

Use this when the architecture verification gate fails (file over `{max_file_loc}`, multi-responsibility, duplicated helper, hard to test in isolation). Insert in the **working file**. Number sequentially across both Bug and Refactoring rounds within the same phase.

```markdown
## Refactoring Round 1: {Short description} — {YYYY-MM-DD}

### Violation
{Which gate check failed and on which file. Be specific:}
- File: `{path}` — {N} LOC (limit: `{max_file_loc}`)
- Shim: "{file is N% re-export — pure metric laundering, no behavior}"
- Responsibility audit: "{the single sentence with 'and' that surfaced the split}"
- DRY: "{the existing helper that already covers this}"
- Coupling enumeration: "{foreign feature/domain modules touched: A, B, C, D, E, F — over 5}"
- Testability: "{global state / static dependency that blocks isolation}"
- Meaningfulness Test: "{which of the four conditions failed — independent name / plural callers / real coupling reduction / inline-back}"

### Split plan
- New module: `{path}` — responsibility: {one sentence, no "and"}
- Public API: `{symbols}`
- Code moved: {what came out of the original file}
- Tests moved: {test files that follow the code}

### Fix
- [x] Extracted `{symbol(s)}` from `{old path}` to `{new path}`
- [x] Updated callers: {list}
- [x] Re-ran changed test files — green
- [x] Re-ran architecture gate on every touched file — clean

### Verification
- [x] `{old path}` now ≤ `{max_file_loc}` LOC and has a single responsibility
- [x] `{new path}` ≤ `{max_file_loc}` LOC, single responsibility, isolated tests
```

---

## Recording Files

Add entries as files are created or modified during execution.

**Single-phase plans:** Update the plan file's Files Created / Files Modified sections.

**Multi-phase plans:** Update **both**:
1. The **slice file** — phase-specific files only
2. The **master plan** — consolidated list across all phases

**Files Created:** Always record LOC. If a file is under a `**LOC waiver:**`, state it on the same line.
```markdown
- `lib/services/reader_service.dart` (85 lines) — reader service with pagination support
- `test/services/reader_service_test.dart` (120 lines) — unit tests for reader service
- `lib/parsers/grammar.dart` (412 lines) — generated parser. **LOC waiver:** generator output; alternatives (hand-written / split tables) reduce maintainability.
```

**Files Modified:**
```markdown
- `lib/screens/home_screen.dart` — added reader service integration
- `pubspec.yaml` — added new dependency
```

---

## Completing the Plan

### Single-phase plans

1. Verify a `## Architecture Gate Results` block exists with **Overall: PASS** dated within this execution. If absent or FAIL → return to Step 2.3, do not flip status.
2. Change status line: `**Status:** ✅ COMPLETED — {YYYY-MM-DD}`
3. Verify all Implementation Progress checkboxes are `[x]`
4. Verify Files Created/Modified sections are complete
5. Verify Success Criteria checkboxes are `[x]`

### Multi-phase plans

1. Verify each slice file contains its own `## Architecture Gate Results` block with **Overall: PASS** before its `**Status:** ✅ COMPLETED` line.
2. Verify all slice files have `**Status:** ✅ COMPLETED — {YYYY-MM-DD}`
3. Verify all `## Progress` lines in the master plan are `[x]` with dates
4. Change master plan status line: `**Status:** ✅ COMPLETED — {YYYY-MM-DD}`
5. Verify master plan's consolidated Files Created/Modified sections are complete
6. Verify Success Criteria checkboxes are `[x]` in the master plan

---

## When to Invoke the Planning Skill Instead

Handle these directly (no planning skill needed):
- Marking tasks `[x]`
- Adding file entries (with LOC counts and any waivers)
- Adding a bug round for a test failure
- Adding a refactoring round for an architecture-gate failure (extracting one module from another within the current phase)
- Completing a phase header or status line
- Updating master plan progress section

Invoke the `{plan_skill}` skill (see *Invoking companion skills* in `SKILL.md`) in Update mode for:
- Adding a new phase discovered during implementation
- Restructuring remaining phases after a major discovery
- Significant scope changes that require re-analysis
- An architectural split that grows beyond the current phase — when extracting one component reveals a second component that itself needs its own phase, hand back to planning rather than ballooning the current slice.
