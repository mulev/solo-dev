"""Tests for collide.py — the collision graph, the grouping decision, its
determinism, and the exit codes the orchestrator reads.

The load-bearing case is the negative one: two beads touching the same
module, with no shared file and no shared symbol, must NOT group. Grouping
on module membership would collapse a backlog into one unmanageable epic,
which is a worse failure than the one this phase prevents.

Run with `python3 test_collide.py` (no pytest dependency).
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import collide  # noqa: E402

HARNESS = "demo/test/helpers/opds_test_server.dart"
CATALOG = "demo/lib/features/opds/catalog.dart"
READER = "demo/lib/features/reader/reader.dart"


def expect(got, want) -> None:
    assert got == want, f"got {got!r}, want {want!r}"


def module_of(path: str) -> str:
    return str(Path(path).parent)


def fp(bead: str, files=(), symbols=(), modules=None, signature=()) -> dict:
    """A footprint in the block grammar. `signature` names the symbols whose
    contract moves — the ones that force their bead first in a SEQUENCE."""
    return {
        "bead": bead,
        "files": [
            {"path": p, "module": module_of(p), "change": "modify"} for p in files
        ],
        "symbols": [
            {
                "name": s,
                "kind": "method",
                "change": "signature" if s in signature else "behavior",
            }
            for s in symbols
        ],
        "modules": sorted(modules if modules is not None else {module_of(p) for p in files}),
    }


def decisions(footprints, causes=None) -> list:
    graph = collide.build_graph(footprints)
    return [
        collide.decide(component, causes or {})
        for component in collide.group(graph, footprints)
    ]


def only(footprints, causes=None) -> dict:
    records = decisions(footprints, causes)
    expect(len(records), 1)
    return records[0]


# --- the collision graph -----------------------------------------------------


def case_two_beads_sharing_a_file_are_joined_by_an_edge(tmp: Path) -> None:
    graph = collide.build_graph([fp("d-1", [HARNESS]), fp("d-2", [HARNESS, CATALOG])])
    expect(graph["d-1"]["d-2"]["files"], [HARNESS])
    expect(graph["d-1"]["d-2"]["symbols"], [])
    expect(sorted(graph["d-2"]), ["d-1"])


def case_two_beads_sharing_a_file_group_together(tmp: Path) -> None:
    record = only([fp("d-1", [HARNESS]), fp("d-2", [HARNESS])])
    expect(record["members"], ["d-1", "d-2"])


def case_two_beads_sharing_only_a_symbol_group_together(tmp: Path) -> None:
    """No shared path at all — the case a files-only model misses entirely."""
    footprints = [
        fp("d-1", [HARNESS], ["OpdsTestServer.start"], signature=["OpdsTestServer.start"]),
        fp("d-2", [READER], ["OpdsTestServer.start"]),
    ]
    graph = collide.build_graph(footprints)
    expect(graph["d-1"]["d-2"]["files"], [])
    expect(graph["d-1"]["d-2"]["symbols"], ["OpdsTestServer.start"])
    expect(only(footprints)["members"], ["d-1", "d-2"])


def case_two_beads_sharing_only_a_module_do_not_group(tmp: Path) -> None:
    """Same neighbourhood is not the same thing. This must never group."""
    module = "demo/lib/features/opds"
    footprints = [
        fp("d-1", [f"{module}/a.dart"], ["A.one"]),
        fp("d-2", [f"{module}/b.dart"], ["B.two"]),
    ]
    expect(collide.build_graph(footprints), {"d-1": {}, "d-2": {}})
    records = decisions(footprints)
    expect([r["decision"] for r in records], ["INDEPENDENT", "INDEPENDENT"])


def case_module_overlap_is_reported_even_though_it_creates_no_edge(tmp: Path) -> None:
    module = "demo/lib/features/opds"
    footprints = [fp("d-1", [f"{module}/a.dart"]), fp("d-2", [f"{module}/b.dart"])]
    overlaps = collide.module_overlaps(footprints, collide.build_graph(footprints))
    expect(overlaps, [{"beads": ["d-1", "d-2"], "modules": [module]}])


def case_a_chain_forms_one_component(tmp: Path) -> None:
    """A overlaps B, B overlaps C — all three plan against the same edit."""
    footprints = [
        fp("d-1", [HARNESS]),
        fp("d-2", [HARNESS, CATALOG]),
        fp("d-3", [CATALOG]),
    ]
    expect(only(footprints)["members"], ["d-1", "d-2", "d-3"])


def case_paths_are_normalised_before_comparison(tmp: Path) -> None:
    footprints = [fp("d-1", [HARNESS]), fp("d-2", ["./" + HARNESS])]
    expect(only(footprints)["members"], ["d-1", "d-2"])


def case_blank_paths_and_symbols_never_create_an_edge(tmp: Path) -> None:
    footprints = [fp("d-1", ["", " "], [""]), fp("d-2", ["  "], [" "])]
    expect(collide.build_graph(footprints), {"d-1": {}, "d-2": {}})


# --- the decisions -----------------------------------------------------------


def case_overlap_with_the_same_cause_key_merges(tmp: Path) -> None:
    footprints = [fp("d-1", [HARNESS]), fp("d-2", [HARNESS, CATALOG])]
    record = only(footprints, {"d-1": "opds-harness", "d-2": "opds-harness"})
    expect(record["decision"], "MERGE")
    expect(record["late_duplicate"], False)
    assert HARNESS in record["reason"], record["reason"]
    assert "opds-harness" in record["reason"], record["reason"]
    expect(record["dep_intents"], [])


def case_overlap_with_distinct_cause_keys_sequences(tmp: Path) -> None:
    footprints = [fp("d-1", [HARNESS]), fp("d-2", [HARNESS, CATALOG])]
    record = only(footprints, {"d-1": "harness", "d-2": "paywall"})
    expect(record["decision"], "SEQUENCE")
    expect(len(record["dep_intents"]), 1)
    assert HARNESS in record["dep_intents"][0]["why"], record["dep_intents"]


def case_the_signature_changing_bead_is_ordered_first(tmp: Path) -> None:
    footprints = [
        fp("d-1", [HARNESS, CATALOG, READER]),
        fp("d-2", [HARNESS], ["OpdsTestServer.start"], signature=["OpdsTestServer.start"]),
    ]
    record = only(footprints, {"d-1": "one", "d-2": "two"})
    expect(record["decision"], "SEQUENCE")
    expect(record["order"], ["d-2", "d-1"])
    expect(record["dep_intents"][0]["command"], "bd dep add d-1 d-2")


def case_narrower_change_lands_first_when_neither_moves_a_signature(tmp: Path) -> None:
    footprints = [
        fp("d-1", [HARNESS, CATALOG, READER]),
        fp("d-2", [HARNESS]),
    ]
    record = only(footprints, {"d-1": "one", "d-2": "two"})
    expect(record["order"], ["d-2", "d-1"])


def case_overlap_with_no_cause_key_on_record_sequences_never_merges(tmp: Path) -> None:
    """Beads not *proven* to share a cause are not merged — SEQUENCE is the
    conservative answer, and it costs ordering rather than correctness."""
    record = only([fp("d-1", [HARNESS]), fp("d-2", [HARNESS, CATALOG])])
    expect(record["decision"], "SEQUENCE")
    expect(record["late_duplicate"], False)


def case_disjoint_footprints_are_one_independent_group_each(tmp: Path) -> None:
    records = decisions([fp("d-1", [HARNESS]), fp("d-2", [READER])])
    expect([r["decision"] for r in records], ["INDEPENDENT", "INDEPENDENT"])
    expect([r["members"] for r in records], [["d-1"], ["d-2"]])
    expect(records[0]["reason"], "no overlap")


def case_identical_footprints_merge_as_a_late_duplicate(tmp: Path) -> None:
    """The Phase 2 miss: two differently-worded reports of one defect."""
    footprints = [
        fp("d-1", [HARNESS], ["OpdsTestServer.start"]),
        fp("d-2", [HARNESS], ["OpdsTestServer.start"]),
    ]
    record = only(footprints, {"d-1": "one", "d-2": "two"})
    expect(record["decision"], "MERGE")
    expect(record["late_duplicate"], True)


def case_footprints_carrying_no_files_and_no_symbols_are_never_duplicates(
    tmp: Path,
) -> None:
    """Two empty footprints are identical in the trivial sense only. Merging
    on that would fuse two unrelated beads on the strength of no evidence."""
    component = {
        "group_id": "g1",
        "members": ["d-1", "d-2"],
        "edges": {"d-1": {"d-2": {"files": [], "symbols": []}}, "d-2": {}},
        "footprints": {"d-1": fp("d-1"), "d-2": fp("d-2")},
    }
    record = collide.decide(component, {})
    expect(record["late_duplicate"], False)
    expect(record["decision"], "SEQUENCE")


def case_dep_intents_are_text_and_never_run_the_tracker(tmp: Path) -> None:
    footprints = [fp("d-1", [HARNESS]), fp("d-2", [HARNESS, CATALOG])]
    record = only(footprints, {"d-1": "one", "d-2": "two"})
    intent = record["dep_intents"][0]
    expect(sorted(intent), ["command", "from", "to", "why"])
    assert intent["command"].startswith("bd dep add "), intent


def case_a_dep_intent_carries_its_endpoints(tmp: Path) -> None:
    """The pair `collide` decided, as fields. `derive_intents` builds a `dep`
    record from these; reading them back out of the command text would be a
    parser for a shape this function controls."""
    footprints = [fp("d-1", [HARNESS], ["Stub"], signature=["Stub"]),
                  fp("d-2", [HARNESS, CATALOG], ["Stub"])]
    record = only(footprints, {"d-1": "one", "d-2": "two"})
    expect(record["decision"], "SEQUENCE")
    intent = record["dep_intents"][0]
    expect((intent["from"], intent["to"]), ("d-2", "d-1"))


def case_a_dep_intents_fields_match_its_command(tmp: Path) -> None:
    """The case that stops the two halves of one record ever disagreeing."""
    footprints = [fp("d-1", [HARNESS]), fp("d-2", [HARNESS, CATALOG]),
                  fp("d-3", [CATALOG])]
    for record in decisions(footprints, {"d-1": "a", "d-2": "b", "d-3": "c"}):
        for intent in record["dep_intents"]:
            expect(intent["command"],
                   f"bd dep add {intent['from']} {intent['to']}")


# --- the manifest roster: no bead leaves the run unreported -------------------


def case_a_run_bead_with_no_footprint_is_reported_unclassified(tmp: Path) -> None:
    """Regression: a bead the footprints never mentioned used to vanish.

    Groups are seeded from footprints alone, so a parked worker or a malformed
    `footprint:` block put its bead in no group, no decision and no report line
    while the run still exited 0.
    """
    data = {"beads": [{"id": "d-1", "route": "plan"}, {"id": "d-2", "route": "plan"}]}
    groups = decisions([fp("d-1", [HARNESS])])
    records = collide.unclassified(data, groups)
    expect(len(records), 1)
    expect(records[0]["members"], ["d-2"])
    expect(records[0]["decision"], "UNCLASSIFIED")
    assert records[0]["reason"], records[0]


def case_skipped_and_dropped_beads_are_never_flagged_unclassified(tmp: Path) -> None:
    """Calibration the other way: only beads this run is planning are expected.

    A `skip` or `drift-report` bead is not in the run, and a dedup drop already
    left an explicit, reported decision. Flagging those is crying wolf.
    """
    data = {
        "beads": [
            {"id": "d-1", "route": "skip"},
            {"id": "d-2", "route": "drift-report"},
            {
                "id": "d-3",
                "route": "plan",
                "dedup": {"action": "drop", "covered_by": "/x.md"},
            },
        ]
    }
    expect(collide.unclassified(data, []), [])


# --- determinism -------------------------------------------------------------


def case_shuffled_footprints_produce_identical_groups(tmp: Path) -> None:
    footprints = [
        fp("d-3", [CATALOG]),
        fp("d-1", [HARNESS]),
        fp("d-9", [READER]),
        fp("d-2", [HARNESS, CATALOG]),
    ]
    forward = decisions(footprints)
    backward = decisions(list(reversed(footprints)))
    expect(forward, backward)
    expect([r["group_id"] for r in forward], ["g1", "g2"])
    expect(forward[0]["members"], ["d-1", "d-2", "d-3"])



def case_an_excluded_bead_is_not_in_the_run(tmp) -> None:
    """`skills-j39`: `inventory.select` leaves the entry in place.

    Reading `route` alone put beads the run was told not to touch into
    collision groups, so a run scoped to two beads grouped the whole backlog.
    """
    data = {"beads": [
        {"id": "a", "route": "plan", "selected": True},
        {"id": "b", "route": "plan", "selected": False},
        {"id": "c", "route": "investigate"},
    ]}
    assert collide._run_beads(data) == {"a", "c"}, collide._run_beads(data)


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
