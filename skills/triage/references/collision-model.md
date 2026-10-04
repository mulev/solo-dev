# The collision model

Two beads planned in isolation can be planned into contradictory rewrites of
the same code. One changes a method's signature; the other plans against the
old one. Both plans are correct on their own, and the second is wrong the
moment the first lands. Catching that is the whole reason this model exists.

`triage/scripts/collide.py` executes it. This file is the reasoning behind it.

## 1. The three key kinds

A footprint is what one bead's approved work will touch. It carries three
kinds of key, and files alone are not one of them.

| Kind | What it holds | Why it is in the model |
|---|---|---|
| `files` | repo-relative paths the change touches | the obvious collision: two beads editing one file |
| `modules` | the feature or domain module each path belongs to | readable reporting, and it orders a SEQUENCE group |
| `symbols` | public classes, functions and constants whose **contract** the change alters | the collision that hurts most, and the one files miss |

**Files alone are insufficient.** Bead A changes `OpdsTestServer.start` to take
a client. Bead B writes a new test file that calls the old two-argument form.
They share no path. Under a files-only model they do not overlap at all, both
plans read as correct, and B is broken the moment A lands. The symbol set is
the only key that catches it.

## 2. Where a footprint comes from

| Source | Where the content comes from | Cost |
|---|---|---|
| Investigated beads | `investigate` Gate 2 already produces **What changes** file by file and **Side effects considered** caller by caller. The brief requires the worker to emit exactly that as a `footprint:` block. | free — the analysis already happened |
| Plan-only beads | no investigation exists, so a read-only **footprint pass** runs before planning: one agent per bead whose entire output is a file, module and symbol list. | one short read-only agent per bead |

The footprint pass produces no analysis and no fix opinion. It is a locator,
not an investigator: it answers "what code does this bead's title point at".
If that question needs a root-cause argument to answer, the bead was
mis-routed and belongs in `investigate`.

### The block grammar

```yaml
footprint:
  bead: demo-13xd
  files:
    - path: demo/test/helpers/opds_test_server.dart
      module: demo/test/helpers
      change: modify          # add | modify | delete
  symbols:
    - name: OpdsTestServer.start
      kind: method            # class | method | function | constant
      change: signature       # add | signature | behavior | remove
  modules:
    - demo/test/helpers
    - demo/lib/features/opds
```

Mapping from Gate 2, which is what makes investigated beads free:

- each numbered line of **What changes** becomes one `files` entry, its
  `{File}` becoming `path`;
- any of those lines naming a symbol whose signature or contract moves becomes
  one `symbols` entry with `change: signature`;
- each line of **Side effects considered** naming a caller of a changed symbol
  puts that caller's file in `files` with `change: modify` if the fix touches
  it, and its symbol in `symbols` with `change: behavior` if only behaviour
  shifts;
- `modules` is derived, never authored: the module of a path is its nearest
  enclosing feature or domain directory, matching the coupling definition in
  `_shared/architecture-principles.md`.

### What turns a block into a footprint

`triage/scripts/footprints.py`, and nothing else. Wave 3 step 2 runs it over
the run's `<bead>=<artifact>` pairs: it reads the block above off each
worker's own artifact — the report carries counts, the artifact carries the
enumeration — validates its shape, and writes `{run}/footprints.json` as a
**bare list**. That shape is not a preference: the promote-time re-check in
section 7 reads a bare list and only a bare list, while `collide.py` accepts
either, so the list is the one shape both readers take.

A block it cannot read is reported, never raised on. An entry that is not a
record would raise inside `collide._paths`, so it is named as a finding and
its bead reaches the report through section 6's roster rule instead. What the
validation does *not* judge is completeness: a block that parses is written as
it stands, because whether a footprint named enough is a question about the
worker's analysis, which this script cannot see and a reviewer can.

## 3. The grouping rules

Edges come from a shared file path or a shared symbol name. `group()` takes
connected components of that graph, not pairs, because transitivity is real:
if A overlaps B and B overlaps C, whatever B does to reconcile A's work is the
same edit C must plan against. A decision is taken per component.

| Component | Decision | What the orchestrator does with it |
|---|---|---|
| overlap present, **same** underlying cause | `MERGE` | one multi-phase plan, one epic, the beads becoming its phases |
| overlap present, causes distinct | `SEQUENCE` | one ordered planning group, `bd dep` intents emitted so execution order is forced rather than accidental |
| no overlap | `INDEPENDENT` | plannable in parallel with any other group |

**MERGE for same-cause overlap is the decided resolution and is not
configurable in v1.** Merging is what puts the incompatible directions in
front of one planner in one context, which is the only place they can be
reconciled. Two planners each holding half the picture cannot agree however
carefully they are ordered — sequencing a same-cause pair only decides which
of the two contradictory rewrites lands second.

Cause keys are compared by **exact equality and never inferred**; no script in
this epic makes an LLM judgment. A bead with no cause key on record gets its
own bead ID as its key, so two unknown causes are never equal and the pair
sequences instead of merging. That asymmetry is deliberate: a wrong merge
fuses two unrelated beads into one epic and is expensive to undo, while a
redundant ordering edge costs only ordering.

Inside a `SEQUENCE` group the bead whose footprint moves a symbol contract
(`change: signature`) goes first, because everything else in the group must be
planned against the new contract rather than the old one. Ties break on the
narrower change (fewest modules), then on bead ID for determinism.

**A `SEQUENCE` decision does not promise the beads stay separate.** It decides
the grouping and the order, not the plan shape: the planner it dispatches may
still write one multi-phase plan for the group, and both `SEQUENCE` groups in
run `2026-08-31_4d55fd` did. When it does, `derive_intents.py` supersedes the
members with the epic that replaced them and derives the phase chain from that
plan's own Dependency Table — so the ordering this decision made survives, on
the tasks that now carry the work. `references/promoting.md` owns that half.

`dep_intents` are text, never tracker writes. Nothing in this phase mutates
`bd`. Each entry also carries its endpoints as `from` and `to` beside the
command text, so the promote step builds a `dep` record from fields instead of
parsing a command string.

## 4. Why module-only overlap does not group

Two beads touching the same feature module, with no shared file and no shared
symbol, are working in the same neighbourhood — not on the same thing.

Grouping on module membership would collapse most of a backlog into one
unmanageable epic, which is a worse failure than the one this phase prevents.
So module overlap never creates an edge. It is carried in the footprint for
two other reasons: it makes a readable report, and it orders a SEQUENCE group.

The run report lists every module-only overlap under **Module-only overlaps
(did not group)**, so what the model declined to group is auditable rather
than invisible.

The live run over `fixtures/footprints_demo_opds.json` is the case in point.
`demo-13xd`, `demo-njar` and `demo-6dq` all concern OPDS test harnesses
and injected collaborators, and all three touch
`demo/test/features/opds/screens`. They share no file and no symbol, so the
model returns three `INDEPENDENT` groups and reports the module overlap. A
module-level model would have fused all three into one epic.

## 5. The late-duplicate net

Two beads whose footprints are **identical** — the same file set and the same
symbol set — are the same bug that dedup missed. They are merged, flagged
`late_duplicate`, and the miss is recorded in the run report so the dedup
threshold can be tuned.

This is a deliberate second net, not an edge case handled in passing. Dedup
matches on title similarity and tracker edges, which cannot see two
differently-worded reports of one defect; the footprint can, because by this
point the work itself has been described. `deduplication.md` section 5 already
announces this check, so a finding here is the second net doing its job rather
than a defect in the first.

The flag is raised before any cause comparison: two identical footprints are
one bug whatever their cause keys say. Two *empty* footprints are excluded —
identical in the trivial sense only, and merging on the strength of no
evidence is exactly the wrong-merge this model exists to avoid.

## 6. The roster rule: nobody leaves the run in silence

Groups are built from footprints. The manifest is the run's roster. Those are
two different lists, and the difference between them is exactly the set of
beads that used to disappear.

So the two are cross-checked. Every manifest bead routed `investigate` or
`plan` and not already dropped by dedup appears in exactly one record. A bead
the footprints never accounted for gets its own record — decision
`UNCLASSIFIED`, reason `no footprint on record — collisions could not be
checked` — is listed in the collision report like any other group, and makes
the run exit 1.

It is a finding, not a silence. A worker that parked, or a `footprint:` block
that came back malformed or absent, is a fact about the run somebody has to
see; the alternative is a bead with no group, no decision, no report line and
an exit code of 0. A redundant review costs a paragraph. A dropped bead costs
the whole task.

Three routes are exempt, and each for a reason rather than convenience:
`skip` beads are not in the run at all, `drift-report` beads are reported by
inventory and never planned here, and a bead dedup dropped already left the
run by an explicit, reported decision. Flagging any of those would be crying
wolf, which is how a real finding stops being read.

`UNCLASSIFIED` records carry the same keys as a decided group, so they render
in the report's existing loop and write back into the same `groups` list. A
second top-level manifest key would give a reader two places to look for who
is in this run.

The report itself is rendered by `collision_report.py`, which is pure over
these records — it reads the fields they carry and knows nothing about how a
group was formed. That is why an `UNCLASSIFIED` entry needed no rendering
branch of its own. `collide.py` computes; `collision_report.py` writes it down.

### The dry-run case

A `--dry-run` dispatches no worker, so it has no footprints at all. The roster
rule already answers it: run `footprints.py` with no pairs — an empty pair list
writes `[]`, which is the whole dry-run path — then `collide.py` over it, and
every selected bead comes back as its own one-member `UNCLASSIFIED` group with
the same `no footprint on record` reason, and the run exits 1. Run the script
rather than typing the file: a hand-written `footprints.json` is the same hand
step this file's section 2 gave an owner, at a smaller size.

Read that as the finding it is — *this run cannot say what collides* — and not
as a broken wave. It is the same statement a parked worker's bead makes, at the
scale of the whole run, and a full run recomputes all of it from real
footprints.

**Running it is not optional, and the orchestrator does not get to answer
instead.** SKILL.md's dry-run clause promises collision groups, and a phrase
like "not computed" in their place is the orchestrator ruling on a question
`collide.py` already rules on — constraint 7, in the one spot that most looks
like an exception, because the wave's own barrier rule seems to forbid running
it. It does not: no workers is a complete set of workers, not a partial one.
This was found in a live omp dry run on `demo`, where the first close-out
said "not computed" and nine beads left the run with no decision recorded.

## 7. The promote-time re-check

A run's groups are correct for the moment they were computed and for nothing
else. Plans can land from other sessions while a run is staged, so a second
collision check runs at promote time against `todo/` as it exists *then*.

A group computed an hour ago against a `todo/` that has since gained a plan
covering one of its members is stale, and promoting it would stage exactly the
contradiction this model exists to prevent.
