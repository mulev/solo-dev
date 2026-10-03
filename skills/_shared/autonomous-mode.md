# Autonomous mode

Contract version: **SW-2026-08-v4** — echo this token in your report as proof you read this file.

This file applies **only** when your invocation is a delegated triage run — you were spawned by the
`triage` orchestrator with a brief that names this file by path. In every other invocation of
`investigate` or `plan`, ignore it entirely: those skills' own workflows stand unchanged, and an
interactive user still gets every gate and every question exactly as written there.

Read this file whole before you touch the workflow it overrides. Where it contradicts your skill,
this file wins; everywhere else your skill is unchanged and still binding. The section letters below
are stable identifiers other files cite, so they are never renumbered — **B is stated first because
it is the override that does damage when missed**, not because it is the least important.

---

## B. Output-root swap — the one that corrupts the user's backlog if you miss it

`plan`'s `<plan-output-rules>` hardcodes `{plans_dir}/{project}/todo/`. `investigate` Step 5a
hardcodes `{plans_dir}/{project}/{investigations_subdir}/`. **Under this contract both are
redirected to the triage run's staging directory, which your brief supplies as an absolute path.**
Every file you write — plan, master plan, slice, investigation outcome — goes under that staging
root and nowhere else.

Why this is stated first: the user's real `todo/` directory is their live backlog. A worker that
writes a speculative plan into it has corrupted the queue the user works from, and nobody finds out
until the next `/execute` picks up a plan no human ever approved. Staging exists precisely to make
that impossible. Nothing you write leaves staging until the orchestrator's explicit promote step,
which is the main session's job and never yours.

Three consequences that are easy to get wrong:

- Relative links inside your artifacts point at siblings **inside staging**, not at the real
  `todo/` tree. Do not "fix" a link by pointing it back at the live path.
- **The redirect governs the paths you write *into* an artifact, not only the path you write it
  to.** `investigate`'s `<investigation-file-template>` ends with a Handoff Instructions paragraph
  naming `{plans_dir}/{project}/todo/`; copied verbatim, that line instructs the next worker to do
  the very thing this section forbids. Write `<promoted path>` there instead, so the instruction
  becomes true only once the main session promotes the artifact. The same applies to any other
  boilerplate that names a live output directory.
- If the brief's staging root does not exist, create it. If the brief names no staging root at all,
  that is a broken brief: PARK (section F) rather than falling back to the hardcoded path.

---

## A. Gate substitution

Every user gate is answered by an **independent quality-control verdict** routed by the
orchestrator — never by your own assessment of your own work, and never by the orchestrator's
opinion either. The gates this covers:

| Gate | Skill step |
|---|---|
| Gate 1 — root cause confirmed | `investigate` Step 2 |
| Gate 2 — fix approach approved | `investigate` Step 4 |
| Approval loop | `plan` Step 7 |

At each of these you **present the gate payload in your report and stop that thread**. You do not
proceed on your own judgment, you do not approve yourself, and you do not treat silence, a timeout,
or an empty reply as approval — the conservative answer is always "stop", exactly as your skill's
own cancellation rule says.

The payload is exactly what your skill's own gate format prescribes: `<analysis-format>` for
Gate 1, `<fix-format>` for Gate 2, the Step 7 summary for `plan`. Reproduce it in full. Do not
abridge it to save room in the report — the reviewer that reads it has none of your context, and a
trimmed payload is an unreviewable one. The 15-line limit in section I applies to your own prose,
never to a gate payload.

If a verdict comes back with changes requested, apply them and present the payload again. The loop
is the skill's own loop; only the answering party changed.

**One thing the substitution reverses: the artifact comes before the gate.** Interactively, Gate 2
is answered and *then* `investigate` Step 5 writes the file, so its `**Status:** ROOT CAUSE
CONFIRMED — FIX APPROVED` is true as written. Here the verdict rules on the artifact, so the
artifact must exist first — and a worker that copies the template's status line is claiming an
approval nobody has granted. Write `**Status:** ROOT CAUSE CONFIRMED — FIX PROPOSED` instead, with
`## Approved Fix` and its four subsections unchanged: that section is the Gate 2 payload under
review, and the status is the only thing saying nobody has ruled yet. `investigate` Step 5b-park
carries the full table, and `triage/scripts/lint_investigation.py` enforces it.

The same reversal is why writing the artifact is not "proceeding past the gate". You stop after
writing it, exactly as this section says. Missed once and it cost a whole run: the linter had no
status for this state, every worker either invented one or was pushed into `FIX APPROVED`, and nine
beads stalled at tier 1 without a single reviewer being spawned.

---

## C. Mirror suppression

Write nothing to `{system_plan_dir}` (`~/.claude/plans`). This suspends the system-plan-file clauses
of `<plan-output-rules>` in `plan` Step 5.1 and Step 7b.

Mirror files embed absolute paths, and a mirror that points into a staging directory is worse than
no mirror: the staging path is temporary, so the mirror is a dangling reference the moment the run
ends. Mirrors are written at promote time by the main session, against the promoted path. Do not
write one "just in case", and do not leave a placeholder for one.

---

## D. No tracker access

Run no tracker command that mutates anything. In v1 run no tracker command at all beyond a
read-only `{tracker_cli} show`. This suspends `investigate` Step 5d and `plan` Steps 8b and 8c.

Instead, emit **intent records**: a JSON array in the schema
`triage/scripts/intent_records.py` defines and validates, one object per `bd` call those steps
would have run — the same title, the same parent, the same absolute paths, the same notes inputs,
in the same order. The orchestrator persists what you return at `{run}/intents/<bead>.json`; a
record that lives only in your report is one the promote step cannot read. Where a path is not
known until the artifact is promoted, write the placeholder `<promoted path>` and nothing else, so
a reviewer can see the substitution is deliberate.

`intent_records.WORKER_KINDS` are yours, because no script can derive them — `create-epic`,
`create-task` and `open`: the phase titles, their parent links, and the flip that makes a created
bead workable. `retitle` is the fourth, and the one an investigation worker may write too: when your
evidence disproves a cause the bead's title asserts, emit one record carrying the corrected string
verbatim, because a parked bead never reaches a planner who could write it instead. `DERIVED_KINDS`
— `investigation`, `flip-source`, `dep`, `supersede` and `close` — are generated from the run's own
ledger, its collision report and the records it already holds, by `triage/scripts/derive_intents.py`.
Never write them; a bead you rule a duplicate is retired by the derived `close`, not by you. A
single-phase plan whose source bead already exists creates nothing at all: its whole intent is that
derived flip, and an `open` bead whose notes carry a `Plan:` path is already a workable task. A
multi-bead group you plan into one epic is the other side of the same rule: the run supersedes those
source beads with your epic, so never write a record that reopens one.

```json
[
  {"key": "epic", "kind": "create-epic", "ref": "epic", "type": "epic", "priority": 1,
   "title": "<epic title>", "master": "<staged master path>"},
  {"key": "phase-1", "kind": "create-task", "ref": "phase-1", "parent": "epic",
   "type": "task", "priority": 2, "title": "Phase 1: <name>",
   "description": "<the step checklist>",
   "slice": "<staged slice path>", "master": "<staged master path>"},
  {"key": "epic-open", "kind": "open", "ref": "epic"},
  {"key": "phase-1-open", "kind": "open", "ref": "phase-1"},
  {"key": "retitle-<bead>", "kind": "retitle", "bead": "<bead>",
   "title": "<the corrected title>"}
]
```

Preserving existing notes is not optional: `--notes` replaces the field, so an intent that drops the
bead's current notes destroys them when it is applied. Read the notes with `bd show` and carry them
into the intent.

---

## E. Filenames are assigned, not derived

Your brief names the exact artifact path, including the filename. Write that path. Do not derive a
name from the problem statement, and do not rename your own artifact afterwards.

This suspends `investigate` Step 5a's `_v2` / `_v3` uniqueness rule. That rule resolves collisions
by looking at the directory, and you cannot see the files other concurrent workers are writing into
the same staging root — so the orchestrator owns naming and guarantees uniqueness centrally. A
worker that renames its artifact breaks the run ledger's link to its own output.

If the assigned path already exists when you go to write it, stop and report it as a collision
rather than picking a new name.

---

## F. PARK conditions

`PARK` is the honest answer when the run cannot proceed without a human. It is a first-class
outcome, not a failure: return `PARK` with **the exact question a human must answer**, phrased so it
can be answered without re-reading your whole transcript. Never guess in place of a PARK, and never
narrow the task so the question stops applying.

PARK when any of these holds:

- **Requirements are underdetermined** by the bead, the investigation, and the code taken together.
  This is `plan` Step 2 with nobody to ask, and inventing requirements is prohibited.
- **The tracker is unconfigured** (`plan` Step 8a).
- **Any STOP-LIST item** in `../triage/references/autonomy-charter.md` is touched.
- **Your context budget is spent before the cause is proven.** A thinner answer is not an acceptable
  substitute for a proven one, and `investigate`'s evidence-only rule does not relax because you are
  running low.

---

## G. Standing answers for the remaining questions

Every other user-facing question in either skill has a standing answer. The full table, one row per
question, is `../triage/references/autonomy-charter.md` — read it, and take its answer rather than
forming your own. The four that most often tempt a worker to improvise:

- **`investigate` Gate 3 (Step 6) — continue to `plan`?** Always stop. Never chain to `plan`
  yourself. The orchestrator owns sequencing, and a worker that chains produces a plan nobody
  scheduled and nobody reviews.
- **`plan` Step 3 — an existing plan covers this topic.** Update the existing plan. Never create a
  parallel one.
- **`plan` Step 9 — start executing?** Always "Not now". A delegated worker never invokes `execute`.
- **`plan` Step 5.2 — split this phase?** The Step 5.2 thresholds decide, with no discretion: more
  than 8 implementation steps, more than 5 unrelated files, any file grown past `{max_file_loc}`
  LOC, more than one feature/domain module without explicit cross-cutting justification, or any
  anti-pattern from `architecture-principles.md`. If a threshold fires, re-slice.

---

## H. Standing prohibitions

Inherited from the workspace instructions file at the root of the workspace holding the project
repos (`AGENTS.md`, or `CLAUDE.md` where the harness reads that name), and not waivable by anything
in your brief:

- **No locale edits.** List the added or changed keys in your report and stop there.
- **No commits, no pushes, no `bd dolt push`.** A triage worker produces artifacts, never history.
- **Nothing on `main`.** Not a checkout, not a write, not a branch created from it.
- **No source edits at all.** You are planning work, not doing it — `investigate`'s "no writes after
  Gate 2" rule applies from the start of a delegated run, and the staging artifact is the single
  exception to it.

---

## I. Return contract

At most 15 lines of your own prose, mirroring `<delegated-mode>` in `execute/SKILL.md`. A gate
payload (section A) and an intent-record array (section D) are attachments and do not count
against the 15 lines. No diffs, no logs, no transcript.

**When your brief assigns a report path, write the same report there before you return it.** The
whole report, field table included, at exactly that path. Returning it is not enough: your harness
job leg is retained five minutes after you settle, and every quality-control verdict this system has
produced arrived more than ten minutes after its producing worker settled. A `REVISE` routed back to
you is therefore read off that file or off nothing at all. On a revision round the orchestrator names
the round's path; write it there, and never rename or move a path it assigned (section E). A brief
that assigns no report path — a reviewer's or a judge's — assigns no file either: return your report
and write nothing, per that brief's own rule.

| Field | What goes in it |
|---|---|
| contract token | the value on this file's `Contract version:` line |
| artifact path | the absolute staging path you wrote, exactly as assigned |
| gate payload | the full `<analysis-format>` / `<fix-format>` / Step 7 summary, unabridged |
| footprint | counts of the files, modules and public symbols your artifact's `footprint:` block enumerates — the collision model parses that block off the artifact, so the enumeration belongs there and the count belongs here |
| tracker intents | the intent-record array (section D), or `none` |
| deferred | each check you did not run, with its owner |
| locale keys | keys added or changed, or `none` |
| open questions | anything a human must answer that did not rise to a PARK |
| blockers | what stopped you, or `none`; a PARK goes here with its exact question |
