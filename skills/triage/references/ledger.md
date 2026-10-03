# The run ledger

`ledger.md` sits at the root of every triage run directory. It exists for the same reason
`execute`'s `## Dispatch Log` does, and it earns its keep at exactly one moment: **after a
compaction, this table is the run state.** Which beads were dispatched, which returned, what each
artifact was judged to be — all of that is gone from the orchestrator's context, and the table on
disk is what remains.

**Resuming from memory is prohibited.** Not "discouraged", not "unreliable". An orchestrator that
reconstructs a run from what it remembers will re-dispatch a bead that already returned, or skip one
that never did, and both failures are silent — the ledger and the artifacts disagree and nothing
raises. Read `ledger.md` and `manifest.json` before deciding anything about a run in progress.

The two files split the job: `manifest.json` is what the run *decided* (routes, dedup clusters,
collision groups, merge decisions), `ledger.md` is what the run *did* (dispatches, returns,
verdicts, outcomes). Neither substitutes for the other.

Promote reads each bead's `final` and owned artifacts from `ledger.md`, not
from the manifest. Those are run-did facts: Wave 2 settles individual beads,
Wave 4 plan rows attach their artifact to every group member, and Wave 5 only
records review evidence for an artifact that already exists.

---

## Row format

Ten columns, one row per dispatch and one per return — the return updates the dispatch's row rather
than adding a second one.

**A Wave 5 quality-control pass is its own dispatch, so it gets its own row.** It never fills the
`tier-1`, `verdict` and `round` cells of the Wave 2 or Wave 4 row that produced the artifact. Both
readings have been run live, and folding loses evidence the run already paid for: an artifact that
tier 1 bounced and that passed on the next round has two results and one set of cells, so the bounce
is overwritten and the ledger reports a clean first pass. A second review round collides the same
way — `round` holds one number. Record a tier-1 bounce as a Wave 5 row too, with `worker` `—`, since
no reviewer was spawned for it; that row is the only place the run says why a reviewer was not spent.

The artifact row keeps the artifact's own outcome in `final`. **How** that outcome was reached is the
Wave 5 rows underneath it, and **a Wave 5 row leaves `final` empty**: the outcome is the artifact's,
recorded once, on the row that produced it. A live run wrote it on both, and the same run shows the
cost — `demo-7qm`'s Wave 2 row read `final: planned` while one of its Wave 5 rows read
`final: failed`, two rows carrying two outcomes and nothing saying which one is the bead's.

**`final` is the bead's outcome, never a worker's process result.** That `failed` was a reviewer
process that exited 1 without ever returning a verdict — not an outcome the bead ever had. A dispatch
that died is recorded by leaving `returned` empty until the re-dispatch returns: the shape the resume
protocol already reads, and the only one that says this row is still owed an answer. Spending `final`
on it loses both facts at once, the bead's outcome and the fact that a re-dispatch is due. The
re-dispatch goes out at the same round, since no verdict was produced and so no round was spent, and
two consecutive deaths on the same artifact end the loop and escalate to the user.
`references/qc-gates.md` § 1 states the same rule from the reviewer's side.

| Column | Content |
|--------|---------|
| bead | bead ID |
| wave | `0`–`6` |
| worker | agent name, or `—` for a main-session wave |
| dispatched | UTC to the second, `date -u +%Y-%m-%dT%H:%M:%SZ` |
| returned | UTC to the second, or empty while in flight |
| artifact | absolute path inside the run directory — promote's pre-flight reports a relative one, which is the check a wave row goes through: you write these rows yourself, so `staged_run.ledger_row`'s refusal covers only the rows a script writes (the seeded header and the promote log) |
| tier-1 | `PASS` / `FAIL` / `—` |
| verdict | the `triage-qc` verdict, or `—` |
| round | revision round number, starting at 1 |
| final | `planned` / `merged` / `parked` / `duplicate` / `failed` |

```
| bead | wave | worker | dispatched | returned | artifact | tier-1 | verdict | round | final |
|------|------|--------|------------|----------|----------|--------|---------|-------|-------|
| demo-2xc | 5 | triage-qc | 2026-08-28T14:20:10Z | 2026-08-28T14:31:52Z | .../investigations/opds_stall.md | PASS | PASS | 1 |  |
| demo-2xc | 2 | invest-1 | 2026-08-28T14:02:11Z | 2026-08-28T14:19:40Z | .../investigations/opds_stall.md | — | — | 1 | planned |
| demo-9k1 | 2 | invest-2 | 2026-08-28T14:02:14Z |  | .../investigations/import_hang.md | — | — | 1 |  |
| c1 | 1 | dup-judge | 2026-08-28T14:01:02Z | 2026-08-28T14:01:44Z | .../judge_brief.md | — | related-not-duplicate | 1 |  |
| all | 0 | — | 2026-08-28T14:00:31Z | 2026-08-28T14:00:33Z | .../manifest.json | — | — | 1 |  |
```

### The row kinds

Ten columns, five kinds of row. Which columns carry meaning depends on the kind, and a column that
means nothing for a kind is `—` when the kind can never fill it and empty when it is simply not
filled yet.

| kind | written by | `bead` | `verdict` | `final` |
|------|-----------|--------|-----------|---------|
| the artifact row | Waves 2 and 4 | the bead ID | `—` — the review is its own row | the bead's outcome |
| the quality-control row | Wave 5 | the bead ID | the `triage-qc` verdict | empty |
| the decision record | Wave 4 | the group ID | `—` — nothing was produced to review | why no plan exists: `parked` or `duplicate` |
| the cluster row | Wave 1 | the group ID | that group's dedup ruling | empty |
| the wave row | Waves 0, 1, 3, 6 | `all` for the wave's own script run, and the group ID for each group it produced | the group's collision decision on Wave 3, else `—` | empty |

The decision record is the one Wave 4 row that is not an artifact row, and the table has to say so:
read as an artifact row it claims an artifact of `—` and a bead's outcome it does not have, which is
the reading that stranded a resume at Wave 5 and fed `promote` a path that is not one. § *Row format*
below says how one is written, and *Resume protocol* says why it owes nothing.

**`verdict` holds whichever ruling its row carries** — the `triage-qc` verdict on a quality-control
row, the dedup ruling on a cluster row, the collision decision on a Wave 3 group row. Wave 1's judge rules `duplicate` /
`distinct` / `related-not-duplicate` on a cluster, which is neither a `triage-qc` verdict nor a
per-bead outcome. The first live demo run had nowhere to put that ruling: it went into `final`,
whose vocabulary is `planned` / `merged` / `parked` / `duplicate` / `failed`, and the ledger had to
be rewritten to point at `manifest.json` instead. A wave whose output lives only in the manifest
breaks this file's opening claim — a resumed run reading `ledger.md` alone could not tell whether
the judge had ruled.

`final` stays empty on a cluster row because nothing about a bead is settled at Wave 1: a cluster
ruled `duplicate` still needs its members' own rows before any of them is `duplicate` or `planned`.

**One row per group, not per cluster or per wave.** The judge rules on `clusters[].groups`, and it
may partition a cluster — `references/deduplication.md` allows it and a live demo run did it,
splitting `c1` into three beads ruled `related-not-duplicate` and one ruled `distinct`. One row
cannot hold that: `verdict` is a single cell, and the run wrote `related-not-duplicate + distinct
(partitioned)` into it, a value outside the three the judge is allowed to return. So a partitioned
cluster gets a row per group, keyed by the group ID, each carrying its own verdict; an unpartitioned
one is the same rule with a single group.

**The group ID comes from `cluster_ruling.identify`, never from the orchestrator.** A judge's ruling
arrives unnamed, and while these rows were keyed by a name nobody assigned, three live runs invented
three formats — `c1-g1`, `c1-g1`, `c1g1` — and one of them wrote rows whose group appears nowhere in
the manifest. A row that cannot be matched back to what it describes is the one thing this table is
for.

**Which leaves the dispatch row, written before the groups exist.** `identify` needs a ruling, and a
row is owed before the judge is dispatched, so the two rules above cannot both be satisfied by one
key: that row carries the **cluster ID**, and the ruling's return replaces it with one row per group.
That is the ordinary "the return updates the dispatch's row" rule with a partition in it — one row
in, several out — and it is the one place in this file where a row's `bead` cell changes.

**Replacing it is not rewriting the ledger.** The header is the thing that may never be retyped; the
rows beneath it are written as they are learned. Read append-only literally and the `c1` row keeps an
empty `returned` for the life of the run, `first_incomplete_wave` reports Wave 1 outstanding on every
resume, and the judge is re-dispatched forever. A live run replaced the row correctly and was told by
a reviewer to put it back, which is how far apart the two readings sit.

**Why the header is the one line that may never be retyped.** Those ten column names are what every
rule in this file is written against, so a run that replaces the header with one it typed puts the
schema back where seeding took it from — whatever the session remembered. `SKILL.md` used to state
the prohibition as "append rows; never rewrite it", which a live run's reviewer read as append-only
rows: the reading that strands every Wave 1 dispatch row unreturned. The hot path now says only
"never retype that header", and keeps the `Mode:` line `create_run` seeds for the same reason — it
is the run's own answer to what a resume is continuing (§ *Resume protocol*).

Wave 3 works the same way and for the same reason — one row per collision group, keyed by the group
ID, **with its `MERGE` / `SEQUENCE` / `INDEPENDENT` / `UNCLASSIFIED` decision in `verdict`**. Two
live runs read this differently, one writing nine `UNCLASSIFIED` rows and the other a single `all`
row that recorded no decision at all; the nine are right — **alongside** the `all` row for
`collide.py`'s own run, not instead of it, per the two-rows rule below.

Naming the column matters because the first draft of this rule did not. It said the decision needed
"somewhere to live" while the table above still gave a wave row `verdict` `—`, and the next two runs
split on exactly that: one wrote `—`, one wrote `UNCLASSIFIED`. `verdict` is right — the column
already holds whatever ruling its row carries, which is why a cluster row uses it for the dedup
ruling rather than getting a column of its own.

**Bare dates are not acceptable in the timestamp columns**, for the reason `execute` item 7 gives:
the row's job is to line up against the artifact's own stamps, and a date cannot say whether a
result was earned before or after its own dispatch. A row whose `returned` precedes its `dispatched`
is a run that reused a stale artifact.

**Nor is a stamp you typed.** Every value in `dispatched` and `returned` is the output of

```
date -u +%Y-%m-%dT%H:%M:%SZ
```

run at the moment the row records — once before the dispatch, once when the result comes back. Never
a rounded minute, never a value carried forward from an earlier row, never nine rows sharing one
value because they were appended together. That last shape is how this was found: a live run's Waves
0 and 1 carried measured stamps while its nine Wave 3 rows all read `08:49:04` and its close-out read
`08:50:00`, typed from memory when the rows were batched at the end.

A written stamp is indistinguishable from a measured one, which is exactly the problem — the whole
ordering check above assumes the numbers were observed. A ledger of invented stamps still passes
every eye and proves nothing, so the run looks audited and is not. If a row is being written late,
that is the defect; write it on time rather than reconstructing what its clock would have said.

**A re-dispatch row's `returned` is measured when its report is read.** A `REVISE` reaches a worker
whose job leg expired ten minutes earlier, so the observable event is not the worker finishing — it
is the orchestrator opening `{run}/reports/<bead-id>_r<round>.md` and finding the contract fields
parse. Take `date -u` at that moment. An artifact's mtime is never the source: run `2026-09-02_3f7d`
row 9 used one, and an mtime says when a file was written, possibly by a worker that then died
mid-write, rather than when a result was taken — which is both prohibitions above at once.

A row is written **before** anything else is done with a dispatch or a result. A verdict acted on
before it is recorded is a verdict that vanishes if the session dies between the two.

Waves with no per-bead work still get a row — `0`, `1`, `3` and `6` are main-session waves, so their
`worker` is `—`. Such a wave records **two different things, and owes a row for each**: the script it
ran, keyed `all`, and every group that script's output was ruled into, keyed by the group ID.

Wave 0 and Wave 6 make no groups, so `all` is all they have. Waves 1 and 3 have both, and the two
are not substitutes: a Wave 1 whose only rows are `c1-g1` and `c1-g2` has recorded the judge and
left nothing saying `dedup.py` ran, when it ran, or that `judge_brief.md` came from it. The group
rows carry the judge's clock, not the script's. This is a correction — the first draft of the rule
above said `all` was "only for Wave 0 and Wave 6", which read as forbidding the script row on any
wave that produced groups, and two live runs duly dropped it.

**A group nobody planned still owes a Wave 4 row.** A collision group whose beads are all parked or
duplicate gets no planner, correctly — and a run that then writes nothing for it is indistinguishable
on the page from a group that was dropped. The row is written with `worker` `—`, `artifact` `—`, both
stamps measured at the moment the decision is taken, and `final` naming why no plan exists: `parked`
or `duplicate`. A live run left `g4`, `g5` and `g6` — holding its two parked beads and its retired
duplicate — with a Wave 3 row and nothing after it. The row costs one line and is the only place the
run says the omission was a decision rather than a loss.

An `artifact` of `—` is load-bearing: a reader that collects artifacts off Wave 4 rows must skip it,
or it hands promote a path that is not one. `staged_run.recorded` is that rule in code, and
`first_incomplete_wave` reads the same cells to tell a decision record from an artifact still owed a
gate. `staged_run.relative_artifact` is the one test both absoluteness surfaces go through, and it
reads the sentinel through `recorded` — so neither of them can mistake `—` for a relative path.

---

## The recorded investigation hashes

`{run}/hashes.txt` is the run's second provenance file, and it has exactly one consumer:
`lint_plan.py --investigation-hash-file`. Wave 4 appends one line per investigation **at the moment
it hands that investigation to a planner** —

```
shasum -a 256 <absolute investigation path> >> {run}/hashes.txt
```

— which writes `<sha256>  <absolute path>`: hash first, path second, the order
`lint_plan.expectations()` parses. (`sha256sum` prints the same two fields where it exists; macOS
ships `shasum`.) The path must be absolute, because the linter resolves it and matches it against the
plan's own `**Investigation:**` link.

Wave 5 then passes the file and the plan's `background` check reports a real comparison. Without it
the check reports `SKIP background — no hash was recorded … the comparison was skipped, not passed`,
which is the state every plan of every run to date has linted in.

**A missing or unlisted hash stays a `SKIP`, never an error.** `plan_artifact_checks.py` already
behaves this way and must keep behaving this way: a run whose Wave 4 predates this file, or a plan
built from no investigation at all, has nothing to compare and is not thereby defective. The one
thing the check may never do is pass silently.

A later revision of the investigation changes its hash and the lint then reports a mismatch. That is
the finding, not a false alarm: the plan on disk was written against a different investigation than
the one on disk now, and one of the two has to move.

---

## Resume protocol

`--resume {runid}` reads `ledger.md` and `manifest.json` from the run directory and continues from
the first incomplete wave.

**Read the `Mode:` line above the table first.** `create_run` seeds it, and it is the run's own
answer to what is being continued: a `--dry-run` stops after Wave 1 and dispatches one judge, so a
resume that assumes a full run walks into Wave 2 and spends workers the invocation never asked for.
A ledger whose mode reads `unrecorded` cannot answer that — treat it as a dry run, the cheaper of
the two wrong guesses, and say so in the report.

**A wave is incomplete when any row belonging to it has an empty `returned`.** That is the whole
dispatch test — do not infer completeness from the presence of artifacts on disk, because a worker
that died mid-write leaves a file behind.

**An artifact row that returned and has no Wave 5 row carrying a terminal verdict — `PASS` or
`PARK` — for the same artifact makes Wave 5 incomplete.** Not Wave 2, and not Wave 4: the artifact
came back, so the work that is missing is the gate. A resume pointed at the producing wave
re-dispatches an investigation that already returned and overwrites an artifact that was already
paid for, which is the failure this protocol exists to prevent. A Wave 4 row that names no worker and
no artifact is the exception: it is a decision record — § *Row format* says how one is written — so
there is no artifact to gate and the row owes nothing.

**`final` is not a completeness signal, on any row kind.** It records an outcome once that outcome
is known, and for a Wave 2 row that is not until Wave 4 or Wave 5 settles the bead — so between
Wave 2 and Wave 6 an empty `final` is the normal state of a healthy run, not a row owing work. A
column that fills in later cannot be a readiness test for the wave that wrote it. The earlier rule
tested it, and a live run working Wave 5 with all nine of its investigations returned was told to
restart at Wave 2; the same shape one wave down had already been fixed for cluster rows, which leave
`final` empty by design (see *The row kinds*). Which row kind owns `final` is a separate
question from which rows a resume owes work: `final` answers "how did this bead end", and only the
artifact row can answer it.

- A row dispatched but never returned is **re-dispatched**, and its stale artifact, if one exists, is
  overwritten at the same assigned path. The path was assigned by the orchestrator and does not
  change on a re-dispatch; a second path would orphan the first artifact and break the row's link to
  its own output.
- An artifact row that returned with **no terminal Wave 5 verdict for its artifact** resumes at its
  Wave 5 quality control, at the round named by the **last Wave 5 row for that artifact** — or round
  1 when the artifact has none, which is exactly what an interruption before the first review looks
  like. The condition is the missing gate, never an empty `final`: a row can carry an outcome and
  still be ungated, and a decision record carries `parked` or `duplicate` while owing nothing.
  Rounds are not restarted: the round counter is what `next_action()` in `validate_verdict.py`
  consumes, and resetting it hands a worker a third revision it already spent.
- **Never start a new run directory to recover an old one.** A second directory splits the run's
  state across two ledgers, and neither one is then the answer to "what happened".

A run whose ledger is unreadable or whose manifest fails to load is not resumable. Say so and stop:
`discard` that run and start a clean one, rather than guessing at what it had done.

---

## After a compaction

Before dispatching anything, before writing any close-out, and before answering any question about
what the run has done:

1. Read `ledger.md` in the run directory.
2. Read `manifest.json` in the same directory.
3. Only then decide the next action.

This is the same rule `execute` states for an epic's Dispatch Log, and it is here for the same
reason: the cheapest possible way to lose a day's work is to trust a memory that was summarised
away.
