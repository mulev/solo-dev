# Issue Tracker Templates

Templates and command sequences for the execute skill's tracker integration. These cover task selection, lifecycle management, and diagnostic flows.

---

## Input Routing

Classify the argument passed to this skill:

| Input | Detection | Route |
|-------|-----------|-------|
| No argument | Empty args | Step 0a: Tracker-driven selection |
| Task ID | Short identifier — alphanumeric with optional hyphens, no `/` or `.md` suffix (e.g., `EP-3`, `abc123`) | Step 0b: Direct tracker execution |
| Plan file path | Contains `/` or ends with `.md` | Step 0c: Plan file execution |
| Anything else | Does not match above patterns | Error — show usage hint |

Usage hint on unrecognized input:
```
"This skill accepts: no argument (pick from ready tasks), a task ID, or a .md plan file path."
```

---

## Task Selection (Step 0a — no argument)

### Query ready tasks

Run in the detected project directory:

```bash
{tracker_cli} ready --sort priority
```

This returns tasks that are:
- Status: open (not in_progress, blocked, deferred, or closed)
- All blocking dependencies resolved
- Sorted by priority (P0 highest)

### Present to user

```yaml
question: "{N} tasks ready in {project}. Which one do you want to work on?"
header: "Task"
options:
  - label: "{task-id}: {task title}"
    description: "P{priority} | Epic: {parent epic title or 'standalone'}"
  # Up to 4 options, sorted by priority (highest first).
  # If more than 4 ready tasks exist, show top 4 and note in the question
  # text: "Showing top 4 of {N} ready tasks by priority."
```

### No ready tasks

If `{tracker_cli} ready` returns nothing, check why:

```bash
{tracker_cli} list --status open     # Any open tasks at all?
{tracker_cli} blocked                # What's blocked?
{tracker_cli} list --all             # Are there only closed tasks?
```

Then use the appropriate diagnostic:

**No tracker tasks at all:**
```yaml
question: "No tracker tasks found in {project}. What do you want to do?"
header: "No tasks"
options:
  - label: "Pick a plan file to execute"
    description: "Fall back to selecting a .md plan from {plans_dir}/{project}/todo/."
  - label: "Create a plan first"
    description: "Invoke {plan_skill} to create a plan and decompose it into tracker tasks."
```

**All tasks blocked:**
```yaml
question: "All {N} open tasks in {project} are blocked. What do you want to do?"
header: "Blocked"
options:
  - label: "Show blockers"
    description: "Display what's blocking each task so you can resolve dependencies."
  - label: "Pick a plan file instead"
    description: "Fall back to selecting a .md plan from {plans_dir}/{project}/todo/."
  - label: "Force-start a blocked task"
    description: "Override blockers and start working — dependencies may not be met."
```

**All tasks closed:**
```
"All tracker tasks in {project} are closed — nothing to execute. Create new work with {plan_skill}."
```

---

## Direct Tracker Execution (Step 0b — task ID argument)

### Validate task

```bash
{tracker_cli} show {id}
```

Check the returned status:

| Status | Action |
|--------|--------|
| `open` | Proceed — task is ready |
| `in_progress` | Warn user: "Task {id} is already in progress (assignee: {name}). Continue anyway?" |
| `blocked` | Show blockers: `{tracker_cli} dep list {id}`. Ask user if they want to force-start or pick a different task |
| `deferred` | Show defer date. Ask user if they want to un-defer and start, or pick a different task |
| `closed` | Error: "Task {id} is already closed. Nothing to execute." |

### Extract plan file from notes

Parse the `notes` field from `{tracker_cli} show {id}` output. Look for lines matching these prefixes (in priority order):

**Multi-phase tasks** (created by the planning skill for folder plans):
```
Slice: {absolute path to phase_N_{slug}.md}
Master: {absolute path to plan.md}
```
- `Slice:` → the **working file** — implementation detail, progress checkboxes, status
- `Master:` → the **context file** — shared requirements, dependency table, cross-cutting concerns

**Single-phase tasks:**
```
Plan: {absolute path}
```
or
```
Plan file: {absolute path}
```
- This is both the working file and the context file

**Resolution rules:**
- If `Slice:` is found and file exists → use it as the working file. Read `Master:` for shared context.
- If `Plan:` or `Plan file:` is found and file exists → use it as the working file (single-phase mode).
- If a path is found but the file is missing → error with diagnostic (see Missing Plan template below).
- If no recognized prefix is found → offer to create a plan (see Orphan Task template below).

### Identify working file and phase

**Multi-phase tasks** (notes contain `Slice:`): The slice file IS the phase — the entire file is the working scope. No header matching needed. The phase number is in the file name (`phase_N_{slug}.md`) and the H1 heading (`# Phase {N}: {Name}`).

**Single-phase tasks** (notes contain `Plan:` / `Plan file:`): The plan file contains one phase under `## Implementation Progress` → `### Phase 1: {Name}` with `#### Step 1.1–1.6` sub-headers. Use the only phase present.

**Master plan path given (Step 0c):** Use the Resolve the Working File logic below — do not execute from a master plan directly.

---

## Plan File Execution (Step 0c — .md file argument)

### Check Tracker Availability

Canonical check — referenced by Steps 0a, 0b, and 0c:

1. Look for `{tracker_data}/` in the project root
2. Verify `{tracker_cli}` is on the PATH (`which {tracker_cli}`)
3. If `{tracker_data}/` exists but `{tracker_cli}` is not found: tell the user tracker is initialized but the CLI is not installed
4. If `{tracker_data}/` is not found: tracker is not available — set `tracker_active = false`
5. If both exist: tracker is available — proceed with `{tracker_cli}` commands

### Resolve the Working File

Determine the working file and context file from the given path:

**Master plan** (`plan.md` inside a folder): Do not execute from it directly. Read its `## Progress` section, find the first unchecked `- [ ]` line, follow its link to the corresponding slice file, and use that as the working file. The master plan remains the context file. If all `## Progress` lines are `[x]`: the plan is already complete — tell the user "All phases are done. Nothing to execute." and stop.

**Slice file** (`phase_N_{slug}.md`): Use it directly as the working file. Read the `**Parent plan:**` link to find the master plan for shared context. If `**Parent plan:**` is missing or the linked file doesn't exist: warn the user ("Slice file has no valid parent plan link — shared context unavailable"), then proceed with the slice file alone as both working and context file.

**Standalone single-phase plan**: Use it as both working file and context file.

### Check for tracker tasks

Search for tracker tasks whose notes reference this plan file (or its parent folder):

```bash
{tracker_cli} search "{plan file path}"
```

### Three states

**State 1 — Ready tracker tasks exist:**
Filter to tasks with status `open` and no unresolved blockers. If only one is ready, proceed with it. If multiple are ready, present them using the Task Selection template (sorted by phase number, not priority — phases have a natural order) and let the user pick.

**State 2 — Tracker tasks exist but none are ready:**
All matching tasks are either `blocked`, `in_progress`, `deferred`, or `closed`.

- If some are `blocked`: show blockers using the Blocked diagnostic template
- If some are `in_progress`: tell user who's working on them
- If all are `closed`: "All tracker tasks for this plan are closed — plan is complete."

**State 3 — No tracker tasks for this plan:**
```yaml
question: "This plan has no tracker tasks. How do you want to proceed?"
header: "No tracker"
options:
  - label: "Create tracker tasks from the plan (Recommended)"
    description: "Invoke {plan_skill} to decompose this plan into tracker tasks, then execute."
  - label: "Execute without tracker"
    description: "Work directly from the plan file — no tracker tracking or dependency management."
```

If "Execute without tracker": set `tracker_active = false` and proceed with Steps 1–5, skipping all `{tracker_cli}` commands in Steps 1 and 3.

---

## Task Lifecycle Commands

### Claim (before writing code — part of branch setup)

```bash
{tracker_cli} update {id} --claim
```

This atomically sets status to `in_progress` and assigns the task. Run this in Step 1 (branch setup), after confirming the branch but before writing any code.

If claim fails (task already claimed by someone else), warn the user and ask whether to proceed anyway.

### Close (after phase/task completion)

```bash
{tracker_cli} close {id} --reason "Phase {N} complete: {one-line summary}" --suggest-next
```

- `--reason` records what was done
- `--suggest-next` shows tasks that were unblocked by this closure — useful for the user to know what's available next

### Epic auto-close check (after closing any child task)

```bash
{tracker_cli} epic close-eligible
```

If the parent epic appears in the output (all its children are closed):

```bash
{tracker_cli} close {epic-id} --reason "All phases complete"
```

Notify the user: "Epic {epic-id}: {title} auto-closed — all child tasks are done."

### Persist state (if Dolt auto-commit is off)

```bash
{tracker_cli} vc commit "execute: closed {id} — {summary}"
```

Only run this if `{tracker_cli} vc status` shows uncommitted changes. If auto-commit is on or batch, Dolt handles persistence automatically.

---

## Partial Completion (phase-by-phase "Stop here")

When the user selects "Stop here" during phase-by-phase execution:

1. The tracker task remains `in_progress` (already claimed — do NOT close or revert status)
2. The plan file has progress checkboxes showing what's done
3. Tell the user: "Task {id} stays in progress. Resume by invoking execute with the task ID or plan file path."

No tracker commands needed — the task is already in the right state.

---

## Orphan Task (no plan file reference)

When a tracker task has no plan file path in its notes:

```yaml
question: "Task {id} has no linked plan file. A plan is required before execution. Create one?"
header: "No plan"
options:
  - label: "Create a plan from this task (Recommended)"
    description: "Invoke {plan_skill} using the task description as requirements. The plan will be linked back to this task."
  - label: "Cancel"
    description: "Don't execute. Add a plan file reference manually first."
```

If "Create a plan": invoke `{plan_skill}` with the task description as the task source. After the plan is created, update the tracker task notes to reference the plan files:

**If the planning skill created a single-phase plan:**
```bash
{tracker_cli} update {id} --notes "Plan: {absolute path to plan .md}
{existing notes content}"
```

**If the planning skill created a multi-phase plan** (this task becomes one phase's task):
```bash
{tracker_cli} update {id} --notes "Slice: {absolute path to phase_N_{slug}.md}
Master: {absolute path to folder/plan.md}
{existing notes content}"
```

Then resume execution from Step 1 (set up branch and claim task).

---

## Missing Plan File

When a tracker task references a plan file that doesn't exist on disk:

```yaml
question: "Task {id} references plan file '{path}' but the file doesn't exist. What do you want to do?"
header: "Missing plan"
options:
  - label: "Create a new plan for this task (Recommended)"
    description: "Invoke {plan_skill} using the task description as requirements. Overwrites the missing file path."
  - label: "Cancel"
    description: "Don't execute. Investigate the missing file first."
```

---

## Resume After Previous Session

When this skill is called with a task ID that is already `in_progress` (claimed in a previous session):

1. Skip the claim step — task is already claimed
2. Read the working file (slice file for multi-phase, plan file for single-phase) to find which checkboxes are already `[x]`
3. Resume from the first unchecked `- [ ]` step — do NOT re-execute checked steps
4. For single-phase plans with `#### Step N.M` sub-headers: identify which sub-step group the first unchecked item belongs to for a precise resume message

**Resume messages:**

Single-phase plan (sub-step aware):
```
"Resuming task {id} — Phase 1 is partially complete. Continuing from Step 1.{M}: {sub-step name} ({done}/{total} tasks done)."
```

Multi-phase slice file (flat checklist):
```
"Resuming task {id} — Phase {N} is partially complete ({done}/{total} tasks done). Continuing from next unchecked task."
```
