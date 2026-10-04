#!/usr/bin/env python3
"""Tests for staged_run.py's run creation — the staging root's own protection.

Run with `python3 test_staged_run.py` (no pytest dependency).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import staged_run  # noqa: E402


def expect(got, want) -> None:
    assert got == want, f"got {got!r}, want {want!r}"


# --- creating a run, and marking the staging root uncommittable --------------


def case_create_run_makes_the_run_directory(tmp: Path) -> None:
    run = staged_run.create_run(tmp / "triage", "2026-08-29_ab12")
    assert run.is_dir(), run
    expect(run.name, "2026-08-29_ab12")


def case_the_staging_root_gets_a_gitignore(tmp: Path) -> None:
    """A run swept into a commit is permanent, and `discard` then deletes a
    directory whose contents are already in history."""
    staged_run.create_run(tmp / "triage", "2026-08-29_ab12")
    marker = tmp / "triage" / ".gitignore"
    assert marker.is_file(), sorted(p.name for p in (tmp / "triage").iterdir())
    body = marker.read_text(encoding="utf-8")
    assert "\n*\n" in body, body
    # No negation, not even for the marker itself: one un-ignored file makes
    # git report the whole staging directory as untracked, which is the state
    # this exists to remove.
    assert "!" not in body, body


def case_git_reports_nothing_for_a_staged_run(tmp: Path) -> None:
    """The assertion that matters. Checking the marker's text says only that a
    file was written; a `git status` that is still dirty says the fix does not
    work, which is what the first version of this shipped."""
    if not shutil.which("git"):
        return
    subprocess.run(["git", "init", "-q", str(tmp)], check=True)
    run = staged_run.create_run(tmp / "plans" / "demo" / "triage", "2026-08-29_ab12")
    (run / "manifest.json").write_text("{}\n", encoding="utf-8")
    (run / "todo").mkdir(exist_ok=True)
    (run / "todo" / "plan.md").write_text("# staged\n", encoding="utf-8")
    out = subprocess.run(["git", "-C", str(tmp), "status", "--porcelain"],
                         capture_output=True, text=True, check=True).stdout
    expect(out, "")


def case_an_existing_gitignore_is_left_alone(tmp: Path) -> None:
    """Idempotent across runs, and it never overwrites what a human wrote."""
    root = tmp / "triage"
    root.mkdir(parents=True)
    (root / ".gitignore").write_text("# mine\n*\n", encoding="utf-8")
    staged_run.create_run(root, "2026-08-29_ab12")
    expect((root / ".gitignore").read_text(encoding="utf-8"), "# mine\n*\n")


def case_creating_the_same_run_twice_is_a_no_op(tmp: Path) -> None:
    first = staged_run.create_run(tmp / "triage", "2026-08-29_ab12")
    (first / "ledger.md").write_text("kept\n", encoding="utf-8")
    second = staged_run.create_run(tmp / "triage", "2026-08-29_ab12")
    expect(second, first)
    expect((first / "ledger.md").read_text(encoding="utf-8"), "kept\n")


def case_a_new_run_gets_the_canonical_ledger_header(tmp: Path) -> None:
    """The ten columns come from here, not from an orchestrator's memory.

    Every rule in `references/ledger.md` is stated in terms of these column
    names, and until this existed each run retyped the header by hand — so the
    schema those rules bind to was whatever the session happened to write.
    """
    run = staged_run.create_run(tmp / "triage", "2026-08-29_ab12")
    header = (run / "ledger.md").read_text(encoding="utf-8")
    for column in staged_run.LEDGER_COLUMNS:
        assert f"| {column} |" in header or f" {column} |" in header, (column, header)


def case_a_new_run_has_a_home_for_generated_briefs(tmp: Path) -> None:
    """The four generators print to stdout and SKILL.md redirects them here.

    Unassigned, the redirect target is the orchestrator's choice, and two live
    runs chose differently — one a dotfile inside the run, one `/tmp`, which
    puts a dispatched brief where `discard` cannot reach it. The directory has
    to exist before the first redirect or that command simply fails.
    """
    run = staged_run.create_run(tmp / "triage", "2026-08-29_ab12")
    assert (run / "briefs").is_dir(), sorted(p.name for p in run.iterdir())


def case_a_new_run_has_every_directory_a_wave_writes_into(tmp: Path) -> None:
    """A wave that has to create its own output directory does it mid-flight.

    A live run dispatched three Wave 2 workers against an `investigations/`
    that did not exist, and wrote Wave 5's verdicts to `/tmp` — outside the
    run, where `discard` cannot reach them and a resume cannot find them.

    `reports/` is the same failure one step over: a worker's return lives only
    on its harness job leg, which is retained five minutes after the job
    settles, and every verdict this system has produced arrived later than
    that. The report has to be a file inside the run, so `discard` reaches it
    and a resume finds it.
    """
    run = staged_run.create_run(tmp / "triage", "2026-08-29_ab12")
    present = sorted(p.name for p in run.iterdir() if p.is_dir())
    expect(present, ["briefs", "intents", "investigations", "reports", "todo",
                     "verdicts"])


def case_re_creating_a_run_keeps_its_ledger_and_its_directories(tmp: Path) -> None:
    """Re-creation is a resume, not a reset: the rows, the verdict files and a
    human's staging marker all outlive it."""
    root = tmp / "triage"
    root.mkdir(parents=True)
    (root / ".gitignore").write_text("# mine\n*\n", encoding="utf-8")
    first = staged_run.create_run(root, "2026-08-29_ab12")
    (first / "ledger.md").write_text("kept\n", encoding="utf-8")
    (first / "verdicts" / "b1_r1.json").write_text("{}\n", encoding="utf-8")
    second = staged_run.create_run(root, "2026-08-29_ab12")
    expect(second, first)
    expect((first / "ledger.md").read_text(encoding="utf-8"), "kept\n")
    expect((root / ".gitignore").read_text(encoding="utf-8"), "# mine\n*\n")
    assert (first / "verdicts" / "b1_r1.json").is_file()


def case_the_seeded_ledger_records_the_run_mode(tmp: Path) -> None:
    """A resume has to know what it is continuing.

    `--dry-run` stops after Wave 1 and dispatches one judge; a full run does
    not. Nothing recorded that, so a resumed dry run could walk into Wave 2 —
    a live run added a `Mode:` line by itself, which is the gap showing.
    """
    run = staged_run.create_run(tmp / "triage", "2026-08-29_ab12", mode="--dry-run")
    assert "Mode: `--dry-run`" in (run / "ledger.md").read_text(encoding="utf-8")


def case_an_unstated_mode_says_so_rather_than_guessing(tmp: Path) -> None:
    """The default must not be `full run`. A caller that forgot would produce a
    ledger claiming the wrong mode, which is worse than one admitting it has
    none — and every existing caller reaches this branch."""
    run = staged_run.create_run(tmp / "triage", "2026-08-29_ab12")
    text = (run / "ledger.md").read_text(encoding="utf-8")
    assert "Mode: unrecorded" in text, text
    assert "full run" not in text, text


def case_a_seeded_ledger_carries_no_rows(tmp: Path) -> None:
    """A header is not a row. The seed must not read as work already done."""
    run = staged_run.create_run(tmp / "triage", "2026-08-29_ab12")
    expect(staged_run.ledger_rows(run), [])


def case_a_seeded_ledger_still_resumes_from_wave_zero(tmp: Path) -> None:
    """The regression the seed could have introduced.

    `first_incomplete_wave` returns 0 for a run with no rows, and `None` — the
    finished answer — when every row is settled. A seed that made an empty
    ledger read as settled would tell a resume that a run which died inside
    Wave 0 had nothing left to do.
    """
    run = staged_run.create_run(tmp / "triage", "2026-08-29_ab12")
    expect(staged_run.first_incomplete_wave(run), 0)


# --- per-bead outcomes (phase 1) ---------------------------------------------


LEDGER_HEAD = "# Run ledger\n\n" + staged_run.LEDGER_TABLE
OUTCOME_LEDGER = LEDGER_HEAD + """\
| bead-a | 2 | invest-a | t1 | t2 | /tmp/run/investigations/a.md | — | — | 1 | planned |
| bead-b | 2 | invest-b | t3 | t4 | /tmp/run/investigations/b.md | — | — | 1 | parked |
| bead-c | 2 | invest-c | t5 | t6 | /tmp/run/investigations/c.md | — | — | 1 | duplicate |
| bead-d | 2 | invest-d | t7 |  |  | — | — | 1 |  |
| group-1 | 4 | plan-1 | t8 | t9 | /tmp/run/todo/plan-one | — | — | 1 | planned |
| group-missing | 4 | plan-x | t10 | t11 | /tmp/run/todo/missing.md | — | — | 1 | planned |
| bead-a | 5 | triage-qc | t12 | t13 | /tmp/run/investigations/a.md | PASS | PASS | 1 | failed |
"""

OUTCOME_MANIFEST = {
    "groups": [
        {"group_id": "group-1", "members": ["bead-a", "bead-b", "bead-c"]},
    ]
}


def outcome_fixture(tmp: Path, ledger: str = OUTCOME_LEDGER) -> Path:
    run = tmp / "r"
    run.mkdir()
    (run / "ledger.md").write_text(ledger, encoding="utf-8")
    return run


def case_a_routed_bead_carries_its_final_and_artifact(tmp: Path) -> None:
    out = staged_run.bead_outcomes(outcome_fixture(tmp), OUTCOME_MANIFEST)
    expect(out["bead-a"], {
        "final": "planned",
        "artifacts": [
            "/tmp/run/investigations/a.md",
            "/tmp/run/todo/plan-one",
        ],
    })


def case_a_group_plan_artifact_reaches_every_member(tmp: Path) -> None:
    out = staged_run.bead_outcomes(outcome_fixture(tmp), OUTCOME_MANIFEST)
    for bead in ("bead-a", "bead-b", "bead-c"):
        assert "/tmp/run/todo/plan-one" in out[bead]["artifacts"], out[bead]


def case_a_parked_bead_records_parked(tmp: Path) -> None:
    out = staged_run.bead_outcomes(outcome_fixture(tmp), OUTCOME_MANIFEST)
    expect(out["bead-b"]["final"], "parked")
    assert "/tmp/run/investigations/b.md" in out["bead-b"]["artifacts"]


def case_a_duplicate_bead_records_duplicate(tmp: Path) -> None:
    out = staged_run.bead_outcomes(outcome_fixture(tmp), OUTCOME_MANIFEST)
    expect(out["bead-c"]["final"], "duplicate")


def case_an_in_flight_bead_is_present_with_an_empty_final(tmp: Path) -> None:
    out = staged_run.bead_outcomes(outcome_fixture(tmp), OUTCOME_MANIFEST)
    expect(out["bead-d"], {"final": "", "artifacts": []})


def case_a_run_with_no_ledger_has_no_outcomes(tmp: Path) -> None:
    run = tmp / "r"
    run.mkdir()
    expect(staged_run.bead_outcomes(run, OUTCOME_MANIFEST), {})


def case_an_unrecognised_wave_4_key_is_kept_under_its_own_key(tmp: Path) -> None:
    """A Wave 4 key the manifest does not name owns itself, so neither its
    artifact nor its outcome is lost. `final` was `""` here while the row
    carried `planned`, for the same reason the unplanned-group case below
    dropped `parked`: the Wave 4 branch read no `final` at all.
    """
    out = staged_run.bead_outcomes(outcome_fixture(tmp), OUTCOME_MANIFEST)
    expect(out["group-missing"], {
        "final": "planned",
        "artifacts": ["/tmp/run/todo/missing.md"],
    })


def case_wave_5_rows_add_no_artifact_and_no_final(tmp: Path) -> None:
    out = staged_run.bead_outcomes(outcome_fixture(tmp), OUTCOME_MANIFEST)
    expect(out["bead-a"]["final"], "planned")
    expect(out["bead-a"]["artifacts"].count("/tmp/run/investigations/a.md"), 1)


def case_wave_3_rows_add_no_artifact(tmp: Path) -> None:
    """Wave 3 is a wave row, not an artifact row.

    Its `artifact` cell holds the run's own `collision_report.md`, and
    `references/ledger.md` gives an owned artifact to the artifact rows only —
    Waves 2, 4 and 5. Treating it as promotable moves the run's evidence into
    the project's real `todo/`, where `footprint_collisions` reads every `*.md`
    under it as a landed plan, on every later run.
    """
    ledger = OUTCOME_LEDGER + (
        "| group-1 | 3 | — | t14 | t15 | /tmp/run/collision_report.md | — | SEQUENCE | 1 |  |\n"
        "| group-report | 3 | — | t16 | t17 | /tmp/run/collision_report.md | — | SEQUENCE | 1 |  |\n")
    out = staged_run.bead_outcomes(outcome_fixture(tmp, ledger), OUTCOME_MANIFEST)
    for bead in ("bead-a", "bead-b", "bead-c"):
        assert "/tmp/run/collision_report.md" not in out[bead]["artifacts"], out[bead]
    assert "group-report" not in out, sorted(out)


def case_an_unplanned_group_row_adds_no_artifact(tmp: Path) -> None:
    """`references/ledger.md`'s unplanned-group row: `worker` `—`, `artifact`
    `—`, and `final` naming why no plan exists.

    `—` is the ledger's "this row records no artifact", not a path — and it is
    truthy, so read literally every member of the group is handed an artifact
    called `—`, which `promote._artifacts_to_promote` then reports missing.

    The `final` goes the other way and must be **kept**. This case first
    asserted `final: ""`, which pinned a second half of the same defect: a
    group whose beads are all parked or duplicate has no Wave 2 row anywhere,
    so the decision record is the only outcome its members ever get. Dropping
    it made `derive_intents` report both members as "still in flight" and exit
    1 immediately before `promote.py`, asserting the opposite of what the
    ledger says. Found by the Step 5 code review of phases 6-8.
    """
    ledger = LEDGER_HEAD + "| g4 | 4 | — | t1 | t2 | — | — | — | 1 | parked |\n"
    manifest = {"groups": [{"group_id": "g4", "members": ["b-x", "b-y"]}]}
    out = staged_run.bead_outcomes(outcome_fixture(tmp, ledger), manifest)
    expect(out, {"b-x": {"final": "parked", "artifacts": []},
                 "b-y": {"final": "parked", "artifacts": []}})


def case_a_revised_wave_2_artifact_is_held_once(tmp: Path) -> None:
    """`references/ledger.md`: a re-dispatch owes its own row, at the *same*
    assigned path — a second path would orphan the first artifact. So two
    equal `artifact` cells are two references to one file, never two files.

    Read literally, a bead whose investigation took a review round names that
    path twice, and `promote.missing_artifacts` — one finding per list entry —
    reports an absent file once per round. No pre-existing case seeds a
    repeated path within one bead, which is the gap that let it ship.
    """
    ledger = LEDGER_HEAD + (
        "| bead-r | 2 | invest-r | t1 | t2 | /tmp/run/investigations/r.md | — | REVISE | 1 |  |\n"
        "| bead-r | 2 | invest-r | t3 | t4 | /tmp/run/investigations/r.md | — | PASS | 2 | planned |\n")
    out = staged_run.bead_outcomes(outcome_fixture(tmp, ledger), OUTCOME_MANIFEST)
    expect(out["bead-r"], {"final": "planned",
                           "artifacts": ["/tmp/run/investigations/r.md"]})


def case_a_revised_group_plan_reaches_every_member_once(tmp: Path) -> None:
    """The same rule one wave over, and the reason the guard is per bead: a
    group plan legitimately belongs to every member once, so the de-duplication
    cannot be a run-level seen-set — that would strip the plan from every
    member after the first.
    """
    ledger = LEDGER_HEAD + (
        "| group-1 | 4 | plan-1 | t1 | t2 | /tmp/run/todo/plan-one | — | REVISE | 1 |  |\n"
        "| group-1 | 4 | plan-1 | t3 | t4 | /tmp/run/todo/plan-one | — | PASS | 2 | planned |\n")
    out = staged_run.bead_outcomes(outcome_fixture(tmp, ledger), OUTCOME_MANIFEST)
    for bead in ("bead-a", "bead-b", "bead-c"):
        expect(out[bead], {"final": "planned",
                           "artifacts": ["/tmp/run/todo/plan-one"]})


# --- the artifact cell's own rule -------------------------------------------


def case_a_relative_artifact_cell_is_refused(tmp: Path) -> None:
    """The surface that would have failed at the moment the mistake was made.

    A run-relative cell reached a bead note as `Plan: todo/....md`, a path
    that resolves from nowhere (`skills-xfu`). This is the writer, so it
    raises rather than reporting: nobody has claimed the row is valid yet.
    """
    try:
        staged_run.ledger_row(bead="proj-a1", wave=4, worker="plan-a1",
                              artifact="todo/skills_epic_demo/plan.md")
    except staged_run.Usage as err:
        assert "path is not absolute" in str(err), err
        assert "proj-a1 wave 4" in str(err), err
    else:
        raise AssertionError("a relative artifact cell was written")


def case_an_absolute_artifact_cell_is_written(tmp: Path) -> None:
    """Calibration, and in the shape every real caller uses: a `Path` built
    from the run directory, which only reads as absolute after `str()`."""
    row = staged_run.ledger_row(bead="proj-a1", wave=2, worker="invest-a1",
                                artifact=tmp / "run" / "investigations" / "a.md",
                                final="planned")
    assert f"| {tmp}/run/investigations/a.md |" in row, row


def case_an_unfilled_artifact_cell_is_not_a_relative_path(tmp: Path) -> None:
    """A row that does not fill the cell yet — `test_promote.outcome_rows`
    writes one for a parked bead — must still be writable."""
    row = staged_run.ledger_row(bead="proj-p9", wave=2, worker="invest-p9",
                                final="parked")
    expect(row.count("|"), len(staged_run.LEDGER_COLUMNS) + 1)


def case_the_decision_records_sentinel_is_not_a_relative_path(tmp: Path) -> None:
    """`references/ledger.md` § *The row kinds*: a Wave 4 decision record for
    a group nobody planned writes `artifact` `—` deliberately. Reading that as
    a relative path breaks the row kind whose misreading already stranded a
    resume at Wave 5."""
    row = staged_run.ledger_row(bead="g4", wave=4, worker="—", artifact="—",
                                final="parked")
    assert "| — |" in row, row


CASES = [v for k, v in sorted(globals().items()) if k.startswith("case_")]


def main() -> int:
    failed = 0
    for case in CASES:
        with tempfile.TemporaryDirectory() as td:
            try:
                case(Path(td))
                print(f"PASS  {case.__name__}")
            except AssertionError as e:
                failed += 1
                print(f"FAIL  {case.__name__}: {e}")
            except Exception:
                failed += 1
                print(f"ERROR {case.__name__}")
                traceback.print_exc()
    print(f"\n{len(CASES) - failed}/{len(CASES)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
