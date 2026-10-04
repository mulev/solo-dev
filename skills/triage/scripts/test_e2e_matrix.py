#!/usr/bin/env python3
"""Hermetic proof that the e2e bead matrix is complete and correct against
the real routing rubric — no bd, no git, no subprocess, no agents.

The fixture under `../e2e/fixtures/` is data that `make_testbed.sh` loads into
a throwaway tracker. Nothing else checks it: a wrong `expect.route` would sail
through every existing test and only surface in Phase 2, as a red suite whose
message points at the harness instead of at the fixture. So every bead here is
run through `inventory.classify` itself rather than against a hand-copied
table — the fixture is answerable to the rubric, not to whoever typed it.

Run with `python3 test_e2e_matrix.py` (no pytest dependency).
Exit 0 = every case passed, 1 = findings.
"""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
FIXTURES = HERE.parent / "e2e" / "fixtures"

import dedup  # noqa: E402
import inventory  # noqa: E402
import plan_coverage  # noqa: E402


def expect(got, want) -> None:
    assert got == want, f"got {got!r}, want {want!r}"


def load_beads() -> list:
    return json.loads((FIXTURES / "beads.json").read_text(encoding="utf-8"))


def load_clean_bead() -> dict:
    return json.loads((FIXTURES / "beads_clean.json").read_text(encoding="utf-8"))[0]


def as_bd_bead(entry: dict) -> dict:
    """Fixture shape -> the dict shape `inventory.classify` expects.

    Mirrors `bd list --limit 0 --json`: `parent` is a top-level key and every
    edge is an object carrying `issue_id`, `depends_on_id` and `type`.
    """
    bead = {
        "id": entry["id"],
        "status": entry["status"],
        "issue_type": entry["issue_type"],
    }
    if entry.get("parent"):
        bead["parent"] = entry["parent"]
    bead["dependencies"] = [
        {"issue_id": entry["id"], "depends_on_id": d["target"], "type": d["type"]}
        for d in entry.get("deps", [])
    ]
    return bead


def classify_entry(entry: dict) -> tuple[str, str]:
    """Route one fixture entry through the real rubric."""
    return inventory.classify(as_bd_bead(entry), entry.get("notes") or "")


# --- the routing table and its precedence rules ------------------------------


def case_every_routing_table_row_has_a_bead() -> None:
    """One bead per row of classification.md §1, by construction."""
    ids = {b["id"] for b in load_beads()}
    for row_ids in (
        {"tb-inv1", "tb-inv2"},
        {"tb-pln1"},
        {"tb-skp1"},
        {"tb-drf1"},
        {"tb-epc", "tb-epc.1"},
        {"tb-blk"},
    ):
        assert row_ids <= ids, row_ids - ids


def case_every_precedence_rule_has_a_bead() -> None:
    """The four rules, in order: plan-over-investigation, epic-over-status,
    terminal-over-epic, and the unrecognised status that still gets a route."""
    ids = {b["id"] for b in load_beads()}
    assert {"tb-both", "tb-epc", "tb-clsepc", "tb-unk"} <= ids


def case_expected_route_matches_classify() -> None:
    """The case that makes the fixture answerable to the rubric, not its author."""
    for entry in load_beads():
        got = classify_entry(entry)
        expect(got, (entry["expect"]["route"], entry["expect"]["reason"]))


def case_every_bead_declares_a_known_expected_route() -> None:
    for entry in load_beads():
        assert entry["expect"]["route"] in inventory.ROUTES, entry


def case_ids_are_unique() -> None:
    ids = [b["id"] for b in load_beads()]
    expect(len(ids), len(set(ids)))


# --- the beads each later wave consumes --------------------------------------


WAVE_IDS = (
    "tb-dup1",
    "tb-dup2",
    "tb-cov1",
    "tb-cov2",
    "tb-cov3",
    "tb-col1",
    "tb-col2",
    "tb-ind1",
    "tb-park",
)


def case_wave_beads_are_present() -> None:
    """Every wave bead must reach a worker, so every one routes `investigate`."""
    by_id = {b["id"]: b for b in load_beads()}
    for wid in WAVE_IDS:
        entry = by_id[wid]
        route, _ = classify_entry(entry)
        expect(route, "investigate")


def case_duplicate_pair_carries_a_dependency_edge() -> None:
    """`dedup.LINK_EDGES` fires on the edge; the titles fire the mechanical
    source. The pair has to exercise both, so the edge is not optional."""
    by_id = {b["id"]: b for b in load_beads()}
    deps = by_id["tb-dup2"]["deps"]
    assert {"type": "duplicate-of", "target": "tb-dup1"} in deps, deps
    for dep in deps:
        assert dep["type"] in dedup.LINK_EDGES, dep


def case_corpus_citations_have_the_declared_strength() -> None:
    """`tb-cov1` is owned by a `Beads task:` field, so it retires unattended;
    the other two are weak citations and must reach the judge."""
    cov = plan_coverage.scan_plan_coverage(
        FIXTURES, "plans", ["tb-cov1", "tb-cov2", "tb-cov3"]
    )
    expect(plan_coverage.coverage_action(cov["tb-cov1"]), "drop")
    expect(plan_coverage.coverage_action(cov["tb-cov2"]), "review")
    expect(plan_coverage.coverage_action(cov["tb-cov3"]), "review")


def case_clean_sibling_bead_is_clean() -> None:
    """`triage-testbed-clean` exists because the main testbed carries a drift
    bead by design and can therefore never produce inventory's exit-0 case."""
    entry = load_clean_bead()
    got = classify_entry(entry)
    expect(got, (entry["expect"]["route"], entry["expect"]["reason"]))
    assert got[0] != "drift-report", got


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
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
