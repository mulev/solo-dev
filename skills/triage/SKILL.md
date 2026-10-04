---
name: triage
description: >
  Autonomous backlog sweep. Routes every unworkable bead in a project to
  investigation or planning, dispatches workers in waves, answers their gates
  with an independent quality-control verdict, and stages every artifact in a
  discardable run directory that never touches the tracker.

  TRIGGER when the user asks to triage the backlog, go through the needs-plan
  beads, investigate and plan everything in a project, sweep or clear the
  backlog, or work through a project's untriaged issues in bulk.
---

# Triage

A triage run turns a pile of unworkable beads into staged, reviewed artifacts a human can promote or
throw away whole. It writes nothing the user has to clean up: the run directory is the entire
footprint, and deleting it undoes the run exactly.

**This skill adds no analysis of its own.** Every routing rule, similarity metric, collision
heuristic and lint check already exists as a script or a reference under `triage/`. If a step below
looks like it needs new judgment, that is a defect in the script it should be calling — escalate
rather than deciding it here. An orchestrator that starts reasoning about the work becomes a second,
untested implementation of it.

## Invocation

When this skill is invoked, **immediately** output the following line before doing anything else —
no preamble, no extra text:

```
[triage] Triaging...
```

This is non-negotiable. It must be the very first thing the user sees. Then, before any other tool
call, run `ToolSearch(query="select:AskUserQuestion", max_results=1)` (Claude Code only) to cache
the question-tool schema for the session.

## Conduct

Read `../_shared/agent-conduct.md` before the first tool call of this workflow. It carries the ownership, evidence, verification, shell, localization and scope rules every step below assumes. **Required reading** — its "never fake completion" rule is what a staged run depends on: nothing here is reviewed by you before it lands, so a worker's own report is the only account of what it did.

---

## Asking the user

Every question MUST go through the host's structured-question tool; plain text is a last-resort
fallback. On Claude Code that is `AskUserQuestion`, loaded once per session with
`ToolSearch(query="select:AskUserQuestion", max_results=1)`. The full resolution ladder for other
harnesses is in `references/harness.md`.

**Ask in the same message.** A turn that ends on a question in prose has asked nothing. **Treat a
cancelled or timed-out question as the conservative answer:** take the option that proceeds no
further, name it, and stop.

**Triage asks the user nothing by design.** Exactly one thing reaches them mid-run: an escalation
neither the brief nor `references/autonomy-charter.md` answers. Everything else already has a
standing answer — take it.

## Invoking companion skills

Workers are dispatched with briefs naming `investigate` and `plan`. On Claude Code, call the `Skill`
tool with `skill: "investigate"` and pass the brief as `args` — emitting the text `Use the
investigate skill.` does not invoke anything. Other harnesses, and the read-the-SKILL-directly
fallback that makes a brief work where no invocation mechanism exists, are in
`references/harness.md`. Configured shorthands hold the bare skill name; the prefix is harness
convention and is never written into config.

## Configuration

This skill reads `skill.config.md` from its base directory on every invocation.

**If `skill.config.md` does not exist:** copy `skill.config.example.md` to `skill.config.md`, then
ask whether to review the defaults. If the user wants to customize, show the path and stop; resume
on the next invocation. **If it exists:** read silently and proceed.

| Shorthand | Config field | Default |
|-----------|-------------|---------|
| `{plans_dir}` | Plans Directory → plans_dir | `project_plans` |
| `{skills_dir}` | Skills Directory → skills_dir | (absolute path, set at setup) |
| `{tracker_enabled}` | Issue Tracker → enabled | `false` |
| `{tracker_cli}` | Issue Tracker → cli_command | `bd` |
| `{staging_subdir}` | Staging → staging_subdir | `triage` |
| `{parallel_cap}` | Dispatch → parallel_cap | `3` |
| `{max_beads}` | Dispatch → max_beads | `0` (unlimited) |

`{project}`, `{run}`, `{runid}` and `{projects_root}` below are runtime values, not config: the
detected project name, the absolute run directory, the run's short random suffix, and the directory
holding the project repos. Every script that resolves a project by name reads `{projects_root}` from
the environment as `TRIAGE_PROJECTS_ROOT`; it has no default, and omitting it is exit `2`.

Detect the project the way `plan` does — explicit mention, then IDE context, then conversation
context, then ask — and resolve it against the Known Projects table.

`{tracker_enabled}` gates only **read-only** `{tracker_cli}` calls; v1 makes no other kind. When it
is `false`, `/triage` cannot run at all: say so and stop. There is no backlog to sweep without a
tracker, and inventing one is not a fallback.

## Invocation surface

```
/triage {project}                            sweep the project's backlog
/triage {project} --dry-run                  stop after Wave 1, dispatch nothing
/triage {project} --only investigate|plan    restrict to one route
/triage {project} --ids a,b,c                only these beads
/triage {project} --max N                    cap the run at N beads
/triage {project} --parallel N               cap concurrent workers
/triage --resume {runid}                     continue an interrupted run
/triage discard {runid}                      delete exactly one run directory
/triage promote {runid}                      move one staged run into the real tree
```

`--max` overrides `{max_beads}`; `--parallel` overrides `{parallel_cap}`. Both are per-run only and
neither is written back to config.

## Staging layout

Every artifact a run produces lands here and nowhere else:

```
{plans_dir}/{project}/{staging_subdir}/{YYYY-MM-DD}_{runid}/
  ledger.md
  manifest.json
  judge_brief.md
  briefs/           every generated dispatch brief — a run artifact `discard` must reach
  collision_report.md
  footprints.json
  investigations/
  todo/
  reports/          one report per worker per round — a return that outlives the worker's job leg
```

The run directory sits under `{plans_dir}` in the project's `{staging_subdir}` folder. `{runid}` is
a short random suffix, so two runs on the same day never collide. `investigations/` and `todo/`
mirror the shape the real plan directories use, which is what lets the promote step move them
without rewriting anything inside them.

**The invariant the whole design rests on: v1 writes nothing outside the run directory.** No tracker
mutation, no `~/.claude/plans` mirror, no touch of the real `todo/`. Deleting the run directory
therefore returns the system to its pre-run state exactly.

Every later feature must preserve that invariant or `discard` becomes a lie. The moment one tracker
write or one mirror file escapes the run directory, deleting the directory leaves the system in a
state no command can name and no human asked for — half-promoted, with the evidence gone.

## Promoting a run

```
python3 {skills_dir}/triage/scripts/derive_intents.py --run-dir {run}
python3 {skills_dir}/triage/scripts/promote.py --run-id {runid} \
        --runs-dir {plans_dir}/{project}/{staging_subdir} \
        --plans-dir {plans_dir} --repo-root {repo_root} \
        --system-plan-dir ~/.claude/plans [--dry-run] [--json]
```

**Promote is never automatic in v1.** A run ends at the Wave 6 report; a human reads it and then
runs this command. Never chain it onto a run, and never run it because a run looked clean.

Derive first — it writes the `investigation`, `flip-source`, `dep`, `supersede` and `close` records into `{run}/intents/`, which promote reads.
Exit `0` clean, `1` findings, `2` usage. `references/promoting.md` covers the steps, where intents live, quarantine, reruns and the deferred mirrors — read it first.

## Discarding a run

```
python3 {skills_dir}/triage/scripts/discard.py --run-id {runid} \
        --runs-dir {plans_dir}/{project}/{staging_subdir} [--dry-run]
```

**Never `rm -rf` by hand.** The script resolves `{runid}` to exactly one run and refuses everything
else: zero or many matches, and a symlink planted in the staging directory. Exit `0` discarded, `1`
refused, `2` usage or environment error. `--dry-run` prints the absolute path and deletes nothing.

Discard is a complete undo only because promote has not run: nothing outside the run directory has
been written yet, for the reason given just above. A run already moved under `promoted/` is past
that point — the script exits `2` on it, because its artifacts are in the real tree and removing the
directory would destroy the record without undoing anything.

## Wave 0 — Inventory

Create the run directory first, and never with a bare `mkdir`:

```
python3 -c "import sys; sys.path.insert(0, '{skills_dir}/triage/scripts'); \
  import staged_run; print(staged_run.create_run('{plans_dir}/{project}/{staging_subdir}', '{YYYY-MM-DD}_{runid}', mode='--dry-run' if dry else 'full run'))"
```

`create_run` also writes a `.gitignore` into the staging root the first time a project stages a run.
A run swept into a commit is permanent, and `discard` then deletes a directory whose contents are
already in history — the invariant would read as true while being false.

It also opens `{run}/ledger.md` on its canonical header and creates `{run}/briefs/`. **Never retype
that header**, and keep the `Mode:` line it seeds. The rows below it are a different matter: a return
**updates the row its own dispatch wrote**, and `references/ledger.md` says when one row becomes several.

```
TRIAGE_PROJECTS_ROOT={projects_root} python3 {skills_dir}/triage/scripts/inventory.py \
        --project {project} --json --out {run}/manifest.json [--ids a,b,c] [--only investigate|plan] [--max N]
```

Exit `1` means drift beads were found, which is normal. Exit `2` is a configuration error: stop the
run and report it. Then Wave 0's ledger row, before anything else is done with the manifest: `all`,
`worker` `—`, `artifact` `{run}/manifest.json`.

Pass `--ids`, `--only` and the bead cap straight through to the script — `--max N`, else
`{max_beads}`, `0` meaning unlimited. **Do not apply them by hand.** `inventory.select` marks every
excluded bead with a reason and leaves its entry in place, so `counts` still describes the backlog
while `selected_counts` describes this run; a later run can then tell "not selected" from "not seen".
An unknown bead id or route is exit `2`, never a silently empty run.

Routing itself is `inventory.py`'s, per `references/classification.md`. Do not re-route a bead
because its title reads a certain way.

## Wave 1 — Dedup

```
TRIAGE_PROJECTS_ROOT={projects_root} python3 {skills_dir}/triage/scripts/dedup.py \
        --manifest {run}/manifest.json --project {project} --plans-dir {plans_dir} --brief {run}/judge_brief.md
```

It writes `clusters` and `covered` back into the manifest and emits `judge_brief.md`. Exit `1` means
candidates were found; exit `2` is a usage or environment error. Wave 1 owes two ledger rows: `all`
for `dedup.py`, `artifact` `{run}/judge_brief.md`, on the script's clock; and one row per group at
the judge's return, keyed by `cluster_ruling.identify`, its dedup ruling in `verdict`, on the judge's.

Then dispatch **one** judge agent over the candidate clusters, with a brief from:

```
{skills_dir}/triage/scripts/brief_judge.sh {run}/judge_brief.md <repo-root> > {run}/briefs/judge.md
```

Generate it; never hand-write it. The rules that make a ruling trustworthy — read the code rather
than the brief's prose, similarity is an input, unsure rules `related-not-duplicate` — live in that
generator, and a prompt improvised per run carries whichever of them the orchestrator happened to
think of. The judge returns a **partition** per cluster: every member in exactly one group, each
group carrying `duplicate` / `distinct` / `related-not-duplicate` and, for `duplicate`, the
representative. Clustering is loose on purpose, so a cluster that is part duplicate and part not
must be sayable — one verdict for the whole cluster forces the safe answer and loses the real
duplicate inside it.

Validate the ruling with `cluster_ruling.validate(members, groups)`, then name its groups with
`cluster_ruling.identify(cluster_id, groups)`, before writing them into `clusters[].groups`. A
member ruled twice or not at all is an incomplete answer, not a judgment call, and goes back to the
judge. The names are what the ledger's Wave 1 rows are keyed by — never mint your own, or the rows
point at groups nothing else in the run can be matched to. `cluster_ruling.dropped(groups)` is then
the list of beads this wave retires — a duplicate group's non-representatives, and nothing else.

The same judge rules on coverage, in the brief's closing section: per flagged bead, `covered` naming
the covering plan, or `not-covered`. Validate with `plan_coverage.validate_coverage(ids, rulings)`,
then act: `plan_coverage.skipped(rulings)` leaves the run and is reported in Wave 6 with its plan,
everything else dispatches as normal. **An unruled flagged bead is the failure this prevents** — it
gets a fresh investigation and plan while an existing plan covers that ground, uncompared.

Neither the script nor the orchestrator rules on sameness or on coverage — that split is deliberate
(`references/deduplication.md`), and collapsing it puts an unreviewed deletion inside a mechanical
script.

**Under `--dry-run` the run stops here.** Report the manifest, the routes, the dedup clusters and
the collision groups; dispatch no worker beyond the single judge; write the ledger.

Those collision groups are still the script's. A dry run has no worker and so no footprint: run Wave 3's steps 2 and 3 with no pairs,
which writes `[]`. Never write "not computed" instead — `references/collision-model.md` has the reason and the expected output.

**`--dry-run` is the recommended first run on any backlog.** It costs one judge agent and shows
exactly what a full run would spend before anything is spent.

**A full run has no scope gate.** `/triage {project}` already named the scope, and `--ids`, `--only`
and `--max` are how a narrower one is asked for. **Print** the counts here — N to investigate, M to
plan, K dropped as duplicates, the run directory, and the `--max` lever — then dispatch Wave 2.
`references/harness.md` has the reasoning.

## Wave 2 — Investigation

Dispatch investigation workers **in parallel up to `{parallel_cap}`**, each with a brief from:

```
{skills_dir}/triage/scripts/brief_invest.sh <bead-id> <artifact-path> {run} <repo-root> > {run}/briefs/<bead-id>_invest.md
```

Generate a brief per bead. Never copy a previous brief and edit it: a copy carries the previous
bead's target, and a fix to the generator never reaches it.

**The orchestrator assigns each worker's artifact path**, writes it into the brief, and it is not
the worker's to choose. Concurrent workers deriving their own filenames collide, and `investigate`
Step 5a's `_v2` uniqueness rule cannot see a file another worker has not written yet: two workers
both find `bug_x.md` absent, both pick it, and one investigation is lost with no error anywhere.
Assigned naming is also what makes the ledger's artifact column trustworthy.

The path you assign is `{run}/investigations/<project>_invest_<short_name>.md`, where `<short_name>`
is **3–5 lowercase words separated by underscores** derived from the problem, hyphens allowed inside
a word: `triage-testbed_invest_missing_config_crash.md`. Never the bead id, never a slug of the
title. `lint_investigation.py` enforces exactly this in Wave 5 as `filename-convention`, and the
orchestrator chose the name, so no worker can repair it — name them any other way and every artifact
fails tier 1 and never reaches a reviewer. Measured on a run that lost its whole wave to it.

The brief names `../_shared/autonomous-mode.md`, which redirects the worker's output root into
`{run}`. **Never let a real `todo/` or investigations path reach a worker** — not as staging root,
example, or copyable boilerplate. Section B exists because `investigate`'s file template ends with a
handoff paragraph naming the live backlog: a staged artifact can still send the *next* worker there.

Workers are read-only against source, so parallelism cannot collide on files. Merge a returned
`retitle` record with `intent_records.merge` into `{run}/intents/`, in the same move as the ledger row.
The brief assigns `{run}/reports/<bead-id>_r1.md` the same way: the return outlives the job leg.

## Wave 3 — Collision

**This wave is a barrier.** Every Wave 2 worker must have returned before it starts.
`collide.py` needs every footprint at once; a group computed from a partial set is wrong, not merely
incomplete. A `--dry-run` is not an exception: no workers is a complete set, and Wave 1 says so.

1. **Plan-only footprint pass.** Beads routed straight to `plan` produced no investigation and so no
   footprint. Derive theirs first, from the bead and the code, so the graph sees the whole set.
2. `python3 {skills_dir}/triage/scripts/footprints.py --run {run} <bead>=<artifact> ...` — every
   returned artifact's block becomes `{run}/footprints.json`; exit 1 names one absent or malformed.
3. Run:
   ```
   python3 {skills_dir}/triage/scripts/collide.py --manifest {run}/manifest.json \
           --footprints {run}/footprints.json --report {run}/collision_report.md
   ```
4. Record each group and its merge decision in the manifest, and write its ledger rows in the same
   step: one row per group carrying its `MERGE` / `SEQUENCE` / `INDEPENDENT` / `UNCLASSIFIED`
   decision in `verdict`, alongside the `all` row for `collide.py`'s own run. Exit `1` means a MERGE
   or a late duplicate was found — both are findings to act on, not failures.

Group membership and the `MERGE` / `SEQUENCE` / `INDEPENDENT` decision are the script's, per
`references/collision-model.md`. Its ordering intents are `dep` records promote applies; never run them here.

## Wave 4 — Planning

Dispatch planning workers **in parallel across groups, sequentially within a group.** Two beads in
one group would edit the same plan files — exactly the collision the grouping exists to prevent —
while two beads in different groups by construction cannot.

```
{skills_dir}/triage/scripts/brief_plan.sh <bead-ids> <investigation-paths> {run} <repo-root> > {run}/briefs/<group>_plan.md
```

One brief per dispatch; `brief_plan.sh`'s usage block owns the argument contract, and the worker receives the staging root, never
a path in the live backlog. Merge the returned JSON intent records with `intent_records.merge` into `{run}/intents/`, in the same
move that writes the ledger row — a report is not storage. `derive_intents.py` adds the `investigation`, `flip-source`, `dep`,
`supersede` and `close` kinds. Every path in a record is absolute: promote's pre-flight validates the whole store, so a relative one stops the run.
The brief assigns `{run}/reports/<first-bead-id>_plan_r1.md` the same way, and the worker writes its report there before returning it.

**Record each investigation's sha256 as you hand it over.** `touch {run}/hashes.txt` before the first
dispatch, then `shasum -a 256 <absolute investigation path> >> {run}/hashes.txt` per path in a brief.
Wave 5 passes that file to `lint_plan.py`; with no file its background check reports `SKIP`, not pass.

## Wave 5 — Quality control

Per artifact, **as it lands** — never batched at the end. A `REVISE` revives the producing worker by
agent id, long after its job leg expired, and reads its revision off disk.

1. **Tier 1, mechanical.**
   ```
   python3 {skills_dir}/triage/scripts/lint_investigation.py <artifact> --repo <repo-root>
   python3 {skills_dir}/triage/scripts/lint_plan.py <plan-folder> --project-root <repo-root> --investigation-hash-file {run}/hashes.txt
   ```
   Pass the repo explicitly: derived from a staging path it would resolve to the wrong tree. Exit
   `0` passes, `1` is findings, `2` is a broken invocation.
2. **Tier 2, adversarial.** Only if tier 1 passed, dispatch the review with a brief from
   `{skills_dir}/triage/scripts/brief_qc.sh <artifact-path> <kind> <round> <repo-root> > {run}/briefs/<bead-id>_qc<round>.md`, where
   `<kind>` is `investigation` or `plan`. Dispatch the registered `triage-qc` agent when this harness's
   roster carries that name, else a worker you spawn on `opus` with `Read`, `Grep` and `Glob` only, whose first read is `{skills_dir}/triage/agents/triage-qc.md` — `references/qc-gates.md` § 1.
3. **Route the verdict.** Write it to `{run}/verdicts/<bead-id>_r<round>.json`, then act on what
   `next_action(history)` returns over that directory sorted by round: `PASS`, `PARK`, or `REVISE` —
   same worker, same artifact path, its revision read from the round's report file — that lane's own name, `references/qc-gates.md` § 2 step 3.

**`references/qc-gates.md` owns the routing** — validating the verdict, a reviewer that returned
none, the gate mapping the orchestrator may never overrule, the revision cap — and
`references/ledger.md` the rows: every pass is its own Wave 5 row, a tier-1 bounce included, `final` empty.

## Wave 6 — Report

Write the close-out into the ledger and present it, naming which tier-2 branch reviewed (`references/qc-gates.md` § 1):

- **the inventory tally**, read from the manifest's `total`, `counts`, `selected_total` and
  `selected_counts` — never counted by hand. Every other figure in a close-out is script output, and
  the one that was arithmetic is the one two runs got wrong, both reporting 24 over a table of 23
- **what was planned**, with the artifact path per bead
- **what was merged**, with the group and the reason
- **what was parked**, with the exact question each parked bead needs answered — a park with no
  question is a dropped bead, and nobody will reconstruct the question later
- **what duplicates were dropped**, with the representative that covers each
- **the promote command and the discard command**, both ready to paste — except after a
  `--dry-run`, which stages no investigation and no plan. Give only `discard` there, and say in one
  line that promote does not apply. Printing it anyway invites promoting an empty run, and four live
  dry runs each improvised their own way of refusing because this sentence did not cover them.

## The ledger

`{run}/ledger.md` records every dispatch and every return, one row each, written **before** anything
else is done with the result — with both timestamps taken from `date -u +%Y-%m-%dT%H:%M:%SZ` at the
moment the row records, never typed from memory when rows are batched. `--resume {runid}` continues from
`staged_run.first_incomplete_wave({run})` — never from memory, and never inferred from artifacts on
disk, because a worker that died mid-write leaves a file behind. Ten columns, the resume protocol and the after-compaction rule are in
`references/ledger.md`. Read it before Wave 0, and again before resuming or reporting on a run.

## Escalation

A worker cannot ask the user. It sends its question to the main session and stops that thread.

Answer it yourself when the brief or `references/autonomy-charter.md` already covers the point; only
when neither does may you use the question tool. **A question that merely confirms what invoking
`/triage` already authorised is not worth a round trip.** The user who started the sweep chose to
stop being in the loop, so a confirmation charges them the full round trip that choice was meant to
buy. A real fork in the work is worth asking. A checkpoint is not.

A `PARK` is not an escalation. It is a finished outcome that carries its question into the Wave 6
report, where the user reads all of them at once.

## Constraints

<constraints>
1. MUST NOT mutate the tracker. Every `{tracker_cli}` call in a run is read-only. Tracker writes
   happen only in the explicit promote step, which is not part of a run.
2. MUST NOT write outside the run directory. No `~/.claude/plans` mirror, no touch of the real
   `todo/`, no source edits. This is what makes `discard` a complete undo.
3. MUST route every gate answer from the quality-control verdict — never a worker's self-assessment,
   never the orchestrator's own reading of the artifact.
4. MUST assign every worker's artifact path. A worker that names or renames its own artifact breaks
   the ledger's link to its output.
5. MUST write a ledger row for every dispatch and every return before doing anything else with the
   result.
6. MUST NOT resume a run from memory. Read `ledger.md` and `manifest.json` from the run directory.
7. MUST NOT add analysis of its own. Routing, similarity, collision and lint judgments belong to the
   scripts; a rule that feels missing is a bug to escalate, not a decision to make here.
</constraints>
