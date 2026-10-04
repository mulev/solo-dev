"""Tests for dedup.py's pure half — the three duplicate sources, how coverage
gates clustering, the representative order, and the propose/decide split.

No subprocesses: every case calls the module's functions directly. The
command-line contract is tested next door in test_dedup_cli.py.

Run with `python3 test_dedup.py` (no pytest dependency).
"""

from __future__ import annotations

import re
import sys
import tempfile
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import cluster_ruling  # noqa: E402
import dedup  # noqa: E402


def expect(got, want) -> None:
    assert got == want, f"got {got!r}, want {want!r}"


def bead(bid: str, **kw) -> dict:
    """A manifest bead entry enriched the way main() enriches it."""
    base = {
        "id": bid,
        "title": f"title {bid}",
        "status": "needs-plan",
        "issue_type": "bug",
        "priority": 2,
        "route": "investigate",
        "reason": "no investigation on record",
        "notes": "",
        "description": f"body {bid}",
        "created_at": "2026-01-01T00:00:00Z",
        "dependencies": [],
    }
    base.update(kw)
    return base


def dep(issue_id: str, depends_on_id: str, kind: str) -> dict:
    return {"issue_id": issue_id, "depends_on_id": depends_on_id, "type": kind}


def dup_json(*pairs) -> dict:
    """Shape captured verbatim from `bd find-duplicates --json`."""
    return {
        "count": len(pairs),
        "method": "mechanical",
        "schema_version": 1,
        "threshold": 0.35,
        "pairs": [
            {
                "issue_a_id": a,
                "issue_a_title": f"title {a}",
                "issue_b_id": b,
                "issue_b_title": f"title {b}",
                "method": "mechanical",
                "similarity": score,
            }
            for a, b, score in pairs
        ],
    }


# --- source 1: mechanical similarity ----------------------------------------


def case_mechanical_pair_above_threshold_clusters(tmp: Path) -> None:
    beads = [bead("d-1"), bead("d-2")]
    pairs = dedup._mechanical_pairs_from(dup_json(("d-1", "d-2", 0.41)), 0.35, beads)
    clusters = dedup.cluster(pairs, {})
    expect(len(clusters), 1)
    expect(clusters[0]["members"], ["d-1", "d-2"])
    expect(clusters[0]["sources"], ["mechanical"])
    expect(round(clusters[0]["score"], 2), 0.41)


def case_mechanical_pair_below_threshold_makes_no_cluster(tmp: Path) -> None:
    beads = [bead("d-1"), bead("d-2")]
    pairs = dedup._mechanical_pairs_from(dup_json(("d-1", "d-2", 0.20)), 0.35, beads)
    expect(pairs, [])
    expect(dedup.cluster(pairs, {}), [])


def case_mechanical_pair_touching_a_non_spend_bead_is_ignored(tmp: Path) -> None:
    beads = [bead("d-1")]  # d-9 routed skip, so it never reaches the spend set
    pairs = dedup._mechanical_pairs_from(dup_json(("d-1", "d-9", 0.90)), 0.35, beads)
    expect(pairs, [])


def case_transitive_pairs_form_a_single_cluster(tmp: Path) -> None:
    beads = [bead("d-1"), bead("d-2"), bead("d-3")]
    dups = dup_json(("d-1", "d-2", 0.40), ("d-2", "d-3", 0.38))
    clusters = dedup.cluster(dedup._mechanical_pairs_from(dups, 0.35, beads), {})
    expect(len(clusters), 1)
    expect(clusters[0]["members"], ["d-1", "d-2", "d-3"])


# --- source 2: how coverage gates clustering ---------------------------------
# The scan that produces this coverage is tested in test_plan_coverage.py.


def case_covered_bead_is_excluded_from_clustering(tmp: Path) -> None:
    beads = [bead("d-1"), bead("d-2")]
    pairs = dedup._mechanical_pairs_from(dup_json(("d-1", "d-2", 0.41)), 0.35, beads)
    cov = {"d-2": [{"path": "/p.md", "how": "beads-task",
                    "line": "**Beads task:** d-2"}]}
    expect(dedup.cluster(pairs, cov), [])


def case_weakly_covered_bead_still_clusters(tmp: Path) -> None:
    beads = [bead("d-1"), bead("d-2")]
    pairs = dedup._mechanical_pairs_from(dup_json(("d-1", "d-2", 0.41)), 0.35, beads)
    cov = {"d-2": [{"path": "/p.md", "how": "bare-id", "line": "saw d-2 once"}]}
    expect(len(dedup.cluster(pairs, cov)), 1)


# --- source 3: explicit tracker links ---------------------------------------


def case_duplicate_of_edge_clusters_with_no_score(tmp: Path) -> None:
    beads = [bead("d-1", dependencies=[dep("d-1", "d-2", "duplicate-of")]), bead("d-2")]
    pairs = dedup._dependency_pairs(beads)
    expect([p["source"] for p in pairs], ["dependency"])
    expect(pairs[0]["score"], None)
    clusters = dedup.cluster(pairs, {})
    expect(clusters[0]["members"], ["d-1", "d-2"])
    expect(clusters[0]["score"], None)


def case_discovered_from_edge_clusters(tmp: Path) -> None:
    beads = [bead("d-1"),
             bead("d-2", dependencies=[dep("d-2", "d-1", "discovered-from")])]
    expect(len(dedup._dependency_pairs(beads)), 1)


def case_unrelated_edge_type_does_not_cluster(tmp: Path) -> None:
    beads = [bead("d-1", dependencies=[dep("d-1", "d-2", "blocks")]), bead("d-2")]
    expect(dedup._dependency_pairs(beads), [])


def case_edge_to_a_bead_outside_the_spend_set_is_ignored(tmp: Path) -> None:
    beads = [bead("d-1", dependencies=[dep("d-1", "d-99", "duplicate-of")])]
    expect(dedup._dependency_pairs(beads), [])


def case_edge_naming_neither_end_is_skipped_not_paired(tmp: Path) -> None:
    """Regression: a malformed edge must not pair two arbitrary beads.

    An edge whose issue_id and depends_on_id are both foreign leaves two
    candidates after the bead's own ID is removed. Popping one of them is
    non-deterministic and pairs beads the tracker never linked, so the edge
    is skipped instead.
    """
    beads = [
        bead("d-1", dependencies=[dep("d-8", "d-9", "duplicate-of")]),
        bead("d-8"),
        bead("d-9"),
    ]
    # d-8 and d-9 are both present and both linkable, so a pop() would have
    # paired d-1 with whichever one it happened to reach first.
    expect(dedup._dependency_pairs(beads), [])


def case_self_edge_is_skipped(tmp: Path) -> None:
    beads = [bead("d-1", dependencies=[dep("d-1", "d-1", "duplicate-of")])]
    expect(dedup._dependency_pairs(beads), [])


def case_duplicate_of_pair_sharing_no_tokens_still_clusters(tmp: Path) -> None:
    a = bead("d-1", title="Icon renders blurry on Android",
             dependencies=[dep("d-1", "d-2", "duplicate-of")])
    b = bead("d-2", title="Sync retry loop never terminates")
    pairs = dedup._dependency_pairs([a, b])
    expect(len(dedup.cluster(pairs, {})), 1)


def case_mechanical_and_dependency_sources_merge_into_one_cluster(tmp: Path) -> None:
    a = bead("d-1", dependencies=[dep("d-1", "d-2", "duplicate-of")])
    b = bead("d-2")
    pairs = dedup._mechanical_pairs_from(dup_json(("d-1", "d-2", 0.41)), 0.35, [a, b])
    pairs += dedup._dependency_pairs([a, b])
    clusters = dedup.cluster(pairs, {})
    expect(len(clusters), 1)
    expect(clusters[0]["sources"], ["dependency", "mechanical"])


# --- representative selection ------------------------------------------------


def case_investigation_bead_wins_over_lower_priority_number(tmp: Path) -> None:
    a = bead("d-9", priority=3, notes="Investigation: /abs/x.md")
    b = bead("d-1", priority=0)
    rep, reason = dedup._pick_representative([a, b])
    expect(rep, "d-9")
    assert "Investigation" in reason, reason


def case_lower_priority_number_wins_without_an_investigation(tmp: Path) -> None:
    a = bead("d-9", priority=0)
    b = bead("d-1", priority=3)
    rep, reason = dedup._pick_representative([a, b])
    expect(rep, "d-9")
    assert "priority" in reason, reason


def case_older_created_at_wins_at_equal_priority(tmp: Path) -> None:
    a = bead("d-9", created_at="2025-01-01T00:00:00Z")
    b = bead("d-1", created_at="2026-01-01T00:00:00Z")
    rep, reason = dedup._pick_representative([a, b])
    expect(rep, "d-9")
    assert "created_at" in reason, reason


def case_lexicographic_tiebreak_is_stable_across_shuffled_input(tmp: Path) -> None:
    members = [bead("d-c"), bead("d-a"), bead("d-b")]
    rep, reason = dedup._pick_representative(members)
    expect(rep, "d-a")
    assert "lexicographically" in reason, reason
    expect(dedup._pick_representative(list(reversed(members)))[0], "d-a")


def case_missing_priority_never_beats_a_real_one(tmp: Path) -> None:
    a = bead("d-1", priority=None)
    b = bead("d-2", priority=3)
    expect(dedup._pick_representative([a, b])[0], "d-2")


# --- propose vs decide -------------------------------------------------------


def case_every_cluster_is_written_as_a_candidate(tmp: Path) -> None:
    beads = [bead("d-1"), bead("d-2")]
    pairs = dedup._mechanical_pairs_from(dup_json(("d-1", "d-2", 0.41)), 0.35, beads)
    expect([c["verdict"] for c in dedup.cluster(pairs, {})], ["candidate"])


def case_no_code_path_writes_a_decided_verdict(tmp: Path) -> None:
    src = (HERE / "dedup.py").read_text(encoding="utf-8")
    written = re.findall(r'"verdict":\s*([^,\n}]+)', src)
    expect(written, ["VERDICT"])
    expect(dedup.VERDICT, "candidate")


# --- defect skills-dm0: the drop is reported against the citation that made it


def _mixed_coverage() -> dict:
    """Filesystem order, so the weak citation lands first and the strong last."""
    return {
        "d-5": [
            {"path": "/plans/demo/todo/a/more.md", "how": "beads-table",
             "line": "| Not this epic | `d-5` | later |"},
            {"path": "/plans/demo/done/b/plan.md", "how": "beads-task",
             "line": "**Beads task:** d-5"},
        ]
    }


def case_covered_by_names_the_strong_citation_not_the_first(tmp: Path) -> None:
    record = dedup._covered_records(_mixed_coverage())[0]
    expect(record["action"], "drop")
    expect(record["covered_by"], "/plans/demo/done/b/plan.md")


def case_judge_brief_quotes_the_citation_that_caused_the_drop(tmp: Path) -> None:
    brief = tmp / "judge_brief.md"
    dedup._write_judge_brief([], dedup._covered_records(_mixed_coverage()), {}, brief)
    text = brief.read_text(encoding="utf-8")
    assert "cited as `beads-task`" in text, text
    assert "beads-table" not in text, text


def case_covered_by_falls_back_to_the_first_when_none_are_strong(tmp: Path) -> None:
    coverage = {"d-6": [{"path": "/plans/demo/todo/a.md", "how": "bare-id",
                         "line": "saw d-6 once"},
                        {"path": "/plans/demo/todo/b.md", "how": "beads-table",
                         "line": "| listed | `d-6` | later |"}]}
    record = dedup._covered_records(coverage)[0]
    expect(record["action"], "review")
    expect(record["covered_by"], "/plans/demo/todo/a.md")


def case_the_brief_asks_for_a_partition_not_a_single_verdict(tmp: Path) -> None:
    """A cluster can be part duplicate and part not, so the brief must let the
    judge say so — one verdict per cluster forced the safe keep-everything."""
    brief = tmp / "judge_brief.md"
    clusters = [{"cluster_id": "c1", "members": ["d-1", "d-2"], "sources": ["mechanical"],
                 "score": 0.5, "representative": "d-1", "representative_reason": "oldest",
                 "verdict": "candidate"}]
    dedup._write_judge_brief(clusters, [], {}, brief)
    text = brief.read_text(encoding="utf-8")
    assert "**Ruling:**" in text, text
    assert "one group per" in text, text
    for verdict in cluster_ruling.VERDICTS:
        assert verdict in text, verdict


def case_the_brief_asks_for_a_ruling_on_every_covered_bead(tmp: Path) -> None:
    """A covered list with no ruling line is what nobody answered on the first
    live run: nine beads flagged, none routed."""
    brief = tmp / "judge_brief.md"
    dedup._write_judge_brief([], dedup._covered_records(_mixed_coverage()), {}, brief)
    text = brief.read_text(encoding="utf-8")
    assert "**Ruling:**" in text, text
    assert "covered" in text and "not-covered" in text, text


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
