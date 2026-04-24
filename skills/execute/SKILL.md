---
name: execute
description: >
  Executes work from tracked tasks or plan files. Finds ready-to-work tasks via
  the configured issue tracker (priority and dependency aware), claims them,
  implements phases (write code, run tests, update plan), handles failures via
  bug rounds, and closes tasks on completion. Use when the user says "execute",
  "work on next task", "execute the plan", "start implementing", "run the
  plan", or passes a task ID or plan file path. Each invocation executes one
  phase — after completion, offers to continue with the next unblocked task.
  Also triggers on "resume", "what's next", or "next task". Accepts no
  argument (pick from ready tasks), a task ID, or a .md plan file path.
---

# Execute

## Invocation

When this skill is invoked, **immediately** output the following line before doing anything else — no preamble, no extra text:

```
[exec] Executing...
```

This is non-negotiable. It must be the very first thing the user sees.

---

## Configuration

This skill reads `skill.config.md` from its base directory on every invocation.

**If `skill.config.md` does not exist:**
1. Copy `skill.config.example.md` → `skill.config.md`.
2. Use `AskUserQuestion` offering interactive or manual setup.
3. **Interactive flow (2 rounds of questions):**
   - Round 1: Plans directory, issue tracker (enable + CLI name), formatter, test command
   - Round 2: Planning skill name, code simplifier agent, code reviewer agent, commit message processor
4. Write resolved values to `skill.config.md`.

**If fully configured:** Read silently and proceed.

**Shorthands used below:**

| Shorthand | Config field | Default |
|-----------|-------------|---------|
| `{plans_dir}` | Plans Directory → plans_dir | `project_plans` |
| `{tracker_cli}` | Issue Tracker → cli_command | `bd` |
| `{tracker_data}` | Issue Tracker → data_dir | `.beads` |
| `{formatter}` | Formatter → command | (from project instructions) |
| `{test_command}` | Test Command → command | (from project instructions) |
| `{plan_skill}` | Companion Skills → plan_skill | `/plan` |
| `{code_simplifier}` | Companion Agents → code_simplifier | (from `skill.config.example.md`) |
| `{code_reviewer}` | Companion Agents → code_reviewer | (from `skill.config.example.md`) |
| `{commit_processor}` | Post-Processing → commit_message_processor | `/humanizer` |

**Tracker state:** Read `Issue Tracker → enabled` from config. If `true`, run all `{tracker_cli}` commands in Steps 1 and 3. If `false`, skip all tracker commands.

---

Read `references/tracker-templates.md` for all tracker interaction templates, AskUserQuestion formats, and `{tracker_cli}` command sequences.

<tracker-state>
Track whether tracker is active for this execution:
- **tracker_active = true**: a tracker task ID was resolved in Step 0. Run all `{tracker_cli}` commands in Steps 1 and 3.
- **tracker_active = false**: no tracker task (plan-only mode, tracker not initialized, or user chose "Execute without tracker"). Skip all tracker commands in Steps 1 and 3.
</tracker-state>

<plan-file-resolution>
Plans come in two shapes. Determine which you're working with and track both files when applicable:

**Single-phase plan** — one `.md` file containing everything: `## Implementation Progress` with `### Phase 1:` and `#### Step 1.1–1.6` sub-headers, plus Implementation, Testing, Files, and Tracker sections. The working file and the plan file are the same.

**Multi-phase plan** — a folder with two file types:
- **Slice file** (`phase_N_{slug}.md`) — the working file. Contains `# Phase {N}: {Name}` (H1), a `**Status:**` line, `## Implementation Progress` with flat checkboxes, and all implementation detail. Each tracker task points to its slice file.
- **Master plan** (`plan.md`) — shared context. Contains `## Progress` with `- [ ] [Phase N: {Name}](phase_N_{slug}.md) — {task-id}` links, plus Objective, Requirements, Dependency Table, Success Criteria, Tracker, and consolidated Files sections.

When working from a tracker task on a multi-phase plan, the **slice file is the working file** — read it for implementation detail, update its checkboxes and status. The **master plan is context** — read it for shared requirements and cross-cutting concerns, update its `## Progress` section on phase completion.

When given a master plan path (Step 0c), resolve the working file using the logic in `references/tracker-templates.md` (Resolve the Working File).
</plan-file-resolution>

## Workflow

### Step 0: Route input

Classify the argument and branch to the appropriate entry point. See `references/tracker-templates.md` (Input Routing) for detection rules.

<input-routing>
**No argument** → Step 0a (tracker-driven selection)
**Task ID** (short identifier — alphanumeric with optional hyphens, no `/` or `.md` suffix) → Step 0b (direct tracker execution)
**.md file path** (contains `/` or ends with `.md`) → Step 0c (plan file execution)
**Anything else** → Error: "This skill accepts: no argument (pick from ready tasks), a task ID, or a .md plan file path."
</input-routing>

---

#### Step 0a: Tracker-driven selection (no argument)

1. **Detect project** using the same priority as the planning skill (explicit mention > IDE files > conversation context > ask).
2. **Check tracker availability**: see `references/tracker-templates.md` (Check Tracker Availability). If tracker is not available, fall back to the plan-file-only workflow (list `.md` files in `{plans_dir}/{project}/todo/` and let user pick).
3. **Query ready tasks**: run `{tracker_cli} ready --sort priority` in the project directory.
4. **Present results** using the Task Selection template from `references/tracker-templates.md`. Show up to 4 tasks sorted by priority. Include parent epic title in the description for context.
5. **Handle empty results**: If no tasks are ready, diagnose why (no tasks at all, all blocked, all closed) using the diagnostic templates in `references/tracker-templates.md`.
6. **After user picks a task**: extract the working file from the task's notes (see `references/tracker-templates.md` — Extract Plan File from Notes). Read the working file. For multi-phase tasks, also read the master plan for shared context. Store the task ID for lifecycle management.

**If the task has no plan file reference**: offer to create one via `{plan_skill}` using the task description as requirements. A plan file is required before execution. See Orphan Task template in `references/tracker-templates.md`.

**If the referenced plan file doesn't exist on disk**: offer to create a new plan. See Missing Plan File template in `references/tracker-templates.md`.

---

#### Step 0b: Direct tracker execution (task ID argument)

1. **Validate the task**: run `{tracker_cli} show {id}`. Check status — see `references/tracker-templates.md` (Validate Task) for the status-action table.
2. **Extract plan file** from the task's notes. Same rules as Step 0a — require a plan, offer to create one if missing.
3. **Identify the working file** — see `references/tracker-templates.md` (Extract Plan File from Notes). For multi-phase tasks, the notes contain a `Slice:` path pointing to the slice file (the working file) and a `Master:` path for shared context. For single-phase tasks, the notes contain a `Plan:` path — the working file and plan file are the same.
4. **Resume check**: if the task is already `in_progress` (claimed in a previous session), skip claiming in Step 1. Read the working file to find which steps are already `[x]` and resume from the first unchecked step. See Resume template in `references/tracker-templates.md`.

---

#### Step 0c: Plan file execution (.md file argument)

1. **Resolve the working file**: The given path may be a master plan, a slice file, or a standalone plan. Follow the resolution logic in `references/tracker-templates.md` (Resolve the Working File) to determine the working file and context file.
2. **Check tracker availability**: see `references/tracker-templates.md` (Check Tracker Availability). If tracker is not available, set `tracker_active = false` and proceed to Step 1.
3. **Check for tracker tasks**: search for tracker tasks whose notes reference this plan file path. Run `{tracker_cli} search "{plan file path}"`.
4. **Route based on tracker state** — three possible outcomes:

   **Ready tasks exist**: filter to tasks with status `open` and no unresolved blockers. If only one is ready, proceed with it. If multiple are ready, present them sorted by phase number (phases have a natural execution order) and let the user pick. Store the task ID for lifecycle management.

   **Tasks exist but none are ready**: diagnose — are they blocked, in_progress, deferred, or closed? Use the appropriate diagnostic template from `references/tracker-templates.md`. Show blockers if blocked. Show assignee if in_progress. Report completion if all closed.

   **No tracker tasks for this plan**: use `AskUserQuestion` — offer to create tracker tasks via `{plan_skill}`, or proceed without tracker. See `references/tracker-templates.md` (Plan File — No Tracker Tasks). If "Execute without tracker": set `tracker_active = false` and proceed with Steps 1–5, skipping all `{tracker_cli}` commands in Steps 1 and 3.

---

### Step 1: Set up branch and claim task

Before writing any code, ensure a clean git branch and claim the tracker task.

**Branch setup:**

1. Check the current branch of the project repo.
2. **If on `main`**: pull latest, create a new branch named after the plan (e.g., `feat/user-profile-settings` from `myapp_feat_user_profile_settings.md`).
3. **If NOT on `main`**: use `AskUserQuestion`:
```
question: "You're on branch '{current}'. How do you want to proceed?"
header: "Branch"
options:
  - label: "Continue on '{current}' (Recommended)"
    description: "Keep working on the existing branch."
  - label: "Switch to main, create new branch"
    description: "Pull latest main and create a fresh branch named after the plan."
```

Never commit to `main`.

**Claim tracker task** (skip if `tracker_active = false`, or if task is already `in_progress`):

Run `{tracker_cli} update {id} --claim` — see `references/tracker-templates.md` (Task Lifecycle Commands — Claim). If claim fails (already claimed), warn the user and ask whether to proceed.

### Step 2: Execute phase

Execute the single phase in the working file:

1. **Read the working file** (slice file for multi-phase, plan file for single-phase) to identify unchecked tasks. For single-phase plans, tasks are grouped under `#### Step N.M` sub-headers — work through them in order (Exploration → Tests → Implementation → Integration Tests → Documentation → Polish). For multi-phase slice files, tasks are a flat checklist under `## Implementation Progress` — work top to bottom.
2. **TDD red-green cycle**: Write the test → run to confirm it fails → implement the minimum code to pass → run to confirm it passes. At each step, run only the changed test file(s), not the full suite (e.g., `{test_command} test/path/to/changed_test.dart`). Never write implementation before the test exists. Skip only when genuinely impossible — state the reason in the plan.
3. **Regression tests**: For any change to existing code, write regression tests covering the modified behavior before touching the implementation.
4. **Integration tests**: For any feature added or changed, verify or add integration tests covering the complete app-level flow.
5. **Simplify**: After each implementation step passes its changed test file(s), launch the `{code_simplifier}` agent on the newly written or modified source files. Re-run the same changed test file(s) after simplification to confirm nothing broke.
6. **Run formatter**: Run `{formatter}` (skip if empty in config).
7. **If all phase tasks pass their changed test files** → go to Step 3. **Do not proceed until Step 3 is fully complete.**
8. **If tests fail** → go to Step 4.

### Step 3: Update plan, close task, and offer continuation

After tests pass for the phase:

**Update plan files** (see `references/update-format.md` for format rules):

**Single-phase plans:**
1. Mark all completed tasks with `[x]` in the Implementation Progress section.
2. Add ` ✅ COMPLETED — {YYYY-MM-DD}` to the `### Phase 1:` header.
3. Add created/modified files to the Files Created / Files Modified sections.

**Multi-phase plans** — update both files:
1. **Slice file:** Mark all completed tasks with `[x]` in `## Implementation Progress`. Change `**Status:**` to `✅ COMPLETED — {YYYY-MM-DD}`. Add files to the slice's Files Created / Files Modified sections.
2. **Master plan:** Mark the corresponding `- [ ]` line `[x]` in the `## Progress` section and append ` ✅ {YYYY-MM-DD}`. Add files to the master's consolidated Files Created / Files Modified sections.

**Then, for both plan types:** Commit changes as atomic, logical chunks — see Commit Strategy below.

**Close tracker task** (skip if `tracker_active = false`):

Run the close → epic auto-close → persist sequence from `references/tracker-templates.md` (Task Lifecycle Commands). This unblocks dependent tasks as early as possible and prevents stale `in_progress` states across sessions.

**Offer continuation**: After closing the task, check if `--suggest-next` output from the close command listed newly unblocked tasks. If tasks were unblocked (or if working from a multi-phase plan with remaining phases), use `AskUserQuestion`:

```
question: "Phase {N}: {name} complete — all tests pass. {M} task(s) now unblocked."
header: "Continue?"
options:
  - label: "Execute next task"
    description: "Pick from ready tasks and continue."
  - label: "Done for now"
    description: "Stop here. Resume later by invoking execute again."
```

If "Execute next task": present the ready tasks using the Task Selection template from `references/tracker-templates.md`, then loop back to Step 1 (branch setup) with the selected task. If "Done for now": proceed to Step 5 (finalize).

If no tasks were unblocked and no phases remain, skip the question and proceed directly to Step 5.

**When to invoke the planning skill**: If during execution you discover the plan needs a new phase, significant restructuring, or additional analysis — invoke `{plan_skill}` in Update mode. Do NOT invoke it for minor adjustments like adding a single sub-task or fixing a typo in the plan.

### Step 4: Handle failure (Bug Round)

When tests fail or implementation hits an unexpected problem:

1. Add a Bug Round section to the **working file** — the slice file for multi-phase plans, the plan file for single-phase plans (see `references/update-format.md`).
2. Analyze the failure — identify root cause.
3. Implement the fix.
4. Add a regression test for the bug.
5. Re-run the affected test file(s) — not the full suite.
6. If fixed → mark the bug round as resolved, return to Step 3.
7. If still failing → add another bug round. After 3 consecutive failed rounds, stop and use `AskUserQuestion`:
```
question: "3 bug rounds failed without resolution. How do you want to proceed?"
header: "Escalate"
options:
  - label: "I'll debug manually"
    description: "Stop execution. You take over — resume with execute when ready."
  - label: "Retry with a different approach"
    description: "Describe the alternative approach in the 'Other' field."
  - label: "Abandon this phase"
    description: "Skip the phase and mark it as blocked in the plan."
```

### Step 5: Finalize

After the phase is complete (or the user chose "Done for now" after continuing through multiple phases):

<finalization-rules>
1. **Update documentation**: Review all changes made during this round and update project docs in `{project}/docs/`. This is mandatory — do not skip.
2. **Verify localization**: If any user-facing content changed, scan for locale files (`*.arb`, `*.strings`, `l10n/`) regardless of whether the plan has a Localization section. Update all supported locales — adopt native speaker role for each non-English locale to ensure natural, idiomatic translation, never word-for-word from English. English is always the baseline. This is mandatory, not optional.
3. **Verify test coverage**: MUST achieve 100% coverage — no untested code paths. Write tests for any gaps before finishing.
4. **Run final test suite**: Run `{formatter}` (skip if empty in config) → full test run including integration tests. All tests must pass.
5. **Code review** (only when all phases are complete and the full test suite passes): invoke `{code_reviewer}` (skip if empty in config) on all source files changed during this execution. Apply any improvements suggested. Re-run the full test suite after applying changes to confirm nothing broke. Only proceed to the next step once code review is clean and tests still pass.
6. **Update the plan**: If all phases are done, mark the plan as `✅ COMPLETED — {YYYY-MM-DD}`. For multi-phase plans, update both the master plan's `**Status:**` line and verify all slice file statuses are `✅ COMPLETED`. If phases remain, leave as `🔄 IN PROGRESS`.
7. **Commit**: Commit docs and additional tests as a separate commit from implementation work. Follow the Commit Strategy.
</finalization-rules>

---

## Commit Strategy

<commit-strategy>
Every commit must be **atomic** — small, logically self-contained, and independently rollbackable. Never bundle unrelated changes into a single commit.

**Split by logical unit, not by phase boundary.** A phase that touches multiple concerns gets multiple commits. A phase that does one thing gets one commit.

How to split:
1. After a phase passes tests, review all staged/unstaged changes.
2. Group files by logical concern (e.g., "add model class + its tests" is one commit; "update UI to use new model" is another).
3. Stage and commit each group separately with a descriptive message scoped to that change.
4. Plan file updates go in their own commit, separate from code changes.

Rules:
- One commit per logical unit of work — not one commit per phase.
- Test files commit together with the code they test.
- Config/dependency changes (pubspec.yaml, build.gradle) commit with the code that requires them.
- Plan file updates and doc updates are always separate commits from implementation code.
- Bug round fixes are their own commit(s), separate from the phase work that surfaced them.
- Commit messages follow the pattern: `{type}: {what changed}` (e.g., `feat: add reader service with pagination`, `test: add reader service unit tests`, `docs: update plan with phase 2 completion`).
- Run `{commit_processor}` on every commit message before finalizing (skip if empty in config) — plain language, no marketing tone.
</commit-strategy>

---

## Constraints

<constraints>
These override default behavior — the workflow steps handle everything else.

- Always work on feature branches — NEVER commit to or merge into `main`.
- Plan file update is a hard gate between phases — the plan is the crash-recovery checkpoint. If a session ends mid-execution, only phases with `[x]` marks and `✅ COMPLETED` headers are recoverable. Never batch updates across phases.
- Close the tracker task immediately after its phase completes — this unblocks dependent tasks as early as possible. Check `{tracker_cli} epic close-eligible` after every child task closure and auto-close the epic silently if all children are done.
- On partial completion ("stop here"), leave the tracker task as `in_progress`. Do NOT close or revert status.
- A plan file is required for execution — tracker task descriptions contain step checklists but omit code snippets, insertion points, and done-when criteria needed for implementation. If a tracker task has no linked plan, offer to create one via `{plan_skill}` before proceeding.
- TDD is mandatory: write tests → confirm failure → implement → confirm passing. Skip only when genuinely impossible — state the reason.
</constraints>
