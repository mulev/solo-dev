# Promoting a run

The cold path. A run never promotes itself, so none of this is needed while a run is in
flight — `triage/SKILL.md` carries the command and the one rule that governs when to reach
for it, and everything below is what the command actually does.

```
python3 {skills_dir}/triage/scripts/promote.py --run-id {runid} \
        --runs-dir {plans_dir}/{project}/{staging_subdir} \
        --plans-dir {plans_dir} --repo-root {repo_root} \
        --system-plan-dir ~/.claude/plans [--dry-run] [--json]
```

**Promote is never automatic in v1.** A run ends at the Wave 6 report; a human reads it and then
runs this command. Never chain it onto a run, and never run it because a run looked clean.

## Where intents live

A run's tracker intents are JSON records under `{run}/intents/<bead>.json`, one list per bead — not
a manifest key. `manifest.json` is what the run *decided*; an intent is something it *did*, and
promote reads the store, never the manifest.

**The file's name is the owning bead**, and `intent_records.load_all` attaches it to every record it
returns — one source for the owner, nothing to drift, and it is what lets step 3 skip a quarantined
bead's records without the whole run stopping on them. A worker therefore never writes `bead`: the
orchestrator files what the worker returns under the bead it briefed. Where a record does carry the
field — `investigation`, `flip-source`, `dep`, `supersede`, `retitle`, `close` — it names the `bd`
target rather than the owner, and it wins over the filename.

The orchestrator derives its half before promoting:

```
python3 {skills_dir}/triage/scripts/derive_intents.py --run-dir {run}
```

Exit `1` names every bead whose outcome maps to no kind — today only a bead still in flight, whose
ledger holds no outcome yet. A duplicate is no longer one of them: the ruling is a cell in the run's
own ledger and its reasoning is an artifact the run already staged, so it derives a `close`. A
manifest written before `collide.py` emitted its `dep` endpoints is the same shape of finding: pass
the reviewed manifest with `--manifest` rather than inventing the pair. So is a bead the manifest
routed and selected for which the ledger holds no outcome row at all: the derivation names it and
the route it was routed on, and stops there — a record for a bead the run recorded no outcome for
would be an invented one. Both writers share one file per bead: a rerun of the derivation replaces
the derived records and leaves the worker's alone. The per-kind required-key table lives in
`scripts/intent_records.py`, beside the validator that enforces it.

Eleven steps, fail-closed, in this order: re-lint every staged artifact; re-check collisions against
`todo/` as it exists now; check the ledger's own clock, so a row whose `returned` precedes its
`dispatched` — or whose stamp is not the `date -u` form at all — stops the promote rather than
vouching for an artifact that dispatch never produced; verify each bead the run routed `investigate`
or `plan` still holds the state the manifest recorded; refuse to move a bead's pending artifacts when
no source-kind record of ours names them; move `investigations/` and `todo/` into the real directories; rewrite
the absolute paths inside every moved file; write the `~/.claude/plans` mirrors and back-links;
apply the tracker intents serially — epic, then tasks, then `dep add`, then the `open` flips, then
the source beads last: flipped or superseded, retitled, and a duplicate retired at the very end;
write every created ID back into the promoted plan files, resolving each `<bead:{ref}>` token by the
intent that created it, failing closed on one it cannot resolve, and sweeping every other promoted
markdown file for a token no intent names rather than letting it ship;
close the ledger and move the run under `promoted/`.

Exit `0` promoted clean, `1` findings, `2` usage or environment error. Run `--dry-run` first: it
prints the ordered `{tracker_cli}` commands and moves nothing.

`plans_dir`, `repo_root`, and the mirror root are command arguments because they are environment
the orchestrator reads from `skill.config.md`. Recording them in the run would make a staged
directory unrelocatable across checkouts or machines.

**Two of the steps are per bead, and both cover only the beads the run routed `investigate` or
`plan`.** The first is the state check: a bead whose tracker state moved since the run is
quarantined — its artifacts stay staged and its intents are skipped, while every other bead
promotes. The second is the artifact check below. A bead the run skipped is never asked about, so
it can neither block a promote nor strand one. Everything else stops the whole run. A partial
tracker apply rolls forward: rerun promote and it skips what the ledger records and creates only
what is missing. The ledger also records **where each artifact moved**, one row per artifact, which
is what lets a rerun's intents carry promoted paths — the staged file is gone by then, and without
the row the rerun would write the run directory's own path into a bead note. An artifact that is
neither staged nor recorded is `promote-artifact-missing` and stops the run before anything moves,
rather than being skipped.

**That guarantee runs in both directions.** Its mirror is `promote-intentless-artifact`: a bead
whose pending artifacts would move while the run's intent store holds no `SOURCE_KINDS` record
retiring, parking or planning that bead is quarantined alone. An artifact landing in the real
`investigations/` with nothing in the tracker pointing at it is a file nobody will find again, and
for one release nothing asked that direction — `promote.missing_artifacts` asks only whether every
artifact an outcome names still exists. The live instance is `demo-y0k` in run
`2026-08-31_4d55fd`, a duplicate whose investigation promoted into the real directory while the run
reported success; the same bead derives a `close` today and passes. The check keys on the bead and
never on the artifact, because a planned bead's Wave 2 investigation legitimately moves under the
`flip-source` record that names its plan instead — six of that run's twelve moves. Never delete a
bead to "clean up".

**A bead's existing notes survive.** `{tracker_cli} update --notes` replaces the whole field, so
every kind that writes notes onto an existing bead — the source flip, the investigation outcome, a
supersede and a `close` — reads the bead first and rewrites its marker lines only. Every other line
a human put there is carried forward. A `retitle` writes no notes at all, so it cannot race them.

**Why the mirrors and the bead notes wait until here.** Both embed absolute paths. A mirror written
during the run would point into a temporary directory, and a bead note written during the run would
send the execution skill to a path `discard` can delete. Deferring both is what keeps the invariant
under *Staging layout* true, so a worker emits a tracker *intent* carrying staged paths and promote
is what turns those into real paths and real commands.

## Which intents come from where

`intent_records.DERIVED_KINDS` and `intent_records.WORKER_KINDS` are the partition, and the two
constants are the only statement of it — never a list retyped in a brief, a skill or a test.

| Kind | Written by | Read from |
|---|---|---|
| `investigation` | `derive_intents.py` | a parked bead's outcome plus its staged investigation |
| `flip-source` | `derive_intents.py` | a planned bead's outcome plus its staged plan |
| `dep` | `derive_intents.py` | `collide.py`'s ordering, endpoints carried through as fields |
| `supersede` | `derive_intents.py` | a merged group's members plus the `create-epic` the run stored for their plan folder |
| `close` | `derive_intents.py` | a bead ruled a duplicate in Wave 2, plus the staged investigation that argues it |
| `create-epic` | the planning worker | the plan it just wrote |
| `create-task` | the planning worker | one per phase, with its parent link and slice path |
| `open` | the planning worker | one per bead the array creates |
| `retitle` | the planning or investigation worker | a bead whose title its own evidence contradicts |

The split falls where knowledge does. A kind the run can reconstruct from its own ledger, manifest,
collision report or its own stored records is derived, because a worker cannot get wrong an intent
it is never asked for. A kind that needs the planner's own decisions — the phase titles, the parent
links, the plan path that justifies the `open` flip — is the worker's, because nothing else in the
run knows them.

`dep` is derived from two inputs, not one. `collide.py`'s pre-merge ordering between beads is the
first; the second is the phase chain of a group planned into an epic, read out of the master plan's
own Dependency Table with `plan_artifact_checks.dep_table` and joined to the worker's `create-task`
records by slice filename. A pre-merge edge whose two endpoints the same epic retired is dropped —
the beads it ordered no longer carry the work, and the phase chain states that ordering between the
tasks that do. A row the join cannot resolve is a finding naming the group and the row, never a
guessed edge.

Three consequences, stated because all three are what a later reader "corrects" back:

- **A single-phase plan whose source bead already exists creates nothing.** The flip is the whole
  intent: an `open` bead whose notes carry a `Plan:` path is a workable task. A records file holding
  only a derived `flip-source` is a complete conversion, not a failed one — `demo-5srl` in run
  `2026-08-31_4d55fd` is the live instance. Adding a `create-task` there would give one piece of
  work two beads carrying the same plan path, and the flipped source bead would be the orphan.
- **A multi-bead group planned into an epic flips none of its members.** They are superseded
  instead: the epic and its phase tasks carry the work, so a member left `open` on the same plan
  path is a workable duplicate of the epic. The choice is made once, per bead, in the derived pass,
  so no bead ever comes out both flipped open and closed. A group with no `create-epic` is not an
  epic group and keeps its flips — that is the self-limit, not an omission.
- **A title correction is a record, not a hand edit.** `retitle` is the one kind both worker
  populations may write, because a corrected title is a finding only the worker that disproved the
  old one holds — and the investigation worker needs it most, since a parked bead never reaches a
  planner. It writes `--title` and nothing else, which is why it is not in `SOURCE_KINDS`: it moves
  no status, so a resumed promote has no state of its own to read back off it. The live instance is
  `demo-7qm` in run `2026-08-31_4d55fd`, corrected by hand before the kind existed — and a
  correction applied by hand is one the promote log never records and a rerun never replays.
  The same rule is what clears `promote-intentless-artifact`: a promoter who decides the file
  should land anyway moves that one file and records the move in the promote log, and the rerun
  passes. A move made by hand and left unrecorded is a move the run has no memory of, so the check
  keeps stopping on it — which is the point.
