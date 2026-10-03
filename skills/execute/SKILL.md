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

## Dispatching companion agents

`Companion Agents` values are an **ordered candidate list**, most specific first. A plugin-scoped name resolves on one harness only, so a single name is never a portable default.

Resolve, first hit wins, once per session:

1. **A configured candidate on this harness's roster.** The roster is in the dispatch tool's own description (`Task` on Claude Code, `task` on omp) — read it there. Never spawn to find out: a preflight rejection does list the roster, but paying a failed spawn every phase to learn a fact the description already carries is waste.
2. **A generic worker (`task`-class) you brief yourself.** Model and tool set are fixed at spawn and a worker cannot impose them on itself (`README.md`), so choose them when you spawn it; the brief carries the rest. State in it: its first read is `../_shared/architecture-principles.md`, the files it may examine, and **write nothing — report findings only**. Who acts on the findings differs by step: for `{code_simplifier}` **you** apply them before re-running the tests, which is how the pass still lands; for `{code_reviewer}` they go into the working file as the review result.
3. **The step's local fallback** — this harness has no subagent mechanism, or the configured value is empty. Step 2.2's fallback is its simplification checklist; Step 5 item 11's is a self-review of the diff against `../_shared/architecture-principles.md`. Either way the reason is logged; a step is never simply skipped.

Two obligations, both discharged in the Companion-skill status line (`references/update-format.md`): **name the rung that ran**, and when a spawn fails preflight anyway, **quote the error** and drop to the next rung. A delegation-limiting rule in project or user instructions is never a trigger for any rung below 1 — invoking this skill authorizes these agents.

---

## Configuration

This skill reads `skill.config.md` from its base directory on every invocation.

**If `skill.config.md` does not exist:**
1. Copy `skill.config.example.md` → `skill.config.md`.
2. Use `AskUserQuestion` offering interactive or manual setup.
3. **Interactive flow (2 rounds of questions):**
   - Round 1: Plans directory, issue tracker (enable + CLI name), formatter, test command
   - Round 2: Planning skill name, code simplifier candidates, code reviewer candidates (ordered lists, most specific first), commit message processor
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
| `{code_simplifier}` | Companion Agents → code_simplifier | (ordered candidate list — see `skill.config.example.md`; the resolved name is what the status line records) |
| `{code_reviewer}` | Companion Agents → code_reviewer | (ordered candidate list — see `skill.config.example.md`; the resolved name is what the status line records) |
| `{commit_processor}` | Post-Processing → commit_message_processor | `humanizer` |
| `{skills_dir}` | Skills Directory → skills_dir | `~/.agents/skills` |
| `{max_file_loc}` | Architecture → max_file_loc | `300` |

**Tracker state:** Read `Issue Tracker → enabled` from config. If `true`, run all `{tracker_cli}` commands in Steps 1 and 3. If `false`, skip all tracker commands.

---

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

1. **Baseline — read it before you run it.** From the repo root, `cat ledger` and `./validate verify <the stage that block names>` (`../_shared/validators.md`). Green and current ⇒ you already have your baseline: cite it in the master plan's `## Dispatch Log` (`subsumed by finalize @<sha>`) and dispatch. Run `./validate run phase-exit` only when there is no ledger, its block is red, or `verify` reports it stale — a `run` **overwrites** the ledger, so a baseline run over a green block that is not yet committed destroys the very proof you were checking for. A red baseline is not a worker's problem — fix or record it first, and note the result in the Dispatch Log either way. An epic spanning repos does this per repo, as it does branch, ledger and `finalize`; every Dispatch Log row then names the repo it belongs to.
2. **Order the work.** If the tracker can compute waves, use it (`{tracker_cli} swarm validate {epic-id}` in beads: ready fronts, max parallelism, cycles). Otherwise list the epic's children and their `--deps`. Fix a reported cycle or orphan before dispatching.
3. **Decide once, for the whole epic:** the branch (Step 1 rules — never `main`), whether workers may commit, and — where the answer is "no" — that the main session commits each phase itself as it verifies it. These go into every brief; workers never re-decide them, and neither do you. A commit permission decided here is decided for every phase: never re-open it with the user mid-epic.
4. **Generate the brief, never hand-write it:** `scripts/brief.sh {bead-id} {slice-path} {branch} {repo-root}` prints the invariant half — instruction files, branch, commit permission, the verbatim `phase-exit` stage, the iterate-until-green rule, the report fields. Append only `# Target`, `# Change`, `# Acceptance` for that phase. **Run it again for every bead**; never copy a previous brief and edit it, because a copy carries the previous bead's stage and any fix to the generator never reaches it. The brief deliberately does not contain the contract token — the worker looks it up in `<delegated-mode>`, which is what makes the echo mean something.
5. **Dispatch one worker per ready bead, one at a time** unless the user explicitly asked for parallel work.
6. **Verify before trusting.** When a worker returns: `cd {repo root} && ./validate verify phase-exit` — exit 0 is required. It takes no file argument: it reads the repo's `ledger`, the file the run wrote and the worker committed with its source, so a ledger the worker never earned does not exist to be read, and one that predates the worker's own last commit fails as stale. `DRIFT` lines are expected when the worker's phase added a validator row. The report's `contract:` token must match the `Contract version:` line in `<delegated-mode>`; a wrong or missing token means the worker never opened the contract, so treat its other claims as unverified. Then check the slice has `## Architecture Gate Results` with **Overall: PASS** dated in this execution, checkboxes are `[x]`, `**Status:**` is `✅ COMPLETED`, and the bead is closed. Any failure → send the worker back; do not close the bead, do not dispatch the next one.
7. **Log every return** in the master plan's `## Dispatch Log`, one row per bead. `Dispatched` and `Returned` are **UTC timestamps to the second** (`date -u +%Y-%m-%dT%H:%M:%SZ`), never bare dates: the row's only job is to be lined up against that bead's ledger header (`started=` / `finished=` / `finished_epoch=`), and a date cannot tell you whether a worker's ledger was earned before or after its own dispatch. Copy this shape:

   | Bead | Worker | Dispatched | Returned | Commits | Gate | Ledger | Bead state |
   |------|--------|------------|----------|---------|------|--------|------------|
   | `{bead-id}` | `{worker name}` | `2026-08-19T19:41:27Z` | `2026-08-19T20:14:03Z` | `a1b2c3d` | Overall: PASS | {verdict line verbatim} @ `a1b2c3d` | closed |

   That table is the epic's state on disk — after a compaction it is how you know where you are. The `Ledger` cell carries the verdict line `verify` printed, word for word, and the sha of the commit holding that `ledger`. A bare `verify exit 0` is not enough: before the ledger was a file, that same exit code was what a worker got for a plan file with no ledger in it at all.
8. **Answer escalations.** A worker cannot ask the user. Answer yourself when the brief already covers the point; otherwise use `AskUserQuestion`, then reply to the worker so it resumes with full history.
9. **Route discovered work.** A bead for a defect this epic introduced is `parent-child` to the epic — it blocks the epic's close. Anything else found mid-epic is `discovered-from` **and** listed in the master plan's Beads table. The close-out message tables every bead filed, with its routing.
10. **Never delegated, keep here:** master plan and Beads table updates, locale updates, the `finalize` stage, pushes, tracker push, and Step 5.
11. **Close out.** After the last bead closes: Step 5 for the whole execution, then confirm the epic itself is closed (`{tracker_cli} show {epic-id}` must not still report it open with all children done), then the PR and Step 5 item 11's code review — resolved through *Dispatching companion agents* like every other dispatch, never waived on policy.

**After any compaction inside an epic:** read the `## Dispatch Log` and run `{tracker_cli} show {epic-id}` before dispatching or finalizing. Never resume epic state from memory.
</epic-dispatch-mode>

<delegated-mode>
Contract version: **DM-2026-09-v1** — echo this token in your report as proof you read this block.

You are in delegated mode when you were spawned to work a single bead. The whole skill still applies, with these overrides:

- **Step 1 branch setup:** the branch is given. Verify you are on it, never switch, never touch `main`. Claim with `{tracker_cli} -C {repo root} update {id} --claim` — your `cd` does not persist between shell calls, so pass the repo root on every tracker command.
- **Every question:** you cannot ask the user. Send it to the parent session (`hub` send to `Main` in omp, `SendMessage` in Claude Code) with what you need and why, then stop that thread. This replaces the Step 3 continuation question, the Step 4 three-round escalation, and any Step 0 diagnostic that would have asked. Never guess, never narrow the bead to dodge the question.
- **Step 2.2 stands:** run `{code_simplifier}` on your changed files, resolved per *Dispatching companion agents* — rung 2 is yours to brief. Re-run the changed test files, then compute the gate; the gate is computed after simplification.
- **Validation is yours, and it is not a judgement call:** when the slice's work is done, run `cd {repo root} && ./validate run phase-exit`. Any FAIL opens a Bug Round or Refactoring Round (Step 4), you fix it, and you re-run the **whole** stage. Report only when every row is PASS; after three failed rounds, escalate with the failing ledger and the kept output the header's `log=` names, then stop. Exit 2 means the config is wrong, not the code — do not loop on it. Never defer a check the stage contains, including compiles and native suites. Only `user`-stage rows are handed over, and `./validate run` records those itself.
- **Run the stage last, and commit its ledger:** `./validate run phase-exit` writes `{repo root}/ledger` — the header and rows it just printed. You transcribe nothing. `verify` measures staleness from that file's own commit, so finish editing, then run the stage, then stage `ledger` in the same commit as the source it proves. A fix applied after the run invalidates it, which is the point.
- **Step 5 is the parent's:** the `finalize` stage, locales, docs beyond your slice, and `{code_reviewer}` belong to the parent. Name each in your report's `deferred` field with its owner.
- **Commits:** only if the brief grants them, staging explicit paths — your source files **and** `ledger` — never `git add -A`, never `git commit -a`. Never push, never `{tracker_cli} dolt push`.
- **Files you own:** your bead's source files and your own slice file. Master plan, system mirror and other slices belong to the parent.
- **Locales:** never edit them. List the added or changed keys in your report and stop.

Finish with the return contract: at most 15 lines — contract token, files created/modified, the `verify` verdict line verbatim plus the sha of the commit carrying `ledger`, gate Overall line, bead status and commits, deferred checks with owners, locale keys, open questions, blockers. No diffs, no logs.
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
2. **If on `main`**: pull latest, create a new branch named after the plan (e.g., `feat/epub-table-of-contents` from `myapp_feat_epub_table_of_contents.md`).
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
Dispatch `{code_simplifier}` on the newly written or modified source files, resolved per *Dispatching companion agents*. Re-run the changed test file(s) after.

**Rung 3 — local fallback**, entered on the section's terms and never silently: do **not** skip the step when no rung above it is available.
1. Apply the simplification checklist locally on the changed files: remove dead code, inline single-use helpers, collapse redundant branches, prefer existing utilities over new ones.
2. Re-run the changed test file(s).
3. Record the rung in Step 2.3's Companion-skill status line: ``{code_simplifier}: skipped — {reason}``, where the reason is `empty config`, `no subagent mechanism`, or the quoted spawn error of the **rung-2 worker**. A preflight rejection of a configured candidate drops to rung 2, never to here — that shortcut is the dead pass this ladder exists to end.

#### Step 2.3: Architecture Gate — REQUIRED ARTIFACT
Run the architecture verification gate from `../_shared/architecture-principles.md` on every file in `git diff --name-only` for this phase. The simplifier is not a substitute.

For each changed file:
1. Run the helper script: `python3 {skills_dir}/execute/scripts/run_arch_gate.py <file> --max-loc {max_file_loc}`. Capture the `[arch-gate] file=...` banner line. If the script does not cover the language, run the LOC count manually and proceed.
2. Apply the manual checks (SRP, DRY, testability) from `../_shared/architecture-principles.md` and record one-sentence reasoning per file.

Then write the `## Architecture Gate Results` block into the **working file** using the template in `references/update-format.md`. The block must include the banner per file, the results table, the companion-skill status, an **Overall:** line, and the `### Validation` record from Step 2.3b.

**Fail-closed contract:**
- If any row is FAIL → open a Refactoring Round (Step 4) and do not proceed.
- If the block is missing or any row's status is unrecorded → not a valid completion. Stop and write the block.
- The architecture gate is **the** phase-exit checkpoint — green tests alone are insufficient.
- **No pre-existing-condition exemption.** A violation that existed before this phase still blocks phase exit. "It was already there" is never an acceptable reason to leave a FAIL row. Fix it in a Refactoring Round.

#### Step 2.3b: Validation stage — REQUIRED ARTIFACT
Run the repo's `phase-exit` stage (`../_shared/validators.md`) **from the repo root** — `./validate` exists only there, the config's commands `cd` from there, and the runner writes `./ledger` there:

```
cd {repo root} && ./validate run phase-exit
```

The run overwrites `{repo root}/ledger` with the header and rows it just printed. That file is the artifact; you transcribe nothing. Then confirm it:

```
cd {repo root} && ./validate verify phase-exit
```

Exit 0 is required. `verify` takes no file argument — it reads `./ledger`. Record two lines under `### Validation` in the working file: the verdict line `verify` printed, verbatim, and the sha of the commit that will carry `ledger` (see `references/update-format.md`). Stage `ledger` in the same commit as the source it proves.

If your shell tool's timeout is shorter than the stage takes (native suites and builds routinely run minutes), launch it as a supervised process instead — `hub` `start` plus `wait` in omp — so a timeout cannot kill the run and leave you without a ledger.

**Fail-closed contract:**
- **Exit 1** — a row FAILed, or verification found no ledger, a ledger naming another stage, a row missing or mis-stamped, or source that moved since the ledger's commit → Bug Round or Refactoring Round (Step 4), fix, then re-run the **whole** stage. Never re-run a single row and call the stage green.
- **Exit 2** — misconfigured (no `validators.conf`, a stage this repo does not define, or a file path passed to `verify`, which no longer takes one). **Do not loop**: no round will fix a config error, and the config is not yours to write (`../_shared/validators.md`). Record `validators: none — {reason}` under `### Validation`, name it in your report's `deferred` field owned by `human`, and continue with the slice. Never edit the config and never stop a thread over it.
- The stage is coarse on purpose: a change in one language routinely breaks another. "This phase only touched Dart" is not a reason to skip a row, and neither is cost — a row too slow for every phase belongs in `finalize`, decided in `validators.conf`, not skipped ad hoc.
- `user`-stage rows are recorded `PENDING-USER` by the runner and handed to the user in the close-out. Nothing else may be deferred.
- If **a validator row was added since the ledger's run**, `verify` reports it as `DRIFT`, which is a report and not a failure. Never re-run a stage to refresh a stamp (`../_shared/validators.md` — "Two rules that keep verification from becoming busy work").

#### Step 2.4: Format
Run `{formatter}` (skip if empty in config).

**Phase exit gate** (all four required to enter Step 3):
1. Step 2.1's changed-test-file run is green.
2. `## Architecture Gate Results` block exists in the working file with **Overall: PASS** dated within this execution.
3. `cd {repo root} && ./validate verify phase-exit` exits 0.
4. Step 2.4 ran clean.

Any failure → Step 4 (Bug Round for test failures, Refactoring Round for gate failures).

### Step 3: Update plan, close task, and offer continuation

**Step 3.0 — Fail-closed precondition.** Before doing anything else in Step 3, verify that the working file (slice file for multi-phase, plan file for single-phase) contains a `## Architecture Gate Results` block with **Overall: PASS** dated within this execution **and** that `cd {repo root} && ./validate verify phase-exit` exits 0. If the block is missing, any row is FAIL, or verification fails, **STOP** — return to Step 2.3 and produce the artifact. Do not commit, do not close the tracker task, do not flip the status line. This precondition holds even if all tests are green.

After tests pass for the phase **and** the gate artifact exists:

**Update plan files** (see `references/update-format.md` for format rules):

**Single-phase plans:**
1. Mark all completed tasks with `[x]` in the Implementation Progress section.
2. Add ` ✅ COMPLETED — {YYYY-MM-DD}` to the `### Phase 1:` header.
3. Add created/modified files to the Files Created / Files Modified sections.

**Multi-phase plans** — update both files:
1. **Slice file:** Mark all completed tasks with `[x]` in `## Implementation Progress`. Change `**Status:**` to `✅ COMPLETED — {YYYY-MM-DD}`. Add files to the slice's Files Created / Files Modified sections.
2. **Master plan:** Mark the corresponding `- [ ]` line `[x]` in the `## Progress` section and append ` ✅ {YYYY-MM-DD}`. Add files to the master's consolidated Files Created / Files Modified sections.

**Then, for both plan types:** Commit changes as atomic, logical chunks — see Commit Strategy below. `ledger` is staged with the source commit it proves — same commit, explicit path, never staged alone and never amended in afterwards.

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
3. **Per-phase ledger**: before running anything that overwrites it, confirm the ledger the last phase earned: `cd {repo root} && ./validate verify phase-exit` — exit 0 required. This is the last moment `ledger` names `phase-exit`. A `DRIFT` row (a row the stage gained after that ledger ran) is a report, not a failure, and never a reason to re-run the stage. A row that is FAIL, missing while the config is unchanged, mis-stamped, or older than the ledger's commit is a real failure → back to Step 2.3b for that phase. **Never re-run a stage to re-date a passing ledger**: gate 4 proves the final tree, and a re-dated ledger claims a run that phase never made.
4. **Finalize stage**: from the repo root, run `./validate run finalize` (`../_shared/validators.md`), then `./validate verify finalize` — exit 0 required. The run overwrites `ledger`, which now names `finalize`, and that is the repo's validation state from here on; record its verdict line in the final-sweep block and stage `ledger` with this execution's close-out commit (item 12). Every row must be PASS. This stage runs whole suites and can take tens of minutes — launch it as a **supervised process** (`hub` `start` in omp, or the harness's equivalent) and wait on it, never as a plain shell call that a tool timeout can kill mid-run. It owns the coverage no per-phase stage carries. The two stages differ in *when* they run: `phase-exit` catches breakage before a commit lands, `finalize` proves the finished tree. Once it is green here, nothing on this tree needs re-running.
5. **User-stage handover**: run `./validate list user` and reproduce any rows verbatim in the close-out message. Empty output (exit 0) means this repo hands nothing over — that is a pass, not a gap. Those rows are the only checks allowed to leave this execution unrun.
6. **Dispatch Log (delegated epics only)**: the master plan's `## Dispatch Log` has one row per child bead, each carrying its dispatch and return timestamps (UTC, to the second), commits, gate result, ledger state and bead state. A missing row means the epic's state is not recoverable after a compaction — fill it before finalizing.
7. **Locales (if locale files exist)**: scan the repo for locale files (`*.arb`, `*.strings`, `l10n/`, `Localizable.strings`). If any are present **and** user-facing content changed in this execution, every supported locale must be updated — adopt a native-speaker role for each non-English locale, never word-for-word; English is the baseline. If no locale files exist in the repo, skip this gate and note the skip reason in the working file. This is a hard gate — failing locales blocks finalization, not just lowers quality.
8. **Tracker close-out**: every task this execution completed is closed, and if it was an epic, the epic itself is closed. `{tracker_cli} show {epic-id}` reporting all children done while the epic is still open is a failed gate, not a formality.

**Quality items (project-policy-overridable — do these after hard gates pass):**
9. **Docs**: update project docs in `{project}/docs/` for every change. Skip only if project instructions explicitly say so; log the skip.
10. **Coverage gap analysis**: verify 100% test coverage on changed code paths and fill gaps. Skip threshold may be lowered by project instructions; log the threshold used.
11. **Code review**: open the PR if the work is PR-bound, then invoke `{code_reviewer}` on it, resolved per *Dispatching companion agents* — rung 3 here is a self-review of the diff, logged with its reason, never an unexamined skip. `code review: skipped — {reason}` goes in the working file. "No PR existed yet" is a reason to open one, not a reason to skip the review.
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
- `ledger` commits with the source it proves, in the same commit, staged by explicit path — a validation record that lands in a later commit no longer matches the code it claims.
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
3. MUST produce a `## Architecture Gate Results` block with **Overall: PASS** in the working file, containing a `### Validation` record — the `verify` verdict line and the sha of the commit carrying `ledger` — and `cd {repo root} && ./validate verify phase-exit` must exit 0, before flipping any phase to `✅ COMPLETED`, before committing, and before closing any tracker task. Green tests alone are insufficient, and a green architecture block over an unrun validation stage is worse — it reads as proof while proving nothing about whether the code builds. Conversely, never re-run a stage to refresh a stamp: `DRIFT` against a later config is not a defect. See `../_shared/architecture-principles.md`, `../_shared/validators.md` and `references/update-format.md`.
4. Plan-file update is a hard gate between phases — the plan is the crash-recovery checkpoint. Only phases with `[x]` marks and `✅ COMPLETED` headers are recoverable. Never batch updates across phases.
5. A plan file is required for execution. If a tracker task has no linked plan, offer to create one via the `{plan_skill}` skill before proceeding.

Full architecture rules (SRP/DRY/KISS/YAGNI, modular monolith, anti-patterns) → `../_shared/architecture-principles.md`.
Validator stages, config format and per-stack recipes → `../_shared/validators.md`. **Required reading before Step 2.3b.**
Full tracker lifecycle rules (claim, close, epic auto-close, partial completion, refactoring rounds) → `references/tracker-templates.md`.
</constraints>
