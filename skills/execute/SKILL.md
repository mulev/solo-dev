---
name: execute
description: >
  Executes work from tracked tasks or plan files. Finds ready-to-work tasks
  via the configured issue tracker (priority and dependency aware), claims
  them, implements phases (write code, run tests, update plan), handles
  failures via bug rounds, and closes tasks on completion. Use when the user
  says "execute", "implement", "build", "ship", "code this up", "work on the
  next task", "pick up", "start coding", "run the plan", "resume", "continue
  the implementation", "what's next", or passes a task ID or .md plan file
  path. Each invocation executes one phase and then offers the next unblocked
  task. A bare epic ID is the exception: ask whether to dispatch the whole epic
  or run a single phase. Accepts no argument (pick from ready tasks), a task ID,
  or a .md plan file path.
---

# Execute

## Invocation

When this skill is invoked, **immediately** output the following line before doing anything else — no preamble, no extra text:

```
[exec] Executing...
```

This is non-negotiable. It must be the very first thing the user sees.

---

## Conduct

Read `../_shared/agent-conduct.md` before the first tool call of this workflow. It carries the ownership, evidence, verification, shell, localization and scope rules every step below assumes. **Required reading** — the gates in this skill are checkable only because of the "a check that did not run is a failed check" and "never fake completion" rules stated there.

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

When this skill hands off to another (e.g., `{plan_skill}`, `{commit_processor}`), use the harness's skill-invocation mechanism. Configured shorthands hold the **bare skill name** with no prefix — the prefix is harness convention, never written into config.

Pick the first mechanism available in the current environment:

- **Claude Code:** call the `Skill` tool with `skill: "{plan_skill}"`. If `Skill` is not available but the skill is exposed as a user-runnable slash command, write `/{plan_skill}`.
- **Codex (interactive TUI):** invoke as `${plan_skill}`.
- **Codex (`codex exec` non-interactive):** the slash-skill invocation is not available — emit the literal sentence `Use the {plan_skill} skill.` as your next assistant message (OpenAI deterministic-workflow pattern; fuzzy phrasing drops the handoff).
- **Fallback (any harness):** read `{skills_dir}/{plan_skill}/SKILL.md` directly with `Read` and follow its workflow inline in the current conversation. Pass the handoff context (task description, plan path, scope) as the first message of that inline workflow.

Do not write a literal `/` or `$` inside config values — the harness adds it.

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
| `{plan_skill}` | Companion Skills → plan_skill | `plan` |
| `{code_simplifier}` | Companion Agents → code_simplifier | (from `skill.config.example.md`) |
| `{code_reviewer}` | Companion Agents → code_reviewer | (from `skill.config.example.md`) |
| `{commit_processor}` | Post-Processing → commit_message_processor | `humanizer` |
| `{skills_dir}` | Skills Directory → skills_dir | `~/.agents/skills` |
| `{max_file_loc}` | Architecture → max_file_loc | `300` |

**Tracker state:** Read `Issue Tracker → enabled` from config. If `true`, run all `{tracker_cli}` commands in Steps 1 and 3. If `false`, skip all tracker commands.

---

**Path convention:** every file path in this skill and in the files it points at is written **relative to this skill's own directory** — the one holding `SKILL.md`. So `references/x.md` means `<this skill>/references/x.md` even when you read it from inside `references/`, and `../_shared/x.md` means the `_shared` sibling skill. Resolve from the skill root, never from the file you happen to be reading.

Read `references/tracker-templates.md` for all tracker interaction templates, AskUserQuestion formats, and `{tracker_cli}` command sequences.
Read `../_shared/architecture-principles.md` for SRP/DRY/KISS/YAGNI rules, the `{max_file_loc}` smell threshold, the Meaningfulness Test that gates every split, the architecture verification gate, the per-file banner format, and the anti-patterns to refactor on sight (re-export shim, barrel index, single-caller satellite, metric-laundering split). **Required reading before Step 2.**
Read `references/update-format.md` for the `## Architecture Gate Results` artifact template and the bug/refactor round formats. **Required reading before Step 2.3.**

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

When given a master plan path, resolve the working file using `references/tracker-templates.md` (Resolve the Working File).
</plan-file-resolution>

<epic-dispatch-mode>
When the resolved tracker task is an **epic** (it has child tasks), the scope is a question, never an inference. Ask it with the tool from *Asking the user*, batched with Step 1's branch question when that one fires too. This is the one fork the harness's "default to informed action" rule must not decide for you: a bare epic ID carries no phrasing either way, so a guess costs either five phases nobody ran or six workers nobody asked for.

```yaml
question: "{epic-id} is an epic with {N} child tasks ({M} ready). Execute the whole epic, or one phase?"
header: "Scope"
options:
  - label: "Dispatch the whole epic (Recommended)"
    description: "One worker per child bead, sequential, following the steps below. Keeps the epic out of this session's context."
  - label: "One phase only"
    description: "Execute the first ready child inline, then offer to continue."
```

Two answers arrive without asking: the user named a child bead ID, or asked for exactly one phase in the invocation ("just phase 3"). Do not re-ask those. Where project instructions forbid delegation, say so and execute the children here, one phase per invocation, as usual.

On "Dispatch the whole epic", do not implement it inline — dispatch one child at a time:

**"Dispatch the whole epic" is the last answer you need until the close-out.** It is not permission to start; it is the user leaving. From here to Step 5 the only thing that may interrupt them is a worker escalation the brief genuinely cannot answer (item 8) — a real fork in the work, never a confirmation, never a checkpoint, never a "shall I continue". Anything a repo convention, this plan, or a reversible default can settle, settle yourself and say so in the close-out. Why: the user chose dispatch to stop being in the loop, so a question that only confirms what dispatch already authorised charges them the full round trip that choice was meant to buy. Committing verified work on the epic's own feature branch is the standard case — it is decided in item 3 and never re-asked.

1. **Baseline.** From the repo root, run `./validate run phase-exit` before dispatching anything (`../_shared/validators.md`). A red baseline is not a worker's problem — fix or record it first, and note the result in the master plan's `## Dispatch Log`.
2. **Order the work.** If the tracker can compute waves, use it (`{tracker_cli} swarm validate {epic-id}` in beads: ready fronts, max parallelism, cycles). Otherwise list the epic's children and their `--deps`. Fix a reported cycle or orphan before dispatching.
3. **Decide once, for the whole epic:** the branch (Step 1 rules — never `main`), whether workers may commit, and — where the answer is "no" — that the main session commits each phase itself as it verifies it. These go into every brief; workers never re-decide them, and neither do you. A commit permission decided here is decided for every phase: never re-open it with the user mid-epic.
4. **Generate the brief, never hand-write it:** `scripts/brief.sh {bead-id} {slice-path} {branch} {repo-root}` prints the invariant half — instruction files, branch, commit permission, the verbatim `phase-exit` stage, the iterate-until-green rule, the report fields. Pass `TRACKER_CLI={tracker_cli}` (or `TRACKER_CLI=` when `tracker_active = false`) and `NO_COMMIT=1` when item 3 withheld commit permission. Append only `# Target`, `# Change`, `# Acceptance` for that phase. **Run it again for every bead**; never copy a previous brief and edit it, because a copy carries the previous bead's stage and any fix to the generator never reaches it. The brief deliberately does not contain the contract token — the worker looks it up in `<delegated-mode>`, which is what makes the echo mean something.
5. **Dispatch one worker per ready bead, one at a time** unless the user explicitly asked for parallel work.
6. **Verify before trusting.** When a worker returns: `cd {repo root} && ./validate verify phase-exit {slice-path}` — exit 0 is required. It reads the ledger's provenance header, so a hand-written or pasted ledger fails on its stamps, and a ledger older than the worker's own last edit fails as stale. `DRIFT` lines are expected when the worker's phase added a validator row. The report's `contract:` token must match the `Contract version:` line in `<delegated-mode>`; a wrong or missing token means the worker never opened the contract, so treat its other claims as unverified. Then check the slice has `## Architecture Gate Results` with **Overall: PASS** dated in this execution, checkboxes are `[x]`, `**Status:**` is `✅ COMPLETED`, and the bead is closed. Any failure → send the worker back; do not close the bead, do not dispatch the next one.
7. **Log every return** in the master plan's `## Dispatch Log`, one row per bead. `Dispatched` and `Returned` are **UTC timestamps to the second** (`date -u +%Y-%m-%dT%H:%M:%SZ`), never bare dates: the row's only job is to be lined up against that bead's ledger header (`started=` / `finished=` / `finished_epoch=`), and a date cannot tell you whether a worker's ledger was earned before or after its own dispatch. Copy this shape:

   | Bead | Worker | Dispatched | Returned | Commits | Gate | Ledger | Bead state |
   |------|--------|------------|----------|---------|------|--------|------------|
   | `{bead-id}` | `{worker name}` | `2026-08-19T19:41:27Z` | `2026-08-19T20:14:03Z` | `a1b2c3d` | Overall: PASS | `verify` exit 0 | closed |

   That table is the epic's state on disk — after a compaction it is how you know where you are.
8. **Answer escalations.** A worker cannot ask the user. Answer yourself when the brief already covers the point; otherwise use `AskUserQuestion`, then reply to the worker so it resumes with full history.
9. **Route discovered work.** A bead for a defect this epic introduced is `parent-child` to the epic — it blocks the epic's close. Anything else found mid-epic is `discovered-from` **and** listed in the master plan's Beads table. The close-out message tables every bead filed, with its routing.
10. **Never delegated, keep here:** master plan and Beads table updates, locale updates, the `finalize` stage, pushes, tracker push, and Step 5.
11. **Close out.** After the last bead closes: Step 5 for the whole execution, then confirm the epic itself is closed (`{tracker_cli} show {epic-id}` must not still report it open with all children done), then the PR and code review per project instructions.

**After any compaction inside an epic:** read the `## Dispatch Log` and run `{tracker_cli} show {epic-id}` before dispatching or finalizing. Never resume epic state from memory.
</epic-dispatch-mode>

<delegated-mode>
Contract version: **DM-2026-08-v1** — echo this token in your report as proof you read this block.

You are in delegated mode when you were spawned to work a single bead. The whole skill still applies, with these overrides:

- **Step 1 branch setup:** the branch is given. Verify you are on it, never switch, never touch `main`. Claim with `{tracker_cli} -C {repo root} update {id} --claim` — your `cd` does not persist between shell calls, so pass the repo root on every tracker command.
- **Every question:** you cannot ask the user. Send it to the parent session (`hub` send to `Main` in omp, `SendMessage` in Claude Code) with what you need and why, then stop that thread. This replaces the Step 3 continuation question, the Step 4 three-round escalation, and any Step 0 diagnostic that would have asked. Never guess, never narrow the bead to dodge the question.
- **Step 2.2 stands:** run `{code_simplifier}` on your changed files, re-run the changed test files, then compute the gate — the gate is computed after simplification. The 2.2 fallback applies only if the spawn itself fails.
- **Validation is yours, and it is not a judgement call:** when the slice's work is done, run `cd {repo root} && ./validate run phase-exit`. Any FAIL opens a Bug Round or Refactoring Round (Step 4), you fix it, and you re-run the **whole** stage. Report only when every row is PASS; after three failed rounds, escalate with the failing ledger and stop. Exit 2 means the config is wrong, not the code — do not loop on it. Never defer a check the stage contains, including compiles and native suites. Only `user`-stage rows are handed over, and `./validate run` records those itself.
- **Run the stage last, and paste the header:** the ledger carries a provenance header, and `verify` fails a ledger that predates your own last source edit. So finish editing, then run the stage — a fix applied after the run invalidates it, which is the point. Copy the header with the rows; a ledger without it is unverifiable.
- **Step 5 is the parent's:** the `finalize` stage, locales, docs beyond your slice, and `{code_reviewer}` belong to the parent. Name each in your report's `deferred` field with its owner.
- **Commits:** only if the brief grants them, staging explicit paths — never `git add -A`, never `git commit -a`. Never push, and never run the tracker's remote-sync command (in beads, `{tracker_cli} dolt push`) — publishing state is the parent's.
- **Files you own:** your bead's source files and your own slice file. Master plan, system mirror and other slices belong to the parent.
- **Locales:** never edit them. List the added or changed keys in your report and stop.

Finish with the return contract: at most 15 lines — contract token, files created/modified, the ledger lines plus whether `verify` exited 0, gate Overall line, bead status and commits, deferred checks with owners, locale keys, open questions, blockers. No diffs, no logs.
</delegated-mode>

## Workflow

### Step 0: Route input and resolve working file

Classify the argument, run the matching entry routine in `references/tracker-templates.md`, and end this step with: a working file (read), a task ID (or `tracker_active = false`), and any context file for multi-phase plans.

| Input | Detection | Routine in `references/tracker-templates.md` |
|-------|-----------|----------------------------------------------|
| No argument | Empty args | Task Selection (no argument) |
| Task ID | Alphanumeric with optional hyphens, no `/` or `.md` | Direct Tracker Execution (task ID) |
| `.md` file path | Contains `/` or ends with `.md` | Plan File Execution |
| Anything else | Doesn't match above | Error: "This skill accepts: no argument (pick from ready tasks), a task ID, or a .md plan file path." |

**Common rules across all three routes** (full templates in `references/tracker-templates.md`):
- Detect project the same way the planning skill does (explicit mention > IDE files > conversation context > ask).
- Check tracker availability before any `{tracker_cli}` command. If tracker isn't available, set `tracker_active = false` and continue plan-file-only.
- Plan file is mandatory. If a task has no linked plan, offer to create one via `{plan_skill}` (Orphan Task template). If the linked file is missing, offer to recreate it (Missing Plan File template).
- For multi-phase tasks, the **slice file is the working file**; the master plan is context.
- If a task is already `in_progress`, skip claiming and resume from the first unchecked step (Resume template).
- If the resolved ID is an **epic** with child tasks, stop here and follow `<epic-dispatch-mode>`, which asks whether to dispatch the epic or run one phase. Never resolve that fork by inference.

---

### Step 1: Set up branch and claim task

Before writing any code, ensure a clean git branch and claim the tracker task.

**Branch setup:**

1. Check the current branch of the project repo.
2. **If on `main`**: pull latest, create a new branch named after the plan (e.g., `feat/epub-table-of-contents` from `project_feat_epub_table_of_contents.md`).
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

Read the working file (slice file for multi-phase, plan file for single-phase) and execute its unchecked tasks in order. Single-phase plans group tasks under `#### Step N.M` sub-headers (Exploration → Tests → Implementation → Integration Tests → Documentation → Polish). Multi-phase slice files use a flat checklist under `## Implementation Progress`.

For each implementation step, run sub-steps 2.1 → 2.4 in order. Sub-step 2.3 produces a **required visible artifact** — no artifact, no phase exit.

#### Step 2.1: TDD cycle
Write the test → run to confirm it fails → implement the minimum code to pass → run to confirm it passes. Run only the changed test file(s), not the full suite. Never write implementation before the test. Cover regressions on changed code and integration flows on added features.

#### Step 2.2: Simplify
Launch `{code_simplifier}` on the newly written or modified source files. Re-run the changed test file(s) after.

**Companion-skill fallback:** If `{code_simplifier}` is empty in config, or the spawn itself fails — no subagent mechanism in this harness, unknown agent name, spawn error — do **not** silently skip. A delegation-limiting rule in project or user instructions is **not** a trigger: a skill-prescribed agent is covered by the invocation of this skill, so never infer the block from policy text. On a real failure:
1. Apply the simplification checklist locally on the changed files: remove dead code, inline single-use helpers, collapse redundant branches, prefer existing utilities over new ones.
2. Re-run the changed test file(s).
3. Record the skip + local fallback in Step 2.3's Companion-skill status line: ``{code_simplifier}: skipped — {reason}``.

#### Step 2.3: Architecture Gate — REQUIRED ARTIFACT
Run the architecture verification gate from `../_shared/architecture-principles.md` on every file in `git diff --name-only` for this phase. The simplifier is not a substitute.

For each changed file:
1. Run the helper script: `python3 {skills_dir}/execute/scripts/run_arch_gate.py <file> --max-loc {max_file_loc}`. Capture the `[arch-gate] file=...` banner line. If the script does not cover the language, run the LOC count manually and proceed.
2. Apply the manual checks (SRP, DRY, testability) from `../_shared/architecture-principles.md` and record one-sentence reasoning per file.

Then write the `## Architecture Gate Results` block into the **working file** using the template in `references/update-format.md`. The block must include the banner per file, the results table, the companion-skill status, an **Overall:** line, and the `### Validation` ledger from Step 2.3b.

**Fail-closed contract:**
- If any row is FAIL → open a Refactoring Round (Step 4) and do not proceed.
- If the block is missing or any row's status is unrecorded → not a valid completion. Stop and write the block.
- The architecture gate is **the** phase-exit checkpoint — green tests alone are insufficient.
- **No pre-existing-condition exemption.** A violation that existed before this phase still blocks phase exit. "It was already there" is never an acceptable reason to leave a FAIL row. Fix it in a Refactoring Round.

#### Step 2.3b: Validation stage — REQUIRED ARTIFACT
Run the repo's `phase-exit` stage (`../_shared/validators.md`) **from the repo root** — `./validate` exists only there, and the config's commands `cd` from there:

```
cd {repo root} && ./validate run phase-exit
```

Paste its output verbatim — **provenance header included** — into the working file as a fenced block under `### Validation`, inside this phase's `## Architecture Gate Results` block, then confirm with `cd {repo root} && ./validate verify phase-exit {working file}` — exit 0 is required. The header is what makes the ledger checkable: `verify` requires every row stamped inside that run's window and the run to be no older than the code it claims, so a ledger copied from an earlier phase, written by hand, or earned before your last edit all fail. Drop the header and you have an unverifiable ledger.

If your shell tool's timeout is shorter than the stage takes (native suites and builds routinely run minutes), launch it as a supervised process instead — `hub` `start` plus `wait` in omp — so a timeout cannot kill the run and leave you without a ledger.

**Fail-closed contract:**
- **Exit 1** — a row FAILed, or verification found a row missing, mis-stamped, or older than the code → Bug Round or Refactoring Round (Step 4), fix, then re-run the **whole** stage. Never re-run a single row and call the stage green.
- **Exit 2** — misconfigured (no `validators.conf`, or a stage this repo does not define). **Do not loop**: no round will fix a config error, and the config is not yours to write (`../_shared/validators.md`). Write `validators: none — {reason}` into the ledger block, name it in your report's `deferred` field owned by `human`, and continue with the slice. Never edit the config and never stop a thread over it.
- The stage is coarse on purpose: a change in one language routinely breaks another. "This phase only touched Dart" is not a reason to skip a row, and neither is cost — a row too slow for every phase belongs in `finalize`, decided in `validators.conf`, not skipped ad hoc.
- `user`-stage rows are recorded `PENDING-USER` by the runner and handed to the user in the close-out. Nothing else may be deferred.
- If **a validator row was added since an earlier phase ran**, it runs here for the first time. Earlier phases' ledgers stay exactly as they are: `verify` reports the new row as `DRIFT` against them, which is not a failure and never a reason to re-run their stage (`../_shared/validators.md` — "Two rules that keep verification from becoming busy work").

#### Step 2.4: Format
Run `{formatter}` (skip if empty in config).

**Phase exit gate** (all four required to enter Step 3):
1. Step 2.1's changed-test-file run is green.
2. `## Architecture Gate Results` block exists in the working file with **Overall: PASS** dated within this execution.
3. `cd {repo root} && ./validate verify phase-exit {working file}` exits 0.
4. Step 2.4 ran clean.

Any failure → Step 4 (Bug Round for test failures, Refactoring Round for gate failures).

### Step 3: Update plan, close task, and offer continuation

**Step 3.0 — Fail-closed precondition.** Before doing anything else in Step 3, verify that the working file (slice file for multi-phase, plan file for single-phase) contains a `## Architecture Gate Results` block with **Overall: PASS** dated within this execution **and** that `cd {repo root} && ./validate verify phase-exit {working file}` exits 0. If the block is missing, any row is FAIL, or verification fails, **STOP** — return to Step 2.3 and produce the artifact. Do not commit, do not close the tracker task, do not flip the status line. This precondition holds even if all tests are green.

After tests pass for the phase **and** the gate artifact exists:

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

**When to invoke the planning skill**: If during execution you discover the plan needs a new phase, significant restructuring, or additional analysis — invoke the `{plan_skill}` skill (see *Invoking companion skills*) in Update mode. Do NOT invoke it for minor adjustments like adding a single sub-task or fixing a typo in the plan.

### Step 4: Handle failure (Bug Round or Refactoring Round)

Two failure types are tracked in the working file:
- **Bug Round** — a test failed or implementation hit an unexpected runtime problem.
- **Refactoring Round** — the architecture verification gate (`../_shared/architecture-principles.md`) failed: a file is over `{max_file_loc}` and no waiver applies, has more than one responsibility, duplicates an existing helper, is a re-export shim or single-caller satellite, touches >5 foreign feature modules, or is hard to test.

**Bug Round procedure:**
1. Add a Bug Round section to the **working file** — the slice file for multi-phase plans, the plan file for single-phase plans (see `references/update-format.md`).
2. Analyze the failure — identify root cause.
3. Implement the fix.
4. Add a regression test for the bug.
5. Re-run the affected test file(s) — not the full suite.
6. If fixed → mark the bug round as resolved, return to Step 3.

**Refactoring Round procedure:**
1. Add a Refactoring Round section to the working file (see `references/update-format.md` — Adding a Refactoring Round).
2. Name the violation (e.g., "`reader_service.dart` is 412 LOC; pagination + caching are two responsibilities").
3. Plan the split: which new module to extract, what its single responsibility is, what its public API will be.
4. Perform the extraction. Move tests with the code they cover.
5. Re-run the changed test file(s). All must pass.
6. Re-run the architecture gate on every file touched by the refactor.
7. If clean → mark the refactoring round as resolved, return to Step 2 (Format substep), then Step 3.

**If still failing** (either type) → add another round. After 3 consecutive failed rounds of the same type, stop and use `AskUserQuestion`:
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

After the phase is complete (or the user chose "Done for now" after multiple phases):

<finalization-rules>
Step 5 has two tiers. **Hard gates fail closed** — they block finalization unconditionally. **Quality items** can be skipped only when explicit project policy overrides them; every skip must be logged in the working file as `{item}: skipped — {policy reference}`.

**A gate must add information.** If a gate's outcome is already established by an artifact on this same tree, cite that artifact and pass the gate — re-running a check to make its timestamp look fresher is prohibited busy work, not diligence. The litmus before any repeat run: *would this run's outcome be knowable from something already on disk?* (`../_shared/validators.md` — "Two rules that keep verification from becoming busy work".)

**Hard gates (fail-closed — do these first, in order):**
1. **Architecture sweep**: re-run the architecture gate from `../_shared/architecture-principles.md` against every file in `git diff --name-only` for the entire execution, not just the last phase. Update the most recent `## Architecture Gate Results` block (or append a final-sweep block) with the consolidated results. Every row must be PASS. If any row is FAIL → Refactoring Round, then re-run this step.
2. **Format**: run `{formatter}` (skip if empty in config).
3. **Finalize stage**: from the repo root, run `./validate run finalize` (`../_shared/validators.md`) and append its output — provenance header included — to the final-sweep block. Every row must be PASS. This stage runs whole suites and can take tens of minutes — launch it as a **supervised process** (`hub` `start` in omp, or the harness's equivalent) and wait on it, never as a plain shell call that a tool timeout can kill mid-run. It owns the coverage no per-phase stage carries, and it is the only check that catches a per-phase ledger someone wrote without earning. The two stages differ in *when* they run: `phase-exit` catches breakage before a commit lands, `finalize` proves the finished tree. Once it is green here, nothing on this tree needs re-running.
4. **Per-phase ledgers**: every working file this execution touched carries an earned ledger. Run `./validate verify phase-exit {file}` on the phase that exited last — the one whose ledger should match the current config. For earlier phases, `DRIFT` rows (a row the stage gained after that phase exited) are expected: record the drift line in that file and move on. A row that is FAIL, missing while the config is unchanged, mis-stamped, or older than the code it claims is a real failure → back to Step 2.3b for that phase. **Never re-run a stage to re-date a passing ledger**: gate 3 already proved the final tree, and a re-dated ledger claims a run that phase never made.
5. **User-stage handover**: run `./validate list user` and reproduce any rows verbatim in the close-out message. Empty output (exit 0) means this repo hands nothing over — that is a pass, not a gap. Those rows are the only checks allowed to leave this execution unrun.
6. **Dispatch Log (delegated epics only)**: the master plan's `## Dispatch Log` has one row per child bead, each carrying its dispatch and return timestamps (UTC, to the second), commits, gate result, ledger state and bead state. A missing row means the epic's state is not recoverable after a compaction — fill it before finalizing.
7. **Locales (if locale files exist)**: scan the repo for locale files — `l10n/`, `locales/`, `i18n/`, `*.arb`, `*.strings`, `Localizable.strings`, `*.xcstrings`, `*.po`/`*.pot`, `*.xliff`/`*.xlf`, `*.resx`, `*.properties`, or per-locale `*.json`/`*.yml` under a locale directory. If any are present **and** user-facing content changed in this execution, every supported locale must be updated — adopt a native-speaker role for each non-English locale, never word-for-word; English is the baseline. If no locale files exist in the repo, skip this gate and note the skip reason in the working file. This is a hard gate — failing locales blocks finalization, not just lowers quality.
8. **Tracker close-out**: every task this execution completed is closed, and if it was an epic, the epic itself is closed. `{tracker_cli} show {epic-id}` reporting all children done while the epic is still open is a failed gate, not a formality.

**Quality items (project-policy-overridable — do these after hard gates pass):**
9. **Docs**: update project docs in `{project}/docs/` for every change. Skip only if project instructions explicitly say so; log the skip.
10. **Coverage gap analysis**: verify 100% test coverage on changed code paths and fill gaps. Skip threshold may be lowered by project instructions; log the threshold used.
11. **Code review**: open the PR if the work is PR-bound, then invoke `{code_reviewer}` on it. Skip only with a logged reason — `code review: skipped — {reason}` in the working file. "No PR existed yet" is a reason to open one, not a reason to skip the review.
12. **Plan + commit**: if all phases are done, mark the plan `✅ COMPLETED — {YYYY-MM-DD}` (master plan and every slice). Otherwise leave `🔄 IN PROGRESS`. Commit docs, locales, and additional tests as separate commits from implementation per the Commit Strategy.
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
- Refactoring round commits (architecture splits, extractions, deduplications) are separate from feature commits — message prefix `refactor:`.
- Commit messages follow the pattern: `{type}: {what changed}` (e.g., `feat: add reader service with pagination`, `test: add reader service unit tests`, `docs: update plan with phase 2 completion`).
- Run `{commit_processor}` on every commit message before finalizing (skip if empty in config) — plain language, no marketing tone.
</commit-strategy>

---

## Constraints

<constraints>
**Critical — MUST follow:**
1. NEVER commit to or merge into `main`. Always work on feature branches.
2. MUST follow TDD: write test → confirm failure → implement → confirm passing. Skip only when genuinely impossible — state the reason in the plan.
3. MUST produce a `## Architecture Gate Results` block with **Overall: PASS** in the working file, containing a `### Validation` ledger — provenance header included — whose stage passes `./validate verify phase-exit`, before flipping any phase to `✅ COMPLETED`, before committing, and before closing any tracker task. Green tests alone are insufficient, and a green architecture block over an unrun validation stage is worse — it reads as proof while proving nothing about whether the code builds. Conversely, never re-run a stage to refresh a stamp: `DRIFT` against a later config is not a defect. See `../_shared/architecture-principles.md`, `../_shared/validators.md` and `references/update-format.md`.
4. Plan-file update is a hard gate between phases — the plan is the crash-recovery checkpoint. Only phases with `[x]` marks and `✅ COMPLETED` headers are recoverable. Never batch updates across phases.
5. A plan file is required for execution. If a tracker task has no linked plan, offer to create one via the `{plan_skill}` skill before proceeding.

Full architecture rules (SRP/DRY/KISS/YAGNI, modular monolith, anti-patterns) → `../_shared/architecture-principles.md`.
Validator stages, config format and per-stack recipes → `../_shared/validators.md`. **Required reading before Step 2.3b.**
Full tracker lifecycle rules (claim, close, epic auto-close, partial completion, refactoring rounds) → `references/tracker-templates.md`.
</constraints>
