"""Assert the route and reason the routing table records for every bead.

The oracle is `fixtures/beads.json`'s own `expect` block, read back out of a
manifest `inventory.py` produced from a real `bd` database — not out of a
hand-built dict.

One row is asserted differently, and deliberately. `inventory.collect` reads
its roster from `bd list --limit 0 --json`, and `bd list` omits closed issues
unless `--all` is passed, so no closed bead can ever reach a manifest.
`tb-clsepc` is therefore asserted by calling `inventory.classify` directly,
and this suite asserts the absence too, so the gap stays visible rather than
being papered over. Tracked as `skills-lyo`; fixing it is not this suite's
job, and claiming manifest coverage it does not have would be exactly the
dishonesty the epic exists to prevent.

Row 5 names two arms — an epic, or a child of one — and each has its own
corpus bead, because `_is_epic_or_child` short-circuits on `issue_type` and
would never reach its later clauses if an epic were the only bead behind the
row. `tb-epc` covers the `issue_type` arm and `tb-epc.1` covers the child arm,
asserted out of a manifest built from a real `bd list --json`.

What that does **not** pin is the `parent` key on its own. `bd update --parent`
writes the key *and* a redundant `parent-child` edge, and `bd list` emits
both — every child in `../scripts/fixtures/bd_list_demo.json` carries the
pair — so `_is_epic_or_child`'s dependencies clause answers for a real child
whether or not the key is read. The manifest therefore proves that a
bd-created child routes `owned by its master plan`, which is the behaviour
that matters, and no corpus built by `bd` can isolate either clause.
`test_inventory.py`'s `case_child_via_parent_key_is_owned_by_master_plan` and
`case_child_via_dependencies_is_owned_by_master_plan` are what separate them,
in process, on beads they construct themselves.

`tb-inv2` stays a plan-less child of the same epic and is the corpus proof of
`skills-viw`: revert the `and has_plan` gate and it is the bead that reddens,
because a followup no plan covers must be routed rather than dropped.
"""

from __future__ import annotations

import json
import sys

import harness

sys.path.insert(0, str(harness.SCRIPTS))

import inventory  # noqa: E402

BEADS = json.loads((harness.FIXTURES / "beads.json").read_text(encoding="utf-8"))
EXPECTED = {row["id"]: row["expect"] for row in BEADS}

# Every row of ../references/classification.md §1, and the bead that covers it.
ROUTING_TABLE = {
    "needs-plan, no markers": ("tb-inv1", "tb-inv2"),
    "needs-plan, Investigation:": ("tb-pln1",),
    "open, plan path": ("tb-skp1",),
    "open, no plan path": ("tb-drf1",),
    "epic or child of an epic, with a plan path": ("tb-epc", "tb-epc.1"),
    "terminal status": ("tb-blk", "tb-clsepc"),
}

CLASSIFY_ONLY = ("tb-clsepc",)


def _routed(testbed) -> tuple[int, dict]:
    """(exit code, manifest) from one real inventory.py run over the testbed."""
    out = harness.scratch_path(testbed, "manifest_routing.json")
    code, _, err = harness.run("inventory.py", "--project", testbed.path.name,
                               "--json", "--out", str(out), testbed=testbed)
    assert out.is_file(), f"inventory wrote no manifest at {out}: {err}"
    return code, json.loads(out.read_text(encoding="utf-8"))


def _fixture_bead(bead_id: str) -> dict:
    entry = next(row for row in BEADS if row["id"] == bead_id)
    bead = {"id": entry["id"], "status": entry["status"],
            "issue_type": entry["issue_type"], "dependencies": []}
    if entry.get("parent"):
        bead["parent"] = entry["parent"]
    return bead


def _fixture_notes(bead_id: str) -> str:
    """The notes the fixture declares, so a `classify` probe reads the same
    oracle the manifest cases do. Passing `""` instead would leave `has_plan`
    False and silently disarm any case whose subject is the epic branch."""
    entry = next(row for row in BEADS if row["id"] == bead_id)
    return entry.get("notes") or ""


def case_inventory_routes_every_bead_as_the_matrix_declares(testbed) -> None:
    _, manifest = _routed(testbed)
    seen = set()
    for entry in manifest["beads"]:
        want = EXPECTED[entry["id"]]
        assert entry["route"] == want["route"], (entry["id"], entry["route"])
        assert entry["reason"] == want["reason"], (entry["id"], entry["reason"])
        seen.add(entry["id"])
    missing = set(EXPECTED) - seen - set(CLASSIFY_ONLY)
    assert not missing, f"beads the manifest never routed: {sorted(missing)}"


def case_closed_epic_is_asserted_through_classify_not_the_manifest(testbed) -> None:
    _, manifest = _routed(testbed)
    ids = {entry["id"] for entry in manifest["beads"]}
    assert "tb-clsepc" not in ids, (
        "tb-clsepc reached the manifest — skills-lyo is fixed, so this row "
        "must move back to manifest coverage")
    got = inventory.classify(_fixture_bead("tb-clsepc"),
                             _fixture_notes("tb-clsepc"))
    assert got == ("skip", "status: closed"), got


def case_every_routing_table_row_is_covered(testbed) -> None:
    _, manifest = _routed(testbed)
    ids = {entry["id"] for entry in manifest["beads"]}
    for row, beads in ROUTING_TABLE.items():
        covered = any(b in ids or b in CLASSIFY_ONLY for b in beads)
        assert covered, f"routing-table row {row!r} has no bead behind it"


def case_drift_bead_makes_inventory_exit_1(testbed) -> None:
    code, manifest = _routed(testbed)
    assert code == 1, code
    drift = [e for e in manifest["beads"] if e["route"] == "drift-report"]
    assert [e["id"] for e in drift] == ["tb-drf1"], drift
    assert manifest["counts"]["drift-report"] == 1, manifest["counts"]


def case_inventory_writes_only_to_out(testbed) -> None:
    """Regression for commit 4e94681 — the default used to litter the cwd."""
    out = harness.scratch_path(testbed, "manifest_only_out.json")
    for args in (("--json", "--out", str(out)), ("--table",)):
        harness.run("inventory.py", "--project", testbed.path.name, *args,
                    testbed=testbed, cwd=testbed.path)
        stray = sorted(p.name for p in testbed.path.glob("manifest*.json"))
        assert not stray, f"{args} left {stray} in the working directory"


def case_precedence_reasons_are_the_specific_ones(testbed) -> None:
    _, manifest = _routed(testbed)
    reasons = {entry["id"]: entry["reason"] for entry in manifest["beads"]}
    assert reasons["tb-both"] == "already planned", reasons["tb-both"]
    assert reasons["tb-epc"] == "owned by its master plan", reasons["tb-epc"]
    assert reasons["tb-unk"] == "status not routed in v1: snoozed", reasons["tb-unk"]
    got = inventory.classify(_fixture_bead("tb-clsepc"),
                             _fixture_notes("tb-clsepc"))[1]
    assert got == "status: closed", f"precedence rule 1: {got}"


def case_database_guard_refuses_a_testbed_without_its_own_database(testbed) -> None:
    """Phase 1 demonstrated this with a fake `bd`; the guard is what has to
    catch it. A testbed directory with no `.beads` of its own resolves, by
    bd's own upward walk, to the skills repo's real tracker."""
    harness.assert_db_inside(testbed)
    fake = harness.Testbed(
        root=testbed.root, path=harness.SKILLS_ROOT / "triage" / "e2e",
        clean=testbed.clean, corpus=testbed.corpus, scratch=testbed.scratch,
        bead_ids=testbed.bead_ids)
    try:
        harness.assert_db_inside(fake)
    except AssertionError as err:
        assert str(harness.SKILLS_ROOT / ".beads") in str(err), err
    else:
        raise AssertionError(
            "the guard passed a testbed with no database of its own")


CASES = [v for k, v in sorted(globals().items()) if k.startswith("case_")]
