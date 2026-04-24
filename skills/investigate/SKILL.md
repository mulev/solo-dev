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
[debug] Investigating...
```

This is non-negotiable. It must be the very first thing the user sees.

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
| `{plan_skill}` | Companion Skills → plan_skill | `/plan` |
| `{execute_skill}` | Companion Skills → execute_skill | `/execute` |
| `{plans_dir}` | Plans Directory → plans_dir | `project_plans` |

---

## Workflow

### Step 0: Define the problem

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
**Problem:** Clicking "Resume" opens the document at the beginning instead of the saved position.

**Execution chain:**
1. User clicks "Resume" button → calls `EditorBloc.openDocument(docId, resume: true)` — *evidence: `lib/features/documents/widgets/doc_card.dart:142`*
2. `EditorBloc.openDocument` calls `progressRepository.getLastPosition(docId)` → returns `SavedPosition(cursor: CursorPos(...), updatedAt: ...)` — *evidence: `lib/features/editor/bloc/editor_bloc.dart:87`, confirmed non-null via database query*
3. `openDocument` passes the position to `viewService.open(document, initialPosition: position)` — *evidence: `editor_bloc.dart:93`*
4. `ViewService.open` calls `renderer.navigateTo(initialPosition)` — *evidence: `lib/features/editor/services/view_service.dart:41`*
5. **Failure:** `renderer.navigateTo` receives the position but `renderer` is not yet initialized at this point — `_renderer` is `null`, the call is silently dropped, and the editor falls back to the beginning — *evidence: `view_service.dart:38` shows `_renderer` is set in `onViewReady` callback, which fires asynchronously after `open()` returns*

**Root cause:** `navigateTo(savedPosition)` is called synchronously during `initialize()`, but the renderer is only available after the view finishes setup (`onViewReady`). The position is sent to a null renderer and silently discarded.

**Supporting evidence:**
- `view_controller.dart:38`: `_renderer = null` until `onViewReady` assigns it at line 52
- Framework docs confirm view initialization callbacks are asynchronous and fire after the first frame
- `view_controller.dart:41`: no null check or queuing mechanism — `_renderer?.navigateTo(position)` uses `?.` which silently no-ops on null

**What was ruled out:**
- Database returning stale/null position: verified via direct SQL query — position is correctly stored and retrieved
- Position format mismatch: the returned position uses the same `Position` type the renderer expects — confirmed by type analysis
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

### Step 5: Hand off to implementation

After both gates are passed, hand off to implementation.

**If the planning skill is available** (see `{plan_skill}`): Invoke `{plan_skill}` and provide it with the full context:
- The root cause analysis from Step 2
- The approved fix from Step 4
- All files that need to change
- Side effects that were checked
- Any related issues discovered during investigation

The plan skill handles the execute handoff after creating the plan — do not invoke `{execute_skill}` separately here.

**If the planning skill is not available:** Use `AskUserQuestion`:

```
question: "Root cause and fix are confirmed. How do you want to proceed?"
header: "Next step"
options:
  - label: "Create a plan file manually"
    description: "Write a structured plan in {plans_dir}/ before implementing."
  - label: "Implement the fix now"
    description: "Skip planning and start implementing via the execution skill."
```

If "Implement the fix now": Invoke `{execute_skill}` with the approved fix context — pass the root cause analysis from Step 2, the approved fix from Step 4, all files that need to change, and side effects that were checked. The execute skill handles branch setup, TDD, testing, and commits. It will detect the missing plan file and offer to create one before proceeding.

---

## Constraints

<constraints>
- NEVER propose a fix before the root cause is confirmed by evidence AND approved by the user. Sequence is always: investigate → present analysis → user approves → investigate fix → present fix → user approves → hand off.
- NEVER skip the execution chain trace — scale its depth to bug complexity (see Step 1), but always trace beyond the immediate failure site.
- NEVER use assumption language ("probably", "likely", "I think", "should be", "presumably", "I believe", "it seems"). Instead, state verified facts with evidence citations, or say "This is unverified — I need to check X" and then check it.
- NEVER proceed past Gate 1 or Gate 2 without explicit user approval via `AskUserQuestion`.
- NEVER modify code during the debug skill. This skill outputs analysis and a fix proposal only — implementation happens via the configured planning and execution skills, or direct implementation after handoff.
- When investigation hits a dead end, present what was found, what remains unknown, and what additional information is needed. Do not fabricate an explanation to fill the gap.
- When multiple root causes are plausible, investigate each and present the evidence for and against all of them. Let evidence decide — do not rank by "likelihood."
</constraints>
