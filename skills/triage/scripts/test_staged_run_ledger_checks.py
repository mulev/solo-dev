#!/usr/bin/env python3
"""Tests for the promote preflight's two checks on one ledger row's own shape.

Split out of `test_staged_run_checks.py`, which covers the preflight's rules
about the world around the run — collisions, coverage, footprints, tracker
state. The cases here judge a single row against `references/ledger.md`. The
artifact cases call `ledger_artifacts` directly, so the row under test is the
whole fixture; the clock cases assert through `preflight`, which is also what
proves each check is wired into it.

Fixtures come from `test_promote.py` and `check` from `test_staged_run_checks.py`.
Run with `python3 test_staged_run_ledger_checks.py`.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import staged_run  # noqa: E402
import staged_run_checks  # noqa: E402
from test_promote import LEDGER, codes, expect, staged  # noqa: E402
from test_staged_run_checks import check  # noqa: E402


# --- the ledger's own clock -------------------------------------------------


def ledger(run: Path, *rows: str) -> None:
    """The fixture ledger plus wave rows.

    A row names only the five columns this check reads; the remaining five of
    `staged_run.LEDGER_COLUMNS` are padded empty, because `ledger_rows` reads a
    row as a wave row only when its width matches the header.
    """
    tail = "  |" * (len(staged_run.LEDGER_COLUMNS) - 5)
    (run / "ledger.md").write_text(
        LEDGER + "".join(f"{row}{tail}\n" for row in rows), encoding="utf-8")


def case_a_well_ordered_ledger_passes(tmp: Path) -> None:
    """The anchor for this check: the fixture's ledger carries no rows at all,
    so without one of these the other cases prove only that a check exists."""
    run = staged(tmp)
    ledger(run,
           "| all | 0 | — | 2026-08-31T08:43:53Z | 2026-08-31T08:43:54Z |",
           "| proj-a1 | 2 | invest-1 | 2026-08-31T08:44:00Z | 2026-08-31T09:01:12Z |")
    findings, _ = check(run)
    assert "promote-ledger-out-of-order" not in codes(findings), codes(findings)


def case_a_return_before_its_own_dispatch_stops_the_promote(tmp: Path) -> None:
    """What `references/ledger.md` says the ordering means: an artifact that
    came back before it was asked for was not produced by this dispatch."""
    run = staged(tmp)
    ledger(run,
           "| proj-a1 | 2 | invest-1 | 2026-08-31T09:01:12Z | 2026-08-31T08:44:00Z |")
    findings, _ = check(run)
    assert "promote-ledger-out-of-order" in codes(findings), codes(findings)


def case_a_same_second_row_is_not_out_of_order(tmp: Path) -> None:
    """Waves 0, 1, 3 and 6 are main-session work that starts and finishes
    inside one second. Flagging those makes the check fire on every run."""
    run = staged(tmp)
    ledger(run, "| all | 3 | — | 2026-08-31T08:49:04Z | 2026-08-31T08:49:04Z |")
    findings, _ = check(run)
    assert "promote-ledger-out-of-order" not in codes(findings), codes(findings)


def case_an_in_flight_row_is_not_out_of_order(tmp: Path) -> None:
    """An empty `returned` is a row mid-dispatch, which the resume protocol
    reads. It is not a promote-time defect and must not read as one."""
    run = staged(tmp)
    ledger(run, "| proj-a1 | 2 | invest-1 | 2026-08-31T08:44:00Z |  |")
    findings, _ = check(run)
    assert "promote-ledger-out-of-order" not in codes(findings), codes(findings)


def case_an_unreadable_timestamp_is_its_own_finding(tmp: Path) -> None:
    """A stamp the check cannot parse is a stamp it cannot vouch for. Skipping
    it silently is how a bare date — which the ledger already forbids — walks
    past the only check that would have caught it."""
    run = staged(tmp)
    ledger(run, "| proj-a1 | 2 | invest-1 | 2026-08-31 | 2026-08-31 |")
    findings, _ = check(run)
    assert "promote-ledger-bad-timestamp" in codes(findings), codes(findings)


# --- the artifact cell -------------------------------------------------------


def artifact_rows(run: Path, *rows: str) -> None:
    """The fixture ledger plus wave rows that fill six columns, `artifact`
    included; the remaining four are padded empty.

    These rows cannot come from `staged_run.ledger_row` — it refuses the cell
    this check is about, which is the whole reason the check exists: a cell
    typed straight into `ledger.md` never passes through the writer.
    """
    tail = "  |" * (len(staged_run.LEDGER_COLUMNS) - 6)
    (run / "ledger.md").write_text(
        LEDGER + "".join(f"{row}{tail}\n" for row in rows), encoding="utf-8")


STAMPS = "2026-08-31T08:44:00Z | 2026-08-31T09:01:12Z"


def case_a_relative_artifact_cell_typed_into_the_ledger_is_one_finding(tmp: Path) -> None:
    """The incident's own shape, and the row is named so the user can find it."""
    run = staged(tmp)
    artifact_rows(run, f"| proj-a1 | 4 | plan-a1 | {STAMPS} | todo/demo/plan.md |")
    findings = staged_run_checks.ledger_artifacts(run)
    expect([f.code for f in findings], ["promote-ledger-relative-artifact"])
    expect(findings[0].subject, "proj-a1 wave 4")
    assert "todo/demo/plan.md" in findings[0].detail, findings[0]


def case_an_absolute_artifact_cell_adds_no_finding(tmp: Path) -> None:
    """The anchor: a check that fires on a correct ledger is worse than none.
    The `staged` fixture's own ledger is written by `ledger_row`, so this is
    also the pair of surfaces agreeing on one value."""
    expect(staged_run_checks.ledger_artifacts(staged(tmp)), [])


def case_an_unfilled_artifact_cell_adds_no_finding(tmp: Path) -> None:
    run = staged(tmp)
    artifact_rows(run, f"| proj-p9 | 2 | invest-p9 | {STAMPS} |  |")
    expect(staged_run_checks.ledger_artifacts(run), [])


def case_a_decision_records_sentinel_adds_no_finding(tmp: Path) -> None:
    """The row kind this check must not break: `worker` `—`, `artifact` `—`,
    `final` naming why no plan exists (`references/ledger.md:181-192`)."""
    run = staged(tmp)
    artifact_rows(run, f"| g4 | 4 | — | {STAMPS} | — |")
    expect(staged_run_checks.ledger_artifacts(run), [])


def case_the_relative_cell_reaches_preflights_findings(tmp: Path) -> None:
    """The wiring. A check nothing calls reports nothing, and `preflight` is
    the only thing between a bad cell and a `bd` write."""
    run = staged(tmp)
    artifact_rows(run, f"| proj-a1 | 4 | plan-a1 | {STAMPS} | todo/demo/plan.md |")
    findings, _ = check(run)
    assert "promote-ledger-relative-artifact" in codes(findings), codes(findings)


# --- the rules this phase states as prose and enforces nowhere --------------


def case_the_stalled_runs_ledger_adds_no_finding(tmp: Path) -> None:
    """The guard that keeps the ledger's new rules from stranding a live run.

    `2026-08-31_4d55fd` breaks all three: `final` on its Wave 5 rows, one of
    them reading `failed` for a reviewer process that died, and `g4`/`g5`/`g6`
    carrying a Wave 3 row and no Wave 4 row. It must still promote — a new
    `preflight` finding on that shape is the failure this epic exists to
    prevent. It reads the vendored copy of the run's own ledger, the one
    `test_resume_rule.py` also uses, so no transcription can drift from the
    run it stands for. Green today by design; it turns red the day someone
    enforces one of these rules in `preflight`, which is the day they need to
    be told.
    """
    run = staged(tmp)
    shutil.copyfile(HERE / "fixtures" / "ledger_2026-08-31_4d55fd.md",
                    run / "ledger.md")
    # Guard against a vacuous fixture: a header width that stopped matching
    # would make `ledger_rows` skip every row and this case prove nothing.
    expect(len(staged_run.ledger_rows(run)), 44)
    findings, quarantined = check(run)
    expect([f for f in findings if f.severity == "error"], [])
    expect(quarantined, set())



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
