# e2e testbed

`make_testbed.sh` builds a disposable world for the end-to-end suites: a real
git repo with a real bd database, a second smaller database, and a plan corpus.
Everything it builds is generated from the committed fixtures here — a Dolt
database does not belong in git, and a committed snapshot rots where a
generated one is reproducible.

## What is committed

- `fixtures/beads.json` — the 20-bead matrix loaded into `triage-testbed`, and
  it adds up as nine plus two plus nine. Nine beads sit behind the six rows of
  `../references/classification.md`'s routing table, because three of those
  rows carry two each. Two more exist only for a precedence rule — `tb-both`
  for rule 3 and `tb-unk` for rule 4 — while rules 1 and 2 are covered by
  `tb-clsepc` and `tb-epc`, already counted among the nine. The last nine are
  the wave beads later suites consume. Each bead carries an `expect` block
  naming the route and reason `inventory.classify` must return for it.
- `fixtures/beads_clean.json` — the single bead loaded into
  `triage-testbed-clean`. It exists because the main testbed carries a drift
  bead (`tb-drf1`) by design and can therefore never produce `inventory.py`'s
  exit-0 case.
- `fixtures/src/` — the citable source tree copied into `triage-testbed` and
  committed as its initial history. Bead titles cite `file.py:line` into it,
  so its line numbers are load-bearing.
- `fixtures/plans/` — the plan corpus copied into `triage-testbed-plans/`,
  carrying one strong citation (`tb-cov1`), one beads-table row (`tb-cov2`),
  one bare mention (`tb-cov3`), and the investigation `tb-pln1` routes on.

The exit-code suite adds its own artifacts, one matched clean/defective pair
per linter, so no case inlines the thing it lints:

- `fixtures/investigation_ok/` and `fixtures/investigation_bad/` — the second
  drops `## Ruled Out` and hedges once, so `lint_investigation.py` reports
  exactly `section-missing` and `assumption-language`. Both are linted with
  `--root` at their own directory and `--repo` at the testbed, whose `lib/`
  tree is what their citations resolve against.
- `fixtures/plan_ok/` and `fixtures/plan_bad/` — one plan folder each. The
  folder inside carries the name `lint_plan.py`'s shape check requires
  (`{project}_{kind}_{short_name}`), and it holds two phases because a
  single-phase plan written as a folder is itself an error. The defective one
  differs in one line: its `## Verification` names an invented command.
- `fixtures/verdict_valid.json` and `fixtures/verdict_invalid.json` — the
  second is a `PASS` carrying a defect, the cross-field contradiction no JSON
  schema can express.
- `fixtures/footprints.json` and `fixtures/footprints_merge.json` —
  `collide.py`'s exit 0 (one bead, one file nothing else touches) and its
  exit 1 (two beads with byte-identical footprints, a late duplicate).

### Fixture artifacts — the verdicts the QC suite routes

`fixtures/artifacts/verdicts/` holds ten hand-written verdict objects, one per
branch of `validate_verdict.next_action`. `suite_qc.py` is the only reader.

| File | Shape | Read by |
|---|---|---|
| `pass.json` | round 1, `PASS`, `defect_class: none`, no defects | the tier-1-gates-tier-2 cases, and every case that needs a verdict the router will accept |
| `revise_round1.json` | round 1, `REVISE`, `repairable`, defects at `a.md:10` and `a.md:20` | `case_round_one_revise_sends_it_back`, and round 1 of both round-2 pairs |
| `revise_round2_converged.json` | round 2, one defect at `a.md:10` — a **strict** subset | `case_converged_round_two_unlocks_a_third_round` |
| `revise_round2_restated.json` | round 2, the same two locations again | `case_restated_round_two_parks` |
| `park_round2_diverged.json` | round 2, one defect at `b.md:5`, a location round 1 never named | `case_diverged_round_two_parks` |
| `park_root_cause_unproven.json`, `park_requirement_invented.json`, `park_stop_list.json` | round 1, `PARK`, one hard class each | the three cases generated from `validate_verdict.HARD_CLASSES` |
| `park_with_question.json` | round 1, `PARK`, `why` phrased as a real question | `case_park_carries_a_question` |
| `invalid_missing_confidence.json` | `PASS` with `confidence` deleted | `case_invalid_verdict_is_rejected_before_routing` |

Round 1 carries **two** locations on purpose. `_converged` in
`validate_verdict.py` requires round 2 to be a strict subset, and a one-defect
round 1 makes convergence unreachable — the equal sets would park, which is
`revise_round2_restated.json`'s job, not the converged pair's.

There is deliberately no second copy of a clean investigation or a clean plan
here. `suite_qc.py` and `staged_fixture.py` lint and promote the
`investigation_ok/`, `investigation_bad/`, `plan_ok/` and `plan_bad/` fixtures
the exit-code suite already committed: they cite the testbed's own source tree
and already lint to the exit codes these suites need, so a parallel set under
`artifacts/` would be the same bytes under a second name, drifting the moment
one of them was edited.

`__TESTBED_PLANS__` is the placeholder for the corpus root. `make_testbed.sh`
substitutes it in bead notes and in corpus markdown, because the absolute path
is only known once a build picks a `--root`.

## What is generated

`triage-testbed/`, `triage-testbed-plans/` and `triage-testbed-clean/` are
built by `make_testbed.sh`, gitignored, and disposable. Never edit them by
hand — re-run the script, which wipes and rebuilds all three.

```sh
sh triage/e2e/make_testbed.sh [--root DIR]
```

## What checks it

- `../scripts/test_e2e_matrix.py` runs in the `phase-exit` stage and proves the
  fixture data is complete and correct — every bead through the real
  `inventory.classify`, every corpus citation through the real
  `plan_coverage`. No bd, no git, no subprocess.
- The generator itself is exercised by the `e2e` stage, which runs it for real.

## Running the suites

```sh
python3 triage/e2e/run_e2e.py                  # every deterministic suite
python3 triage/e2e/run_e2e.py --only routing   # one suite
python3 triage/e2e/run_e2e.py --only exit-codes --keep
python3 triage/e2e/run_e2e.py --live           # and the live suites — real agents
```

`--only NAME` runs a single suite; the names are the keys of `run_e2e.SUITES`.

**A failing run always keeps its trees**, and prints the path it kept. `--keep`
is only needed to inspect a run that *passed*. The default used to be the other
way round, and it destroyed the evidence in exactly the case that wanted it: a
live orchestrator run died mid-sweep on a usage limit, and the teardown took the
run directory with it, so the only way to see what the agent had done was to
spend the whole run again. When the driver does remove a tree it removes only
one carrying the `.triage-testbed` marker, the same rule `make_testbed.sh`
applies before it wipes. `--root DIR` builds somewhere other than the skills
repo.

The driver builds the testbed once, asserts the database guard, then prints one
`PASS`/`FAIL` line per case and exits 1 if any case failed — the reporting shape
`../scripts/run_tests.py` already uses. Suites are imported lazily, so
`--only routing` never loads a suite it is not going to run.

**`SUITES` is ordered, and the order is load-bearing.** `suite_promote` and
`suite_lifecycle` create real beads in the testbed's tracker, while
`suite_routing` asserts that every bead the manifest routes is one
`fixtures/beads.json` declares. Read-only suites therefore run first, and the
driver iterates `SUITES` in insertion order rather than sorting it. Nothing
leaks between invocations — every run wipes and rebuilds all three trees.

## Why verdicts are fixtures here

`suite_qc.py` feeds hand-written artifacts *and* hand-written verdicts, and
dispatches no agent at all. What is under test is the orchestrator's routing of
a verdict — which worker gets it, at which path, and what the convergence
policy decides — never an agent's ability to produce one.

Mixing the two makes a red run ambiguous: a suite that spent a live reviewer
and then asserted on the routing cannot tell "the router regressed" from "the
model had an off day", and a test that cannot distinguish those two is not a
test. Live reviewers belong to Suite C, where the oracle asserts the *shape* of
what an agent returned and a red run means an agent misbehaved.

The instrument is the `Reviewer` stub in `suite_qc.py`. It counts its own
calls, so "tier 2 never ran" is asserted rather than assumed, and it raises
when a case asks it for a verdict the case never queued — a router that spends
an unplanned revision round fails loudly instead of reading a fixture off the
end of a list.

## The `system_plan_dir` guard

`promote.write_mirrors()` takes `system_plan_dir` from `--system-plan-dir`,
which is **required** — a promote that omits it exits 2 rather than resolving
`~/.claude/plans`. What the guard still covers is a fixture that *passes* a
real path: `stage_run` accepts a `system_plan_dir` argument, and a case that
handed it the operator's own tree would write mirror files outside the testbed,
outside `discard`'s reach, and not recoverable by re-running anything. (It read
`data["system_plan_dir"]` from the manifest until `skills-way.2` made the four
promote roots command-line arguments, and the flag defaulted to `~/.claude/plans`
until Phase 1 of `skills_fix_guard_scope_collapse` made it required; the risk
moved from an absent key to an unpassed flag to a wrongly-passed one, and the
guard covers all three.)

The guard is `assert_inside_testbed` in `staged_fixture.py`, and it runs inside
`stage_run`, the one builder every promote and lifecycle case starts from. That
placement is the point: a guard written as a `case_*` is one a new case can
forget to copy, while a guard in the builder cannot be skipped without
bypassing the fixture entirely. It raises before any directory is created, so a
refused manifest leaves nothing on disk —
`suite_promote.case_a_manifest_outside_the_testbed_is_refused` asserts both
halves.

`suite_promote.case_the_home_plans_mirror_is_never_written` is the measured
half: it hashes every file under `~/.claude/plans` before and after a full
clean promote and compares before against after, then asserts the mirror landed
in the testbed — a passing before/after would otherwise prove only that
`write_mirrors` never ran. `suite_lifecycle` does not repeat that check;
nothing in it promotes, and `write_mirrors` is the only code in the triage
system that can write there.

## Two gaps these suites pin rather than paper over

- **`skills-p1j`** — `tracker_intents._verify` reads `bd show <bead>` in its
  human format, which hard-wraps the notes block at ~60 columns and breaks any
  real absolute path mid-token. Every promote that writes a note therefore
  reports `promote-notes-unverified` even though the note landed correctly, and
  `promote._close` never moves the run under `promoted/`. The clean and rerun
  paths assert exit 1 with exactly that code, and
  `case_notes_verification_cannot_read_a_wrapped_bd_show` pins the wrap itself
  so the day it is fixed the suite says so.
- **`skills-j4q`** — `../references/ledger.md`'s resume paragraph used to say a
  wave is incomplete when any of its rows has an empty `final`, while the same
  file's row-kind table says a cluster row's `final` stays empty by design.
  Read literally, Wave 1 was incomplete forever. Closed by `skills-way.6`:
  `final` is no longer read for completeness at all, so the carve-out this
  entry described is now a consequence of the general rule — a row is
  outstanding when its `returned` is empty, and an artifact row that returned
  and was never gated makes Wave 5 incomplete, never the wave that produced it.
  `case_a_complete_wave_one_cluster_row_is_not_incomplete` still pins it.

Both follow the rule `skills-lyo` set below: a suite that quietly works around
a gap it found is the dishonesty this epic exists to prevent.

## The harness contract

`harness.py` owns three things and nothing else.

- `build(root=None)` runs `make_testbed.sh` and returns a `Testbed`: the three
  generated trees, a `scratch` directory every suite writes into, and the bead
  IDs the fixture declares. One call per driver run is a full rebuild, so no
  suite inherits another's writes.
- `env(testbed)` and `run(script, *args, testbed=...)` are the only way a suite
  reaches a triage script. `run` starts a real process — that is what makes the
  exit-code suite cover argument parsing — and passes `TRIAGE_PROJECTS_ROOT`,
  one of the two isolation seams this epic is allowed to use. It runs the
  repo's own scripts, never a copy, and picks the launcher by suffix — this
  interpreter for a `.py` CLI, `sh` for a shell generator — so a launch
  depends on neither a file's shebang nor its mode.
- `assert_db_inside(testbed)` is the guard below.

`staged_fixture.py` owns the fourth thing, and it is a separate module rather
than the `harness.staged_run()` the epic's plan first drew. Building a
promotable run means creating real beads, copying artifact fixtures and writing
a manifest — a job with nothing in common with owning the testbed's lifecycle,
and folding it into `harness.py` would have given that file a second
responsibility its own docstring rules out. It exposes `stage_run(testbed,
name)` plus the `bd` helpers a case needs to read the tracker back — `bd`,
`bd_create`, `bd_notes`, `bd_list` and `bead_ids` — and `suite_promote.py` and
`suite_lifecycle.py` are both callers. `bd_list` passes `--all`, which is what
makes closed beads visible; it lives here once so the two suites cannot drift
on that flag.

`scratch_path(testbed, name)` hands a suite a writable path under the corpus
tree that no triage script can mistake for a project, so a manifest a case
writes never lands in the testbed's own working directory.

## The database guard is a hard stop

`bd` finds its database by walking *up* from the working directory, and the
testbed is built inside the skills repo. A testbed whose `.beads` is missing
therefore resolves to the **skills repo's own tracker**, and every `bd` call a
suite makes writes into real work. That is not recoverable, so
`assert_db_inside` raises and never warns: `run_e2e.py` calls it immediately
after `build()`, before any suite runs.

The guard asks `bd info` which database `bd` opened, and checks both of them —
the main testbed and the clean sibling. It used to answer from a Python replica
of bd's upward walk instead, and that replica is what let the worst case
through: `bd init` copies the *enclosing* workspace's `.beads/config.yaml`
verbatim, `sync.remote` included, then clones the history that remote names, so
a testbed's database came up holding eighty real skills beads at the testbed's
own path. Every path check agreed, because the path was right. Measured both
ways — an outer repo with a git remote and no `.beads/` yields an empty
database; an outer `.beads/config.yaml` naming a remote, with no git remote at
all, yields the eighty. It is the config file that travels.
`suite_routing.py` exercises the guard in both directions: it must pass on the
real testbed and must raise on a testbed directory that has no database of its
own.

Two questions, asked separately, because the first cannot see the second's
failure: `assert_db_inside` asks **where** the database is, and
`assert_fixture_roster` asks **what is in it**. An inherited clone answers the
first one correctly by construction, which is the whole reason the second one
exists. The generator's half is prevention — `apply_beads` seeds
`.beads/config.yaml` with an empty `sync.remote` before `bd init`, which is
what makes the new database empty — and the roster check is detection, which
is why it lives in the harness and runs at run start rather than at build
time: `run_e2e.py --reuse` adopts trees an older generator left behind, and
those may predate the seed. One rule, one implementation, both paths.

## One routing row is asserted differently, on purpose

`inventory.collect` reads its roster from `bd list --limit 0 --json`, and
`bd list` omits closed issues unless `--all` is passed. No closed bead can
reach a manifest, so `classification.md`'s terminal-status row is covered for
`tb-blk` through the manifest and for `tb-clsepc` by calling
`inventory.classify` directly. `suite_routing.py` asserts the absence too, so
the gap stays visible instead of reading as coverage it does not have. Tracked
as `skills-lyo`.

## Two guards worth knowing about

`make_testbed.sh` wipes a target only when it already carries the
`.triage-testbed` marker file the script writes itself, so it cannot delete a
directory it did not create — including one named by `--root`.

`bd` finds its database by walking *up* from the working directory, stopping at
a git root. The testbed sits inside the skills repo, so a testbed with neither
`.beads` nor `.git` resolves to the **skills repo's own tracker**, and every
`bd create` would write a real bead into it. The script gives each database
directory its own git root, then asserts through `bd info` that the resolved
path lies inside the testbed — before the first bead and after the last one.
Anything else exits 2 without calling `bd`.

## Suite D and the `e2e` validator stage

`suite_invariant.py` fingerprints the five trees a triage run must not change —
the testbed it builds, `~/.claude/plans`, `project_plans/`, and any sibling
repo named in `TRIAGE_GUARDED_EXTERNAL` — before a worker is dispatched and
again after it returns, and
**names what moved** in any tree that did: a content tree reports the file
paths, a tracker tree reports the porcelain line or the bead id. A fingerprint
pair is not a report — sixteen hex characters say something moved and nothing
about what to fix.

It compares before against after; it never asserts a tree is clean. A repo you
work in routinely carries uncommitted work, and a sweep demanding cleanliness
would be red on an ordinary working day and then ignored.

Both fingerprints exclude what no run can write, and they do it with **two**
predicates rather than one, because the two halves guard different things and
one exclusion was only ever measured on one of them. Both skip `.git/`
internals, `__pycache__/` and `.pyc` files. `suite_invariant.TRACKER_NOISE_RE`
additionally skips `.beads/dolt.gate.lock`, which some repos track, so a Dolt
server settling moved that repo's `sample_tracker` fingerprint across 60s
with nothing guarded having changed. `suite_invariant.CONTENT_NOISE_RE` does
not: content-hashing that lock was never the measured problem, so excusing it
there bought no stability and forfeited leak detection — a lock appearing
under `project_plans` or `~/.claude/plans` is a real write, and the shared
predicate used to hide it. The split follows the measurement, not symmetry.

`project_plans` is itself a git repo and 82% of its files are git internals — a
neighbour's commit moved the guarded surface, and a triage run's leak is always
a *working* file: a plan, an artifact, a mirror. Excluding them drops that
tree's hashed surface from 6136 files to 1091, with the `.git/` share going 82%
to 0%.

Each half has exactly one predicate, and both of that half's readers use it, so
a half's tripwire and its adjudicator cannot drift apart over what counts as
noise: `content_map` is the only content-side reader, and on the tracker side
the hashed porcelain lines and `sample_tracker`'s worktree tuple both go
through `suite_invariant.porcelain_noise`.

That function is where the tracker half's shape is decided: a status line is
two status characters, a space, then a path, and a rename or copy names two as
`old -> new`. **A line is noise only when every path it names is noise.**
Matching the predicate against the whole line excused a tracked file renamed
*into* a cache path. Reading the paths out of the line is also why both
predicates can anchor on `(?:^|/)`: the older shared predicate needed
`(?:^|[\s/])` because a bare `?? __pycache__/` matched neither `^` nor `/` in a
raw line, and a path with no status prefix in front of it does not have that
problem.

Each guarded tree is read **once** per sample point, by `suite_invariant.sample`,
and `case_each_guarded_tree_is_read_once_per_sample_point` in
`test_live_dispatch.py` counts it rather than trusting it.
One read answers both questions the sweep asks — the fingerprint that decides
whether anything moved, and the detail that names what did — so no other tree's
work can sit between them. Two passes over the guarded set used to be separated
by roughly a second per tree, and a write landing in that gap reached exactly
one of the two answers: the tripwire fired, the detail explained nothing, and a
real tracker write was reported as `NOISE`. Pairing them removes that window by
construction rather than shrinking it, and halves the I/O — `project_plans` is
walked once instead of twice, and each external repo runs `git status` and
`bd list` once instead of twice.

The two halves are still adjudicated differently, and the asymmetry follows
from what each can see. `content_map` is lossless against the hash
`suite_invariant.sample_content` returns, because that hash is built from the
map. `sample_tracker`'s detail is lossy against its fingerprint: it keeps sorted
porcelain lines and `(id, status, updated_at)` per bead, while `bd list --json`
also carries title, priority and notes. So the hash is the tripwire for both
kinds of tree, and the detail only adjudicates a fire — a map cannot tell a
deleted tree from an empty one, which is why it never replaces the hash. A fire
the detail cannot explain prints `NOISE  invariant.<tree>` with both hash
prefixes and still counts as a failure. Forgiving it would be a hole, because
the bracket is the last thing that looks.

Every exclusion carries a paired case proving the real signal still fires. In
`test_suite_invariant.py`: `case_git_internals_do_not_move_the_content_fingerprint`
beside `case_a_working_file_beside_git_still_moves_the_fingerprint`,
`case_the_tracked_dolt_lock_does_not_move_the_tracker_fingerprint` beside
`case_tracker_fingerprint_includes_the_worktree_state`, and
`case_a_dolt_lock_under_a_content_tree_moves_the_fingerprint` beside
`case_bytecode_under_a_content_tree_is_still_excused`. In
`test_suite_invariant_facts.py`, where the predicates themselves are asserted:
that same lock beside
`case_the_tracked_dolt_lock_is_still_excused_in_a_porcelain_line`, which is the
oscillation the tracker half still forgives, and
`case_a_rename_into_a_cache_path_is_not_noise` beside
`case_a_rename_between_two_cache_paths_is_still_noise`. An exclusion added
without its pair is how a guard stops guarding while the green output still
reads as proof.

**One list, one window.** The testbed is on that list too — `suite_promote`
and `suite_lifecycle` create beads in it by design, so the only window it can
be compared across is one worker's — and that is now the window *every* tree
is compared across. `live_dispatch.sample_guarded_trees` takes one sample
immediately before a dispatched worker's process and one immediately after it.
Nothing samples across a whole run.

Phase 5 is what needs it, and attribution is why. A live worker can write a
file it never reports, and a per-artifact check only sees the ones it does —
but a filesystem before/after cannot say *who* wrote either. Across a whole
run, minutes wide, over `project_plans` and `~/.claude/plans` which the
operator writes to continuously, `5 file(s) moved` was as likely to be the
session in the next window as a leak: measured, one commit was red twice under
a concurrent session in a guarded repo and green in a quiet hour with no code change in
between. One dispatch wide, the window holds exactly one writer, so the same
comparison over the same predicates names it. What `run_e2e` still does is ask
`suite_invariant.missing` whether every guarded tree is on disk — an absent
internal one is a failure and never a silent skip — and take no sample at all.

An absent **external** repo is not a failure. This repo travels between
machines and the repos beside it do not, and a repo that is not here cannot be
written into, so there is nothing to fail about. The run prints
`SKIP invariant.<name> (not on this machine)` rather than passing in silence,
because a guard that quietly stops guarding is worse than no guard. A missing
**internal** tree still fails and names the path it could not find:
`_shared/validators.md` is explicit that a row which did not run is a failed
row, and the testbed or the plan trees being absent means something is wrong
with the run itself.

`--skip-external` is now only about sampling: it drops the configured external
repos from the sweep even when they are checked out here.

The roster's external half is configuration, not a constant. This repo is not
pinned to a machine and cannot name the repos that happen to sit beside it, so
`TRIAGE_GUARDED_EXTERNAL` takes a comma separated list of directory names under
the workspace root, and is empty unless you set it.

**Do not do any work in a guarded tree while a `--live` run is in flight.**
That is wider than it sounds. `project_plans/` and `~/.claude/plans` are the
obvious two, but each configured external row fingerprints that repo's
tracker **and** its worktree — so *any* coding in either project, not only a
plan edit, reddens a bracket. The guard cannot tell your concurrent edit from
a leak, and will report it as one. That is correct behaviour for a guard, and
the reason this stage is on demand rather than automatic. What the per-worker
window buys you is the size of the hole you have to stay out of: one
dispatch, not the whole run.

### Running it

```sh
./validate run e2e          # from the repo root
python3 triage/e2e/run_e2e.py --only promote --keep
```

The stage is deliberately **not** part of `phase-exit`: it builds three real
`bd` databases and takes minutes, and a per-phase stage that slow stops being
run honestly. The cost of that choice is a stage that can rot when nothing
invokes it — so run it after any change under `triage/scripts/` or to
`triage/SKILL.md`. `validators.conf` carries the same note above the row.

## Suites B and C, and the `--live` flag

```sh
python3 triage/e2e/run_e2e.py --live              # every suite, live ones included
python3 triage/e2e/run_e2e.py --live --only live  # just B and C
```

`--live` is **off by default and never part of a validator stage.** The `e2e`
stage runs `run_e2e.py` with no flags, and it stays that way: the live suites
dispatch a dozen or more real agents — minutes and dollars each — and a stage that
expensive would stop being run at all. `--only live` without `--live` is
refused rather than treated as an implicit opt-in, because the default is the
thing worth protecting.

`test_run_e2e.py` is the guard on that. It asserts the live suites reach no
default run and that `--live` is purely additive, so the flag cannot leak into
the stage by accident.

### What they cost

| Case | Workers | What is dispatched |
|---|---|---|
| `suite_b_full_pipeline` | 2 | one investigation over `tb-inv1`, then one plan from it |
| `suite_c_duplicate_pair`, `suite_c_coverage` | 1 (shared) | one Wave 1 judge over the clusters *and* the coverage section |
| `suite_c_collision` | 3 | one plan-only footprint derivation per bead |
| `suite_c_park` | 1 | one investigation over `tb-park` |
| `suite_c_deny_rules_refuse_a_real_plan_write` | 1 | one probe session that attempts two writes, one denied and one allowed |
| `case_a_fresh_orchestrator_produces_a_complete_run` | 1 driver, ~10 of its own | one agent driving the whole skill, which dispatches the sweep's workers itself |

Eight workers in Suites B and C, plus the orchestrator case, whose single
dispatched agent then spawns the sweep's own workers — measured at around ten
on a six-bead scope, and not a number this side controls. `TRIAGE_E2E_MODEL`
picks the model (unset means the CLI's own default) and
`TRIAGE_E2E_WORKER_TIMEOUT` caps each worker in seconds (default 1800). The
orchestrator case is the one most likely to meet a usage limit; that is also
why a failing run now keeps its trees.

Dispatch is `claude -p --output-format json --settings <inline JSON>` — a real
session, in its own process, reading a generated brief as its prompt, under a
permission floor the next section describes. The worker's working directory is
`triage-testbed/`, which has its own `.git` and `.beads`, so even a bare `bd`
resolves inside the sandbox instead of walking up to the skills repo's tracker.

### Shape, never verdict

`oracles.py` holds every assertion these suites make, and each one holds across
models. A partition is a partition regardless of which beads landed in which
group. A flagged bead needs exactly one coverage line regardless of which way
it was ruled. A park needs a real question regardless of what the question is.
A written path either sits inside the run directory or it does not.

`tb-dup1` and `tb-dup2` were built to be duplicates, and **nothing here asserts
they were ruled that way.** An oracle demanding a specific judgment goes red
the day a model change produces a different but equally defensible answer, and
a test that cannot separate "the code broke" from "the model had an off day" is
a mood ring that happens to be green today. The full argument is in the phase
plan's "Oracles assert shape, never verdict" section.

The same rule governs the Wave 5 gate. `suite_b` runs `lint_investigation.py`
over the live artifact and records what it said, but only a broken invocation
(exit 2) fails the case: a tier-1 finding is a REVISE round in a real run, and
asserting a live artifact lints clean first time would be asserting the model
wrote a good one.

`test_oracles.py` runs in the TDD inner loop with no testbed and no agents.
Every oracle carries an accepting fixture and at least one **mutation** of it —
one true condition flipped — that it must reject, and `MUTATIONS` records which
condition. `case_every_oracle_has_a_recorded_mutation` asserts that record, so
a sixth oracle cannot arrive with no rejecting case.

### The per-worker fingerprint is the point

Suite D's roster is the list of trees a run must not touch, and the per-worker
bracket is the only window in which that list can be checked and the answer
attributed. Every agent up to this point was read-only by construction; a live
worker can write anywhere, and a window a whole run wide cannot say which of
the two writers inside it — the run, or the operator in the next terminal —
left the delta.

So every dispatch is bracketed. Immediately before the process and immediately
after it, `live_dispatch.sample_guarded_trees` takes **one** sample of every
guarded tree — the testbed, `~/.claude/plans`, `project_plans` and the
configured external repos, resolved by `suite_invariant.sample(root=testbed.root)`
— plus the
**skills repo's** tracker and worktree, plus a path-to-hash map of the whole
plan corpus. The only delta any worker is allowed is inside the run directory
it was assigned.

One sample, not two: a tracker's fingerprint and its facts come out of the
same read of `git status --porcelain` and `bd list --json`. The hash is the
tripwire and the facts are what may forgive a fire, so reading them in
separate passes left a gap a write could sit in — present in the facts,
missing from the hash, which made the fire unexplainable and filed a real
`bd` write as `noise/` with the assert satisfied (`skills-rjb`). A write can
no longer hide between the tripwire and the adjudicator.

The skills repo is added by hand rather than declared on the roster, and it is
the precedent the roster's own sampling generalises. It is where the sandbox
lives — a `bd create` run without `-C` walks up into the real tracker — and it
is not a tree `guarded_trees` can list, because the run builds the testbed
inside it: stable across one worker's window, never across a run. What used to
be one worker-scoped tree plus that hand-add is now every guarded tree plus
the same hand-add.

This catches what `artifact_is_inside` cannot. That oracle only sees files the
worker *reported*, so a worker that writes a file it never mentions passes
every other check in the phase.

**Workers run one at a time**, against `{parallel_cap}`. The bracket is only
sound while nothing else touches the guarded trees between its two samples;
two concurrent workers make every delta ambiguous and the
assertion this suite exists to make unprovable. Parallelism is the cheaper
thing to give up.

**Do not edit the skills repo, `project_plans/` or `~/.claude/plans` while a
`--live` run is in flight.** The brackets cannot tell your concurrent edit from
a worker's leak and will report it as one — correct behaviour for a guard, and
the reason this is on demand rather than automatic.

### What the dispatch refuses, and what it does not

The bracket above is a tripwire: it reports a leak after the fact. `--settings`
is the boundary, and it comes first. Every dispatch carries an inline settings
blob built by `live_dispatch.permission_settings`, denying `Read` and `Edit` on
every guarded tree except the testbed — the two real plan trees
(`~/.claude/plans`, `project_plans`) plus the configured external repos — by the
names `suite_invariant` gives them, so a rename in the guarded-tree table fails
loudly here instead of quietly shortening the deny list.

The testbed is the exception because it is the tree the worker is supposed to
write in. The external repos are in the list not because the bracket
misses them — `sample_guarded_trees` samples all four on every dispatch — but
because a deny rule and a bracket are different instruments: the rule refuses
the write, the bracket reports it afterwards. A tree you can make unreachable
for the cost of two strings is not a tree worth merely watching. The deny list
is derived from the roster in
`case_the_deny_list_names_every_tree_but_the_testbed`, so a tree added to
`guarded_trees` and forgotten here fails a test rather than shipping as a
watched-but-reachable path.

These rules are enforced by Claude Code, not by the model, so the boundary does
not rest on the brief being persuasive. Both rule names are written for every
path: `Edit` is what file-modification checks actually consult, and a rule
written for `Write` or `NotebookEdit` is accepted and never used; `Read`
additionally blocks Edit and Write and keeps the real backlog out of the
worker's context, but leaves NotebookEdit uncovered on its own. A shell
redirect (`>`, `>>`, `2>`) into a denied tree is checked as a file write
against the same Edit rules and refused.

**It does not cover a subprocess that opens a file itself.** A `python3 -c` or
a Node script that writes a path matches no path rule, and Bash rules that try
to constrain arguments are documented as fragile, so there is no useful Bash
rule to add. That residual is what the per-worker bracket is for, and it is the
only thing that catches it. Full immunity needs an OS-level boundary; that was
considered at this epic's fix gate and deliberately excluded, because on macOS
both the supported and the hand-rolled route buy a platform-specific dependency
on an Apple-deprecated facility for a residual the bracket already reports by
name.

`case_suite_c_deny_rules_refuse_a_real_plan_write` is what keeps that claim
honest against a real session. It spends one worker and asks it for two writes:
one at a real plan path, one inside the run directory it was assigned. The
second is the positive control — a worker that simply declined to try would
otherwise satisfy "the denied file is absent" and turn the case green for the
wrong reason.

### The orchestrator suite

```sh
python3 triage/e2e/run_e2e.py --live --only orchestrator
```

Everything above this line tests the *parts* an orchestrator would call.
`suite_routing` runs `inventory.py`; Suites B and C call the brief generators
and the ruling scripts directly, assembling the waves themselves. None of that
proves the thing the skill actually claims: that a session handed
`triage/SKILL.md` and nothing else drives six waves in the right order, with
the right inputs, and stages every artifact where it belongs.

`suite_orchestrator.py` is that case. One agent, one brief, and the brief
carries no wave list, no command lines and no artifact paths — only the project,
the two isolation seams, and the standing answers to the questions the skill
would otherwise stop on (the Wave 2 scope gate is approved, this is a full run,
do not promote, never mutate the tracker). Everything else it must get from the
skill.

What is asserted is the **shape of a complete run**, on the same rule as the
oracles: which waves left ledger rows, whether every dispatched row also
returned, whether the artifacts a row names exist and sit inside the run
directory, whether Wave 6 wrote a report, and whether a park carries a
question. A judge ruling `distinct` where a human might have said `duplicate`
is not a failure here. A Wave 3 that never ran is.

Scope is capped to six beads with `--ids` — a duplicate pair for Wave 1, a
collision pair for Wave 3, one bead needing investigation and one that already
has one. That is enough to force every wave to do real work; a full sweep of the
twenty-bead matrix would prove nothing more and costs several times as much.

**A run that is cut off can be continued.** The suite is resume-aware: if the
testbed carries a run whose ledger still has an incomplete wave, it dispatches
the resume brief for that run instead of starting a fresh one, and asserts the
same complete-run shape at the end — a resumed run has to finish where a fresh
one finishes, which is the whole claim `--resume` makes. It also asserts that
no *second* run directory appeared, `references/ledger.md`'s rule about never
recovering one run by starting another.

```sh
python3 triage/e2e/run_e2e.py --live --only orchestrator            # fresh
python3 triage/e2e/run_e2e.py --live --only orchestrator --reuse    # continue
```

`--reuse` is what makes that possible: the driver adopts the trees already on
disk instead of calling the generator, which wipes and rebuilds. Before it
existed, restarting the driver to continue an interrupted sweep destroyed the
sweep — the ledger a resume reads included. Keeping the trees on a failing run
made the run survivable; `--reuse` is what lets the harness use it. A `--reuse`
with nothing to adopt exits 2 rather than quietly building over the spot, since
the caller asked to continue something and a rebuild answers by deleting it.

This is also the only coverage that `--resume` works under a *real*
interruption — a usage limit mid-Wave-4 — rather than a simulated one.
`suite_lifecycle` proves the resume reader against a hand-built ledger; this
proves it against a ledger a live sweep actually wrote.

Two things about the bracket differ from Suites B and C, and both follow from
the agent choosing its own run directory:

- The `dispatch` bracket is widened to the **staging root** via `permit=`,
  because nothing tighter is knowable before the agent starts. The tight
  assertion is made afterwards, once the directory it chose is known:
  everything it wrote must be inside that one run.
- The suite's own bookkeeping ledger is created under `tempfile.mkdtemp()`,
  outside the corpus. A bookkeeping file inside the measured tree shows up in
  the fingerprint it is helping to take — the instrument reading itself as a
  change the run made.

### Why Suite B branches on the outcome

`case_suite_b_full_pipeline` runs the investigation, and then either asserts a
park carries a question and stops, or dispatches the planning worker. Both
paths are correct and neither is asserted against.

That branch was not designed — a live worker forced it. `tb-inv1` originally
asserted a startup crash against a source tree with no entry point and no code
that opened `config.yaml`, so an honest worker returned `PARK` every time:
`investigate`'s evidence-only rule forbids inventing a cause, and the fixture
was what was wrong. `fixtures/src/lib/app_startup.py` now gives the bead a real
unguarded `open()` to find, so the planning dispatch actually runs
(`skills-24t`).

The branch stays anyway. A bead whose cause cannot be proven is a normal thing
for a triage run to meet, `PARK` is a finished outcome rather than a failure,
and a suite that could only pass on the happy path would be asserting that the
model reaches a cause — the verdict assertion everything here refuses to make.
