#!/usr/bin/env python3
"""Tests for what happens to absolute paths once the move is done.

Split out of `test_promote.py`, which owns the move itself and the `staged`
fixture both files share. The seam is real: everything here is about the
rewrite and the guard that catches what the rewrite could not map, on the
files and on the intents alike. The move map is the only source of pairs —
there is no catch-all, and the two `skills-foa` cases at the end are what
pins that down.

Run with `python3 test_promote_paths.py` (no pytest dependency).
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import intent_records  # noqa: E402
import manifest as manifest_io  # noqa: E402
import promote  # noqa: E402
import tracker_intents  # noqa: E402
from staged_run import ledger_row  # noqa: E402
from test_lint_plan import slice_text  # noqa: E402
from test_promote import (INVEST_NAME, LEDGER, PLAN_FOLDER, PROJECT,  # noqa: E402
                          RecordingRunner, codes, expect, manifest_bead,
                          moved_for, plans_dir, repo_root, seed_ledger, staged)


# --- the rewrite, and the guard on what it could not map ---------------------


def case_rewrite_respects_path_boundary(tmp: Path) -> None:
    old, new = "/runs/r1/todo", "/plans/p/todo"
    text = f"a {old}/x.md b {old}_backup/y.md c {old} d\n"
    expect(promote.rewrite_paths(text, old, new),
           f"a {new}/x.md b {old}_backup/y.md c {new} d\n")


def case_rewrite_replaces_staging_root_everywhere(tmp: Path) -> None:
    run = staged(tmp)
    body = (f"### File: `demo/thing_1.py`\n\nSee {run}/investigations/{INVEST_NAME}\n"
            f"and {run}/todo/{PLAN_FOLDER}/plan.md for the rest.\n")
    (run / "todo" / PLAN_FOLDER / "phase_1_demo_slice.md").write_text(
        slice_text(1, files=body), encoding="utf-8")
    _, findings, _ = moved_for(run)
    expect(codes(findings), [])
    text = (tmp / "plans" / PROJECT / "todo" / PLAN_FOLDER /
            "phase_1_demo_slice.md").read_text(encoding="utf-8")
    assert str(run) not in text, text
    assert f"{tmp}/plans/{PROJECT}/investigations/{INVEST_NAME}" in text, text
    assert f"{tmp}/plans/{PROJECT}/todo/{PLAN_FOLDER}/plan.md" in text, text


def case_stale_path_left_behind_is_a_finding(tmp: Path) -> None:
    """A run-root path no move-map entry covers must stop the run, not be
    rewritten to an invented target — there is no catch-all prefix pair."""
    run = staged(tmp)
    stray = run / "todo" / PLAN_FOLDER / "plan.md"
    stray.write_text(stray.read_text(encoding="utf-8") +
                     f"\nunmapped: {run}/collision_report.md\n", encoding="utf-8")
    _, findings, _ = moved_for(run)
    assert "promote-stale-path" in codes(findings), codes(findings)


def case_intent_naming_the_run_root_is_a_finding(tmp: Path) -> None:
    run = staged(tmp)
    findings = promote.stale_intents(
        [{"key": "solo", "kind": "create-task",
          "slice": str(run / "todo" / "x.md")}], run)
    expect(codes(findings), ["promote-stale-path"])
    expect(findings[0].subject, "solo.slice")


def case_promoted_intents_are_not_stale(tmp: Path) -> None:
    run = staged(tmp)
    moved, _, _ = moved_for(run)
    expect(promote.stale_intents(
        promote.remap(intent_records.load_all(run), moved), run), [])


def case_remap_moves_intent_paths_to_promoted_homes(tmp: Path) -> None:
    run = staged(tmp)
    moved, _, _ = moved_for(run)
    out = promote.remap(intent_records.load_all(run), moved)
    joined = json.dumps(out)
    assert str(run) not in joined, joined
    assert f"{tmp}/plans/{PROJECT}/todo/{PLAN_FOLDER}/plan.md" in joined, joined


def case_citation_to_a_quarantined_artifact_is_a_stale_path(tmp: Path) -> None:
    """A quarantined bead's file stays staged, so a citation to it maps nowhere.

    Rewriting it to the real directory anyway invents a target for a path
    nothing moved: the promoted plan ends up linking a file that was never
    promoted, and because the text no longer names the run root the
    `promote-stale-path` guard cannot see it.
    """
    run = staged(tmp)
    art = run / "investigations" / INVEST_NAME
    data = manifest_io.load(run / "manifest.json")
    data["beads"].append(manifest_bead("proj-b2", "investigate"))
    manifest_io.save(run / "manifest.json", data)
    seed_ledger(run, [
        ledger_row(bead="proj-a1", wave=4, worker="plan-a1",
                   dispatched="2026-08-28T10:02:00Z", returned="2026-08-28T10:03:00Z",
                   artifact=run / "todo" / PLAN_FOLDER, final="planned"),
        ledger_row(bead="proj-b2", wave=2, worker="invest-b2",
                   dispatched="2026-08-28T10:04:00Z", returned="2026-08-28T10:05:00Z",
                   artifact=art, final="planned"),
    ])
    plan = run / "todo" / PLAN_FOLDER / "plan.md"
    plan.write_text(plan.read_text(encoding="utf-8") +
                    f"\n**Investigation:** {art}\n", encoding="utf-8")
    _, findings, _ = moved_for(run, {"proj-b2"})
    expect(codes(findings), ["promote-stale-path"])
    real = tmp / "plans" / PROJECT / "investigations" / INVEST_NAME
    assert not real.exists(), real
    assert (run / "investigations" / INVEST_NAME).is_file()


def case_a_promoted_sibling_is_still_rewritten(tmp: Path) -> None:
    """Calibration: the pair that does exist must keep working.

    The move map covers every artifact of every promoting bead, so a citation
    between two of them is rewritten with no catch-all in sight.
    """
    run = staged(tmp)
    art = str(run / "investigations" / INVEST_NAME)
    plan = run / "todo" / PLAN_FOLDER / "plan.md"
    plan.write_text(plan.read_text(encoding="utf-8") +
                    f"\n**Investigation:** {art}\n", encoding="utf-8")
    _, findings, _ = moved_for(run)
    expect(codes(findings), [])
    promoted = tmp / "plans" / PROJECT / "todo" / PLAN_FOLDER / "plan.md"
    text = promoted.read_text(encoding="utf-8")
    assert str(tmp / "plans" / PROJECT / "investigations" / INVEST_NAME) in text, text
    assert str(run) not in text, text


# --- the epic's whole point, end to end -------------------------------------


def case_a_relative_artifact_cell_never_reaches_a_bd_write(tmp: Path) -> None:
    """The epic's whole point, end to end: a run whose ledger carries a
    relative artifact cell cannot reach a `bd --notes` write.

    Promote stops on the pre-flight's finding, before the move and before any
    tracker write, so the note that orphaned a bead from its plan is never
    written. Reads still happen — `bead_states` asks the tracker whether a
    bead moved — so the assertion is about writes.
    """
    run = staged(tmp)
    rows = (run / "ledger.md").read_text(encoding="utf-8")
    seed_ledger(run, [rows.split(LEDGER, 1)[1].replace(
        str(run / "todo" / PLAN_FOLDER), "todo/" + PLAN_FOLDER)])
    fake = RecordingRunner()
    real, tracker_intents.default_runner = tracker_intents.default_runner, fake
    try:
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = promote.main([
                "--run-id", run.name, "--runs-dir", str(run.parent),
                "--plans-dir", str(plans_dir(run)), "--repo-root", repo_root(run),
                "--system-plan-dir", str(tmp / "system_plans"), "--json"])
    finally:
        tracker_intents.default_runner = real
    expect(code, 1)
    report = json.loads(out.getvalue())
    assert "promote-ledger-relative-artifact" in [
        f["code"] for f in report["findings"]], report["findings"]
    writes = [argv for argv, _ in fake.calls if argv[1] != "show"]
    expect(writes, [])
    assert not (tmp / "plans" / PROJECT / "todo" / PLAN_FOLDER).exists(), \
        "a preflight stop moves nothing"


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
