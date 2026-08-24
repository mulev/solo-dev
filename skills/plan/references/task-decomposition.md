# Task Decomposition Template

After the user approves the plan, decompose it into tracker tasks. The plan files remain the source of truth — tracker tasks reference them, not duplicate them.

Shorthands (`{tracker_cli}`) come from `skill.config.md`.

---

## Epic (multi-phase plans only)

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

## Task per phase

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

## Single-phase plans (no epic)

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

## Key rules

- **Master plan** (`plan.md`) is the source of truth for shared context — objective, requirements, dependency table, cross-cutting concerns. Referenced by the epic.
- **Slice files** (`phase_N_{slug}.md`) are the source of truth for implementation detail — code snippets, insertion points, test cases. Referenced by individual tasks.
- Task descriptions contain **step checklists** — enough to orient from `{tracker_cli} show`, with the slice file pointer for deep detail.
- Dependencies between tasks must match the dependency table in the master plan.
- Labels should include the relevant technology/platform (e.g., `ios`, `android`, `web`, `dart`).
