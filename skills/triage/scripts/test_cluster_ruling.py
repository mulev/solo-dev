#!/usr/bin/env python3
"""Tests for cluster_ruling.py — the judge's partition of one dedup cluster.

Run with `python3 test_cluster_ruling.py` (no pytest dependency).
"""

from __future__ import annotations

import sys
import tempfile
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import cluster_ruling  # noqa: E402

MEMBERS = ["d-1", "d-2", "d-3", "d-4"]


def expect(got, want) -> None:
    assert got == want, f"got {got!r}, want {want!r}"


def group(members, verdict, representative=None) -> dict:
    out = {"members": members, "verdict": verdict}
    if representative:
        out["representative"] = representative
    return out


# --- a whole-cluster ruling stays as simple as it was ------------------------


def case_one_group_covering_every_member_is_valid(tmp: Path) -> None:
    expect(cluster_ruling.validate(MEMBERS,
                                   [group(MEMBERS, "related-not-duplicate")]), [])


def case_a_whole_cluster_duplicate_needs_a_representative(tmp: Path) -> None:
    expect(cluster_ruling.validate(MEMBERS, [group(MEMBERS, "duplicate", "d-2")]), [])


# --- the partition this file exists for --------------------------------------


def case_a_cluster_can_split_into_duplicate_and_distinct(tmp: Path) -> None:
    """The reason for the whole change: two of four are the same bug.

    A single verdict per cluster forced the safe answer — keep everything —
    which silently converts a partial duplicate into no duplicate at all.
    """
    groups = [group(["d-1", "d-3"], "duplicate", "d-1"),
              group(["d-2", "d-4"], "distinct")]
    expect(cluster_ruling.validate(MEMBERS, groups), [])
    expect(cluster_ruling.dropped(groups), ["d-3"])


def case_nothing_is_dropped_when_no_group_is_a_duplicate(tmp: Path) -> None:
    groups = [group(["d-1", "d-2"], "distinct"),
              group(["d-3", "d-4"], "related-not-duplicate")]
    expect(cluster_ruling.dropped(groups), [])


def case_the_representative_is_never_dropped(tmp: Path) -> None:
    expect(cluster_ruling.dropped([group(MEMBERS, "duplicate", "d-2")]),
           ["d-1", "d-3", "d-4"])


# --- a malformed partition is a finding, never a judgment call ---------------


def case_a_member_left_out_is_a_finding(tmp: Path) -> None:
    got = cluster_ruling.validate(MEMBERS, [group(["d-1", "d-2"], "distinct")])
    assert any("d-3" in f and "d-4" in f for f in got), got


def case_a_member_in_two_groups_is_a_finding(tmp: Path) -> None:
    groups = [group(["d-1", "d-2"], "distinct"),
              group(["d-2", "d-3", "d-4"], "distinct")]
    assert any("d-2" in f for f in cluster_ruling.validate(MEMBERS, groups)), groups


def case_an_unknown_member_is_a_finding(tmp: Path) -> None:
    groups = [group(MEMBERS + ["d-9"], "distinct")]
    assert any("d-9" in f for f in cluster_ruling.validate(MEMBERS, groups))


def case_an_unknown_verdict_is_a_finding(tmp: Path) -> None:
    got = cluster_ruling.validate(MEMBERS, [group(MEMBERS, "probably")])
    assert any("probably" in f for f in got), got


def case_a_duplicate_group_without_a_representative_is_a_finding(tmp: Path) -> None:
    got = cluster_ruling.validate(MEMBERS, [group(MEMBERS, "duplicate")])
    assert any("representative" in f for f in got), got


def case_a_representative_outside_its_own_group_is_a_finding(tmp: Path) -> None:
    groups = [group(["d-1", "d-2"], "duplicate", "d-3"),
              group(["d-3", "d-4"], "distinct")]
    got = cluster_ruling.validate(MEMBERS, groups)
    assert any("d-3" in f for f in got), got


def case_a_lone_bead_cannot_be_a_duplicate(tmp: Path) -> None:
    """Duplication is a relation. One bead alone has nothing to duplicate."""
    groups = [group(["d-1"], "duplicate", "d-1"),
              group(["d-2", "d-3", "d-4"], "distinct")]
    got = cluster_ruling.validate(MEMBERS, groups)
    assert any("one member" in f for f in got), got


def case_an_empty_group_is_a_finding(tmp: Path) -> None:
    got = cluster_ruling.validate(MEMBERS, [group([], "distinct"),
                                            group(MEMBERS, "distinct")])
    assert any("empty" in f for f in got), got


def case_no_groups_at_all_is_a_finding(tmp: Path) -> None:
    assert cluster_ruling.validate(MEMBERS, []), "an unruled cluster must not pass"


def case_a_nameless_member_is_a_finding(tmp: Path) -> None:
    """Same defect as `plan_coverage.validate_coverage`: the duplicate check
    sorted and joined whatever the judge put in `members`, so a malformed
    ruling raised out of the validator written to reject it."""
    got = cluster_ruling.validate(MEMBERS, [group([None, None], "distinct"),
                                            group(MEMBERS, "distinct")])
    assert any("not a member" in f for f in got), got


# --- the group's name, so the ledger can point at it -------------------------


def case_identify_names_each_group_after_its_cluster(tmp: Path) -> None:
    """`references/ledger.md` keys a Wave 1 row by the group ID. Until this
    existed there was none: `collide.py` names its groups and the judge's
    ruling did not, so three live runs each invented a format — `c1-g1`,
    `c1-g1`, `c1g1` — for rows nothing else in the run could be matched to.
    """
    groups = cluster_ruling.identify("c1", [group(["d-1"], "distinct"),
                                            group(["d-2", "d-3"], "duplicate", "d-2")])
    expect([g["group_id"] for g in groups], ["c1-g1", "c1-g2"])


def case_identify_leaves_the_ruling_itself_alone(tmp: Path) -> None:
    """It names groups; it does not rule on them. A judge's verdict, members
    and representative survive untouched."""
    ruled = group(["d-2", "d-3"], "duplicate", "d-2")
    out = cluster_ruling.identify("c1", [ruled])[0]
    expect(out["verdict"], "duplicate")
    expect(out["members"], ["d-2", "d-3"])
    expect(out["representative"], "d-2")


def case_identify_is_stable_when_run_again(tmp: Path) -> None:
    """A resumed run re-reads its manifest and re-identifies. Renumbering would
    orphan every ledger row already written against the old names."""
    groups = [group(["d-1"], "distinct"), group(["d-2", "d-3"], "distinct")]
    once = [g["group_id"] for g in cluster_ruling.identify("c1", groups)]
    twice = [g["group_id"] for g in cluster_ruling.identify("c1", groups)]
    expect(once, twice)


def case_identify_never_renames_a_group_that_already_has_an_id(tmp: Path) -> None:
    """The ledger is written from these names, so one that exists is load
    bearing — an ID assigned by an earlier pass outranks this one's counter."""
    kept = group(["d-1"], "distinct")
    kept["group_id"] = "c1-g7"
    out = cluster_ruling.identify("c1", [kept, group(["d-2", "d-3"], "distinct")])
    expect([g["group_id"] for g in out], ["c1-g7", "c1-g2"])


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
