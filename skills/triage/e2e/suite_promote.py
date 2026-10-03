"""Assert every promote path against a staged run in the real testbed.

Six paths, each a row of `promote.py`'s own `EPILOG`: `--dry-run`, a clean
promote, a quarantined bead, `promote-artifact-missing`, `promote-stale-path`,
and a rerun that has to be idempotent through the ledger. Every one runs the
real command line against a real `bd` database, because promote is the only
code in the triage system that writes outside a run directory and the unit
suite reaches it through an injected runner that cannot write anything.

**Coupling waiver:** this file reaches six foreign modules —`promote`,
`staged_run`, `manifest`, plus `harness` and `staged_fixture`. Its
responsibility is one sweep over `promote.py`'s eight-step orchestration
boundary, and every step of that sequence already lives in a different module
by the production code's own design. See the phase slice's Component
Decomposition for the split that was ruled out.

**`skills-p1j`, found here and since fixed.** `tracker_intents._verify` used to
read `bd show <bead>` in its human format, which hard-wraps the notes block and
breaks any real absolute path mid-token, so every promote that wrote a note
reported `promote-notes-unverified` and no run ever reached `promoted/`. This
suite pinned that behaviour rather than papering over it, and left a tripwire
saying what to do when it changed. The read-back now asks for `--json`, so the
clean and rerun paths assert exit 0 and a run that actually completes.
`case_the_human_bd_show_still_wraps_which_is_why_the_read_back_uses_json` keeps
the wrap under test — it is the reason for the `--json`, and a reader who does
not know that will eventually "simplify" it back.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import harness
import staged_fixture
from staged_fixture import INVEST_NAME, PLAN_FOLDER

sys.path.insert(0, str(harness.SCRIPTS))

import promote  # noqa: E402
import staged_run  # noqa: E402

HOME_PLANS = Path.home() / ".claude" / "plans"


def _promote(testbed, fixture, *extra: str):
    """(exit code, the `--json` payload, stderr) from one real promote."""
    code, out, err = harness.run(
        "promote.py", "--run-id", fixture.run.name,
        "--runs-dir", str(fixture.runs_dir), "--plans-dir", str(fixture.plans),
        "--repo-root", str(testbed.path), "--system-plan-dir", str(fixture.system),
        "--json", *extra, testbed=testbed)
    return code, (json.loads(out) if out.strip() else {}), err


def _codes(payload: dict, severity: str = "error") -> set:
    """Finding codes of one severity. Split because only `error` changes the
    exit code, so a case that lumped both in would go red the day a linter
    gained a warning that changes nothing about whether the run promoted."""
    return {finding["code"] for finding in payload.get("findings", [])
            if finding["severity"] == severity}


def _tree(root: Path) -> list:
    """Every path under `root`, relative; a missing directory reads as empty."""
    if not root.is_dir():
        return []
    return sorted(str(p.relative_to(root)) for p in root.rglob("*"))


def _home_plans_state() -> list:
    """Name, size and mtime of every file in the user's real plan mirrors.

    Compared before against after rather than asserted clean, the rule
    plan.md's Suite D paragraph sets: this tree belongs to the user and is
    never empty, so the only checkable claim is that nothing in it moved.
    """
    if not HOME_PLANS.is_dir():
        return []
    return sorted((str(p.relative_to(HOME_PLANS)), p.stat().st_size,
                   p.stat().st_mtime_ns)
                  for p in HOME_PLANS.rglob("*") if p.is_file())


def _master(fixture) -> str:
    return str(fixture.real / "todo" / PLAN_FOLDER / "plan.md")


# --- path 1: --dry-run -------------------------------------------------------


def case_dry_run_prints_ordered_commands_and_moves_nothing(testbed) -> None:
    fixture = staged_fixture.stage_run(testbed, "dry_run")
    before_beads = staged_fixture.bead_ids(testbed)
    before_run = _tree(fixture.run)
    code, payload, err = _promote(testbed, fixture, "--dry-run")
    assert code == 0, (code, payload, err)

    verbs = [command.split()[1] for command in payload["commands"]]
    assert verbs == ["create", "create", "create", "dep", "update", "update",
                     "update", "update"], payload["commands"]
    epic, phase_1, phase_2 = payload["commands"][:3]
    assert "-t epic" in epic, epic
    # Every intent name is qualified by the bead whose store defined it
    # (`intent_records._qualified`), so the placeholder a phase blocks on
    # carries that owner. Asserting the bare `${epic}` passed only while one
    # flat namespace held every ref — the bug that namespace caused.
    ref = f"{fixture.plan_bead}/epic"
    assert f"--parent ${{{ref}}}" in phase_1, phase_1
    assert f"--parent ${{{ref}}}" in phase_2, phase_2
    assert (f"dep add ${{{fixture.plan_bead}/phase_2}} "
            f"${{{fixture.plan_bead}/phase_1}}" in payload["commands"][3]), payload

    assert _tree(fixture.run) == before_run, "a dry run touched the staging tree"
    assert _tree(fixture.real / "todo") == [], "a dry run moved a plan"
    assert _tree(fixture.real / "investigations") == [], "a dry run moved a file"
    assert _tree(fixture.system) == [], "a dry run wrote a mirror"
    assert staged_fixture.bead_ids(testbed) == before_beads, "a dry run wrote to bd"
    assert staged_run.completed_steps(fixture.run) == {}, "a dry run wrote a ledger row"


# --- path 2: the clean promote ----------------------------------------------


def case_clean_promote_moves_rewrites_mirrors_and_applies(testbed) -> None:
    fixture = staged_fixture.stage_run(testbed, "clean")
    before = staged_fixture.bead_ids(testbed)
    code, payload, err = _promote(testbed, fixture)
    assert _codes(payload) == set(), (payload, err)
    assert code == 0, (code, err)
    assert _codes(payload, "warning") == {"source-tree-unchecked"}, payload

    assert not (fixture.run / "todo" / PLAN_FOLDER).exists(), "the plan stayed staged"
    assert not (fixture.run / "investigations" / INVEST_NAME).exists()
    plan = Path(_master(fixture))
    assert plan.is_file(), plan
    promoted_invest = fixture.real / "investigations" / INVEST_NAME
    assert promoted_invest.is_file(), promoted_invest

    text = plan.read_text(encoding="utf-8")
    assert str(fixture.run) not in text, text
    mirror = fixture.system / f"{PLAN_FOLDER}.md"
    assert mirror.is_file(), sorted(fixture.system.iterdir())
    assert str(plan) in mirror.read_text(encoding="utf-8")
    assert f"**System plan file:** {mirror}" in text, text

    created = staged_fixture.bead_ids(testbed) - before
    assert len(created) == 3, created          # the epic and its two phases
    notes = staged_fixture.bd_notes(testbed, fixture.plan_bead)
    assert str(plan) in notes and str(fixture.run) not in notes, notes
    assert str(promoted_invest) in staged_fixture.bd_notes(
        testbed, fixture.invest_bead)

    # The step no promote ever reached while `skills-p1j` stood: verification
    # failed, so the run was left staged and `promoted/` stayed empty. A clean
    # promote is not finished until the run is out of the staging directory —
    # which is also why the ledger has to be read at its new home. Reading it
    # at the staging path returns nothing and looks like "no steps ran".
    assert not fixture.run.exists(), "the run stayed in staging"
    promoted = fixture.runs_dir / "promoted" / fixture.run.name
    assert promoted.is_dir(), sorted((fixture.runs_dir / "promoted").iterdir())

    done = staged_run.completed_steps(promoted)
    # An intent's step key is its qualified name, so the bead that owns the
    # store owns the key; `move` and `close` are promote's own steps and stay
    # bare. Listing them exactly is the point — a substring matcher here would
    # have passed straight through the flat-namespace bug.
    expected = ["move", "close"]
    expected += [f"{fixture.plan_bead}/{key}" for key in
                 ("epic", "phase-1", "phase-2", "dep-2-on-1", "open-1",
                  "open-2", "flip")]
    expected.append(f"{fixture.invest_bead}/invest")
    for key in expected:
        assert key in done, (key, sorted(done))


def case_the_home_plans_mirror_is_never_written(testbed) -> None:
    """plan.md guard 3, measured rather than argued.

    `--system-plan-dir` is required, so no promote reaches `~/.claude/plans` by
    omission. What is still unproven by inspection is that nothing else in the
    promote sequence writes there, and the only proof of that is the tree
    itself, before against after.
    """
    fixture = staged_fixture.stage_run(testbed, "home_mirror")
    before = _home_plans_state()
    _promote(testbed, fixture)
    assert _home_plans_state() == before, "a promote wrote into ~/.claude/plans"
    assert (fixture.system / f"{PLAN_FOLDER}.md").is_file(), (
        "the mirror landed nowhere — a passing before/after would then prove "
        "only that write_mirrors never ran")


# --- path 3: quarantine ------------------------------------------------------


def case_quarantined_bead_keeps_its_artifacts_staged(testbed) -> None:
    """A bead someone moved since the run stops itself, never the run."""
    fixture = staged_fixture.stage_run(testbed, "quarantine")
    staged_fixture.bd(testbed, "update", fixture.plan_bead, "--status", "blocked")
    code, payload, err = _promote(testbed, fixture)
    assert code == 1, (code, err)
    assert "promote-bead-state-changed" in _codes(payload), payload

    assert (fixture.run / "todo" / PLAN_FOLDER).is_dir(), "a quarantined artifact moved"
    assert not (fixture.real / "todo" / PLAN_FOLDER).exists()
    assert not (fixture.system / f"{PLAN_FOLDER}.md").exists(), "a mirror was written"
    assert (fixture.real / "investigations" / INVEST_NAME).is_file(), (
        "quarantining one bead stranded the whole run")
    assert str(fixture.real) in staged_fixture.bd_notes(testbed, fixture.invest_bead)


# --- path 4: promote-artifact-missing ----------------------------------------


def case_missing_artifact_stops_the_promote_before_anything_moves(testbed) -> None:
    fixture = staged_fixture.stage_run(testbed, "missing")
    (fixture.run / "investigations" / INVEST_NAME).unlink()
    before = staged_fixture.bead_ids(testbed)
    code, payload, err = _promote(testbed, fixture)
    assert code == 1, (code, err)
    assert _codes(payload) == {"promote-artifact-missing"}, payload

    assert (fixture.run / "todo" / PLAN_FOLDER).is_dir(), (
        "the healthy artifact moved while its sibling was missing")
    assert _tree(fixture.real / "todo") == [], "something moved"
    assert _tree(fixture.system) == [], "a mirror was written"
    assert staged_fixture.bead_ids(testbed) == before, "bd was written to"


# --- path 5: promote-stale-path ----------------------------------------------


def case_stale_path_stops_the_promote_before_any_bd_write(testbed) -> None:
    """A run-root path no move-map entry covers is a hard stop.

    The move has already happened by the time the rewrite finds it — that is
    the design, and it is why the assertion below is about `bd`, not about the
    files. A bead note pointing into a run directory is the failure promote
    exists to prevent, and `discard` would later delete what it names.
    """
    fixture = staged_fixture.stage_run(testbed, "stale")
    plan = fixture.run / "todo" / PLAN_FOLDER / "plan.md"
    plan.write_text(
        plan.read_text(encoding="utf-8")
        + f"\nunmapped: {fixture.run}/collision_report.md\n", encoding="utf-8")
    before = staged_fixture.bead_ids(testbed)
    code, payload, err = _promote(testbed, fixture)
    assert code == 1, (code, err)
    assert "promote-stale-path" in _codes(payload), payload
    assert staged_fixture.bead_ids(testbed) == before, "bd was written to"
    assert _tree(fixture.system) == [], "a mirror was written"


# --- path 6: the rerun -------------------------------------------------------


def case_rerun_is_idempotent_through_the_ledger(testbed) -> None:
    """The one case that steps below the CLI seam, because a subprocess cannot
    be interrupted mid-write deterministically.

    `promote_artifacts` is the crash point: it moves and rewrites, records each
    move in the ledger, and dies before the mirrors or a single `bd` call. By
    the rerun the staged file is gone, so the ledger row is the only record of
    where it went — and without it the rerun writes a run-directory path into a
    bead note, a path `discard` could later delete.
    """
    fixture = staged_fixture.stage_run(testbed, "rerun")
    outcomes = staged_run.bead_outcomes(fixture.run, fixture.data)
    moved, findings = promote.promote_artifacts(
        fixture.run, outcomes, set(), fixture.plans, fixture.data["project"])
    assert findings == [], findings
    assert len(moved) == 2, moved
    assert not (fixture.run / "todo" / PLAN_FOLDER).exists(), "nothing moved"

    code, payload, err = _promote(testbed, fixture)
    assert _codes(payload) == set(), (payload, err)
    assert code == 0, (code, err)

    notes = staged_fixture.bd_notes(testbed, fixture.plan_bead)
    assert str(fixture.run) not in notes, notes
    assert _master(fixture) in notes, notes
    invest = staged_fixture.bd_notes(testbed, fixture.invest_bead)
    assert str(fixture.run) not in invest, invest
    assert str(fixture.real / "investigations" / INVEST_NAME) in invest, invest


# --- the guard, and the gap it cannot close ----------------------------------


def case_a_manifest_outside_the_testbed_is_refused(testbed) -> None:
    """The `system_plan_dir` guard fires before a directory is created, so a
    fixture that would have written into the user's real mirrors never builds."""
    try:
        staged_fixture.stage_run(testbed, "guard_probe",
                                 system_plan_dir=HOME_PLANS)
    except AssertionError as err:
        assert "~/.claude/plans" in str(err), err
    else:
        raise AssertionError("the guard accepted the real plans tree")
    assert not (testbed.scratch / "guard_probe").exists(), (
        "the guard fired after the fixture was already on disk")


def case_the_human_bd_show_still_wraps_which_is_why_the_read_back_uses_json(
        testbed) -> None:
    """The reason `_verify` asks for `--json`, kept under test.

    `bd show`'s human format breaks an absolute path across lines, so no
    substring match on it can find one. That is what made every promote report
    `promote-notes-unverified` and never reach `promoted/` (`skills-p1j`). The
    fix reads `--json`; this case exists so the justification is checkable
    rather than a comment somebody later decides is stale.
    """
    bead = staged_fixture.bd_create(testbed, "e2e wrapped-notes probe")
    path = str(testbed.scratch / "wrapped" / "plans" / testbed.path.name
               / "todo" / PLAN_FOLDER / "plan.md")
    staged_fixture.bd(testbed, "update", bead, "--notes", f"Plan: {path}")
    assert path in staged_fixture.bd_notes(testbed, bead), "the note did not land"
    human = staged_fixture.bd(testbed, "show", bead)
    assert "NOTES" in human, human
    assert path not in human, (
        "bd show no longer wraps — the --json read-back in tracker_intents."
        "_verify may now be unnecessary; check before simplifying it away")


CASES = [v for k, v in sorted(globals().items()) if k.startswith("case_")]
