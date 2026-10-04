#!/usr/bin/env python3
"""Tests for the promote preflight's rules about the intent store's own records.

Split out of `test_staged_run_checks.py`, which covers the preflight's rules
about the world around the run — collisions, coverage, footprints, tracker
state. These cases seed one malformed record into the store and assert the
preflight *reports* it: a bad record has to come back as a finding, never as a
traceback that replaces the whole report (`intent_records.py:12-20`).

Every case goes through `preflight`, deliberately. `invalid_intents` computing
a finding is not the property under test — the run reaching the point where it
can print one is, and two of the defects here were readers downstream of that
check crashing on the same record it had just named.

Fixtures come from `test_promote.py` and `check` from `test_staged_run_checks.py`.
Run with `python3 test_staged_run_store_checks.py`.
"""

from __future__ import annotations

import sys
import tempfile
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import intent_records  # noqa: E402
import staged_run  # noqa: E402
from test_promote import PLAN_FOLDER, expect, staged  # noqa: E402
from test_staged_run_checks import check  # noqa: E402


def case_a_worker_written_record_with_a_relative_slice_stops_the_run(tmp: Path) -> None:
    """`intent_records.validate` is called by `derive_intents` over what it
    derives, and by nothing else. A Wave 5 worker saves its own records
    (`triage/SKILL.md:330-332`), so this record used to reach
    `tracker_intents.render` validated by nothing at all.
    """
    run = staged(tmp)
    intent_records.save(run, "proj-w1", [{
        "key": "phase-9", "kind": "create-task", "ref": "phase_9",
        "bead": "proj-w1", "title": "Phase 9: worker written",
        "description": "Step 9.1 ...", "parent": "epic",
        "master": str(run / "todo" / PLAN_FOLDER / "plan.md"),
        "slice": "todo/skills_epic_demo_thing/phase_9_worker.md"}])
    findings, _ = check(run)
    hits = [f for f in findings if f.code == "promote-intent-invalid"]
    expect([f.subject for f in hits], ["proj-w1/phase-9"])
    assert "slice" in hits[0].detail, hits
    assert "path is not absolute" in hits[0].detail, hits


def case_a_record_that_is_not_an_object_is_named_rather_than_crashed_on(tmp: Path) -> None:
    """A store file is a JSON list, and nothing guarantees its members are
    objects. `load_all` returns them as they are, so `invalid_intents` reads
    the key only when there is something to read it off — the alternative is
    an `AttributeError` from the check that exists to report bad records.
    `validate` names the type, and `<no key>` is its own placeholder for a
    record that cannot have one.
    """
    run = staged(tmp)
    intent_records.save(run, "proj-w2", ["not an object"])
    findings, _ = check(run)
    hits = [f for f in findings if f.code == "promote-intent-invalid"]
    expect([f.subject for f in hits], ["<no key>"])
    assert "not an object" in hits[0].detail, hits


def case_a_record_with_no_key_is_named_rather_than_crashed_on(tmp: Path) -> None:
    """A record can be an object and still name no key — the shape `validate`
    reports as `<no key>: flip-source carries no key`. `applied_states` reads
    `key` off every record of a `SOURCE_KIND` to ask whether this run already
    applied it, so a keyless one used to raise `KeyError` out of `preflight`
    *after* `invalid_intents` had already computed the finding for it. A record
    that names no key cannot be one an earlier pass applied.
    """
    run = staged(tmp)
    intent_records.save(run, "proj-w3", [{
        "kind": "flip-source", "bead": "proj-w3",
        "plan": str(run / "todo" / PLAN_FOLDER / "plan.md")}])
    findings, _ = check(run)
    hits = [f for f in findings if f.code == "promote-intent-invalid"]
    expect([f.subject for f in hits], ["<no key>"])
    assert "carries no key" in hits[0].detail, hits


def case_an_applied_record_with_a_relative_path_is_reported_not_raised(tmp: Path) -> None:
    """The incident's own recovery path: a first pass applied the record that
    carried the relative path, so `applied_states` reads its status back off
    `render` — which now refuses a relative path. That `Usage` used to escape
    `preflight` and exit 2, the code `promote.py`'s EPILOG reserves for a usage
    or environment error and never a bad artifact. A record `invalid_intents`
    has already reported is not one to render.
    """
    run = staged(tmp)
    intent_records.save(run, "proj-w4", [{
        "key": "flip-w4", "kind": "flip-source", "bead": "proj-w4",
        "plan": "todo/skills_epic_demo_thing/plan.md"}])
    staged_run.record_step(run, "proj-w4/flip-w4", "proj-w4")
    findings, _ = check(run)
    hits = [f for f in findings if f.code == "promote-intent-invalid"]
    expect([f.subject for f in hits], ["proj-w4/flip-w4"])
    assert "path is not absolute" in hits[0].detail, hits


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
