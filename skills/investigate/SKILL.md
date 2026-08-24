---
name: investigate
description: >
  Systematic root cause analysis and fix design for software bugs and unexpected
  behavior. Evidence-only methodology with no assumptions — traces full execution
  chains, consults real documentation, presents findings with proof before
  proposing fixes. Two mandatory user gates: root cause confirmation and fix
  approval. Hands off to the configured planning skill for implementation.

  TRIGGER when: (1) the user reports a bug, error, crash, test failure, or
  unexpected behavior; (2) the user asks to debug, investigate, diagnose,
  troubleshoot, figure out, look into, trace, or understand why something is
  failing, broken, or wrong — including phrases like "not working", "something's
  off", "why does this happen", "find the root cause", "find the bug"; (3) during
  your own chain of thought you are about to guess a root cause, assume why
  something fails, or propose a fix without evidence — stop and invoke this skill
  instead of speculating.
---

# Investigate

Debugging is scientific research. Every conclusion requires evidence. Assumptions are prohibited — if something is unknown, investigate it; never fill the gap with speculation.

## Core principles

<principles>
1. **Evidence only.** Every claim must cite a specific file, line, log entry, doc passage, or observable behavior. If you cannot point to proof, do not state it as fact.
2. **No assumptions.** Never say "probably", "likely", "I think", "this should", or "presumably". If you are uncertain, investigate further or state explicitly: "This is unverified — I need to check X."
3. **Trace the full chain.** Follow execution from the entry point to the failure site, step by step. Do not skip intermediate steps. Every link in the chain must be read and understood.
4. **Consult real documentation.** When the bug involves a framework, library, or API, read its actual documentation — do not rely on general knowledge. Use Context7 MCP, web search, or `WebFetch` to retrieve current docs.
5. **User gates are hard stops.** Do not proceed past a gate until the user explicitly approves. Present your findings, wait for confirmation, then move on.
6. **Fix the root cause, not the symptom.** Patches and workarounds are not acceptable. The fix must address why the bug exists, not just suppress its visible effect.
</principles>

---

## Invocation

When this skill is invoked, **immediately** output the following line before doing anything else — no preamble, no extra text:

```
[invest] Investigating...
```

This is non-negotiable. It must be the very first thing the user sees. Then, before any other tool call, run `ToolSearch(query="select:AskUserQuestion", max_results=1)` (Claude Code only) to cache the question-tool schema for the session.

---

## Conduct

Read `../_shared/agent-conduct.md` before the first tool call of this workflow. It carries the ownership, evidence, verification, shell, localization and scope rules every step below assumes. **Required reading** — its Evidence section is the same standard as the Core principles above, stated once for the whole bundle, and its "genuine blockers are the only acceptable 'I can't'" rule is what separates a dead-end report from a skipped investigation.

---

## Asking the user

Every question you ask the user — clarification, confirmation, choice between options, gate approvals — MUST go through the host's structured-question tool. Plain-text questions are a last-resort fallback only.

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

Verify resolution every session — never assume the prior choice still applies. Batch up to 4 questions per call. Provide likely answers as options; the user picks "Other" for custom input. Gate approvals (Gate 1, Gate 2) MUST use the resolved tool — never proceed past a gate without explicit user approval through it.

**Ask in the same message.** Attach the question call to the message carrying the gate prose. A turn that ends on gate prose has asked nothing — the gate becomes a rhetorical question and the workflow proceeds unapproved.

**Treat a cancelled or timed-out question as the conservative answer.** Take the option that proceeds no further, name it, and stop. A cancellation is never permission to continue.

See `../_shared/tooling-examples.md` for the canonical call shape.

Where the rest of this skill says `AskUserQuestion`, treat it as a placeholder for whichever tool resolved above.

---

## Invoking companion skills

When this skill hands off to another (e.g., `{plan_skill}`, `{execute_skill}`), use the harness's skill-invocation mechanism. Configured shorthands hold the **bare skill name** with no prefix — the prefix is harness convention, never written into config.

Pick the first mechanism available in the current environment:

- **Claude Code:** call the `Skill` tool with `skill: "{plan_skill}"` and pass the handoff payload as `args`. **Text-emitting `Use the {plan_skill} skill.` does NOT invoke the skill on Claude Code** — only the `Skill` tool call triggers invocation. If `Skill` is unavailable but the skill is exposed as a user-runnable slash command, write `/{plan_skill}` as a literal first-line message.
- **Codex (interactive TUI):** invoke as `${plan_skill}`.
- **Codex (`codex exec` non-interactive):** the slash-skill invocation is not available — emit the literal sentence `Use the {plan_skill} skill.` as your next assistant message, immediately followed by the handoff payload (OpenAI deterministic-workflow pattern; fuzzy phrasing drops the handoff).
- **Fallback (any harness):** read `{skills_dir}/{plan_skill}/SKILL.md` directly with `Read` and follow its workflow inline in the current conversation. Pass the handoff context (root cause analysis, approved fix, file list, side effects) as the first message of that inline workflow.

Do not write a literal `/` or `$` inside config values — the harness adds it.

---

## Configuration

This skill reads `skill.config.md` from its base directory on every invocation.

**If `skill.config.md` does not exist:**
1. Copy `skill.config.example.md` → `skill.config.md`.
2. Use `AskUserQuestion`:
   ```
   question: "The investigate skill needs one-time setup. Config created with defaults. Review settings?"
   header: "Setup"
   options:
     - label: "Defaults are fine"
       description: "Proceed with default configuration."
     - label: "Let me customize"
       description: "I'll edit skill.config.md before continuing."
   ```
3. If "Let me customize": show the config file path and stop. Resume on next invocation.

**If `skill.config.md` exists:** Read silently and proceed.

**Shorthands used below:**

| Shorthand | Config field | Default |
|-----------|-------------|---------|
| `{plan_skill}` | Companion Skills → plan_skill | `plan` |
| `{execute_skill}` | Companion Skills → execute_skill | `execute` |
| `{plans_dir}` | Plans Directory → plans_dir | `project_plans` |
| `{investigations_subdir}` | Investigations Directory → investigations_subdir | `investigations` |
| `{skills_dir}` | Skills Directory → skills_dir | `~/.agents/skills` |
| `{tracker_cli}` | Issue Tracker → cli_command | `bd` |
| `{tracker_enabled}` | Issue Tracker → enabled | `false` |

The resolved investigations directory is `{plans_dir}/{project}/{investigations_subdir}/`. Create it on first write if missing.

**Tracker state:** read `Issue Tracker → enabled` from config. If `true`, run the `{tracker_cli}` commands in Step 0 and Step 5d. If `false`, skip them and treat every investigation as untracked.

---

## Workflow

### Step 0: Define the problem

**If the user's request is a bare tracker ID** (e.g. `myapp-37h`), that ID is the investigation's subject. Run `{tracker_cli} show <id>` from the repo root that owns the ID's prefix — never from a parent directory — and treat its description and notes as the initial report. Record the ID; Step 5d writes back to it.

A prior investigation referenced in the bead's notes may belong to a *different* bug that merely spawned this one. Read it as context, never as this bead's answer, and never treat a cause the bead's title asserts as already proven.

Gather enough information to begin investigation. Use `AskUserQuestion` if any of these are missing from the user's initial report:

- What is the expected behavior?
- What is the actual behavior?
- Reproduction steps (or conditions under which it occurs)
- Error messages, stack traces, logs (if available)

Do not over-question — if the user gave a clear description, start investigating immediately.

### Step 1: Collect evidence

Scale investigation depth to bug complexity:
- **Small bugs** (typo, wrong constant, missing null check): locate the failure site, read the immediate context, verify the fix. Full chain trace is unnecessary when the cause is visible at the call site.
- **Medium bugs** (wrong behavior, state corruption, race condition): trace the execution chain through the involved subsystem. Check docs for APIs in the chain.
- **Large bugs** (intermittent failures, data loss, cross-module breakage): full chain trace from entry point to failure, documentation review, dependency version check, and prior art comparison.

When in doubt, start at medium depth and escalate if the cause is not evident.

<evidence-collection>
**1a. Locate the failure site.**
Read the file and function where the bug manifests. Identify the exact line(s) producing the incorrect behavior.

**1b. Trace the execution chain backwards.**
From the failure site, trace every caller, every data source, every state mutation that contributes to the outcome. Read each file. Follow every function call. Map the chain from entry point to failure — do not skip any link.

**1c. Trace the execution chain forwards.**
From the entry point, walk through the chain in execution order. At each step, note:
- What data enters
- What transformation occurs
- What data exits
- Whether the behavior at this step matches the documented contract

**1d. Check documentation for involved technologies.**
For every framework API, library function, or platform behavior involved in the execution chain — read its actual documentation. Do not assume you know how it works. Use Context7 MCP for library docs. Use web search for platform-specific behavior, release notes, or known issues.

**1e. Check dependency versions.**
If the bug may relate to a dependency, verify the exact version in use (pubspec.lock, package-lock.json, go.sum, etc.) and check the docs/changelog for that specific version.

**1f. Look for prior art.**
Search the codebase for similar patterns that work correctly. Compare them against the broken code to identify divergences.
</evidence-collection>

Use parallel tool calls aggressively during evidence collection — read multiple files simultaneously, search in parallel, fetch docs while reading code.

**Parallel research agents are allowed here, and only here.** When separate evidence trails do not depend on each other, dispatch one read-only agent per trail in a single batch — they are read-only, so they cannot collide. They gather and report; they never write, never touch the tracker, and never conclude. The root-cause gate, the ruling on the evidence, and the Step 5 outcome file stay with you.

### Step 2: Present root cause analysis — GATE 1

Compile your findings into a structured analysis. Present it to the user as a text message with this structure:

<analysis-format>
**Problem:** {one-sentence description of the observed bug}

**Execution chain:**
1. {Step 1}: {what happens} — *evidence: {file:line or doc reference}*
2. {Step 2}: {what happens} — *evidence: {file:line or doc reference}*
3. ...
N. {Failure point}: {what goes wrong and why} — *evidence: {file:line or doc reference}*

**Root cause:** {precise explanation of why the bug exists, with evidence}

**Supporting evidence:**
- {evidence item 1 — quote the relevant code, doc passage, or log entry}
- {evidence item 2}
- ...

**What was ruled out:** {alternative hypotheses you investigated and disproved, with evidence for why they are not the cause}
</analysis-format>

<example>
**Problem:** Tapping "Resume reading" opens the book at page 1 instead of the saved position.

**Execution chain:**
1. User taps "Resume reading" button → calls `ReaderBloc.openBook(bookId, resume: true)` — *evidence: `lib/features/library/widgets/book_card.dart:142`*
2. `ReaderBloc.openBook` calls `progressRepository.getLastPosition(bookId)` → returns `ReadingPosition(locator: Locator(...), updatedAt: ...)` — *evidence: `lib/features/reader/bloc/reader_bloc.dart:87`, confirmed non-null via database query*
3. `openBook` passes the locator to `readerService.open(publication, initialLocator: locator)` — *evidence: `reader_bloc.dart:93`*
4. `ReaderService.open` calls `navigator.goTo(initialLocator)` — *evidence: `lib/features/reader/services/reader_service.dart:41`*
5. **Failure:** `navigator.goTo` receives the locator but `navigator` is not yet initialized at this point — `_navigator` is `null`, the call is silently dropped, and the reader falls back to page 1 — *evidence: `reader_service.dart:38` shows `_navigator` is set in `onReaderReady` callback, which fires asynchronously after `open()` returns*

**Root cause:** `goTo(initialLocator)` is called synchronously during `open()`, but the navigator is only available after the reader widget finishes initialization (`onReaderReady`). The locator is sent to a null navigator and silently discarded.

**Supporting evidence:**
- `reader_service.dart:38`: `_navigator = null` until `onReaderReady` assigns it at line 52
- Flutter framework docs confirm widget initialization callbacks are asynchronous and fire after the first frame
- `reader_service.dart:41`: no null check or queuing mechanism — `_navigator?.goTo(locator)` uses `?.` which silently no-ops on null

**What was ruled out:**
- Database returning stale/null position: verified via `{tracker_cli} show` and direct SQL query — position is correctly stored and retrieved
- Locator format mismatch: the returned locator uses the same `Locator` type the navigator expects — confirmed by type analysis
</example>

After presenting the analysis, use `AskUserQuestion`:

```
question: "Does this root cause analysis match your understanding of the problem?"
header: "Root cause"
options:
  - label: "Yes, this is correct"
    description: "The analysis is accurate. Proceed to identifying a fix."
  - label: "Partially correct"
    description: "Some parts are right but I have corrections or additions."
  - label: "No, this is wrong"
    description: "The analysis misses the real cause. I'll explain what's off."
```

**If "Partially correct" or "No":** Collect the user's feedback, investigate the areas they pointed out, update the analysis, and present it again. Repeat until the user confirms.

**If "Yes":** Proceed to Step 3.

### Step 3: Investigate potential fixes

Only after root cause is confirmed. Investigate fix options grounded in the real codebase.

<fix-investigation>
**3a. Identify the minimal change set.**
What is the smallest set of changes that addresses the root cause? Read the surrounding code to understand constraints, patterns, and conventions.

**3b. Check for side effects.**
For each file you plan to modify, trace all callers and consumers of the changed code. Verify that the fix does not break any existing behavior.

**3c. Check for related occurrences.**
Search the codebase for the same pattern or bug in other locations. If the root cause is systemic, the fix should address all occurrences.

**3d. Verify against documentation.**
Confirm that the proposed fix aligns with the documented behavior of all APIs and frameworks involved.

**3e. Consider the fix's permanence.**
A good fix makes the bug impossible to recur — not just unlikely. Prefer structural fixes (type changes, API redesign, invariant enforcement) over behavioral fixes (adding a check, special-casing).
</fix-investigation>

### Step 4: Present the proposed fix — GATE 2

Present the fix to the user as a text message:

<fix-format>
**Proposed fix:** {one-sentence summary}

**What changes:**
1. {File}: {what changes and why} — *addresses: {which part of the root cause}*
2. ...

**Why this fix is correct:**
- {Reason 1, with evidence from code or docs}
- {Reason 2}

**Side effects considered:**
- {Caller/consumer 1}: {why it is unaffected}
- {Caller/consumer 2}: {why it is unaffected}
- ...

**What this fix does NOT address:** {any related but separate issues discovered during investigation — these become separate issues}
</fix-format>

After presenting the fix, use `AskUserQuestion`:

```
question: "Does this fix approach look right to you?"
header: "Fix"
options:
  - label: "Yes, proceed with this fix"
    description: "Approved. Create a plan and implement it."
  - label: "I'd prefer a different approach"
    description: "I'll describe what I'd rather do."
  - label: "I need more information"
    description: "Explain more about a specific part before I decide."
```

**If "I'd prefer a different approach" or "I need more information":** Address the feedback, investigate the alternative, and present an updated fix. Repeat until the user approves.

**If "Yes":** Proceed to Step 5.

### Step 5: Save investigation outcome to disk

**Why:** Investigations consume large context during evidence collection. Passing the full analysis inline to `{plan_skill}` degrades plan-skill performance and burns budget the planning work needs. Persisting the outcome to a file lets the next session (clean context) run `{plan_skill}` against the saved file.

This step is **mandatory** before any handoff. Skip only if `{plans_dir}` is empty in config (see *Fallback* in Step 6).

Writing this file and the Step 5d tracker update are the ONLY exceptions to the "no writes after Gate 2" rule in *Constraints*. Once 5d completes, the no-writes rule resumes — no further Edit/Write/mutating Bash until handoff fires.

**5a. Resolve target path.**
- Directory: `{plans_dir}/{project}/{investigations_subdir}/` — create if missing (the Write tool creates parent directories automatically).
- Filename: `{project}_invest_{short_name}.md`
  - `short_name`: 3–5 lowercase words separated by underscores, derived from the problem statement. Hyphens allowed within a word.
  - Example: `myapp_invest_resume_locator_dropped.md`
- If a file with that name already exists in the directory, append `_v2`, `_v3`, … until unique. Do not overwrite — prior investigations are evidence.

**5b. Write the file.** Use the Write tool with this template, filling every bracketed field from Steps 2 and 4. Do not paraphrase the Gate-1 and Gate-2 content — copy it verbatim so the file is self-contained.

<investigation-file-template>
````markdown
# {Project} Investigation: {Short title}

**Status:** ROOT CAUSE CONFIRMED — FIX APPROVED
**Date:** {YYYY-MM-DD from currentDate}
**Project:** {project}
**Beads task:** {tracker id, or "none"}

---

## Problem

{one-sentence description from Gate 1}

## Execution Chain

{numbered steps from Gate 1, with evidence citations}

## Root Cause

{precise explanation from Gate 1}

## Supporting Evidence

{evidence items from Gate 1 — quote code, doc passages, log entries verbatim}

## Ruled Out

{alternative hypotheses with evidence for rejection from Gate 1}

---

## Approved Fix

**Summary:** {one-sentence from Gate 2}

**What changes:**
{file-by-file change list from Gate 2}

**Why this fix is correct:**
{reasons from Gate 2}

**Side effects checked:**
{caller/consumer list from Gate 2}

**Not addressed (separate issues):**
{related-but-separate items from Gate 2, or "none"}

---

## Handoff Instructions

Pass this file path to the planning skill as background context. The planning skill MUST NOT overwrite this file — it MUST create the implementation plan as a separate file under `{plans_dir}/{project}/todo/` and reference this investigation from the plan's Background section.
````
</investigation-file-template>

**5c. Confirm the write.** After the Write call returns, present the absolute path to the user as a single line of text, then continue with 5d:

```
[invest] Saved → {absolute path}
```

**5d. Write the outcome back to the tracker.** Skip when `{tracker_enabled}` is `false`, or when Step 0 resolved no tracker ID. Otherwise, from the repo root that owns the ID's prefix:

```sh
{tracker_cli} update <id> --status needs-plan --notes "Investigation: {absolute path}
Root cause confirmed and fix approved. Use the planning skill to create the implementation plan."
```

The status stays `needs-plan`: an investigation produces a proven cause, not a plan, so the bead is still not workable — `{plan_skill}` is what flips it to `open`.

If your evidence disproved a cause the bead's title asserts, correct the title in the same call with `--title`. A title that states a wrong cause is worse than one that states only the symptom.

Then add one line to the 5c confirmation, and proceed to Step 6:

```
[invest] <id> → needs-plan
```

### Step 6: Hand off to implementation — GATE 3

After saving, ask the user whether to continue immediately or stop so `{plan_skill}` can run in a clean session.

**If `{plan_skill}` is non-empty in config (default `plan`):** Use `AskUserQuestion`:

```
question: "Investigation saved. Continue to {plan_skill} now, or stop so it can run in a clean session?"
header: "Next step"
options:
  - label: "Stop here — I'll run {plan_skill} in a clean session (Recommended)"
    description: "Best for context budget. /clear or start a new session, then invoke {plan_skill} with the investigation file path."
  - label: "Continue to {plan_skill} now"
    description: "Invoke {plan_skill} in this session. Higher context usage; acceptable for small fixes."
```

**If "Stop here":** Output the exact resume command for the next session and end. Do not invoke anything. Format:

```
Resume in clean session with:
    /{plan_skill} {absolute path to investigation file}
```

**If "Continue now":** Invoke `{plan_skill}` via the mechanism resolved in *Invoking companion skills*, passing **only the investigation file path** as the payload (not the full analysis — the file holds it). Payload format:

```
Investigation: {absolute path to investigation file}

Read this file for the confirmed root cause, approved fix, files to change, and side-effect notes. Create the implementation plan based on the approved fix. Do not overwrite the investigation file — reference it from the plan's Background section.
```

**Per-harness application of the payload:**

- **Claude Code:** call the `Skill` tool with `skill: "{plan_skill}"` and pass the payload above as the `args` parameter. Do NOT emit the payload as a text message — Claude Code only invokes skills via the `Skill` tool call. Emitting "Use the plan skill." as text is a silent no-op and breaks the handoff.
- **Codex (`codex exec`):** emit the literal sentence `Use the {plan_skill} skill.` as your next assistant message, immediately followed by the payload above. This is the only working path on `codex exec`.
- **Codex (interactive TUI):** invoke as `${plan_skill}` and pass the payload as the argument.

The plan skill handles the execute handoff after creating the plan — do not invoke the `{execute_skill}` skill separately here.

**Fallback — only when `{plan_skill}` is literally empty in config:** Use `AskUserQuestion`:

```
question: "Root cause and fix are confirmed. How do you want to proceed?"
header: "Next step"
options:
  - label: "Create a plan file manually"
    description: "Write a structured plan in {plans_dir}/ before implementing."
  - label: "Implement the fix now"
    description: "Skip planning and start implementing via the execution skill."
```

If "Implement the fix now": invoke the `{execute_skill}` skill (see *Invoking companion skills*) with the investigation file path as the payload. The execute skill handles branch setup, TDD, testing, and commits. It will detect the missing plan file and offer to create one before proceeding.

---

## Constraints

<constraints>
- NEVER propose a fix before the root cause is confirmed by evidence AND approved by the user. Sequence is always: investigate → present analysis → user approves → investigate fix → present fix → user approves → hand off.
- NEVER skip the execution chain trace — scale its depth to bug complexity (see Step 1), but always trace beyond the immediate failure site.
- NEVER use assumption language ("probably", "likely", "I think", "should be", "presumably", "I believe", "it seems"). Instead, state verified facts with evidence citations, or say "This is unverified — I need to check X" and then check it.
- NEVER proceed past Gate 1 or Gate 2 without explicit user approval through the resolved question tool, and NEVER end a turn on gate prose with no call attached — an unasked gate is a skipped gate.
- NEVER modify code during this skill. Implementation happens ONLY via `{plan_skill}` or `{execute_skill}`. NEVER call Edit/Bash-mutate against codebase files.
- After Gate 2: the ONLY writes permitted are the Step 5 investigation-outcome file at `{plans_dir}/{project}/{investigations_subdir}/` and the Step 5d `{tracker_cli} update`. All other writes are forbidden until handoff invoked — no Edit, no Write to codebase files, no NotebookEdit, no other Bash mutation (`git commit`, `mv`, `rm`, `>`, `>>`, `sed -i`). Allowed = read-only Bash, Read, Grep, the resolved question tool, the Step 5 write, the Step 5d tracker update, the handoff itself.
- NEVER skip Step 5. The investigation-outcome file is mandatory whenever `{plans_dir}` is configured. Direct inline handoff (passing the analysis as a tool argument) is forbidden — the file is the handoff medium.
- When investigation hits a dead end, present what was found, what remains unknown, and what additional information is needed. Do not fabricate an explanation to fill the gap.
- When multiple root causes are plausible, investigate each and present the evidence for and against all of them. Let evidence decide — do not rank by "likelihood."
</constraints>
