#!/usr/bin/env python3
"""Tests for derive_intents.py — the three intent kinds a run can build from
its own record, and the beads it must refuse to build one for.

The load-bearing cases are the ones that produce nothing: a bead whose outcome
no kind covers, and a `dep_intents` entry written before `collide.py` emitted
its endpoints. Both are findings naming the bead or the group — a dropped bead
is the defect class this epic exists to close.

Run with `python3 test_derive_intents.py` (no pytest dependency).
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import derive_intents  # noqa: E402
import intent_records  # noqa: E402
import manifest as manifest_io  # noqa: E402
import staged_run  # noqa: E402

PROJECT = "proj"
PLAN_FOLDER = "proj_epic_demo_thing"
INVEST_NAME = "proj_invest_thing_goes_wrong.md"


def expect(got, want) -> None:
    assert got == want, f"got {got!r}, want {want!r}"


# --- the fixture: a ledger and a manifest in a tmp dir -----------------------


def new_run(tmp: Path) -> Path:
    """The run directory shape `create_run` makes, minus everything a
    derivation does not read."""
    run = tmp / "triage" / "2026-08-28_ab12"
    for name in ("investigations", "todo", "intents"):
        (run / name).mkdir(parents=True, exist_ok=True)
    return run


def seed(run: Path, rows=(), groups=(), beads=()) -> Path:
    run.parent.mkdir(parents=True, exist_ok=True)
    (run / "ledger.md").write_text(
        staged_run.ledger_header("full run") + "".join(rows), encoding="utf-8")
    manifest_io.save(run / "manifest.json",
                     {"schema_version": 1, "project": PROJECT,
                      "generated_at": "2020-01-01T00:00:00Z",
                      "beads": list(beads), "groups": list(groups)})
    return run


def plan_folder(run: Path) -> Path:
    folder = run / "todo" / PLAN_FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "plan.md").write_text("# Plan\n", encoding="utf-8")
    return folder


def investigation(run: Path) -> Path:
    path = run / "investigations" / INVEST_NAME
    path.write_text("# Investigation\n", encoding="utf-8")
    return path


def planned_rows(run: Path, bead: str, artifact: Path) -> list:
    """Wave 2 investigates, Wave 4 plans — the two artifact rows a planned
    bead leaves behind."""
    return [
        staged_run.ledger_row(bead=bead, wave=2, worker=f"invest-{bead}",
                              dispatched="2026-08-28T10:00:00Z",
                              returned="2026-08-28T10:01:00Z",
                              artifact=investigation(run), final="planned"),
        staged_run.ledger_row(bead=bead, wave=4, worker=f"plan-{bead}",
                              dispatched="2026-08-28T10:02:00Z",
                              returned="2026-08-28T10:03:00Z",
                              artifact=artifact, final="planned"),
    ]


def settled_row(run: Path, bead: str, final: str, artifact=None) -> str:
    return staged_run.ledger_row(
        bead=bead, wave=2, worker=f"invest-{bead}",
        dispatched="2026-08-28T10:04:00Z", returned="2026-08-28T10:05:00Z",
        artifact=investigation(run) if artifact is None else artifact,
        final=final)


def derived(run: Path) -> tuple:
    return derive_intents.derive(run, staged_run.load_run(run))


def cli(run: Path, *extra) -> tuple:
    """`main` plus what it printed, which is the orchestrator's whole view."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = derive_intents.main(["--run-dir", str(run), *extra])
    return code, out.getvalue()


def group(gid: str, members: list, dep_intents: list) -> dict:
    return {"group_id": gid, "members": members, "decision": "SEQUENCE",
            "order": members, "dep_intents": dep_intents}


def dep_intent(first: str, second: str) -> dict:
    return {"command": f"bd dep add {first} {second}", "why": "shared files: x",
            "from": first, "to": second}


def roster(bid: str, route: str = "plan", selected: bool = True) -> dict:
    """One manifest bead entry, in the shape `run_scope` reads."""
    return {"id": bid, "route": route, "selected": selected}


PHASES = ("phase_1_one.md", "phase_2_two.md", "phase_3_three.md")
DEP_TABLE = """# Plan

## Dependency Table

| Phase | Scope | Depends on | Slice |
|-------|-------|------------|-------|
| **1: One** | first | — | [phase_1_one.md](phase_1_one.md) |
| **2: Two** | second | Phase 1 | [phase_2_two.md](phase_2_two.md) |
| **3: Three** | third | Phases 1, 2 | [phase_3_three.md](phase_3_three.md) |
"""


def epic_run(tmp: Path, groups=None, members=("proj-a1", "proj-m2"),
             final: str = "planned") -> tuple:
    """A group planned into an epic, staged the way a run stages it.

    The folder carries a real Dependency Table and its slices — that is what
    makes the group an epic rather than one plan — and the `create-epic` and
    `create-task` records sit under the bead the orchestrator briefed, which
    is where `intent_records.load_all` reads their owner from. So the
    derivation sees the epic through the store, never through a manifest field
    only this fixture would know about.
    """
    run = new_run(tmp)
    folder = plan_folder(run)
    (folder / "plan.md").write_text(DEP_TABLE, encoding="utf-8")
    for name in PHASES:
        (folder / name).write_text("# Phase\n", encoding="utf-8")
    seed(run, [group_row(folder, final=final)],
         groups or [group("g1", list(members), [])],
         [roster(bead) for bead in members])
    master = str(folder / "plan.md")
    intent_records.save(run, "proj-a1", [
        {"key": "epic", "kind": "create-epic", "ref": "epic",
         "title": "Demo thing", "master": master}]
        + [{"key": f"phase-{n}", "kind": "create-task", "ref": f"phase_{n}",
            "parent": "epic", "title": f"Phase {n}",
            "slice": str(folder / name), "master": master}
           for n, name in enumerate(PHASES, 1)])
    return run, folder


def group_row(artifact: Path, gid: str = "g1", final: str = "planned") -> str:
    """The Wave 4 row a group plan lands with — every member's outcome."""
    return staged_run.ledger_row(
        bead=gid, wave=4, worker=f"plan-{gid}",
        dispatched="2026-08-28T10:02:00Z", returned="2026-08-28T10:03:00Z",
        artifact=artifact, final=final)


# --- one record per settled outcome ------------------------------------------


def case_a_planned_bead_yields_one_flip_source(tmp: Path) -> None:
    run = new_run(tmp)
    folder = plan_folder(run)
    seed(run, planned_rows(run, "proj-a1", folder))
    by_bead, findings = derived(run)
    expect(findings, [])
    expect([r["kind"] for r in by_bead["proj-a1"]], ["flip-source"])
    record = by_bead["proj-a1"][0]
    expect(record["plan"], str(folder / "plan.md"))
    expect(record["key"], "flip-source-proj-a1")
    expect(intent_records.validate(record), [])


def case_a_parked_bead_yields_one_investigation(tmp: Path) -> None:
    run = new_run(tmp)
    seed(run, [settled_row(run, "proj-p9", "parked")])
    by_bead, findings = derived(run)
    expect(findings, [])
    record = by_bead["proj-p9"][0]
    expect(record["kind"], "investigation")
    expect(record["investigation"], str(run / "investigations" / INVEST_NAME))
    expect(record["key"], "investigation-proj-p9")
    expect(intent_records.validate(record), [])


def case_a_duplicate_bead_yields_one_close_naming_its_investigation(tmp: Path) -> None:
    """The duplicate ruling is a cell in the run's own ledger and its reasoning
    is an artifact the run already staged, so the record is derived rather than
    handed to a human."""
    run = new_run(tmp)
    seed(run, [settled_row(run, "proj-d3", "duplicate")])
    by_bead, findings = derived(run)
    expect(findings, [])
    record = by_bead["proj-d3"][0]
    expect(record["kind"], "close")
    expect(record["investigation"], str(run / "investigations" / INVEST_NAME))
    expect(record["key"], "close-proj-d3")
    expect(intent_records.validate(record), [])


def case_a_duplicate_with_no_staged_investigation_is_still_a_finding(tmp: Path) -> None:
    """The settled-outcome-without-an-artifact path `_outcome_records` already
    owns: a ruling whose reasoning nobody staged is named, never written with a
    `None` path."""
    run = new_run(tmp)
    seed(run, [settled_row(run, "proj-d3", "duplicate", plan_folder(run))])
    by_bead, findings = derived(run)
    expect(by_bead, {})
    expect(len(findings), 1)
    assert "proj-d3" in findings[0] and "investigation" in findings[0], findings
    code, printed = cli(run)
    expect(code, 1)
    assert "proj-d3" in printed, printed


def case_an_in_flight_bead_is_named_not_dropped(tmp: Path) -> None:
    run = new_run(tmp)
    seed(run, [settled_row(run, "proj-f1", "")])
    by_bead, findings = derived(run)
    expect(by_bead, {})
    expect(len(findings), 1)
    assert "proj-f1" in findings[0], findings


def case_a_planned_bead_with_no_plan_artifact_is_a_finding(tmp: Path) -> None:
    """An outcome that maps to a kind but has only an investigation artifact is
    reported, never written with a `None` path."""
    run = new_run(tmp)
    seed(run, [settled_row(run, "proj-a1", "planned")])
    by_bead, findings = derived(run)
    expect(by_bead, {})
    expect(len(findings), 1)
    assert "proj-a1" in findings[0] and "plan" in findings[0], findings


def case_a_single_phase_plan_file_is_its_own_plan_path(tmp: Path) -> None:
    run = new_run(tmp)
    solo = run / "todo" / "proj_refactor_solo.md"
    solo.write_text("# Solo\n", encoding="utf-8")
    seed(run, planned_rows(run, "proj-a1", solo))
    by_bead, findings = derived(run)
    expect(findings, [])
    expect(by_bead["proj-a1"][0]["plan"], str(solo))


# --- the roster the ledger never recorded ------------------------------------


def case_a_routed_bead_with_no_ledger_row_is_a_finding(tmp: Path) -> None:
    """`bead_outcomes` builds its dict from Wave 2 and Wave 4 rows, so a bead
    the run selected and routed but never returned one for has no outcome at
    all — and is named here rather than dropped. The text is pinned because
    `NO_KIND` already spends "no outcome recorded" on the in-flight bead, which
    is a different thing for a human to go and look at."""
    run = seed(new_run(tmp), beads=[roster("proj-a1", "plan"),
                                    roster("proj-b2", "investigate")])
    by_bead, findings = derived(run)
    expect(by_bead, {})
    expect(findings,
           ["proj-a1: routed plan but the ledger holds no outcome row for it",
            "proj-b2: routed investigate but the ledger holds no outcome row"
            " for it"])


def case_the_cli_exits_1_on_a_rowless_routed_bead(tmp: Path) -> None:
    run = seed(new_run(tmp), beads=[roster("proj-a1", "plan")])
    code, printed = cli(run)
    expect(code, 1)
    assert "proj-a1" in printed, printed


def case_a_skip_routed_or_unselected_bead_raises_no_roster_finding(
    tmp: Path,
) -> None:
    """`run_scope`'s two carve-outs, pinned: a `skip` bead left before Wave 1
    and an `--ids`/`--only`/`--max` excluded one owe no outcome."""
    run = seed(new_run(tmp), beads=[roster("proj-s1", "skip"),
                                    roster("proj-d4", "drift-report"),
                                    roster("proj-x2", "plan", selected=False)])
    by_bead, findings = derived(run)
    expect(by_bead, {})
    expect(findings, [])


def case_a_bead_whose_group_row_covers_it_raises_no_roster_finding(
    tmp: Path,
) -> None:
    """A Wave 4 group row is every member's outcome, so a member with no row of
    its own is recorded and owes no finding — the false-positive guard."""
    run = new_run(tmp)
    folder = plan_folder(run)
    seed(run, [group_row(folder)], [group("g1", ["proj-a1", "proj-m2"], [])],
         [roster("proj-a1"), roster("proj-m2")])
    by_bead, findings = derived(run)
    expect(findings, [])
    expect(sorted(by_bead), ["proj-a1", "proj-m2"])


# --- what a merged group produces --------------------------------------------


def case_an_epic_group_supersedes_its_members_instead_of_flipping_them(
    tmp: Path,
) -> None:
    """A group this run's own epic replaced retires its members rather than
    leaving them workable duplicates of the epic. The choice is made once per
    bead, so no bead comes out both flipped open and closed."""
    run, folder = epic_run(tmp)
    by_bead, findings = derived(run)
    expect(findings, [])
    for bead in ("proj-a1", "proj-m2"):
        kinds = [r["kind"] for r in by_bead[bead]]
        assert "supersede" in kinds, (bead, kinds)
        assert "flip-source" not in kinds, (bead, kinds)
    record = next(r for r in by_bead["proj-a1"] if r["kind"] == "supersede")
    expect(record["key"], "supersede-proj-a1")
    # The epic belongs to whichever bead's file the planner wrote, and this
    # record lands in the member's file, so `by` has to carry the owner:
    # `intent_records.load_all` qualifies a bare local name and leaves this
    # one alone, which is what lets it resolve at apply time.
    expect(record["by"], "proj-a1/epic")
    expect(record["master"], str(folder / "plan.md"))
    expect(intent_records.validate(record), [])


def case_the_phase_chain_comes_from_the_master_plans_dependency_table(
    tmp: Path,
) -> None:
    """Phase 3 depends on phases 1 and 2, so exactly those two edges plus 2-on-1
    land — joined by slice filename against the worker's own `create-task`
    records, never by parsing a phase title."""
    run, _ = epic_run(tmp)
    by_bead, findings = derived(run)
    expect(findings, [])
    deps = [r for records in by_bead.values() for r in records
            if r["kind"] == "dep"]
    expect(sorted((r["from"], r["to"]) for r in deps),
           [("proj-a1/phase_2", "proj-a1/phase_1"),
            ("proj-a1/phase_3", "proj-a1/phase_1"),
            ("proj-a1/phase_3", "proj-a1/phase_2")])
    for record in deps:
        expect(record["dep_type"], "blocks")
        expect(record["bead"], "proj-a1")
        expect(intent_records.validate(record), [])


def case_a_collide_edge_between_two_superseded_beads_is_dropped(
    tmp: Path,
) -> None:
    """The pre-merge edge ordered two beads that no longer carry the work, and
    the phase chain states the same ordering between the tasks that do. An
    edge whose endpoints this epic did not retire is untouched."""
    run, _ = epic_run(tmp, [group("g1", ["proj-a1", "proj-m2"],
                                  [dep_intent("proj-m2", "proj-a1")]),
                            group("g3", ["b-7", "b-8"],
                                  [dep_intent("b-7", "b-8")])])
    by_bead, findings = derived(run)
    expect(findings, [])
    pairs = [(r["from"], r["to"]) for records in by_bead.values()
             for r in records if r["kind"] == "dep"]
    assert ("proj-m2", "proj-a1") not in pairs, pairs
    assert ("b-7", "b-8") in pairs, pairs


def case_a_single_phase_group_still_flips_its_source(tmp: Path) -> None:
    """The self-limit, and it must pass before and after this phase: a group
    with no `create-epic` is nothing this run replaced, so its members keep the
    flip that makes them workable."""
    run = new_run(tmp)
    folder = plan_folder(run)
    seed(run, [group_row(folder)], [group("g1", ["proj-a1", "proj-m2"], [])],
         [roster("proj-a1"), roster("proj-m2")])
    by_bead, findings = derived(run)
    expect(findings, [])
    for bead in ("proj-a1", "proj-m2"):
        expect([r["kind"] for r in by_bead[bead]], ["flip-source"])


def case_a_merged_group_supersedes_its_members_like_a_planned_one(
    tmp: Path,
) -> None:
    """`merged` is in `references/ledger.md`'s `final` vocabulary and it names
    exactly this population — a MERGE group planned into one epic. Mapped to
    no kind, the members got no record at all, and Phase 6's gate then
    quarantined every one of them and stranded the run on a legal value."""
    run, folder = epic_run(tmp, final="merged")
    by_bead, findings = derived(run)
    expect(findings, [])
    for bead in ("proj-a1", "proj-m2"):
        kinds = [r["kind"] for r in by_bead[bead]]
        assert "supersede" in kinds, (bead, kinds)
        assert "flip-source" not in kinds, (bead, kinds)


def case_a_one_member_group_planned_into_an_epic_is_superseded(
    tmp: Path,
) -> None:
    """Every INDEPENDENT bead is a one-member group. Its plan is still an epic
    with phase tasks, so flipping the source open would leave the workable
    duplicate the whole kind exists to prevent — the member count is not the
    self-limit, the absent `create-epic` is."""
    run, _ = epic_run(tmp, members=("proj-a1",))
    by_bead, findings = derived(run)
    expect(findings, [])
    kinds = [r["kind"] for r in by_bead["proj-a1"]]
    assert "supersede" in kinds, kinds
    assert "flip-source" not in kinds, kinds


# --- the ordering collide.py already decided ---------------------------------


def case_dep_records_equal_the_manifests_dep_intents(tmp: Path) -> None:
    """Carried through, field for field, in manifest order: nothing is
    re-derived from `order` and nothing is parsed out of `command`."""
    groups = [group("g1", ["b-1", "b-2", "b-3"],
                    [dep_intent("b-2", "b-1"), dep_intent("b-3", "b-1")]),
              group("g3", ["b-7", "b-8"], [dep_intent("b-7", "b-8")])]
    run = seed(new_run(tmp), [], groups)
    by_bead, findings = derived(run)
    expect(findings, [])
    deps = [r for records in by_bead.values() for r in records
            if r["kind"] == "dep"]
    expect([(r["from"], r["to"]) for r in deps],
           [("b-2", "b-1"), ("b-3", "b-1"), ("b-7", "b-8")])
    expect([r["why"] for r in deps], ["shared files: x"] * 3)
    for record in deps:
        expect(record["dep_type"], "blocks")
        expect(intent_records.validate(record), [])


def case_a_dep_intent_with_no_endpoints_is_a_finding(tmp: Path) -> None:
    """The shape a pre-Phase-4 manifest holds: reported and skipped, while
    every other group still derives."""
    stale = {"command": "bd dep add b-2 b-1", "why": "shared files: x"}
    groups = [group("g1", ["b-1", "b-2"], [stale]),
              group("g3", ["b-7", "b-8"], [dep_intent("b-7", "b-8")])]
    run = seed(new_run(tmp), [], groups)
    by_bead, findings = derived(run)
    expect(len(findings), 1)
    assert "g1" in findings[0], findings
    expect(sorted(by_bead), ["b-7"])


def case_a_dep_record_lives_in_its_from_beads_file(tmp: Path) -> None:
    run = seed(new_run(tmp), [], [group("g1", ["b-1", "b-2"],
                                        [dep_intent("b-2", "b-1")])])
    expect(cli(run)[0], 0)
    expect([r["key"] for r in intent_records.load(run, "b-2")],
           ["dep-b-2-on-b-1"])
    expect(intent_records.load(run, "b-1"), [])


# --- a rerun is a no-op on disk ----------------------------------------------


def case_a_rerun_keeps_worker_records_and_does_not_double_derived_ones(
    tmp: Path,
) -> None:
    run = new_run(tmp)
    folder = plan_folder(run)
    seed(run, planned_rows(run, "proj-a1", folder))
    intent_records.save(run, "proj-a1", [
        {"key": "phase-1", "kind": "create-task", "ref": "phase_1",
         "bead": "proj-a1", "title": "Phase 1",
         "slice": str(folder / "phase_1.md"), "master": str(folder / "plan.md")},
        {"key": "open-1", "kind": "open", "ref": "phase_1", "bead": "proj-a1"}])
    for _ in range(2):
        expect(cli(run)[0], 0)
    expect([r["kind"] for r in intent_records.load(run, "proj-a1")],
           ["create-task", "open", "flip-source"])


# --- the CLI -----------------------------------------------------------------


def case_the_json_report_tallies_every_kind(tmp: Path) -> None:
    run = new_run(tmp)
    folder = plan_folder(run)
    rows = planned_rows(run, "proj-a1", folder) + [
        settled_row(run, "proj-p9", "parked")]
    seed(run, rows, [group("g1", ["b-1", "b-2"], [dep_intent("b-2", "b-1")])])
    code, printed = cli(run, "--json")
    expect(code, 0)
    payload = json.loads(printed)
    expect(payload["kinds"], {"flip-source": 1, "investigation": 1, "dep": 1})
    expect(payload["records"], 3)
    expect(payload["beads"], 3)
    expect(payload["findings"], [])
    expect(len(intent_records.load_all(run)), 3)


def case_the_human_report_is_one_summary_line_plus_findings(tmp: Path) -> None:
    run = new_run(tmp)
    seed(run, [settled_row(run, "proj-f1", "")])
    code, printed = cli(run)
    expect(code, 1)
    lines = printed.strip().splitlines()
    expect(len(lines), 2)
    assert lines[0].startswith("derive: "), lines
    assert "0 record(s)" in lines[0], lines


def case_usage_and_an_unreadable_run_exit_two(tmp: Path) -> None:
    expect(derive_intents.main([]), 2)
    expect(derive_intents.main(["--run-dir"]), 2)
    expect(derive_intents.main(["--nope", "x"]), 2)
    expect(derive_intents.main(["--run-dir", str(tmp / "absent")]), 2)


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
