#!/usr/bin/env python3
"""Tests for intent_records.py — the schema `tracker_intents` implies, and the
per-bead store the records live in.

The load-bearing cases are the negative ones: a malformed record is *reported*
and never raised on, because the validator written to reject a malformed
ruling was the thing that crashed on one. An unreadable store file is the one
exception and it raises — returning `[]` there would report an empty store
where there is an unreadable one.

Run with `python3 test_intent_records.py` (no pytest dependency).
"""

from __future__ import annotations

import json
import sys
import tempfile
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import intent_records  # noqa: E402
import tracker_intents  # noqa: E402


def expect(got, want) -> None:
    assert got == want, f"got {got!r}, want {want!r}"


def record(kind: str) -> dict:
    """One complete record per kind, carrying every required key and nothing
    a `bd` call does not consume."""
    fields = {
        "create-epic": {"ref": "epic", "title": "Demo", "master": "/p/plan.md"},
        "create-task": {"ref": "phase_1", "title": "Phase 1",
                        "slice": "/p/phase_1.md", "master": "/p/plan.md"},
        "open": {"ref": "phase_1"},
        "investigation": {"bead": "proj-a1", "investigation": "/i/a1.md"},
        "flip-source": {"bead": "proj-a1", "plan": "/p/plan.md"},
        "dep": {"from": "proj-a1", "to": "proj-p9"},
        "supersede": {"bead": "proj-a1", "by": "epic", "master": "/p/plan.md"},
        "retitle": {"bead": "proj-a1", "title": "the corrected title"},
        "close": {"bead": "proj-d3", "investigation": "/i/d3.md"},
    }
    return {"key": f"{kind}-1", "kind": kind, **fields[kind]}


def required(kind: str) -> tuple:
    return intent_records.COMMON + intent_records.REQUIRED[kind]


RELATIVE = "todo/skills_fix_epic_child_routing_skip.md"


def path_fields(kind: str) -> tuple:
    """The `PATH_KEYS` fields this kind's complete record actually carries."""
    return tuple(k for k in tracker_intents.PATH_KEYS if record(kind).get(k))


# --- the schema --------------------------------------------------------------


def case_every_kind_validates_with_its_required_fields(tmp: Path) -> None:
    for kind in intent_records.KINDS:
        expect(intent_records.validate(record(kind)), [])


def case_each_missing_required_field_is_one_finding_naming_it(tmp: Path) -> None:
    for kind in intent_records.KINDS:
        for field in required(kind):
            broken = {k: v for k, v in record(kind).items() if k != field}
            findings = intent_records.validate(broken)
            expect(len(findings), 1)
            assert field in findings[0], (field, findings)


def case_a_create_task_needs_slice_plus_master_or_plan(tmp: Path) -> None:
    task = record("create-task")
    del task["master"]
    findings = intent_records.validate(task)
    expect(len(findings), 1)
    assert "slice" in findings[0] and "plan" in findings[0], findings
    del task["slice"]
    task["plan"] = "/p/solo.md"
    expect(intent_records.validate(task), [])


def case_merge_keeps_a_record_the_new_batch_does_not_name(tmp: Path) -> None:
    """Why `merge` exists beside `save`: an investigation worker's `retitle`
    and the planning worker's epic records land in the same bead's file, one
    wave apart, and `save` would silently drop whichever arrived first."""
    intent_records.save(tmp, "proj-a1", [record("retitle")])
    intent_records.merge(tmp, "proj-a1", [record("create-epic")])
    kinds = sorted(r["kind"] for r in intent_records.load(tmp, "proj-a1"))
    expect(kinds, ["create-epic", "retitle"])


def case_merge_replaces_a_record_carrying_the_same_key(tmp: Path) -> None:
    """A second thought about one record is an update, not a duplicate: the
    key is the identity, exactly as it is for `derive_intents._merged`."""
    intent_records.save(tmp, "proj-a1", [record("retitle")])
    corrected = dict(record("retitle"), title="the second correction")
    intent_records.merge(tmp, "proj-a1", [corrected])
    expect(intent_records.load(tmp, "proj-a1"), [corrected])


def case_merge_stores_a_non_object_batch_member_instead_of_raising(
    tmp: Path,
) -> None:
    """The batch is a worker's returned JSON array, so a bare string in it is
    a shape this store already has a home for: `save` keeps it and the promote
    gate names it `promote-intent-invalid`. Raising here would crash the
    orchestrator mid-wave instead."""
    intent_records.save(tmp, "proj-a1", [record("retitle")])
    intent_records.merge(tmp, "proj-a1", ["not an object"])
    expect(intent_records.load(tmp, "proj-a1"),
           [record("retitle"), "not an object"])


def case_an_unknown_kind_is_a_finding_not_an_exception(tmp: Path) -> None:
    findings = intent_records.validate({"key": "x", "kind": "teleport"})
    expect(len(findings), 1)
    assert "teleport" in findings[0], findings


def case_a_record_with_no_kind_names_the_missing_key(tmp: Path) -> None:
    """Regression against the `plan_coverage` class of defect — a validator
    that raises on the shape it exists to reject."""
    findings = intent_records.validate({"key": "x"})
    expect(len(findings), 1)
    assert "kind" in findings[0], findings


def case_a_non_object_record_is_a_finding(tmp: Path) -> None:
    findings = intent_records.validate("flip-source proj-a1")
    expect(len(findings), 1)
    assert "str" in findings[0], findings


def case_derived_and_worker_kinds_partition_the_vocabulary(tmp: Path) -> None:
    """A seventh kind added to `tracker_intents.KIND_ORDER` fails here instead
    of silently belonging to no writer."""
    derived = set(intent_records.DERIVED_KINDS)
    worker = set(intent_records.WORKER_KINDS)
    expect(derived | worker, set(tracker_intents.KIND_ORDER))
    expect(derived & worker, set())
    expect(set(intent_records.REQUIRED), set(intent_records.KINDS))


def case_supersede_requires_bead_by_and_master(tmp: Path) -> None:
    """`bead` is the `bd` target, `by` is the epic ref `tracker_intents._needs`
    blocks on until the run creates it, and `master` is the path its notes
    carry. Nothing else is required, because no `bd` call reads anything else.
    """
    expect(intent_records.REQUIRED["supersede"], ("bead", "by", "master"))
    expect(intent_records.validate(record("supersede")), [])
    for field in ("bead", "by", "master"):
        broken = {k: v for k, v in record("supersede").items() if k != field}
        findings = intent_records.validate(broken)
        expect(len(findings), 1)
        assert field in findings[0], (field, findings)


def case_retitle_requires_bead_and_title(tmp: Path) -> None:
    """`bead` is the `bd` target and `title` is the whole write. `title` is
    deliberately not a `PATH_KEYS` field: it is a string a human reads, and the
    absolute-path rule would otherwise demand a path of a title."""
    expect(intent_records.REQUIRED["retitle"], ("bead", "title"))
    assert "title" not in tracker_intents.PATH_KEYS, tracker_intents.PATH_KEYS
    expect(intent_records.validate(record("retitle")), [])
    for field in ("bead", "title"):
        broken = {k: v for k, v in record("retitle").items() if k != field}
        findings = intent_records.validate(broken)
        expect(len(findings), 1)
        assert field in findings[0], (field, findings)


def case_close_requires_bead_and_investigation(tmp: Path) -> None:
    """`investigation` is already in `PATH_KEYS`, so the absolute-path rule
    reaches this kind with no new code."""
    expect(intent_records.REQUIRED["close"], ("bead", "investigation"))
    expect(intent_records.validate(record("close")), [])
    for field in ("bead", "investigation"):
        broken = {k: v for k, v in record("close").items() if k != field}
        findings = intent_records.validate(broken)
        expect(len(findings), 1)
        assert field in findings[0], (field, findings)
    expect(intent_records.validate({**record("close"), "investigation": RELATIVE}),
           [f"close-1: investigation --notes path is not absolute: {RELATIVE}"])


def case_a_relative_path_field_is_one_finding_naming_key_and_field(tmp: Path) -> None:
    """The defect: `validate` checked kind membership and field presence only,
    so a relative plan path passed with zero findings."""
    # Pinned, so a fixture that stopped carrying a path field cannot turn the
    # loop below into a case that passes by iterating nothing: create-epic.master,
    # create-task.slice, create-task.master, investigation.investigation,
    # flip-source.plan, supersede.master, close.investigation.
    expect(sum(len(path_fields(kind)) for kind in intent_records.KINDS), 7)
    for kind in intent_records.KINDS:
        for field in path_fields(kind):
            findings = intent_records.validate({**record(kind), field: RELATIVE})
            expect(len(findings), 1)
            assert f"{kind}-1" in findings[0], findings
            assert field in findings[0], findings
            assert "--notes path is not absolute" in findings[0], findings
            assert RELATIVE in findings[0], findings


def case_an_absolute_path_inside_the_run_directory_validates(tmp: Path) -> None:
    """Shape, never location. Before promote every artifact path names the run
    directory; `promote.stale_intents` is what rejects one after promote, and a
    check that demanded the promoted home would fire on every correct intent."""
    staged = str(tmp / "runs" / "2026-09-02_3f7d" / "todo" / "plan.md")
    for kind in intent_records.KINDS:
        for field in path_fields(kind):
            expect(intent_records.validate({**record(kind), field: staged}), [])


def case_a_kind_carrying_no_path_gets_no_path_finding(tmp: Path) -> None:
    """`dep` carries no path at all, and `open` carries its path through
    `apply_intents`' notes map rather than in the record — so the rule must not
    invent a finding for either."""
    for kind in ("dep", "open"):
        expect(path_fields(kind), ())
        expect(tracker_intents.relative_paths(record(kind)), [])
        expect(intent_records.validate(record(kind)), [])


# --- the store ---------------------------------------------------------------


def case_save_then_load_all_round_trips(tmp: Path) -> None:
    """`load_all` returns every record carrying the bead its file is named
    after, and every name it defines qualified by that bead.

    The `load` call pins the raw reader unchanged; `load_all`'s docstring says
    why attaching there would write a second copy of the owner to disk, and why
    the qualifying belongs to the reader every consumer shares rather than to
    the one that resolves refs.
    """
    intent_records.save(tmp, "proj-a1", [record("flip-source"), record("dep")])
    intent_records.save(tmp, "proj-p9", [record("open")])
    expect(intent_records.load(tmp, "proj-p9"), [record("open")])
    expect(intent_records.load_all(tmp),
           [{**record("flip-source"), "key": "proj-a1/flip-source-1"},
            {"bead": "proj-a1", **record("dep"), "key": "proj-a1/dep-1"},
            {"bead": "proj-p9", **record("open"),
             "key": "proj-p9/open-1", "ref": "proj-p9/phase_1"}])


def case_a_records_own_bead_wins_over_its_filename(tmp: Path) -> None:
    """Attaching is a default, never an override. An `investigation` record's
    `bead` is the `bd` target it names, and the file it happens to sit in must
    not retarget it — while its neighbour that names no owner still gets one.
    """
    intent_records.save(tmp, "proj-p9", [record("investigation"), record("dep")])
    expect(intent_records.load_all(tmp),
           [{**record("investigation"), "key": "proj-p9/investigation-1"},
            {"bead": "proj-p9", **record("dep"), "key": "proj-p9/dep-1"}])


def case_two_beads_defining_one_ref_name_stay_separate(tmp: Path) -> None:
    """The defect, at the reader: `ref` and `key` are names inside one bead's
    file, and `apply_intents` resolved them in one flat namespace.

    Both planning workers wrote `ref: "epic"` for their own epic, because
    neither knows the other exists - `promoting.md` says the phase titles and
    parent links are theirs and the owner is the filename. The second
    `bd create` then overwrote `ids["epic"]`, so all five phase tasks of a live
    promote were created under one epic, the other epic came out childless, and
    a `supersede` note retired its source bead pointing at the wrong one.
    """
    intent_records.save(tmp, "proj-a1", [
        {"key": "epic", "kind": "create-epic", "ref": "epic",
         "title": "First", "master": "/p/a1/plan.md"},
        {"key": "phase-1", "kind": "create-task", "ref": "phase-1",
         "parent": "epic", "title": "Phase 1: First",
         "slice": "/p/a1/phase_1.md", "master": "/p/a1/plan.md"}])
    intent_records.save(tmp, "proj-p9", [
        {"key": "epic", "kind": "create-epic", "ref": "epic",
         "title": "Second", "master": "/p/p9/plan.md"}])
    loaded = intent_records.load_all(tmp)
    expect([r["key"] for r in loaded],
           ["proj-a1/epic", "proj-a1/phase-1", "proj-p9/epic"])
    expect([r["ref"] for r in loaded],
           ["proj-a1/epic", "proj-a1/phase-1", "proj-p9/epic"])
    expect(loaded[1]["parent"], "proj-a1/epic")


def case_a_dep_endpoint_outside_the_file_is_left_alone(tmp: Path) -> None:
    """Only a name the file itself defines is qualified. `collide.py` derives
    deps between beads that existed before the run, and prefixing one of those
    would send `bd dep add` a bead id no tracker has."""
    intent_records.save(tmp, "proj-a1", [
        {"key": "phase-1", "kind": "create-task", "ref": "phase-1",
         "parent": "proj-epic-legacy", "title": "Phase 1",
         "slice": "/p/phase_1.md", "master": "/p/plan.md"},
        {"key": "dep-1", "kind": "dep", "from": "phase-1",
         "to": "proj-p9", "dep_type": "blocks"}])
    loaded = intent_records.load_all(tmp)
    expect(loaded[0]["parent"], "proj-epic-legacy")
    expect((loaded[1]["from"], loaded[1]["to"]), ("proj-a1/phase-1", "proj-p9"))


def case_qualifying_an_already_qualified_name_changes_nothing(tmp: Path) -> None:
    """`derive_intents` reads the store through `load_all` and writes what it
    read back — a `supersede` under the member it retires, naming an epic that
    belongs to the planner's file. So the reader meets its own output on the
    next run, and a second prefix would bury the owner the name already
    carries and resolve to nothing.
    """
    intent_records.save(tmp, "proj-a1", [
        {"key": "epic", "kind": "create-epic", "ref": "epic",
         "title": "Demo", "master": "/p/plan.md"}])
    intent_records.save(tmp, "proj-m2", [
        {"key": "supersede-proj-m2", "kind": "supersede", "bead": "proj-m2",
         "by": "proj-a1/epic", "master": "/p/plan.md"}])
    once = intent_records.load_all(tmp)
    expect([r.get("by") for r in once if r["kind"] == "supersede"],
           ["proj-a1/epic"])
    for record in once:
        intent_records.save(tmp, record["bead"], [record])
    expect(intent_records.load_all(tmp), once)


def case_a_non_object_member_still_reaches_validate(tmp: Path) -> None:
    """The rule `staged_run_checks.invalid_intents` depends on: a member that
    is not an object comes back unchanged, so `validate` names it instead of
    the reader raising on it while attaching an owner."""
    intent_records.save(tmp, "proj-a1", ["flip-source proj-a1"])
    expect(intent_records.load_all(tmp), ["flip-source proj-a1"])


def case_load_all_on_a_run_with_no_store_is_empty(tmp: Path) -> None:
    """A run that staged no intent is a real state — a `--dry-run` is one."""
    expect(intent_records.load_all(tmp), [])
    expect(intent_records.load(tmp, "proj-a1"), [])


def case_save_replaces_that_beads_file_and_leaves_the_others(tmp: Path) -> None:
    intent_records.save(tmp, "proj-a1", [record("flip-source")])
    intent_records.save(tmp, "proj-p9", [record("investigation")])
    intent_records.save(tmp, "proj-a1", [record("dep")])
    expect(intent_records.load(tmp, "proj-a1"), [record("dep")])
    expect(intent_records.load(tmp, "proj-p9"), [record("investigation")])
    expect(sorted(p.name for p in intent_records.store_dir(tmp).glob("*.json")),
           ["proj-a1.json", "proj-p9.json"])


def case_an_unreadable_store_file_raises(tmp: Path) -> None:
    store = intent_records.store_dir(tmp)
    store.mkdir(parents=True, exist_ok=True)
    for name, text in (("proj-a1.json", json.dumps({})),
                       ("proj-p9.json", '[{"key": "x"')):
        (store / name).write_text(text, encoding="utf-8")
        bead = name.removesuffix(".json")
        try:
            intent_records.load(tmp, bead)
        except intent_records.IntentStoreError as err:
            assert bead in str(err), err
        else:
            raise AssertionError(f"{name} loaded without raising")


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
