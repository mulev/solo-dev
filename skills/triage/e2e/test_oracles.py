#!/usr/bin/env python3
"""Unit cases for the live suites' oracles, both sides of every one.

An oracle that has only ever been shown to accept is indistinguishable from
`return True`, and it is the only thing standing between a live run and a
green report about a worker that misbehaved. So every function here gets an
accepting fixture and at least one **mutation** of that same fixture — one
true condition flipped, nothing else — that it must reject.

`MUTATIONS` records which condition was flipped per function. It is asserted
rather than written as a comment: a mutation record nobody checks rots into a
claim, and `case_every_oracle_has_a_recorded_mutation` is what keeps it true.

Nothing here dispatches an agent, reads a testbed, or touches disk beyond
`pathlib` string arithmetic — the oracles are pure and their tests stay pure,
which is why they can run in the TDD inner loop rather than behind `--live`.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import oracles  # noqa: E402

# A token-shaped string, deliberately not the live one. `test_contract.py`
# fails any file in the repository that re-literalises the contract's real
# version, and it is right to: a pinned copy goes stale the moment the
# contract is versioned up. `report_echoes_contract_token` is generic over
# whatever token it is handed, so a shape-alike proves the same thing and
# keeps these cases off the disk.
TOKEN = "SW-1999-08-v1"
# The stale-token mutation: one digit, the month before.
STALE_TOKEN = "SW-1999-07-v1"

# One line per oracle: the true condition a rejecting case flips. Asserted by
# `case_every_oracle_has_a_recorded_mutation`, never merely documented.
MUTATIONS = {
    "partition_covers_every_member":
        "a member present in the groups is deleted from them (dropped bead), "
        "and separately a member is listed in two groups (ruled twice)",
    "coverage_line_per_flagged_bead":
        "one flagged bead's ruling line is removed, and separately one bead "
        "is given two lines",
    "park_carries_a_question":
        "the question is blanked to whitespace; separately the outcome is "
        "changed away from PARK while the question stays; separately it is cut "
        "to a fragment shorter than MIN_QUESTION_WORDS — the last of those was "
        "found by a live park, not designed, and it is why the floor is words",
    "report_echoes_contract_token":
        "one digit of the version token is changed to a previous month",
    "artifact_is_inside":
        "the path is moved to a sibling of the run directory, and separately "
        "to its parent",
}


# --- fixtures: one clean shape per oracle, mutated in place by each case ------


def _clean_partition() -> tuple:
    """Two clusters' worth of members in one partition, every member once."""
    members = ["tb-dup1", "tb-dup2", "tb-cov1"]
    groups = [
        {"members": ["tb-dup1", "tb-dup2"], "verdict": "duplicate",
         "representative": "tb-dup1"},
        {"members": ["tb-cov1"], "verdict": "distinct"},
    ]
    return members, groups


def _clean_coverage() -> tuple:
    flagged = ["tb-cov2", "tb-cov3"]
    rulings = [
        {"id": "tb-cov2", "verdict": "covered", "plan": "todo/a/plan.md"},
        {"id": "tb-cov3", "verdict": "not-covered"},
    ]
    return flagged, rulings


def _clean_park() -> dict:
    return {"outcome": "PARK",
            "question": "Does the reader own the progress store, or the shelf?"}


# --- partition_covers_every_member -------------------------------------------


def case_partition_covers_every_member_accepts_a_clean_partition() -> None:
    members, groups = _clean_partition()
    assert oracles.partition_covers_every_member(members, groups)


def case_partition_covers_every_member_rejects_a_dropped_bead() -> None:
    """Mutation: `tb-cov1`'s group is removed, so one member is never ruled."""
    members, groups = _clean_partition()
    del groups[1]
    assert not oracles.partition_covers_every_member(members, groups)


def case_partition_covers_every_member_rejects_a_bead_ruled_twice() -> None:
    """Mutation: `tb-dup2` is added to the second group as well as the first."""
    members, groups = _clean_partition()
    groups[1]["members"].append("tb-dup2")
    assert not oracles.partition_covers_every_member(members, groups)


def case_partition_covers_every_member_rejects_a_stranger() -> None:
    """A bead that was never a member cannot be smuggled in by a ruling."""
    members, groups = _clean_partition()
    groups[1]["members"] = ["tb-nope"]
    assert not oracles.partition_covers_every_member(members, groups)


def case_partition_covers_every_member_rejects_no_groups_at_all() -> None:
    members, _ = _clean_partition()
    assert not oracles.partition_covers_every_member(members, [])


def case_partition_covers_every_member_ignores_which_verdict_was_given() -> None:
    """Shape, never judgment: rewriting every verdict must not move the answer.

    This is the guard against the mood-ring failure the phase exists to avoid —
    the day a model rules this pair `related-not-duplicate` instead of
    `duplicate`, the partition is still a partition.
    """
    members, groups = _clean_partition()
    groups[0]["verdict"] = "related-not-duplicate"
    groups[0].pop("representative")
    groups[1]["verdict"] = "related-not-duplicate"
    assert oracles.partition_covers_every_member(members, groups)


# --- coverage_line_per_flagged_bead ------------------------------------------


def case_coverage_line_per_flagged_bead_accepts_one_line_each() -> None:
    flagged, rulings = _clean_coverage()
    assert oracles.coverage_line_per_flagged_bead(flagged, rulings)


def case_coverage_line_per_flagged_bead_rejects_a_missing_line() -> None:
    """Mutation: `tb-cov3`'s ruling is deleted.

    This is the failure the wave's whole coverage step exists to prevent — an
    unruled flagged bead gets a fresh investigation while a plan already covers
    that ground, uncompared.
    """
    flagged, rulings = _clean_coverage()
    del rulings[1]
    assert not oracles.coverage_line_per_flagged_bead(flagged, rulings)


def case_coverage_line_per_flagged_bead_rejects_a_doubled_line() -> None:
    """Mutation: `tb-cov2` is ruled twice, once each way."""
    flagged, rulings = _clean_coverage()
    rulings.append({"id": "tb-cov2", "verdict": "not-covered"})
    assert not oracles.coverage_line_per_flagged_bead(flagged, rulings)


def case_coverage_line_per_flagged_bead_ignores_which_way_it_was_ruled() -> None:
    flagged, rulings = _clean_coverage()
    for ruling in rulings:
        ruling["verdict"] = "not-covered"
        ruling.pop("plan", None)
    assert oracles.coverage_line_per_flagged_bead(flagged, rulings)


# --- park_carries_a_question -------------------------------------------------


def case_park_carries_a_question_accepts_a_real_question() -> None:
    assert oracles.park_carries_a_question(_clean_park())


def case_park_carries_a_question_rejects_a_blank_question() -> None:
    """Mutation: the question is blanked to whitespace.

    A park with no question is a dropped bead — nobody reconstructs the
    question later, and the run reports an outcome nobody can act on.
    """
    report = _clean_park()
    report["question"] = "   \n  "
    assert not oracles.park_carries_a_question(report)


def case_park_carries_a_question_rejects_a_missing_question_field() -> None:
    report = _clean_park()
    del report["question"]
    assert not oracles.park_carries_a_question(report)


def case_park_carries_a_question_rejects_a_non_park_outcome() -> None:
    """Mutation: the outcome moves off PARK while the question stays."""
    report = _clean_park()
    report["outcome"] = "PASS"
    assert not oracles.park_carries_a_question(report)


def case_park_carries_a_question_rejects_a_fragment() -> None:
    """Found live, not designed: a reader pulled `". Report"` out of a real
    park report's opening line and the non-emptiness test passed it. A green
    oracle over an answer nobody could act on is the failure this whole phase
    is built to avoid, so the floor is words rather than characters."""
    report = _clean_park()
    report["question"] = ". Report"
    assert not oracles.park_carries_a_question(report)


def case_park_carries_a_question_accepts_the_shortest_real_question() -> None:
    """The floor is a floor, not a style guide — exactly `MIN_QUESTION_WORDS`
    words passes, and what the question asks is never inspected."""
    report = _clean_park()
    report["question"] = " ".join(["word"] * oracles.MIN_QUESTION_WORDS)
    assert oracles.park_carries_a_question(report)


# --- report_echoes_contract_token --------------------------------------------


def case_report_echoes_contract_token_accepts_an_exact_match() -> None:
    assert oracles.report_echoes_contract_token({"contract": TOKEN}, TOKEN)


def case_report_echoes_contract_token_accepts_markdown_dressing() -> None:
    """`**SW-...**` is the shape the contract file itself uses.

    A worker that copies the line as it reads it has proved exactly what the
    check is for. Rejecting it would fail the run on formatting, which is the
    mood-ring failure in miniature.
    """
    assert oracles.report_echoes_contract_token(
        {"contract": f" `**{TOKEN}**` "}, TOKEN)


def case_report_echoes_contract_token_rejects_a_stale_token() -> None:
    """Mutation: one digit of the month, so the worker read an older contract."""
    assert not oracles.report_echoes_contract_token(
        {"contract": STALE_TOKEN}, TOKEN)


def case_report_echoes_contract_token_rejects_a_missing_field() -> None:
    """No `contract:` line means the worker never opened the contract, so every
    other claim in its report is unverified against the rules it was given."""
    assert not oracles.report_echoes_contract_token({"bead": "tb-inv1"}, TOKEN)


# --- artifact_is_inside ------------------------------------------------------


def case_artifact_is_inside_accepts_a_path_under_the_run_dir() -> None:
    run = Path("/tmp/runs/2026-08-29_abc")
    assert oracles.artifact_is_inside(run, run / "investigations" / "tb-inv1.md")


def case_artifact_is_inside_rejects_a_sibling_directory() -> None:
    """Mutation: the artifact moves one directory sideways.

    `2026-08-29_abcdef` starts with the run directory's whole name, so a
    string-prefix check would accept it. Path arithmetic is what makes this a
    rejection.
    """
    run = Path("/tmp/runs/2026-08-29_abc")
    assert not oracles.artifact_is_inside(
        run, Path("/tmp/runs/2026-08-29_abcdef/investigations/tb-inv1.md"))


def case_artifact_is_inside_rejects_a_parent_directory() -> None:
    """Mutation: the artifact climbs out to the staging root."""
    run = Path("/tmp/runs/2026-08-29_abc")
    assert not oracles.artifact_is_inside(run, Path("/tmp/runs/tb-inv1.md"))


def case_artifact_is_inside_rejects_a_traversal_back_out() -> None:
    run = Path("/tmp/runs/2026-08-29_abc")
    assert not oracles.artifact_is_inside(run, run / ".." / ".." / "todo" / "x.md")


def case_artifact_is_inside_rejects_the_real_backlog() -> None:
    """The one path this oracle exists for: a worker writing into the live tree."""
    assert not oracles.artifact_is_inside(
        Path("/tmp/runs/2026-08-29_abc"),
        Path("/Users/demo/projects/project_plans/skills/todo/x.md"))


# --- the mutation record itself ----------------------------------------------


def case_every_oracle_has_a_recorded_mutation() -> None:
    """Every public oracle is mutation-checked, and the record says how.

    Without this the record is prose: a sixth oracle could be added with no
    rejecting case at all and nothing here would notice.
    """
    assert set(MUTATIONS) == set(oracles.ORACLES), (
        sorted(set(MUTATIONS) ^ set(oracles.ORACLES)))
    names = [name for name in globals() if name.startswith("case_")]
    for oracle in oracles.ORACLES:
        assert any(name.startswith(f"case_{oracle}_rejects") for name in names), (
            f"{oracle} has no rejecting case")


CASES = [v for k, v in sorted(globals().items()) if k.startswith("case_")]


def main() -> int:
    failed = 0
    for case in CASES:
        try:
            case()
            print(f"PASS  {case.__name__}")
        except AssertionError as err:
            failed += 1
            print(f"FAIL  {case.__name__}: {err}")
        except Exception as err:  # a stub, or a case reaching unwritten code
            failed += 1
            print(f"ERROR {case.__name__}: {type(err).__name__}: {err}")
    print(f"\n{len(CASES) - failed}/{len(CASES)} cases passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
