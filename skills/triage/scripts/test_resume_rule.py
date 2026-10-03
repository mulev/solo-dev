#!/usr/bin/env python3
"""Tests for `staged_run.first_incomplete_wave` — the wave a `--resume` continues from.

Split out of `test_staged_run.py` (`skills-way.6`) when that file passed the
300-LOC signal: the resume rule needs ten-column fixtures of its own, and a test
module named for its subject is not a satellite. `run_tests.py` globs
`test_*.py`, so nothing registers it.

Run with `python3 test_resume_rule.py` (no pytest dependency).
"""

from __future__ import annotations

import sys
import tempfile
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import staged_run  # noqa: E402


def expect(got, want) -> None:
    assert got == want, f"got {got!r}, want {want!r}"


# The canonical ten columns — the same names `staged_run.LEDGER_COLUMNS` seeds
# into every real ledger. The six-column shorthand this replaced had no
# `artifact` column, so the rule below could not be expressed against it.
HEAD = "# Triage run ledger\n\nMode: `full run`\n\n" + staged_run.LEDGER_TABLE
ROW_WAVE_0 = ("| all | 0 | — | 2026-08-29T10:00:00Z | 2026-08-29T10:00:03Z "
              "| /r/manifest.json | — | — | 1 |  |")
ROW_CLUSTER = ("| c1-g1 | 1 | dup-judge | 2026-08-29T10:01:00Z "
               "| 2026-08-29T10:04:12Z | /r/judge_brief.md | — "
               "| related-not-duplicate | 1 |  |")
ROW_CLUSTER_IN_FLIGHT = ("| c1-g1 | 1 | dup-judge | 2026-08-29T10:01:00Z |  "
                         "| /r/judge_brief.md | — | — | 1 |  |")
# Returned, gated, and carrying an **empty** `final`: complete under the rule,
# and the single row the old one read as owing Wave 2 work forever.
ROW_B_A = ("| b-a | 2 | invest-a | 2026-08-29T10:05:00Z | 2026-08-29T10:22:31Z "
           "| /r/investigations/a.md | — | — | 1 |  |")
ROW_B_A_GATE = ("| b-a | 5 | triage-qc | 2026-08-29T10:23:00Z "
                "| 2026-08-29T10:31:07Z | /r/investigations/a.md | PASS | PASS "
                "| 1 | planned |")
ROW_B_B_IN_FLIGHT = ("| b-b | 2 | invest-b | 2026-08-29T10:05:00Z |  "
                     "| /r/investigations/b.md | — | — | 1 |  |")
ROW_B_B = ("| b-b | 2 | invest-b | 2026-08-29T10:05:00Z | 2026-08-29T10:24:02Z "
           "| /r/investigations/b.md | — | — | 1 |  |")
ROW_B_B_GATE = ("| b-b | 5 | triage-qc | 2026-08-29T10:25:00Z "
                "| 2026-08-29T10:33:19Z | /r/investigations/b.md | PASS | PASS "
                "| 1 | planned |")
# Two artifact rows that name no path, one gated and one not.
ROW_NO_PATH = ("| b-c | 2 | invest-c | 2026-08-29T10:05:00Z "
               "| 2026-08-29T10:26:44Z | — | — | — | 1 |  |")
ROW_NO_PATH_GATE = ("| b-c | 5 | triage-qc | 2026-08-29T10:27:00Z "
                    "| 2026-08-29T10:35:12Z | — | PASS | PASS | 1 | planned |")
ROW_NO_PATH_UNGATED = ("| b-d | 2 | invest-d | 2026-08-29T10:05:00Z "
                       "| 2026-08-29T10:28:10Z | — | — | — | 1 |  |")
# Phase 8's rows: a settled Wave 2 artifact, its gate row carrying an empty
# `final` (the rule `references/ledger.md` states), and Wave 6's own row.
ROW_B_A_SETTLED = ("| b-a | 2 | invest-a | 2026-08-29T10:05:00Z "
                   "| 2026-08-29T10:22:31Z | /r/investigations/a.md | — | — "
                   "| 1 | planned |")
ROW_B_A_GATE_NO_FINAL = ("| b-a | 5 | triage-qc | 2026-08-29T10:23:00Z "
                         "| 2026-08-29T10:31:07Z | /r/investigations/a.md "
                         "| PASS | PASS | 1 |  |")
ROW_WAVE_6 = ("| all | 6 | — | 2026-08-29T11:00:00Z | 2026-08-29T11:00:02Z "
              "| /r/report.md | — | — | 1 |  |")
# A group nobody planned: no worker, no artifact, both stamps measured. The
# row records a decision, so it owes no gate.
ROW_UNPLANNED_GROUP = ("| g4 | 4 | — | 2026-08-29T10:40:00Z "
                       "| 2026-08-29T10:40:00Z | — | — | — | 1 | parked |")
# A real planning dispatch that omitted its artifact path. It still owes its
# gate — a skip keyed on the wave alone would report this run finished.
ROW_PLAN_NO_PATH = ("| g5 | 4 | plan-g5 | 2026-08-29T10:41:00Z "
                    "| 2026-08-29T10:52:00Z | — | — | — | 1 | planned |")


def ledger(*rows: str) -> str:
    """A ledger whose wave table holds exactly `rows`."""
    return HEAD + "".join(f"{row}\n" for row in rows)


LEDGER = ledger(ROW_WAVE_0, ROW_CLUSTER, ROW_B_A, ROW_B_A_GATE,
                ROW_B_B_IN_FLIGHT)
# A run with nothing outstanding — the rows both Phase 8 cases build on.
FINISHED_ROWS = (ROW_WAVE_0, ROW_CLUSTER, ROW_B_A_SETTLED,
                 ROW_B_A_GATE_NO_FINAL, ROW_WAVE_6)


def ledger_fixture(tmp: Path, text: str = LEDGER) -> Path:
    run = tmp / "r"
    run.mkdir(parents=True)
    (run / "ledger.md").write_text(text, encoding="utf-8")
    return run


def mid_run_ledger() -> str:
    """Nine returned Wave 2 rows, eight of them gated, one gate in flight.

    The live shape of `2026-08-31_4d55fd`: every investigation came back with an
    empty `final`, because a Wave 2 row's outcome is not settled until Wave 4 or
    Wave 5 rules on it.
    """
    beads = [f"b{n}" for n in range(1, 10)]
    rows = [ROW_WAVE_0, ROW_CLUSTER]
    rows += [f"| {bead} | 2 | invest-{bead} | 2026-08-29T10:05:00Z "
             f"| 2026-08-29T10:22:31Z | /r/investigations/{bead}.md | — | — "
             f"| 1 |  |" for bead in beads]
    rows += [f"| {bead} | 5 | triage-qc | 2026-08-29T10:23:00Z "
             f"| 2026-08-29T10:31:07Z | /r/investigations/{bead}.md | PASS "
             f"| PASS | 1 | planned |" for bead in beads[:-1]]
    rows.append(f"| {beads[-1]} | 5 | triage-qc | 2026-08-29T10:32:00Z |  "
                f"| /r/investigations/{beads[-1]}.md | — | — | 1 |  |")
    return ledger(*rows)


def case_ledger_rows_reads_the_wave_table(tmp: Path) -> None:
    rows = staged_run.ledger_rows(ledger_fixture(tmp))
    assert [r["bead"] for r in rows] == [
        "all", "c1-g1", "b-a", "b-a", "b-b"], rows


def case_a_returned_wave_two_with_wave_five_in_flight_resumes_at_five(
        tmp: Path) -> None:
    """`skills-w7z`, the live failure this phase exists for.

    All nine investigations returned and eight are reviewed; the ninth review is
    still out. The work that is missing is the gate, so the resume belongs at
    Wave 5 — sending it to Wave 2 re-dispatches nine workers whose artifacts are
    already on disk.
    """
    expect(staged_run.first_incomplete_wave(
        ledger_fixture(tmp, mid_run_ledger())), 5)


def case_an_undispatched_return_makes_its_wave_incomplete(tmp: Path) -> None:
    run = ledger_fixture(tmp, LEDGER.replace(ROW_CLUSTER,
                                             ROW_CLUSTER_IN_FLIGHT))
    expect(staged_run.first_incomplete_wave(run), 1)


def case_a_wave_two_row_in_flight_resumes_at_two(tmp: Path) -> None:
    """`skills-j4q`'s carve-out, now a consequence rather than a special case.

    `b-b` never returned, so Wave 2 owes work. The cluster row and the Wave 0
    row leave `final` empty by design, and `b-a` — returned and gated — owes
    nothing despite an empty `final` of its own.
    """
    expect(staged_run.first_incomplete_wave(ledger_fixture(tmp)), 2)


def case_an_ungated_wave_two_artifact_resumes_at_five(tmp: Path) -> None:
    """`b-a` returned and was never reviewed, and no Wave 2 work is left."""
    run = ledger_fixture(tmp, ledger(ROW_WAVE_0, ROW_CLUSTER, ROW_B_A,
                                     ROW_B_B, ROW_B_B_GATE))
    expect(staged_run.first_incomplete_wave(run), 5)


def case_a_fully_gated_ledger_has_no_incomplete_wave(tmp: Path) -> None:
    run = ledger_fixture(tmp, ledger(ROW_WAVE_0, ROW_CLUSTER, ROW_B_A,
                                     ROW_B_A_GATE, ROW_B_B, ROW_B_B_GATE))
    expect(staged_run.first_incomplete_wave(run), None)


def case_a_lone_returned_cluster_row_is_complete(tmp: Path) -> None:
    """No artifact row exists yet, so nothing is owed — an empty `final` on
    both rows is the normal state of a run that has only judged its clusters."""
    run = ledger_fixture(tmp, ledger(ROW_WAVE_0, ROW_CLUSTER))
    expect(staged_run.first_incomplete_wave(run), None)


def case_a_row_with_no_artifact_path_is_keyed_by_its_bead(tmp: Path) -> None:
    """`_gate_key`'s fallback, applied to both sides of the match.

    Neither row names a path, so the bead is all there is to key on. `b-c` is
    gated and `b-d` is not; a key that collapsed both to the empty string would
    read `b-d` as gated and report a finished run.
    """
    run = ledger_fixture(tmp, ledger(ROW_NO_PATH, ROW_NO_PATH_GATE,
                                     ROW_NO_PATH_UNGATED))
    expect(staged_run.first_incomplete_wave(run), 5)


def case_a_wave_5_row_without_a_final_does_not_reopen_the_run(tmp: Path) -> None:
    """`references/ledger.md`'s rule that a Wave 5 row leaves `final` empty.

    If `first_incomplete_wave` read `final` on a gate row, every run that
    obeyed that rule would resume at Wave 5 forever.
    """
    run = ledger_fixture(tmp, ledger(*FINISHED_ROWS))
    expect(staged_run.first_incomplete_wave(run), None)


def case_a_group_nobody_planned_owes_no_gate(tmp: Path) -> None:
    """The unplanned-group row records a decision, not an artifact.

    `worker` `—` and `artifact` `—` are sentinels, and both are truthy: read
    literally the row is an ungated artifact row, and the run resumes at Wave 5
    for the rest of its life. A planning dispatch that merely omitted its path
    still owes its gate, which is why the skip tests the worker as well.
    """
    expect(staged_run.first_incomplete_wave(ledger_fixture(
        tmp / "decided", ledger(*FINISHED_ROWS, ROW_UNPLANNED_GROUP))), None)
    expect(staged_run.first_incomplete_wave(ledger_fixture(
        tmp / "omitted", ledger(*FINISHED_ROWS, ROW_PLAN_NO_PATH))), 5)


def case_a_missing_ledger_resumes_from_wave_zero(tmp: Path) -> None:
    run = tmp / "r"
    run.mkdir()
    expect(staged_run.first_incomplete_wave(run), 0)


def case_the_real_finished_run_has_no_incomplete_wave(tmp: Path) -> None:
    """Regression on real data: the finished run whose resume was sent back to
    Wave 2 while it was correctly working Wave 5.

    Read from the copy under `fixtures/`, never from the live run — a test that
    depended on that path would break the day the run was promoted, which it
    was. The copy is verbatim, close-out prose included: its 3-cell tables are
    skipped by `ledger_rows`' width rule, and that is worth having under test.
    """
    fixture = HERE / "fixtures" / "ledger_2026-08-31_4d55fd.md"
    run = ledger_fixture(tmp, fixture.read_text(encoding="utf-8"))
    expect(len(staged_run.ledger_rows(run)), 44)
    expect(staged_run.first_incomplete_wave(run), None)


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
