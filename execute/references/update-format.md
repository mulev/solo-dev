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

## Recording Files

Add entries as files are created or modified during execution.

**Single-phase plans:** Update the plan file's Files Created / Files Modified sections.

**Multi-phase plans:** Update **both**:
1. The **slice file** — phase-specific files only
2. The **master plan** — consolidated list across all phases

**Files Created:**
```markdown
- `lib/services/reader_service.dart` (85 lines) — reader service with pagination support
- `test/services/reader_service_test.dart` (120 lines) — unit tests for reader service
```

**Files Modified:**
```markdown
- `lib/screens/home_screen.dart` — added reader service integration
- `pubspec.yaml` — added new dependency
```

---

## Completing the Plan

### Single-phase plans

1. Change status line: `**Status:** ✅ COMPLETED — {YYYY-MM-DD}`
2. Verify all Implementation Progress checkboxes are `[x]`
3. Verify Files Created/Modified sections are complete
4. Verify Success Criteria checkboxes are `[x]`

### Multi-phase plans

1. Verify all slice files have `**Status:** ✅ COMPLETED — {YYYY-MM-DD}`
2. Verify all `## Progress` lines in the master plan are `[x]` with dates
3. Change master plan status line: `**Status:** ✅ COMPLETED — {YYYY-MM-DD}`
4. Verify master plan's consolidated Files Created/Modified sections are complete
5. Verify Success Criteria checkboxes are `[x]` in the master plan

---

## When to Invoke the Planning Skill Instead

Handle these directly (no planning skill needed):
- Marking tasks `[x]`
- Adding file entries
- Adding a bug round for a test failure
- Completing a phase header or status line
- Updating master plan progress section

Invoke `{plan_skill}` in Update mode for:
- Adding a new phase discovered during implementation
- Restructuring remaining phases after a major discovery
- Significant scope changes that require re-analysis
