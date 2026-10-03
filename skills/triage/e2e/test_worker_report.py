#!/usr/bin/env python3
"""Unit cases for reading a worker's prose report.

This is where both of the phase's live defects lived, and neither was caught by
anything until an agent had already been spent. That is the argument for these
cases: parsing a model's prose is the part most likely to be wrong and the
cheapest part to check, and every function under test is pure over a string.

The two are kept permanently as named regressions —
`case_park_report_ignores_the_word_in_the_opening_line` and
`case_path_field_undresses_backticks`.

Nothing here dispatches an agent or builds a testbed. Fixture reports are
written in the shape workers actually return, including the formatting they
actually use — but with a token-shaped stand-in rather than the live contract
version, because `triage/scripts/test_contract.py` fails any file that
re-literalises it and is right to: a pinned copy goes stale the moment the
contract is versioned up. Nothing here reads the token's value.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import worker_report as wr  # noqa: E402

# The report that produced the `". Report"` defect: the word PARK opens the
# text, and the question a human must answer is three fields further down.
REAL_PARK = """\
PARK. Report:

```
contract: SW-1999-08-v1
bead: tb-inv1
artifact: /runs/2026-08-29_abc/investigations/x.md
root cause: not established — the cited site has no I/O and no callers.
gate: PARK — "evidence cannot establish a root cause"
open questions: which is true — the consumer is in another repository, or the
citation is wrong?
blockers: PARK above. Nothing else.
```
"""

CLEAN_REPORT = """\
contract: `**SW-1999-08-v1**`
bead: tb-inv1
artifact: `/runs/2026-08-29_abc/investigations/x.md`
gate: stopped at Gate 1
blockers: none
"""

JUDGE_REPORT = """\
contract: SW-1999-08-v1
clusters:
- c1 — tb-dup1, tb-dup2 — duplicate — representative `tb-dup1`
- c1 — tb-cov2 — distinct
coverage:
- `tb-cov1` — covered — plan: todo/tb-cov1-fix/plan.md
- `tb-cov2` — not covered
- `tb-cov3` — not-covered
"""


# --- fields -------------------------------------------------------------------


def case_fields_reads_plain_key_value_lines() -> None:
    found = wr.fields(CLEAN_REPORT)
    assert found["bead"] == "tb-inv1", found
    assert found["gate"] == "stopped at Gate 1", found


def case_fields_survives_markdown_dressing() -> None:
    """`**contract:** x` is obedience, not disobedience."""
    assert wr.fields("**contract:** SW-x\n- *bead*: tb-1\n") == {
        "contract": "SW-x", "bead": "tb-1"}


def case_fields_keeps_the_first_occurrence() -> None:
    """A report that restates a field in a later gate payload must not
    overwrite the answer it gave at the top."""
    assert wr.fields("bead: tb-1\nbead: tb-999\n")["bead"] == "tb-1"


def case_fields_ignores_prose_without_a_key() -> None:
    assert wr.fields("Just a sentence, no colon at all\n") == {}


# --- path_field ---------------------------------------------------------------


def case_path_field_undresses_backticks() -> None:
    """Regression, found live: a worker wrapped its assigned path in backticks
    and the assigned-path comparison failed on the punctuation rather than on
    anything the worker did wrong."""
    found = wr.fields(CLEAN_REPORT)
    assert wr.path_field(found, "artifact") == Path(
        "/runs/2026-08-29_abc/investigations/x.md")


def case_path_field_of_a_missing_key_is_not_a_crash() -> None:
    assert wr.path_field({}, "artifact") == Path(".")


# --- park_report --------------------------------------------------------------


def case_park_report_ignores_the_word_in_the_opening_line() -> None:
    """Regression, found live. A first-occurrence reader took `". Report"` off
    the `PARK. Report:` line and the oracle passed it, so a park nobody could
    act on read as a well-formed one. The question comes from the designated
    fields or it does not come at all."""
    parked = wr.park_report(REAL_PARK)
    assert parked["outcome"] == "PARK", parked
    assert "which is true" in parked["question"], parked
    assert ". Report" not in parked["question"], parked


def case_park_report_strips_the_bare_word_from_each_field() -> None:
    """`blockers: PARK above.` contributes its sentence, not the token."""
    parked = wr.park_report("gate: PARK — is the anchor path reachable at all?\n")
    assert parked["question"].startswith("is the anchor"), parked


def case_park_report_says_complete_when_the_word_never_appears() -> None:
    parked = wr.park_report(CLEAN_REPORT)
    assert parked == {"outcome": "COMPLETE", "question": ""}, parked


def case_park_report_of_a_park_with_no_question_stays_empty() -> None:
    """The reader must not manufacture one — that is the oracle's call to make."""
    parked = wr.park_report("gate: PARK\nblockers: PARK\n")
    assert parked["outcome"] == "PARK" and parked["question"] == "", parked


# --- groups -------------------------------------------------------------------


def case_groups_partitions_a_cluster_across_two_lines() -> None:
    groups = wr.groups(JUDGE_REPORT, ["tb-dup1", "tb-dup2", "tb-cov2"])
    assert [g["members"] for g in groups] == [["tb-dup1", "tb-dup2"], ["tb-cov2"]]
    assert [g["verdict"] for g in groups] == ["duplicate", "distinct"]


def case_groups_reads_the_representative_off_the_line() -> None:
    groups = wr.groups(JUDGE_REPORT, ["tb-dup1", "tb-dup2"])
    assert groups[0]["representative"] == "tb-dup1", groups


def case_groups_never_invents_a_representative() -> None:
    """`cluster_ruling` requires one for a `duplicate`; supplying it here would
    turn the judge's incomplete answer into a green run."""
    groups = wr.groups("- tb-a, tb-b — duplicate\n", ["tb-a", "tb-b"])
    assert "representative" not in groups[0], groups


def case_groups_puts_a_member_in_the_first_group_that_claims_it() -> None:
    """Regression, found by a live judge. It ruled the pair and then restated
    both ids and the word `duplicate` in its reasoning, so a reader taking
    every qualifying line built two groups over the same pair and the partition
    oracle rejected what was in fact a clean partition."""
    report = (JUDGE_REPORT
              + "reasoning: tb-dup1 and tb-dup2 are duplicate work on one path.\n")
    groups = wr.groups(report, ["tb-dup1", "tb-dup2"])
    assert len(groups) == 1, groups
    assert groups[0]["members"] == ["tb-dup1", "tb-dup2"], groups
    assert groups[0]["representative"] == "tb-dup1", groups


def case_groups_still_splits_a_cluster_the_judge_really_split() -> None:
    """First-claim-wins must not collapse a genuine split — the case the
    partition exists for, where a cluster is part duplicate and part not."""
    groups = wr.groups(JUDGE_REPORT, ["tb-dup1", "tb-dup2", "tb-cov2"])
    assert [g["members"] for g in groups] == [["tb-dup1", "tb-dup2"], ["tb-cov2"]]


def case_groups_skips_a_line_naming_no_member() -> None:
    assert wr.groups("- tb-zzz — duplicate — representative tb-zzz\n",
                     ["tb-a"]) == []


def case_groups_skips_a_line_naming_no_verdict() -> None:
    assert wr.groups("- tb-a is interesting\n", ["tb-a"]) == []


def case_groups_reads_related_not_duplicate_as_itself() -> None:
    """Live failure, `2026-09-06` suite C: `\\bduplicate\\b` matches inside
    `related-not-duplicate` — a hyphen is a word boundary — and `duplicate`
    comes first in `cluster_ruling.VERDICTS`, so the reader turned the judge's
    one ruled-out member into a one-member `duplicate` group and
    `cluster_ruling.validate` rejected a partition that was in fact clean.

    The same substring-order bug `coverage_rulings` below already fixed for
    `not-covered`/`covered`, one function over and unfixed.
    """
    groups = wr.groups("- tb-cov2 — related-not-duplicate — same file, other "
                       "defect\n", ["tb-cov2"])
    assert [g["verdict"] for g in groups] == ["related-not-duplicate"], groups


def case_groups_never_reads_a_negated_duplicate_as_a_ruling() -> None:
    """The other spelling of the same failure: a judge that rules `distinct`
    and then says why — "not a duplicate of the pair" — is ruling `distinct`."""
    groups = wr.groups("- tb-cov2 — distinct, not a duplicate of the pair "
                       "above\n", ["tb-cov2"])
    assert [g["verdict"] for g in groups] == ["distinct"], groups


# --- coverage_rulings ---------------------------------------------------------


def case_coverage_rulings_reads_one_line_per_flagged_bead() -> None:
    rulings = wr.coverage_rulings(JUDGE_REPORT, ["tb-cov1", "tb-cov2", "tb-cov3"])
    assert [r["id"] for r in rulings] == ["tb-cov1", "tb-cov2", "tb-cov3"], rulings


def case_coverage_rulings_does_not_read_not_covered_as_covered() -> None:
    """`covered` is a substring of `not covered`, and getting the order wrong
    retires a bead the judge explicitly refused to retire."""
    rulings = wr.coverage_rulings(JUDGE_REPORT, ["tb-cov1", "tb-cov2", "tb-cov3"])
    assert [r["verdict"] for r in rulings] == [
        "covered", "not-covered", "not-covered"], rulings


def case_coverage_rulings_names_a_plan_for_a_covered_bead() -> None:
    """`plan_coverage.validate_coverage` rejects a `covered` naming no plan."""
    rulings = wr.coverage_rulings(JUDGE_REPORT, ["tb-cov1"])
    assert rulings[0]["plan"], rulings


def case_coverage_rulings_ignores_a_bead_that_was_never_flagged() -> None:
    assert wr.coverage_rulings(JUDGE_REPORT, ["tb-nope"]) == []


def case_coverage_rulings_counts_a_repeated_bead_once() -> None:
    """Regression, found by a live judge. It ruled `tb-cov3 — not-covered` and
    then named `tb-cov3` again in the reasoning below, so a reader taking every
    mention emitted two rulings and the oracle rejected an answer that was in
    fact complete. First mention wins, the same rule `fields` uses."""
    report = (JUDGE_REPORT
              + "reasoning: tb-cov3 is not covered because the plan de-scopes it.\n")
    rulings = wr.coverage_rulings(report, ["tb-cov1", "tb-cov2", "tb-cov3"])
    assert [r["id"] for r in rulings] == ["tb-cov1", "tb-cov2", "tb-cov3"], rulings


def case_coverage_rulings_keeps_the_first_verdict_not_the_last() -> None:
    """A later prose mention must not overturn the ruling line above it."""
    report = "- tb-cov1 — not-covered\nreasoning: tb-cov1 is covered elsewhere.\n"
    assert wr.coverage_rulings(report, ["tb-cov1"]) == [
        {"id": "tb-cov1", "verdict": "not-covered"}]


def case_coverage_rulings_omits_a_bead_the_judge_never_ruled() -> None:
    """The failure that matters. `coverage_line_per_flagged_bead` sees the gap
    because the bead is simply absent, not because it was mentioned twice."""
    rulings = wr.coverage_rulings("- tb-cov1 — covered — plan: x.md\n",
                                  ["tb-cov1", "tb-cov2"])
    assert [r["id"] for r in rulings] == ["tb-cov1"], rulings


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
        except Exception as err:
            failed += 1
            print(f"ERROR {case.__name__}: {type(err).__name__}: {err}")
    print(f"\n{len(CASES) - failed}/{len(CASES)} cases passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
