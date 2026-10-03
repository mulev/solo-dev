"""Tests for validate_verdict.py's pure model — the schema interpreter, the
cross-field rules, and the convergence policy in `next_action()`.

Everything here runs in process. The command line is covered by
test_validate_verdict_cli.py, which drives the script as a subprocess — the
same seam test_collide.py / test_collide_cli.py already uses.

Run with `python3 test_validate_verdict.py` (no pytest dependency).
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import validate_verdict as vv  # noqa: E402

REQUIRED = ("verdict", "defect_class", "defects", "confidence", "round")
HARD = ("root-cause-unproven", "requirement-invented", "stop-list")


def expect(actual, wanted, note: str = "") -> None:
    prefix = f"{note}: " if note else ""
    assert actual == wanted, f"{prefix}expected {wanted!r}, got {actual!r}"


def mentions(errors, needle: str) -> None:
    joined = " | ".join(errors)
    assert needle in joined, f"no error mentioning {needle!r} in: {joined}"


def defect(location="a.md:1", severity="major", why="claim is not supported"):
    return {"severity": severity, "location": location, "why": why}


def verdict(**over):
    """A well-formed PASS verdict. Keyword arguments replace any field."""
    v = {
        "verdict": "PASS",
        "defect_class": "none",
        "defects": [],
        "confidence": 0.9,
        "round": 1,
    }
    v.update(over)
    return v


def revise(locations, why="claim is not supported", **over):
    """A REVISE verdict carrying one repairable defect per location."""
    defects = [defect(loc, why=why) for loc in locations]
    v = verdict(verdict="REVISE", defect_class="repairable", defects=defects)
    v.update(over)
    return v


# --- validate(): schema rules -------------------------------------------------


def case_wellformed_pass_validates() -> None:
    expect(vv.validate(verdict()), [])


def case_non_object_verdict_rejected() -> None:
    mentions(vv.validate(["not", "an", "object"]), "object")


def case_unknown_verdict_string_rejected() -> None:
    mentions(vv.validate(verdict(verdict="APPROVE")), "APPROVE")


def case_missing_required_field_rejected() -> None:
    for key in REQUIRED:
        v = verdict()
        del v[key]
        mentions(vv.validate(v), key)


def case_unknown_property_rejected() -> None:
    mentions(vv.validate(verdict(reviewer="triage-qc")), "reviewer")


def case_confidence_out_of_range_rejected() -> None:
    mentions(vv.validate(verdict(confidence=1.4)), "confidence")
    mentions(vv.validate(verdict(confidence=-0.1)), "confidence")
    expect(vv.validate(verdict(confidence=0)), [])
    expect(vv.validate(verdict(confidence=1)), [])


def case_round_must_be_integer() -> None:
    mentions(vv.validate(verdict(round=1.5)), "round")
    mentions(vv.validate(verdict(round=True)), "round")
    mentions(vv.validate(verdict(round=0)), "round")


def case_defect_shape_enforced() -> None:
    missing_why = defect()
    del missing_why["why"]
    mentions(vv.validate(revise(["a.md:1"], defects=[missing_why])), "why")
    mentions(vv.validate(revise([""])), "location")
    mentions(vv.validate(revise(["a.md:1"], defects=[defect(severity="blocker")])),
             "blocker")


def case_unsupported_schema_keyword_is_an_error() -> None:
    errors = vv._check("x", {"type": "string", "pattern": "^x$"}, "$")
    mentions(errors, "pattern")
    errors = vv._check({}, {"type": "object", "additionalProperties": True}, "$")
    mentions(errors, "additionalProperties")


# --- validate(): cross-field rules -------------------------------------------


def case_pass_with_defects_rejected() -> None:
    mentions(vv.validate(verdict(defects=[defect()])), "empty defects")


def case_revise_without_defects_rejected() -> None:
    mentions(
        vv.validate(verdict(verdict="REVISE", defect_class="repairable")),
        "at least one defect",
    )


def case_hard_class_with_revise_rejected() -> None:
    v = revise(["a.md:1"], defect_class="root-cause-unproven")
    mentions(vv.validate(v), "PARK")
    expect(vv.next_action([v]), "PARK", "the correction lands in next_action")


def case_defect_class_none_requires_pass() -> None:
    v = verdict(verdict="REVISE", defects=[defect()])
    mentions(vv.validate(v), "'none' is only legal with verdict PASS")


def case_pass_requires_defect_class_none() -> None:
    mentions(vv.validate(verdict(defect_class="repairable")), "defect_class 'none'")


def case_park_with_repairable_is_legal() -> None:
    v = revise(["a.md:1"], verdict="PARK", round=2)
    expect(vv.validate(v), [], "non-convergence PARK is a well-formed verdict")


# --- next_action(): revision and convergence policy ---------------------------


def case_empty_history_raises() -> None:
    try:
        vv.next_action([])
    except ValueError:
        return
    raise AssertionError("next_action([]) must raise ValueError")


def case_hard_classes_park_at_round_one() -> None:
    for klass in HARD:
        v = verdict(verdict="PARK", defect_class=klass, defects=[defect()])
        expect(vv.next_action([v]), "PARK", klass)


def case_repairable_round_one_returns_revise() -> None:
    expect(vv.next_action([revise(["a.md:1", "b.md:9"])]), "REVISE")


def case_repairable_round_two_converged_returns_revise() -> None:
    first = revise(["a.md:1", "b.md:9", "c.md:3"])
    second = revise(["a.md:1", "b.md:9"], round=2)
    expect(vv.next_action([first, second]), "REVISE")


def case_new_location_parks() -> None:
    first = revise(["a.md:1", "b.md:9"])
    second = revise(["a.md:1", "d.md:7"], round=2)
    expect(vv.next_action([first, second]), "PARK", "count unchanged, set is not a subset")


def case_restated_defect_parks() -> None:
    first = revise(["a.md:1", "b.md:9"], why="citation missing")
    second = revise(["a.md:1", "b.md:9"], round=2, why="the citation is still missing")
    expect(vv.next_action([first, second]), "PARK")


def case_drifted_line_number_is_a_new_location() -> None:
    first = revise(["a.md:12", "b.md:9"])
    second = revise(["a.md:40"], round=2)
    expect(vv.next_action([first, second]), "PARK")


def case_round_two_with_no_defects_parks() -> None:
    first = revise(["a.md:1", "b.md:9"])
    second = verdict(verdict="PARK", defect_class="repairable", defects=[], round=2)
    expect(vv.next_action([first, second]), "PARK", "an empty set is not convergence")


def case_round_three_never_extends() -> None:
    history = [
        revise(["a.md:1", "b.md:9", "c.md:3"]),
        revise(["a.md:1", "b.md:9"], round=2),
        revise(["a.md:1"], round=3),
    ]
    expect(vv.next_action(history), "PARK")


def case_pass_short_circuits() -> None:
    expect(vv.next_action([verdict()]), "PASS")
    long_history = [revise(["a.md:1"]), revise(["a.md:1"], round=2), verdict(round=3)]
    expect(vv.next_action(long_history), "PASS")


# --- regression ---------------------------------------------------------------


def case_prior_round_fixture_still_validates() -> None:
    """A verdict captured from an earlier round must survive any schema edit.

    Staged runs keep verdicts on disk. A later phase that tightens
    verdict.schema.json and silently invalidates them fails here first.
    """
    fixture = {
        "verdict": "REVISE",
        "defect_class": "repairable",
        "defects": [
            {
                "severity": "major",
                "location": "project_plans/demo/investigations/x.md:42",
                "why": "The cited line does not contain the quoted call.",
            },
            {
                "severity": "minor",
                "location": "project_plans/demo/investigations/x.md",
                "why": "No locale list although the fix moves user-facing strings.",
            },
        ],
        "confidence": 0.75,
        "round": 2,
    }
    expect(vv.validate(fixture), [])
    expect(vv.next_action([fixture]), "REVISE")


CASES = [v for k, v in sorted(globals().items()) if k.startswith("case_")]


def main() -> int:
    failed = 0
    for case in CASES:
        try:
            case()
            print(f"PASS  {case.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL  {case.__name__}: {e}")
        except Exception:
            failed += 1
            print(f"ERROR {case.__name__}")
            traceback.print_exc()
    print(f"\n{len(CASES) - failed}/{len(CASES)} passed")
    if not failed:
        print("ALL TESTS PASSED")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
