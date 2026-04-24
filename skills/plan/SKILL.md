---
name: plan
description: >
  Creates and manages execution plans for software projects. Plans are vertical
  slices — each phase is an atomic deliverable with TDD tests, implementation,
  integration tests, docs, and polish. Multi-phase plans produce a folder with a
  master plan and per-phase slice files for focused context, optionally
  decomposed into tracked tasks with one task per slice. Handles three operations:
  (1) creating plans via requirements gathering, codebase exploration,
  vertical-slice structuring, and task decomposition, (2) updating plans to mark
  progress, add bug rounds, or
  record files modified, (3) completing plans by updating status and moving to
  done/. Use when the user says "plan", "create a plan", "update the plan",
  "mark as done", or discusses planning any feature, fix, refactoring, or
  technical task. Also triggers when the user references an existing plan file,
  asks about plan status, or wants to split a plan into separate files.
---

# Plan

## Invocation

When this skill is invoked, **immediately** output the following line before doing anything else — no preamble, no extra text:

```
[plan] Planning...
```

This is non-negotiable. It must be the very first thing the user sees.

---

## Configuration

This skill reads `skill.config.md` from its base directory on every invocation.

**If `skill.config.md` does not exist:**
1. Copy `skill.config.example.md` → `skill.config.md`.
2. Use `AskUserQuestion` offering interactive or manual setup.
3. **Interactive flow:**
   - Plans directory (default: `project_plans`)
   - System plan mirror (default: `~/.claude/plans`, or empty to disable)
   - Known projects — name + code path pairs (at least one required)
   - Issue tracker — enable/disable, CLI command name (default: disabled)
   - Formatter and test command (or leave empty to infer from project instructions)
4. Write resolved values to `skill.config.md`.

**If `skill.config.md` exists but the Known Projects table is empty** (contains only the placeholder comment): Ask the user to add at least one project before proceeding.

**If fully configured:** Read silently and proceed.

**Shorthands used below:**

| Shorthand | Config field | Default |
|-----------|-------------|---------|
| `{plans_dir}` | Plans Directory → plans_dir | `project_plans` |
| `{system_plan_dir}` | System Plan Mirror → system_plan_dir | `~/.claude/plans` |
| `{tracker_cli}` | Issue Tracker → cli_command | `bd` |
| `{tracker_data}` | Issue Tracker → data_dir | `.beads` |
| `{formatter}` | Formatter → command | (from project instructions) |
| `{test_command}` | Test Command → command | (from project instructions) |
| `{execute_skill}` | Companion Skills → execute_skill | `/execute` |

**Tracker state:** Read `Issue Tracker → enabled` from config. If `true`, run all `{tracker_cli}` commands in Step 8, Update/Sync, and Complete workflows. If `false`, skip all tracker commands.

---

## Route to the right operation

| User intent | Operation | Reference |
|-------------|-----------|-----------|
| New feature, fix, refactor, or tech task | **Create** | `references/plan-template.md` |
| Progress update, phase completion, bug round | **Update** | `references/plan-template.md` (Bug Round Format) |
| Plan fully done, move to done/ | **Complete** | `references/conventions.md` (Moving to Done) |

Read `references/conventions.md` for file naming, directory structure, and project detection.
Read `references/plan-template.md` for plan templates (single-phase file and multi-phase folder) with all mandatory sections.

---

## Create Workflow

### Step 1: Detect project

Determine the target project — see `references/conventions.md` (Project Detection) for priority rules.

If the project is ambiguous, use `AskUserQuestion`:
```
question: "Which project is this plan for?"
header: "Project"
options: [one per detected candidate project, label = project name, description = path]
```

### Step 2: Gather requirements

**Task file shortcut:** If the user provided a file path as the task source (`.md` file with a task description), read it and treat its content as the full requirements. Store the original content to append as `## Original Task` at the end of the finished plan. When writing the plan (Step 5), single-phase plans overwrite the task file in place; multi-phase plans create a folder at the standard `{plans_dir}/` location and append the original task content to the master plan.

Scale question depth to task complexity:

**Small tasks** (bug fix, single-file change): Confirm what and where. Skip motivation/scope questions if obvious from context.

**Medium tasks** (feature, multi-file change): Ask about objective, constraints, and expected scope. One round of questions.

**Large tasks** (architecture change, new subsystem): Ask about objective, motivation, constraints, prerequisites, and scope. Two rounds maximum.

**How to ask**: Use `AskUserQuestion` for all clarification questions. Batch up to 4 questions per call. For open-ended questions, provide the most likely answers as options — the user can always pick "Other" to type a custom answer. Example structure:
```
questions:
  - question: "What is the primary goal of this feature?"
    header: "Goal"
    options: [likely answers derived from context] + user can pick Other
  - question: "Which files or modules are in scope?"
    header: "Scope"
    options: [candidates from codebase exploration] + Other
```

### Step 3: Check for existing plan

Search `{plans_dir}/{project}/todo/` for a plan covering the same topic. If one exists, use `AskUserQuestion` before proceeding:
```
question: "A plan for this topic already exists: {filename}. What do you want to do?"
header: "Existing plan"
options:
  - label: "Update the existing plan (Recommended)"
    description: "Switch to Update operation — add phases, steps, or notes to the existing file."
  - label: "Create a new separate plan"
    description: "Write a new plan file alongside the existing one."
```

### Step 4: Explore the codebase

Investigate before writing:
- Current implementation of related features
- File structure and naming patterns
- Existing tests that need updating
- API surfaces and data models involved
- Supported locales: scan for `l10n/`, `*.arb`, `*.strings`, or `Localizable.strings` files. If found, list every locale — all must be updated when user-facing content changes.

Use available MCP tools when the plan involves external libraries or frameworks:
- **Context7**: Query documentation for APIs, classes, or patterns you're not certain about. Skip for pure internal refactoring or config-only changes.
- **Other MCP servers**: Use web search or fetching to resolve version-specific behavior, check changelogs, or verify compatibility.

This exploration informs the Implementation, Testing, and Localization sections.

### Step 5: Produce the plan structure

Before writing full detail, draft the **plan structure** — the vertical slice decomposition. This is a lightweight outline that establishes:

1. How many phases (vertical slices) the plan needs
2. What each phase delivers
3. Dependencies between phases
4. Cross-cutting concerns that apply across phases

Calibrate phase count to task scope — see Plan Sizing in `references/plan-template.md`.

<audience>
Write every plan as if it will be handed to a junior engineer who has never touched this codebase. They know the language and framework basics but have zero institutional knowledge and may have poor judgment about what is "obvious." Never leave implied steps. Every step must be self-contained and unambiguous:
- Name the exact files to open and read before starting the step
- Point to relevant docs, architecture files, or existing code patterns to study
- Include a concrete "done when" criterion or verification step for each step
- Add code snippets or pseudocode for any step involving non-trivial logic
- Reference the test command and expected output for every testing step
</audience>

Each phase follows the 6-step vertical slice order: Exploration → Tests (TDD, written to fail) → Implementation (makes tests pass) → Integration tests → Documentation → Polish. See templates in `references/plan-template.md`.

Generate the plan using the appropriate template from `references/plan-template.md`:
- **1 phase:** single-phase template → single `.md` file
- **2+ phases:** multi-phase templates → folder with `plan.md` (master) + `phase_N_{slug}.md` (slice per phase)

<plan-output-rules>
**Single-phase plans (1 phase):**
- **If a task file was detected in Step 0:** overwrite that file with the full plan. Append `## Original Task` at the very end with the original content verbatim. Still create the system plan file at `{system_plan_dir}/{slug}.md` pointing to the task file's path.
- **Otherwise:** write to `{plans_dir}/{project}/todo/{filename}.md` following naming conventions from `references/conventions.md`. Create a system plan file at `{system_plan_dir}/{slug}.md` with a link to the project plan. Link from the project plan back to the system plan file.

**Multi-phase plans (2+ phases):**
- Create folder `{plans_dir}/{project}/todo/{foldername}/` following naming conventions from `references/conventions.md`.
- Write `plan.md` (master plan) inside the folder — shared context, dependency table, progress dashboard. No implementation detail or code snippets.
- Write one `phase_{N}_{slug}.md` (slice file) per phase — self-contained implementation detail, code snippets, tests, docs.
- Create system plan file at `{system_plan_dir}/{slug}.md` pointing to `{folder}/plan.md`.
- Link from the master plan back to the system plan file.
- **If a task file was detected in Step 0:** create the folder at the standard `{plans_dir}/` location. Append the original task file content as `## Original Task` at the end of the master plan.

</plan-output-rules>

### Step 5b: Re-slice oversized phases

After drafting all slice files, count the implementation steps and distinct files per phase. Any phase that exceeds **8 implementation steps** or touches **more than 5 unrelated files** is too fat — re-slice it before continuing.

**How to re-slice:**
1. Identify the natural boundaries inside the oversized phase (platform, layer, concern).
2. Split into thinner phases, each independently shippable and testable.
3. Update the dependency table — new phases may depend on the original or on each other.
4. Re-number subsequent phases and update all cross-references.

**Common split patterns:**
- **Multi-platform work:** one phase per platform (Dart API, Android, iOS, Web). Each platform slice includes its own tests and is shippable on its own.
- **API + consumers:** one phase for the API/interface layer, one for each major consumer.
- **Core + periphery:** one phase for the core logic change, one for docs/example app/integration tests that depend on it.

Do not proceed to self-review until every phase is within the thresholds.

### Step 6: Self-review and refine

Before presenting the plan to the user, re-read the full draft and challenge it against this checklist. Fix every gap found — do not skip items as "probably fine".

<self-review-checklist>
**Structure**
- [ ] Every phase has all 6 steps (exploration → tests → impl → integration → docs → polish)?
- [ ] Every phase has ≤8 implementation steps and touches ≤5 unrelated files? If not, re-slice (Step 5b).
- [ ] Dependency table present and acyclic?
- [ ] Folder structure correct for phase count (single file vs. folder)?
- [ ] Slice files have `**Parent plan:**`, `**Beads task:**`, `## Prerequisites`?

**Completeness**
- [ ] Every user requirement covered by at least one step?
- [ ] Implicit requirements accounted for (error states, edge cases, platforms)?
- [ ] Every requirement traceable to a success criterion?
- [ ] Locales listed if user-facing strings change? Docs step in every phase?

**Quality**
- [ ] Tests appear before implementation in every phase?
- [ ] Test coverage: unit for new paths, regression for changed paths, integration for flows?
- [ ] Each step: concrete file path, "done when" criterion, single atomic action?
- [ ] Code snippets present for non-trivial logic?

**Tracker**
- [ ] Phase titles usable as task titles?
- [ ] Dependencies map 1:1 to tracker `--deps`?
- [ ] Every `{tracker_cli} create` call includes `--notes` with absolute paths to plan/slice files?
- [ ] `--description` and `--notes` are separate flags (file references go in `--notes`, not `--description`)?
</self-review-checklist>

After completing the checklist, update the draft plan to address every gap, then proceed to Step 6b.

### Step 6b: Open reflection

Ask yourself: **"What have I not thought of yet — requirements, failure modes, edge cases, or steps a developer would hit that the plan does not account for?"**

Answer that question honestly. If anything surfaces, add it to the plan before proceeding to Step 7.

### Step 7: Iterative approval loop

After every complete cycle of writing or revising the plan, present a brief summary as text:
- Objective (1 sentence)
- Phase count and names (with dependency relationships)
- Key files that will be created or modified
- Whether this plan is an epic (multi-phase) or a single task

Then use `AskUserQuestion`:
```
question: "How does the plan look?"
header: "Review"
options:
  - label: "Looks good, finalize it (Recommended)"
    description: "Write the plan file and decompose it into tracked tasks."
  - label: "I have critique or refinements"
    description: "I'll share feedback — revise the plan and ask again."
  - label: "I have more requirements to add"
    description: "I'll provide additional requirements — expand the plan."
  - label: "I disagree with the approach"
    description: "Let's discuss the approach before continuing."
```

**If "Looks good":** Finalize the plan file and proceed to Step 8.

**If any other option (or Other):** Collect the user's feedback, apply changes to the plan, re-run Step 6 self-review, and repeat Step 7. This loop continues until the user selects "Looks good."

**Important:** This question must be asked after every fully completed cycle of working on the plan — including after revisions. Never skip the approval step.

### Step 8: Task decomposition

After the user approves the plan, decompose it into tracker tasks for multi-session tracking.

#### Step 8a: Check tracker availability

Determine whether task tracking should be used for this project:

1. Check the project's agent instructions for a tracker declaration. If the project is listed as tracker-enabled → proceed to Step 8b. If it is listed as tracker-disabled → skip Step 8 entirely.
2. If no declaration is found, check for a `{tracker_data}/` directory in the project root. If found → proceed to Step 8b.
3. If neither declaration nor `{tracker_data}/` exists, ask the user:

```
question: "This project doesn't have tracker configuration yet. How should we handle task tracking?"
header: "Tracker"
options:
  - label: "Initialize tracker (Recommended)"
    description: "Run '{tracker_cli} init' to set up the tracker, then create tasks from the plan."
  - label: "Install tracker first"
    description: "Install the configured tracker CLI, then initialize it and create tasks."
  - label: "Skip task tracking"
    description: "Don't create tracker tasks. The .md plan file is sufficient."
```

If "Initialize": run `{tracker_cli} init` in the project directory, then proceed to Step 8b.
If "Install first": install the configured tracker CLI. After installation succeeds, run `{tracker_cli} init`, then proceed to Step 8b. If installation fails, inform the user and fall back to "Skip task tracking."
If "Skip": end the Create workflow. The plan .md file stands alone.

#### Step 8b: Create tracker tasks

Use the Task Decomposition Template from `references/plan-template.md` to create tasks.

<tracker-notes-requirement>
**CRITICAL — `--notes` is mandatory on every `{tracker_cli} create` call.** The `--notes` flag is the only way the execution skill and other tools find the plan files from a tracker task. Without it, the task is an orphan — there is no link back to the implementation detail.

- **`--description`** = step checklist (what shows in `{tracker_cli} show`)
- **`--notes`** = absolute paths to plan files (how tools find the slice)

These are separate flags with separate purposes. Never merge file references into `--description`. Always pass `--notes` as a separate flag with **absolute paths**.

Epic notes format:
```
--notes "Plan: {absolute path}/plan.md
This epic's master plan contains the dependency table, cross-cutting concerns, and success criteria. Each child task has its own slice file with full implementation detail. Use the execution skill to implement."
```

Task notes format:
```
--notes "Slice: {absolute path}/phase_N_{slug}.md
Master: {absolute path}/plan.md
Full implementation detail (code snippets, insertion points, done-when criteria) is in the slice file. Use the execution skill to implement."
```

Single-phase task notes format:
```
--notes "Plan: {absolute path to plan .md}
Full detail: see plan file. Use the execution skill when implementing."
```
</tracker-notes-requirement>

**For multi-phase plans (epics):**
1. Create an epic issue with `--notes` referencing the **master plan file** (`{folder}/plan.md`)
2. For each phase, create a child task with:
   - `--description`: step checklist (actionable from `{tracker_cli} show`)
   - `--notes`: MUST contain absolute paths to the **slice file** and **master plan** (see format above)
   - `--deps`: dependencies matching the dependency table in the master plan
   - `--labels`: relevant technology/platform

**For single-phase plans:**
1. Create a single tracker task (not an epic)
2. `--description`: step checklist
3. `--notes`: MUST contain absolute path to plan file

**Key principle:** Slice files are the source of truth for implementation detail. The master plan is the source of truth for shared context. Tracker tasks reference these files but never duplicate code snippets or insertion-point specifics.

#### Step 8c: Verify and update plan files

After creating tracker tasks, verify the notes were set correctly, then update plan files.

**Verify:** Run `{tracker_cli} show {task-id}` for each created task and confirm the output includes the `NOTES` section with the absolute path to the slice file. If any task is missing notes, run `{tracker_cli} update {task-id} --notes "..."` to fix it before proceeding.

**Update plan files:**
1. Master plan's `## Beads` section — add epic and task IDs
2. Master plan's `## Progress` section — add task IDs next to each phase link
3. Each slice file's `**Beads task:**` field — add the created task ID

Then present the result to the user: issue IDs, dependency graph, and which tasks are immediately ready to work on.

**If `{tracker_cli} create` fails:** Check the error message. Common causes: tracker not initialized (run `{tracker_cli} init`), invalid flag syntax (check `{tracker_cli} create --help`), or missing parent ID (create the epic first). If the failure is unrecoverable, inform the user and skip task decomposition — the plan files stand alone.

### Step 9: Hand off to execution

After the plan is finalized — whether task decomposition was completed, skipped, or unavailable — offer to begin implementation immediately.

**If `{execute_skill}` is configured** (non-empty): Use `AskUserQuestion`:
```
question: "Plan is ready. Start implementing?"
header: "Execute"
options:
  - label: "Start executing now (Recommended)"
    description: "Invoke the execution skill to begin implementing the first phase."
  - label: "Not now"
    description: "Stop here. Start implementing later with {execute_skill}."
```

If "Start executing now": Invoke `{execute_skill}` with the plan file path. For multi-phase plans, pass the master plan path (`{folder}/plan.md`) — the execute skill resolves to the first ready phase. For single-phase plans, pass the plan file path directly.

If "Not now": End the Create workflow.

**If `{execute_skill}` is not configured** (empty): End the Create workflow without offering handoff.

---

## Update Workflow

### Step 1: Locate the plan

Find the plan via (in priority order):
1. User provides the file name or path
2. Search `{plans_dir}/{project}/todo/` matching conversation context — check both `.md` files and folder names
3. If ambiguous — use `AskUserQuestion` with plan names as options (label = name, description = full path). Limit to 4; if more exist, show the 4 most recently modified and note in the question text that others were omitted.

For multi-phase plans (folders), the master plan is at `{folder}/plan.md`. Phase-specific updates target the relevant slice file `{folder}/phase_N_{slug}.md`.

### Step 2: Determine what changed

Infer from context first (completed phases, files mentioned, errors described). If unclear, use `AskUserQuestion`:
```
question: "What needs to be recorded in the plan?"
header: "Update type"
multiSelect: true
options:
  - label: "Phase completed"
    description: "Mark steps [x] and add ✅ COMPLETED to a phase header."
  - label: "Bug found / bug round"
    description: "Add a Bug Round section with root cause and fix."
  - label: "Files added or modified"
    description: "Update the Files Created / Files Modified sections."
  - label: "Plan needs restructuring"
    description: "Add phases, reorder steps, or revise scope."
```

Follow up with specific questions (also via `AskUserQuestion`) only for the selected update types.

### Step 3: Apply updates

<update-rules>
- Mark completed steps with `[x]`
- Add ✅ COMPLETED and date to finished phase headers
- Add bug round sections: `## Bug Round N: {description}` with sub-items for root cause, fix, and regression test
- Add files to "Files Created" or "Files Modified" sections
- Update dates on phase completion headers
- Never remove existing content — append or modify status markers only

**Multi-phase plan specifics:**
- Phase completion: update the slice file status to `✅ COMPLETED — {YYYY-MM-DD}` AND mark the corresponding line in the master plan's `## Progress` section with `[x]`
- Bug rounds: append to the affected **slice file**, not the master plan
- Files created/modified: update both the slice file (phase-specific) and master plan (consolidated)
</update-rules>

**Restructuring: single-file to folder conversion**

If restructuring adds phases to a single-file plan (making it multi-phase): create the folder at `{plans_dir}/{project}/todo/{foldername}/`, extract shared context into `plan.md`, move implementation detail into `phase_1_{slug}.md`, create new `phase_N_{slug}.md` files for added phases, update the system plan pointer to `{folder}/plan.md`, and create a tracker epic if the project uses task tracking.

### Step 3b: Check for missing tracker decomposition

If the project uses task tracking (check the tracker declaration in the project's agent instructions or a `{tracker_data}/` directory) and the plan has no `## Beads` section (or the section is empty with no task IDs):

Use `AskUserQuestion`:
```
question: "This plan has no tracker tasks yet. Want to create them now?"
header: "Task tracking"
options:
  - label: "Yes, create tracker tasks (Recommended)"
    description: "Create a tracker epic and tasks matching the plan's phases."
  - label: "Not now"
    description: "Skip task tracking for now."
```

If "Yes": follow Step 8b from the Create workflow to create the tracker tasks, then update the plan's `## Beads` section.
If "Not now": continue with Step 4.

### Step 4: Sync tracker (if applicable)

If the project has task tracking initialized and the plan's `## Beads` section contains task IDs:
- **Phase completed:** Run `{tracker_cli} close {task-id}` for the completed phase's task.
- **Bug round added:** Run `{tracker_cli} note {task-id} "Bug round {N}: {short description}"` on the affected task.
- **Plan restructured (phases added/removed):** Create or close tracker tasks to match. Update the plan's `## Beads` table.

---

## Complete Workflow

### Step 1: Update status
Set `**Status:** ✅ COMPLETED — {YYYY-MM-DD}`. For multi-phase plans, also update status in each slice file and mark all progress lines with `[x]` in the master plan (see Completion Format in `references/plan-template.md`).

### Step 2: Verify progress
Confirm all Implementation Progress checkboxes are checked. For multi-phase plans, check across all slice files.

### Step 3: Verify files
Confirm Files Created/Modified sections are complete.

### Step 4: Verify success criteria
Confirm all Success Criteria checkboxes are checked.

### Step 5: Move the plan
- Single-file: move `{plans_dir}/{project}/todo/{file}.md` → `{plans_dir}/{project}/done/{file}.md`
- Folder: move `{plans_dir}/{project}/todo/{folder}/` → `{plans_dir}/{project}/done/{folder}/`

### Step 6: Update system plan
Update `{system_plan_dir}/{slug}.md` link if it references the old `todo/` path.

### Step 7: Close tracker tasks
If the plan's `## Beads` section contains task IDs:
1. Close all child tasks first: `{tracker_cli} close {task-id}` for each.
2. Close the epic (if one exists): `{tracker_cli} close {epic-id}`.
3. If the `## Beads` section is empty or missing, skip — the plan predates task tracking.

---

## Constraints

<constraints>
**Critical — MUST follow:**
- MUST structure every plan as vertical slices following the 6-step order in `references/plan-template.md`.
- MUST use folder structure for multi-phase plans: `plan.md` for shared context, `phase_N_{slug}.md` for implementation detail. Single-phase plans use a single file.
- MUST follow TDD: write tests first → confirm they fail → implement → confirm they pass. Never write implementation before tests.
- MUST sync task tracking when updating or completing plans — close tasks for completed phases, add notes for bug rounds, close epic on completion.
- Plan files are the single source of truth for TODOs. Never put TODO comments in code.

**Required:**
- Multi-phase plans include a dependency table. One plan per task — no umbrella plans.
- Slice files own implementation detail; master plan owns shared context. Tracker tasks reference these files but never duplicate code snippets.
- Record task IDs in the master plan's `## Beads` section and each slice file's `**Beads task:**` field.
- Always check if a plan already exists before creating a new one.
- System plan files at `{system_plan_dir}/` are pointers only.
- Update project documentation in `{project}/docs/` in every phase.
- Follow DRY: reference existing code, never plan duplicates.
- Follow YAGNI: every step must trace to a stated requirement.
- Include regression tests for changes to existing code. Achieve 100% coverage of modified paths.
- Include integration tests for complete app-level flows.
- Check for supported locales during exploration. When user-facing strings change, include all locales. English baseline first, native speaker role for others.
</constraints>
