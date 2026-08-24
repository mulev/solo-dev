# Bug Round & Completion Formats

## Bug Round Format

When bugs are discovered during implementation, add a bug round section to the **slice file** of the affected phase (multi-phase plans) or directly in the plan file (single-phase plans):

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
