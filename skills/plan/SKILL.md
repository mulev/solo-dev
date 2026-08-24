---
name: plan
description: >
  Creates, updates, and completes execution plans for software projects. Plans
  are vertical slices — each phase is an atomic deliverable with TDD tests,
  implementation, integration tests, docs, and polish. Multi-phase plans
  produce a folder (master plan + per-phase slice files), optionally decomposed
  into tracked tasks. Handles three operations: create (requirements gathering,
  codebase exploration, slice structuring, task decomposition), update (mark
  progress, add bug rounds, record files modified), complete (set status, move
  to done/). Use when the user says "plan", "create a plan", "draft a plan",
  "spec out", "break down", "roadmap", "update the plan", "mark as done", or
  discusses planning any feature, fix, refactor, migration, or technical task.
  Also triggers when the user references an existing plan file, asks about plan
  status, wants to split a plan into separate files, or says "what's the plan
  for X".
---

# Plan

## Invocation

When this skill is invoked, **immediately** output the following line before doing anything else — no preamble, no extra text:

```
[plan] Planning...
```

This is non-negotiable. It must be the very first thing the user sees.

---

## Conduct

Read `../_shared/agent-conduct.md` before the first tool call of this workflow. It carries the ownership, evidence, verification, shell, localization and scope rules every step below assumes. **Required reading** — the localization rules there are what Step 4's locale scan and the plan's Localization sections enforce, and the "no TODO comments in code" rule is why plan files are the single source of truth for deferred work.

---

## Asking the user

Every question you ask the user — clarification, confirmation, choice between options — MUST go through the host's structured-question tool. Plain-text questions are a last-resort fallback only.

**Tool resolution (try in order, first hit wins for the session):**

1. **Claude Code** — `AskUserQuestion`. Deferred tool. Load its schema once per session:
   ```
   ToolSearch(query="select:AskUserQuestion", max_results=1)
   ```
   If the schema loads, call `AskUserQuestion` directly for the rest of the session.
2. **Codex CLI (interactive TUI)** — `ask_user_question` (preferred, structured single/multi-choice) or `request_user_input` (free text). Native, no loader. If callable, use it.
3. **MCP elicitation** — if any connected MCP server exposes `elicitation/create`, use it (form mode with `requestedSchema` for structured choices).
4. **omp (Oh My Pi)** — `ask`, native, no loader. Emit it as the only tool call in its message; the runtime runs it exclusively. Cancellation raises `ToolAbortError`; headless runs have no `ask`, so use 5 there.
5. **Fallback** — clearly-formatted numbered plain-text question, then wait for the user's reply. Use only when 1–4 are unavailable (e.g. `codex exec` non-interactive runs strip native question tools).

Verify resolution every session — never assume the prior choice still applies. Batch up to 4 questions per call. Provide likely answers as options; the user picks "Other" for custom input.

**Ask in the same message.** Attach the question call to the message carrying the gate prose. A turn that ends on gate prose has asked nothing — the gate becomes a rhetorical question and the workflow proceeds unapproved.

**Treat a cancelled or timed-out question as the conservative answer.** Take the option that proceeds no further, name it, and stop. A cancellation is never permission to continue.

See `../_shared/tooling-examples.md` for the canonical call shape.

Where the rest of this skill says `AskUserQuestion`, treat it as a placeholder for whichever tool resolved above.

---

## Invoking companion skills

When this skill hands off to another (e.g., `{execute_skill}`), use the harness's skill-invocation mechanism. Configured shorthands hold the **bare skill name** with no prefix — the prefix is harness convention, never written into config.

Pick the first mechanism available in the current environment:

- **Claude Code:** call the `Skill` tool with `skill: "{execute_skill}"`. If `Skill` is not available but the skill is exposed as a user-runnable slash command, write `/{execute_skill}`.
- **Codex (interactive TUI):** invoke as `${execute_skill}`.
- **Codex (`codex exec` non-interactive):** the slash-skill invocation is not available — emit the literal sentence `Use the {execute_skill} skill.` as your next assistant message (OpenAI deterministic-workflow pattern; fuzzy phrasing drops the handoff).
- **Fallback (any harness):** read `{skills_dir}/{execute_skill}/SKILL.md` directly with `Read` and follow its workflow inline in the current conversation. Pass the handoff context (plan file path, project) as the first message of that inline workflow.

Do not write a literal `/` or `$` inside config values — the harness adds it.

---

## Configuration

This skill reads `skill.config.md` from its base directory on every invocation.

**If `skill.config.md` does not exist:**
1. Copy `skill.config.example.md` → `skill.config.md`.
2. Use `AskUserQuestion` offering interactive or manual setup.
3. **Interactive flow:**
   - Plans directory (default: `project_plans`)
   - System plan mirror (default: empty/disabled; set it only if the harness has a plan-scanning directory — Claude Code uses `~/.claude/plans`)
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
| `{system_plan_dir}` | System Plan Mirror → system_plan_dir | (empty — mirroring disabled) |
| `{tracker_cli}` | Issue Tracker → cli_command | `bd` |
| `{tracker_data}` | Issue Tracker → data_dir | `.beads` |
| `{formatter}` | Formatter → command | (from project instructions) |
| `{test_command}` | Test Command → command | (from project instructions) |
| `{execute_skill}` | Companion Skills → execute_skill | `execute` |
| `{skills_dir}` | Skills Directory → skills_dir | `~/.agents/skills` |
| `{max_file_loc}` | Architecture → max_file_loc | `300` |

**Tracker state:** Read `Issue Tracker → enabled` from config. If `true`, run all `{tracker_cli}` commands in Step 8, Update/Sync, and Complete workflows. If `false`, skip all tracker commands.

---

## Route to the right operation

| User intent | Operation | Reference |
|-------------|-----------|-----------|
| New feature, fix, refactor, or tech task | **Create** | `references/plan-templates.md` |
| Progress update, phase completion, bug round | **Update** | `references/update-and-complete.md` + `references/bug-and-completion.md` |
| Plan fully done, move to done/ | **Complete** | `references/update-and-complete.md` + `references/bug-and-completion.md` |

**Path convention:** every file path in this skill and in the files it points at is written **relative to this skill's own directory** — the one holding `SKILL.md`. So `references/x.md` means `<this skill>/references/x.md` even when you read it from inside `references/`, and `../_shared/x.md` means the `_shared` sibling skill. Resolve from the skill root, never from the file you happen to be reading.

Read `references/conventions.md` for file naming, directory structure, type codes, and project detection.
Read `references/plan-templates.md` for plan templates (single-phase file and multi-phase folder) with all mandatory sections.
Read `references/task-decomposition.md` for tracker task creation templates (epic + per-phase + single-phase).
Read `references/bug-and-completion.md` for bug round and completion status formatting.
Read `references/update-and-complete.md` for the Update and Complete workflows.
Read `../_shared/architecture-principles.md` for SRP/DRY/KISS/YAGNI rules, hard LOC limits, component decomposition format, anti-patterns to reject, and the architecture self-review checklist. **Required reading before Step 5.**
Read `../_shared/validators.md` for the repo's validator stages — a plan's Verification sections must name the repo's own `phase-exit` stage, not invented commands. **Required reading before Step 5.**

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

**Investigation file shortcut:** If the user provided a `.md` file whose path contains `/investigations/` OR whose first line matches `# {Project} Investigation:` OR whose front matter declares `**Status:** ROOT CAUSE CONFIRMED`, treat it as a pre-loaded investigation outcome from the `investigate` skill.

When detected:
- Read the file. The "Root Cause" + "Approved Fix" + "What changes" + "Side effects checked" sections together are the **already-confirmed requirements** — do not re-investigate, do not ask the user to re-confirm root cause, do not propose alternative fixes.
- Skip bug-clarification questions in this step. Move straight to scope/sizing questions if needed.
- **NEVER overwrite the investigation file.** It is reference evidence, not a task scratchpad. The plan file is written at the standard `{plans_dir}/{project}/todo/` location regardless of phase count.
- In the resulting plan, add a `## Background` section near the top that links to the investigation file with its absolute path. Quote the one-sentence root-cause summary and one-sentence fix summary; do not duplicate the full analysis.

**Task file shortcut (non-investigation):** If the user provided a `.md` file that is NOT an investigation file (per detection above), read it and treat its content as the full requirements. Store the original content to append as `## Original Task` at the end of the finished plan. When writing the plan (Step 5), single-phase plans overwrite the task file in place; multi-phase plans create a folder at the standard `{plans_dir}/` location and append the original task content to the master plan.

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
- **Module boundaries** — how the codebase is decomposed (by feature/domain, not by horizontal layer). Identify the natural module home for each new piece of code. See `../_shared/architecture-principles.md` (Modular monolith).
- **Reusable helpers** — grep for existing utilities, services, or extensions that the new code could call. DRY is enforced at this step — duplicates planned without justification will be rejected during self-review.
- **File-size hot spots** — read the largest files in the area you'll touch. If any approaches `{max_file_loc}` LOC, plan to split rather than grow.
- Supported locales: scan for `l10n/`, `locales/`, `i18n/`, `*.arb`, `*.strings`, `Localizable.strings`, `*.xcstrings`, `*.po`/`*.pot`, `*.xliff`/`*.xlf`, `*.resx`, `*.properties`, or per-locale `*.json`/`*.yml`. If found, list every locale — all must be updated when user-facing content changes.

Use available MCP tools when the plan involves external libraries or frameworks:
- **Context7**: Query documentation for APIs, classes, or patterns you're not certain about. Skip for pure internal refactoring or config-only changes.
- **Other MCP servers**: Use web search or fetching to resolve version-specific behavior, check changelogs, or verify compatibility.

This exploration informs the Implementation, Testing, and Localization sections.

### Step 5: Structure & decompose

Build the plan in three substeps. Do not proceed to Step 6 until every substep passes its gate.

<audience>
Write every plan as if handed to a junior engineer with zero institutional knowledge. Every step self-contained: name the exact files to open, point to relevant docs/patterns, include a "done when" criterion, add code snippets for non-trivial logic, reference test command + expected output for testing steps.
</audience>

#### 5.1 Draft the slice structure

Outline phases (vertical slices), what each delivers, dependencies, cross-cutting concerns. Calibrate phase count to scope — see Plan Sizing in `references/plan-templates.md`. Each phase follows 6-step order: Exploration → Tests (TDD, written to fail) → Implementation → Integration tests → Documentation → Polish.

Pick the output shape from `references/plan-templates.md`. Decide it here; the files themselves are written in Step 7b, after the user approves:
- **1 phase:** single-phase template → single `.md` file
- **2+ phases:** multi-phase templates → folder with `plan.md` + `phase_N_{slug}.md` per slice

Steps 5 and 6 produce the outline in conversation, not on disk: phases, per-phase objective and steps, components, files, tests, docs, dependencies, success criteria. Nothing is written until approval.

<plan-output-rules>
These rules govern the write in Step 7b — where each file goes and what must never be overwritten.

**Mirror writes are conditional.** Every "create system plan file" instruction below applies only when `{system_plan_dir}` is non-empty in config. When it is empty, mirroring is off: skip the mirror file, skip its back-link, and say nothing about it. The plan file under `{plans_dir}` is the source of truth either way — a missing mirror is a configuration choice, never a gap to report.

**Single-phase plans:**
- **If an investigation file was detected in Step 2:** do NOT overwrite the investigation file. Write the plan to `{plans_dir}/{project}/todo/{filename}.md` per `references/conventions.md`. Add a `## Background` section linking to the investigation file (absolute path). Create system plan file at `{system_plan_dir}/{slug}.md`. Link both ways.
- **Else if a task file was detected in Step 2:** overwrite that file. Append `## Original Task` at end with original content verbatim. Create system plan file at `{system_plan_dir}/{slug}.md` pointing to task file path.
- **Otherwise:** write to `{plans_dir}/{project}/todo/{filename}.md` per `references/conventions.md`. Create system plan file at `{system_plan_dir}/{slug}.md`. Link both ways.

**Multi-phase plans:**
- Create folder `{plans_dir}/{project}/todo/{foldername}/` per `references/conventions.md`.
- `plan.md` (master) — shared context, dependency table, progress dashboard. No code snippets.
- `phase_{N}_{slug}.md` per phase — self-contained implementation detail.
- Create system plan file at `{system_plan_dir}/{slug}.md` pointing to `{folder}/plan.md`. Link from master back.
- **If an investigation file was detected in Step 2:** do NOT overwrite or move the investigation file. Add a `## Background` section to the master plan linking to it (absolute path).
- **Else if a task file was detected in Step 2:** append its content as `## Original Task` at end of master.
</plan-output-rules>

#### 5.2 Re-slice oversized phases

A phase must be re-sliced when **any** trigger fires:

- More than **8 implementation steps**
- Touches more than **5 unrelated files**
- Grows any single file past `{max_file_loc}` LOC
- Spans more than **one feature/domain module** without explicit cross-cutting justification
- Introduces a god object, horizontal-layer folder, or catch-all file (see anti-patterns in `../_shared/architecture-principles.md`)

**How to re-slice:** identify natural boundaries (feature/domain module, platform, API vs. consumer) → split into thinner shippable phases → update dependency table → renumber and fix cross-references.

**Common split patterns:** by feature module (preferred), by platform (Dart/Android/iOS/Web), API + consumers, core + periphery (docs/example/integration tests).

**Gate:** every phase within all thresholds before proceeding to 5.3.

#### 5.3 Component decomposition

For every phase, list atomic components before drafting code-level steps. Capture per component:
- **Name** — module/file path (must satisfy Meaningfulness Test #1)
- **Responsibility** — single sentence, no "and"
- **Public API** — exported symbols
- **Callers** — ≥2 unrelated callers, OR `single-caller + independent test` with the test file named
- **Foreign modules touched** — feature/domain modules the behavior reaches (coupling enumeration, not import lines)
- **Projected LOC** — under `{max_file_loc}` (or note the waiver and the alternative considered)
- **Test approach** — unit-testable in isolation

Render as **Component Decomposition** table in the plan (or each slice file). See `references/plan-templates.md`.

**Reject and split when:** responsibility needs "and"; LOC exceeds `{max_file_loc}` without `**LOC waiver:**`; coupling enumeration touches >5 distinct foreign feature/domain modules without a `**coupling waiver:**`; not unit-testable without globals/statics/singleton resets; parallel hierarchies (always-changed-together — fold into one); name is `*Manager`/`*Helper`/`*Util` without concrete domain prefix.

**Reject the split itself when:** the proposed new module fails the Meaningfulness Test (independent name, plural callers or independent test, real coupling reduction, survives inline-back). Re-export shims, barrel indexes, dependency aggregators, and single-caller satellites are anti-patterns — fold them back and take a waiver instead.

**Gate:** every component passes before proceeding to Step 6.

### Step 6: Self-review and refine

Before presenting the plan to the user, re-read the full draft and challenge it against this checklist. Fix every gap found — do not skip items as "probably fine".

<self-review-checklist>
**Structure**
- [ ] Every phase has all 6 steps (exploration → tests → impl → integration → docs → polish)?
- [ ] Every phase has ≤8 implementation steps and touches ≤5 unrelated files? If not, re-slice (Step 5.2).
- [ ] Dependency table present and acyclic?
- [ ] Folder structure correct for phase count (single file vs. folder)?
- [ ] Every phase's Verification section names `./validate run phase-exit` (and the repo has a `validators.conf`, or the plan schedules writing one)?
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

**Architecture** — run the full Architecture self-review checklist in `../_shared/architecture-principles.md`. Every item must pass. If exploration (Step 4) found pre-existing violations in files this plan will touch, schedule their fix within the plan — do not defer or exempt them. "It was already there" is never grounds to leave a violation unaddressed.

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

**If "Looks good":** proceed to Step 7b to write the files, then Step 8.

**If any other option (or Other):** Collect the user's feedback, apply changes to the plan, re-run Step 6 self-review, and repeat Step 7. This loop continues until the user selects "Looks good."

**Important:** This question must be asked after every fully completed cycle of working on the plan — including after revisions. Never skip the approval step.

### Step 7b: Write the plan files

Only now do files get created, following `<plan-output-rules>` and the templates in `references/plan-templates.md`.

**Single-phase plans:** write the file yourself. It is one file and you already hold the outline.

**Multi-phase plans:** write `plan.md` yourself — objective, requirements, dependency table, `## Progress` dashboard, success criteria, `## Background`/`## Original Task` where they apply, and the system mirror file. The slice files are delegated **one subagent per slice, all dispatched in parallel in a single batch**, when project instructions permit it. Parallel is safe and is the point here: each writes one independent file, the content is already approved, and none of them touches git, the tracker, or source. Sequential slice writing wastes wall-clock for no gain.

When delegating slices:
- Give each subagent exactly one slice path plus that phase's approved outline verbatim: objective, steps, component decomposition rows, files, tests, docs, dependencies, success criteria, and the `**Parent plan:**` link to write.
- Name the instruction files it must read first, by absolute path, and the slice template location.
- Nothing else is delegated: no tracker commands, no source edits, no master-plan edits. A subagent cannot ask the user — it escalates to you and stops.
- When the slices come back, verify each one before Step 8: correct path and file name, H1 `# Phase {N}: {Name}`, `**Status:**`, `**Parent plan:**`, `## Prerequisites`, `## Implementation Progress` checkboxes, a Component Decomposition table, and every mandatory per-phase deliverable the project requires (localization, docs, example app, integration tests). Fix or send back anything missing — you own the result.

Either way, re-run the Structure items of the Step 6 checklist against the files on disk once they exist, then proceed to Step 8.

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

Use the Task Decomposition Template from `references/task-decomposition.md` to create tasks.

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

**Close out the source bead.** A bead that motivated this plan is still marked `needs-plan`, so `{tracker_cli} ready` keeps hiding it. Resolve its ID from the investigation file's `**Beads task:**` field, or from the ID the user invoked this skill with, then flip it:

```sh
{tracker_cli} update <id> --status open --notes "Plan: {absolute path}/plan.md
<existing notes, preserved>"
```

For a multi-phase plan, flip the source bead only when it *is* the epic; otherwise link it with `{tracker_cli} dep add` and flip it anyway. Never leave a bead marked once its plan file exists — status and plan file always move together.

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

If "Start executing now": invoke the `{execute_skill}` skill (see *Invoking companion skills*) with the plan file path. For multi-phase plans, pass the master plan path (`{folder}/plan.md`) — the execute skill resolves to the first ready phase. For single-phase plans, pass the plan file path directly.

If "Not now": End the Create workflow.

**If `{execute_skill}` is not configured** (empty): End the Create workflow without offering handoff.

---

## Update & Complete Workflows

Full step-by-step workflows for **Update** (locate plan → determine what changed → apply updates → check missing tracker decomposition → sync tracker) and **Complete** (status → verify progress/files/success criteria → move to done/ → update system plan → close tracker tasks) are in `references/update-and-complete.md`. Read it when invoking either operation.

---

## Constraints

<constraints>
**Critical — MUST follow:**
1. MUST follow TDD: write tests first → confirm they fail → implement → confirm they pass. Never write implementation before tests.
2. MUST structure every plan as vertical slices, 6-step order. Multi-phase ⇒ folder (`plan.md` + `phase_N_{slug}.md`); single-phase ⇒ single file.
3. MUST produce a Component Decomposition table per phase. Every component: single-sentence responsibility (no "and"), ≤ `{max_file_loc}` LOC (or `**LOC waiver:**`), unit-testable in isolation.
4. MUST sync task tracking on update/complete — close phase tasks, note bug rounds, close epic on completion.
5. Plan files are the single source of truth for TODOs. Never put TODO comments in code.

Full architecture rules (SRP/DRY/KISS/YAGNI, modular monolith, anti-patterns, testability) → `../_shared/architecture-principles.md`.
Full coverage rules (regression, integration, locales, docs) → `references/plan-templates.md` (Testing & Localization sections).
</constraints>
