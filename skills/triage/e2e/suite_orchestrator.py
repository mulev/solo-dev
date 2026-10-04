#!/usr/bin/env python3
"""Drive the whole skill with one agent, and assert the run it leaves behind.

This is the epic's first goal, and until now nothing tested it. Every other
suite calls the pieces the orchestrator would call: `suite_routing` runs
`inventory.py`, `suite_live` calls the brief generators and the ruling scripts
directly. All of that proves the parts work. None of it proves that a session
reading `triage/SKILL.md` drives the six waves in the right order, with the
right inputs, and stages everything where it belongs.

So this suite gives an agent the skill and nothing else — no wave list, no
command lines, no artifact paths — and then reads the run directory it
produced. What is asserted is the **shape of a complete run**, never a verdict:
which waves left rows, whether every dispatched row also returned, whether the
artifacts a row names exist, and whether anything at all was written outside
the run directory. A judge ruling `distinct` where a human might have said
`duplicate` is not a failure here; a Wave 3 that never ran is.

Scope is capped with `--ids`. Six beads is enough to force every wave to do
real work — a duplicate pair for Wave 1, a collision pair for Wave 3, one bead
that needs investigation and one that already has one — while keeping the run
to something bounded. A full sweep of the matrix would prove nothing this does
not, and costs several times as much.

`--live` only. Nothing here runs in the deterministic `e2e` stage.
"""

from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path

import harness
import live_dispatch
import staged_run
import suite_invariant

# One bead per wave-shaped job, and no more.
SCOPE = ("tb-inv1", "tb-pln1", "tb-dup1", "tb-dup2", "tb-col1", "tb-col2")

# Waves that must leave a trace for a run over SCOPE. Wave 4 plans, Wave 5
# reviews; Wave 6 is the report, which lives in the ledger rather than a row.
REQUIRED_WAVES = (0, 1, 2, 3, 4, 5)

BRIEF = """\
You are running a triage sweep, autonomously, end to end.

# Read first
1. `cat {skills}/triage/SKILL.md` — the skill you are executing. Follow it.
2. `cat {skills}/_shared/autonomous-mode.md` — the worker contract.

# The run
Project: `triage-testbed`. Restrict the run to exactly these beads:

    --ids {ids}

Two environment facts the skill needs, and the only two seams that point it at
this sandbox:

    TRIAGE_PROJECTS_ROOT={root}
    --plans-dir {corpus}

Every script lives under `{skills}/triage/scripts/`.

# Standing answers — do not ask, these are decided
- There is no run-scope gate before Wave 2. Print the counts and dispatch.
- This is a **full run**, not `--dry-run`. Dispatch the workers the skill says
  to dispatch.
- Do **not** promote. A run ends at the Wave 6 report; promoting is a separate
  command a human issues later.
- Never mutate the tracker. Every `bd` call in a run is read-only.
- Write nothing outside the run directory the skill tells you to create.

# When you are done
Report the absolute path of the run directory, one line per wave saying what it
did, and nothing else.
"""

RESUME_BRIEF = """\
You are resuming an interrupted triage sweep, autonomously, end to end.

# Read first
1. `cat {skills}/triage/SKILL.md` — the skill you are executing. Follow it.
2. `cat {skills}/triage/references/ledger.md` — the resume protocol. Follow it
   exactly: re-dispatch a row that never returned, resume a row that returned
   without a `final` at its Wave 5 quality control on the round its `round`
   column names, and never start a second run directory to recover this one.

# The run
Project: `triage-testbed`. Resume the existing run:

    --resume {runid}

    TRIAGE_PROJECTS_ROOT={root}
    --plans-dir {corpus}

Every script lives under `{skills}/triage/scripts/`.

# Standing answers — do not ask, these are decided
- Any scope gate is **approved**. You cannot reach a user; treat it as yes.
- This is a **full run**, not `--dry-run`.
- Do **not** promote. Never mutate the tracker.
- Write nothing outside the run directory you are resuming.

# When you are done
Report the absolute path of the run directory, one line per wave saying what it
did, and nothing else.
"""


def _staged_runs(testbed) -> set:
    """Run directories under the project's staging root, `promoted/` excluded.

    Both sides of the diff are taken the same way. Filtering one and not the
    other would make a promoted run read as new.
    """
    staging = testbed.corpus / "triage-testbed" / "triage"
    if not staging.is_dir():
        return set()
    return {p for p in staging.iterdir() if p.is_dir() and p.name != "promoted"}


def _run_dir(testbed, before: set) -> Path:
    """The run directory the agent created, found by diffing the staging root.

    Asked of the filesystem rather than parsed out of the agent's report: the
    report is prose and this has to be exact. A run that created none, or more
    than one, is a failure with a specific message rather than a stray index
    error later.
    """
    fresh = sorted(_staged_runs(testbed) - before)
    assert len(fresh) == 1, (
        f"expected exactly one new run directory, got {fresh}")
    return fresh[0]


def _incomplete(testbed):
    """A staged run that stopped mid-sweep, or None if there is none.

    `first_incomplete_wave` is the production reader — the same one `--resume`
    consults — so this cannot disagree with the skill about what "finished"
    means. Under `--reuse` a previous run's directory is still on disk, which
    is what makes continuing it possible at all.
    """
    for run in sorted(_staged_runs(testbed)):
        if staged_run.first_incomplete_wave(run) is not None:
            return run
    return None


def _waves(run: Path) -> dict:
    """Wave number -> its ledger rows, using the production reader."""
    out: dict = {}
    for row in staged_run.ledger_rows(run):
        out.setdefault(int(row["wave"]), []).append(row)
    return out


def case_a_fresh_orchestrator_produces_a_complete_run(testbed) -> None:
    """One agent, the skill, and nothing else.

    This case brackets the plan corpus and nothing else: one `content_map`
    before the dispatch and one after. The only delta permitted is inside the
    run directory the agent created — which it chooses itself, so the
    assertion cannot be arranged in advance — plus the staging root's own
    `.gitignore`, excused by exact path further down because
    `staged_run.create_run` writes it the first time a project stages
    anything. Every *guarded tree* is bracketed inside
    `live_dispatch.dispatch`, around the subprocess alone; see the comment
    below for why no wider pair belongs here.
    """
    before_runs = _staged_runs(testbed)

    # Fresh testbed: a new sweep. Reused testbed carrying a run that stopped
    # mid-way: continue that one. The assertions below do not branch — a
    # resumed run has to end in the same complete state a fresh one does, which
    # is the whole claim `--resume` makes.
    resuming = _incomplete(testbed)
    if resuming:
        brief = RESUME_BRIEF.format(skills=harness.SKILLS_ROOT,
                                    runid=resuming.name, root=testbed.root,
                                    corpus=testbed.corpus)
        target = f"Resume {resuming.name} now. Report the run directory when finished."
    else:
        brief = BRIEF.format(skills=harness.SKILLS_ROOT, ids=",".join(SCOPE),
                             root=testbed.root, corpus=testbed.corpus)
        target = "Run the sweep now. Report the run directory path when finished."
    # Outside the corpus on purpose. `dispatch` records the dispatch and the
    # return into this ledger, and a corpus-resident bookkeeping file shows up
    # in the very fingerprint it is helping to take — the instrument reading
    # itself as a change the run made.
    bookkeeping = staged_run.create_run(
        Path(tempfile.mkdtemp(prefix="orch-ledger-")), "driver")
    # Only the corpus is sampled across this case. The guarded trees are not:
    # `dispatch` brackets that same set around each subprocess and raises on
    # any delta, so an outer pair here cannot catch a leak the inner one
    # missed — between its `after` and this point the only code running is
    # this case, which reads. What an outer pair *can* catch is the operator
    # editing a plan tree during the trailing assertion block, failing the
    # case in the words of a real leak while naming a file the run never
    # touched. That is the report `skills-92s` deleted run scope to remove,
    # and it was reintroduced here by a rename: this pair called
    # `sample_trackers` (testbed + skills repo, neither operator-written)
    # until Phase 4 widened it to the whole roster.
    before_files = suite_invariant.content_map(testbed.corpus)

    # The bracket is widened to the staging root for the dispatch itself: this
    # agent picks its own run directory, so nothing tighter is knowable before
    # it starts. The tighter assertion is made below, once the directory it
    # chose is known — everything it wrote must be inside that one run.
    staging = testbed.corpus / "triage-testbed" / "triage"
    report = live_dispatch.dispatch(
        testbed, bookkeeping, "orchestrator", brief, target,
        permit=staging, timeout=live_dispatch.SWEEP_TIMEOUT)

    if resuming:
        # `references/ledger.md`: never start a new run directory to recover an
        # old one. A second directory splits the run's state across two
        # ledgers, and neither is then the answer to "what happened".
        assert _staged_runs(testbed) == before_runs, (
            f"a resume started a second run directory: "
            f"{sorted(_staged_runs(testbed) - before_runs)}")
    run = resuming or _run_dir(testbed, before_runs)

    # --- the run is complete -------------------------------------------------
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    ids = {b["id"] for b in manifest["beads"]}
    assert set(SCOPE) <= ids, f"the manifest lost beads the run was given: {ids}"
    # `--ids` is honoured when nothing outside SCOPE was selected, and nothing
    # inside it was dropped *for being out of scope*. Demanding
    # `selected == SCOPE` asserts a verdict instead — and the verdict it asserts
    # is the run failing to dedup, because Wave 1 legitimately deselects a bead
    # it rules a duplicate and the tb-dup1/tb-dup2 pair exists to make it do so.
    by_id = {b["id"]: b for b in manifest["beads"]}
    selected = {i for i, b in by_id.items() if b.get("selected", True)}
    assert selected <= set(SCOPE), (
        f"beads outside --ids were selected: {sorted(selected - set(SCOPE))}")
    for bead in SCOPE:
        if bead in selected:
            continue
        why = (by_id[bead].get("excluded") or "").strip()
        assert why, f"{bead} was dropped from the run with no reason recorded"
        assert "not in --ids" not in why, (
            f"--ids was not honoured end to end: {bead} was excluded as {why!r}")

    waves = _waves(run)
    missing = [w for w in REQUIRED_WAVES if w not in waves]
    assert not missing, f"no ledger row for wave(s) {missing}; waves seen: {sorted(waves)}"

    for wave, rows in sorted(waves.items()):
        for row in rows:
            assert row.get("dispatched"), f"wave {wave} row {row} never dispatched"
            assert row.get("returned"), (
                f"wave {wave} row {row.get('bead')} was dispatched and never "
                f"returned — the run stopped mid-wave")

    # --- every artifact a row names is really there --------------------------
    for rows in waves.values():
        for row in rows:
            named = (row.get("artifact") or "").strip()
            if named.startswith("/"):
                path = Path(named)
                # File or directory: Wave 4 stages a multi-phase plan as a
                # folder — `plan.md` plus one slice per phase — which is the
                # shape `plan` writes and the shape `promote.py` moves.
                assert path.exists(), f"ledger names a missing artifact: {named}"
                assert run in path.parents, (
                    f"an artifact landed outside the run directory: {named}")
            else:
                # No path at all. Legitimate only where there was nothing to
                # write: a parked worker, or a bead dropped as a duplicate. A row
                # that claims a finished plan and names prose is what this
                # catches, and prose is exactly how that would be written.
                final = (row.get("final") or "").strip().lower()
                assert final in ("", "parked", "duplicate"), (
                    f"row {row.get('bead')} is {final!r} and names no artifact "
                    f"path: {named!r}")

    # Wave 5 is per artifact, "as it lands", and each pass is its own row
    # (`references/ledger.md`). Requiring the wave to merely exist would pass a
    # run that reviewed one artifact out of four, and a run that folded its
    # verdicts into the producing row reports a review it cannot evidence.
    reviewed = {(row.get("artifact") or "").strip()
                for row in waves.get(5, [])}
    for wave in (2, 4):
        for row in waves.get(wave, []):
            named = (row.get("artifact") or "").strip()
            if named.startswith("/"):
                assert named in reviewed, (
                    f"wave {wave} produced {named} and no Wave 5 row reviews it")

    assert (run / "judge_brief.md").is_file(), "Wave 1 left no judge brief"
    assert (run / "collision_report.md").is_file(), "Wave 3 left no collision report"
    assert any((run / "investigations").glob("*.md")), "Wave 2 produced no artifact"

    # --- Wave 6: the report, and what a park owes ----------------------------
    ledger = (run / "ledger.md").read_text(encoding="utf-8")
    # Either word: SKILL.md heads the wave "Report" and then tells the
    # orchestrator to write the "close-out". Pinning one of the two asserts
    # vocabulary rather than behaviour.
    heading = re.search(r"(?i)^#+ .*(report|close.?out)", ledger, re.M)
    assert heading, "Wave 6 wrote no close-out section into the ledger"
    close_out = ledger[heading.start():]
    for rows in waves.values():
        for row in rows:
            if (row.get("final") or "").strip().lower() != "parked":
                continue
            bead = (row.get("bead") or "").strip()
            assert bead and bead in close_out, (
                f"{bead!r} parked and the close-out never names it — a park the "
                f"report drops is a dropped bead")
            assert "?" in close_out, (
                "a bead parked and the close-out records no question at all")

    # --- nothing escaped -----------------------------------------------------
    # Now the tight one. The only write permitted anywhere in the corpus,
    # outside the run the agent created, is the staging root's own `.gitignore`
    # — `staged_run.create_run` writes it the first time a project stages
    # anything, and it is what keeps runs out of git.
    #
    # Excused by its exact path, never by its basename. A guard that forgives
    # any file called `.gitignore` forgives one written into a real `todo/`,
    # which is the class of leak this whole bracket exists to catch.
    excused = str((staging / ".gitignore").relative_to(testbed.corpus))
    after_files = suite_invariant.content_map(testbed.corpus)
    strays = [name for name in
              live_dispatch.strayed(before_files, after_files, run,
                                    testbed.corpus)
              if name != excused]
    assert not strays, f"the run wrote outside its own directory: {strays}"

    # The agent was told to report the path. Asserting it names the directory
    # the filesystem actually grew is what separates "followed the skill" from
    # "left a directory behind on the way to something else".
    assert run.name in report, (
        f"the report never names the run it produced ({run.name}): {report[:300]}")


CASES = [case_a_fresh_orchestrator_produces_a_complete_run]
