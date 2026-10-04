"""Tests for inventory.py — the routing table, repo resolution, and selection.

The command line lives in test_inventory_cli.py; everything here runs in
process. Run with `python3 test_inventory.py` (no pytest dependency).
"""

from __future__ import annotations

import os
import sys
import tempfile
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import inventory  # noqa: E402


def bead(**kw) -> dict:
    base = {"id": "x-1", "status": "needs-plan", "issue_type": "task"}
    base.update(kw)
    return base


def child(**kw) -> dict:
    dep = {"issue_id": "x-1", "depends_on_id": "x-9", "type": "parent-child"}
    return bead(dependencies=[dep], **kw)


def expect(got, want) -> None:
    assert got == want, f"got {got!r}, want {want!r}"


# --- classify: one case per routing-table row -------------------------------


def case_needs_plan_bare_routes_investigate(tmp: Path) -> None:
    expect(inventory.classify(bead(), ""), ("investigate", "no investigation on record"))


def case_needs_plan_with_investigation_routes_plan(tmp: Path) -> None:
    notes = "Investigation: /abs/path.md"
    expect(inventory.classify(bead(), notes), ("plan", "investigation on record"))


def case_plan_marker_outranks_investigation_marker(tmp: Path) -> None:
    notes = "Investigation: /a.md\nPlan: /b.md"
    expect(inventory.classify(bead(), notes), ("skip", "already planned"))


def case_open_with_plan_marker_skips(tmp: Path) -> None:
    b = bead(status="open")
    expect(inventory.classify(b, "Plan: /b.md"), ("skip", "already planned"))


def case_open_with_slice_marker_skips(tmp: Path) -> None:
    b = bead(status="open")
    expect(inventory.classify(b, "Slice: /b.md"), ("skip", "already planned"))


def case_open_with_master_marker_skips(tmp: Path) -> None:
    b = bead(status="open")
    expect(inventory.classify(b, "Master: /b.md"), ("skip", "already planned"))


def case_open_without_plan_path_is_drift(tmp: Path) -> None:
    b = bead(status="open")
    expect(inventory.classify(b, ""), ("drift-report", "open with no plan path"))


def case_epic_is_owned_by_its_master_plan(tmp: Path) -> None:
    b = bead(status="open", issue_type="epic")
    expect(inventory.classify(b, "Master: /m.md"),
           ("skip", "owned by its master plan"))


def case_child_via_dependencies_is_owned_by_master_plan(tmp: Path) -> None:
    expect(inventory.classify(child(status="open"), "Slice: /s.md"),
           ("skip", "owned by its master plan"))


def case_child_via_parent_key_is_owned_by_master_plan(tmp: Path) -> None:
    b = bead(status="open", parent="x-9")
    expect(inventory.classify(b, "Plan: /p.md"),
           ("skip", "owned by its master plan"))


def case_plan_less_epic_child_routes_investigate(tmp: Path) -> None:
    """A followup parented to an epic under the workspace Scope RULE carries
    no plan path, so nothing owns it and triage must not drop it."""
    expect(inventory.classify(child(status="needs-plan"), ""),
           ("investigate", "no investigation on record"))


def case_open_plan_less_epic_child_is_drift(tmp: Path) -> None:
    """Same bead, `open`: the drift report is what surfaces it."""
    expect(inventory.classify(bead(status="open", parent="x-9"), ""),
           ("drift-report", "open with no plan path"))


def case_blocked_is_skipped_by_status(tmp: Path) -> None:
    expect(inventory.classify(bead(status="blocked"), ""), ("skip", "status: blocked"))


def case_deferred_is_skipped_by_status(tmp: Path) -> None:
    expect(inventory.classify(bead(status="deferred"), ""), ("skip", "status: deferred"))


def case_closed_is_skipped_by_status(tmp: Path) -> None:
    expect(inventory.classify(bead(status="closed"), ""), ("skip", "status: closed"))


def case_pinned_is_skipped_by_status(tmp: Path) -> None:
    expect(inventory.classify(bead(status="pinned"), ""), ("skip", "status: pinned"))


def case_terminal_status_outranks_epic_membership(tmp: Path) -> None:
    """The note is load-bearing: without a plan path the epic branch cannot
    fire at all, so the case would pass wherever that branch sat and stop
    testing the precedence it is named for."""
    b = bead(status="closed", issue_type="epic")
    expect(inventory.classify(b, "Master: /m.md"), ("skip", "status: closed"))


def case_unknown_status_is_still_routed(tmp: Path) -> None:
    b = bead(status="marinating")
    expect(inventory.classify(b, ""), ("skip", "status not routed in v1: marinating"))


# --- resolve_repo_root ------------------------------------------------------


def workspace(tmp: Path, beads: bool = True) -> Path:
    """Build a projects root holding one `demo` project, with or without `.beads/`."""
    root = tmp / "ws"
    project = root / "demo"
    leaf = project / ".beads" if beads else project
    leaf.mkdir(parents=True)
    return root


def case_repo_root_resolves_project_with_beads_dir(tmp: Path) -> None:
    root = workspace(tmp)
    os.environ["TRIAGE_PROJECTS_ROOT"] = str(root)
    try:
        expect(inventory.resolve_repo_root("demo"), root / "demo")
    finally:
        del os.environ["TRIAGE_PROJECTS_ROOT"]


def case_repo_root_without_beads_dir_is_a_usage_error(tmp: Path) -> None:
    root = workspace(tmp, beads=False)
    os.environ["TRIAGE_PROJECTS_ROOT"] = str(root)
    try:
        inventory.resolve_repo_root("demo")
    except inventory.UsageError as e:
        assert "demo" in str(e), str(e)
    else:
        raise AssertionError("expected UsageError")
    finally:
        del os.environ["TRIAGE_PROJECTS_ROOT"]


def case_missing_projects_root_is_a_usage_error(tmp: Path) -> None:
    """No default projects root exists any more. A caller who forgets the seam
    gets a usage error, never a silent resolution of the operator's real tree."""
    saved = os.environ.pop("TRIAGE_PROJECTS_ROOT", None)
    try:
        inventory.resolve_repo_root("demo")
    except inventory.UsageError as e:
        assert "TRIAGE_PROJECTS_ROOT" in str(e), str(e)
    else:
        raise AssertionError("expected UsageError")
    finally:
        if saved is not None:
            os.environ["TRIAGE_PROJECTS_ROOT"] = saved


def case_project_name_with_separator_is_a_usage_error(tmp: Path) -> None:
    """The name check runs before the root check, so this stays a separator
    test even when `TRIAGE_PROJECTS_ROOT` is unset."""
    try:
        inventory.resolve_repo_root("../demo")
    except inventory.UsageError as e:
        assert "not a project name" in str(e), str(e)
    else:
        raise AssertionError("expected UsageError")


# --- the roster query and classify's totality --------------------------------


def case_the_roster_query_never_asks_for_closed_beads(tmp: Path) -> None:
    """`skills-lyo`: the rubric and the query must not drift apart.

    Plain `bd list` omits closed issues, so no closed bead reaches a manifest
    and `classify`'s `closed` branch is unreachable through a run.
    `references/classification.md` precedence rule 1 states that; this pins the
    query it rests on. Adding `--all` here without amending that rule would
    make the documentation wrong and quietly multiply every run's work.
    """
    assert "--all" not in inventory.ROSTER_QUERY, inventory.ROSTER_QUERY
    assert inventory.ROSTER_QUERY == ("list", "--limit", "0", "--json")


def case_classify_still_routes_a_closed_bead(tmp: Path) -> None:
    """Unreachable from the CLI is not the same as unnecessary: `classify` is
    total over any input, and a caller may hand it a closed bead directly."""
    route, reason = inventory.classify(
        {"id": "x", "status": "closed", "issue_type": "epic"}, "")
    assert (route, reason) == ("skip", "status: closed"), (route, reason)


# --- run selection (skills-cbn) ----------------------------------------------


def _entries(*routes) -> list:
    return [{"id": f"b{i}", "route": r, "reason": "", "status": "needs-plan",
             "title": f"t{i}"} for i, r in enumerate(routes, 1)]


def case_selection_marks_rather_than_deletes(tmp: Path) -> None:
    """The manifest must record every bead the backlog holds.

    A later run has to tell "not selected" from "not seen"; deleting the entry
    destroys exactly that distinction.
    """
    entries = _entries("investigate", "plan", "skip")
    kept = inventory.select(entries, ids=["b1"], only=None, max_beads=0)
    assert len(kept) == 3, kept
    assert [e["selected"] for e in kept] == [True, False, False]
    assert kept[1]["excluded"] == "not in --ids", kept[1]


def case_only_restricts_by_route(tmp: Path) -> None:
    kept = inventory.select(_entries("investigate", "plan", "investigate"),
                            ids=None, only="plan", max_beads=0)
    assert [e["selected"] for e in kept] == [False, True, False]
    assert kept[0]["excluded"] == "route is not plan", kept[0]


def case_max_caps_only_the_spend_routes(tmp: Path) -> None:
    """`skip` and `drift-report` cost no worker, so a cap must not spend
    itself on them — capping the roster instead of the spend would silently
    shrink the run for no saving."""
    kept = inventory.select(_entries("skip", "investigate", "plan", "plan"),
                            ids=None, only=None, max_beads=2)
    assert [e["selected"] for e in kept] == [False, True, True, False]
    assert kept[3]["excluded"] == "over --max 2", kept[3]
    assert kept[0]["excluded"] == "route skip costs no worker", kept[0]


def case_max_zero_means_unlimited(tmp: Path) -> None:
    kept = inventory.select(_entries("plan", "plan", "plan"),
                            ids=None, only=None, max_beads=0)
    assert all(e["selected"] for e in kept), kept


def case_filters_compose(tmp: Path) -> None:
    kept = inventory.select(_entries("investigate", "plan", "plan"),
                            ids=["b2", "b3"], only="plan", max_beads=1)
    assert [e["selected"] for e in kept] == [False, True, False]


def case_an_unknown_id_is_a_usage_error(tmp: Path) -> None:
    """Silently selecting nothing would look like an empty backlog."""
    try:
        inventory.select(_entries("plan"), ids=["nope"], only=None, max_beads=0)
    except inventory.UsageError:
        return
    raise AssertionError("expected UsageError")


def case_an_unknown_only_route_is_a_usage_error(tmp: Path) -> None:
    try:
        inventory.select(_entries("plan"), ids=None, only="teleport", max_beads=0)
    except inventory.UsageError:
        return
    raise AssertionError("expected UsageError")


def case_counts_keep_the_backlog_and_selected_counts_the_run(tmp: Path) -> None:
    """Two tallies, because they answer different questions.

    `counts` is what the backlog holds — the thing a later run compares
    against. `selected_counts` is what this run will actually spend workers on.
    Collapsing them loses the distinction the marking exists to preserve.
    """
    m = inventory.build_manifest("proj", inventory.select(
        _entries("plan", "plan"), ids=None, only=None, max_beads=1))
    assert m["counts"]["plan"] == 2, m["counts"]
    assert m["selected_counts"]["plan"] == 1, m["selected_counts"]


def case_the_manifest_carries_the_backlog_total(tmp: Path) -> None:
    """The one number the Wave 6 close-out was left to work out for itself.

    `counts` gives a tally per route and no sum, so the report's headline meant
    adding four values by hand — and two independent live runs added them to 24
    over a table of 23. Every other figure in a close-out is script output;
    this one was arithmetic, and it is the one that was wrong.
    """
    m = inventory.build_manifest("proj", inventory.select(
        _entries("plan", "plan"), ids=None, only=None, max_beads=1))
    expect(m["total"], 2)
    expect(m["total"], len(m["beads"]))


def case_the_selected_total_counts_only_what_the_run_will_spend(tmp: Path) -> None:
    """`--ids`, `--only` and `--max` leave excluded beads in the manifest, so
    the backlog total and the run's own size are different numbers and the
    close-out reports both."""
    m = inventory.build_manifest("proj", inventory.select(
        _entries("plan", "plan"), ids=None, only=None, max_beads=1))
    expect(m["selected_total"], 1)
    expect(m["selected_total"], sum(m["selected_counts"].values()))


def case_an_empty_backlog_totals_zero(tmp: Path) -> None:
    m = inventory.build_manifest("proj", [])
    expect(m["total"], 0)
    expect(m["selected_total"], 0)


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
