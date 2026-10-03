#!/usr/bin/env python3
"""Tests for tracker_intents.py — the order the `bd` calls go out in, the
notes they carry, the read-back after every write, and the roll-forward.

Every case runs against `RecordingRunner`, which captures the argv it would
have run. That is what lets ordering, notes formatting, absolute-path
enforcement and post-write verification be covered without touching a real
beads database: a test that mutates the real tracker is not a test, it is a
promote run with assertions attached.

Fixtures come from `test_promote.py`. Run with `python3 test_tracker_intents.py`.
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
import promote  # noqa: E402
import test_intent_records  # noqa: E402
import test_promote  # noqa: E402
import tracker_intents  # noqa: E402
from staged_run import ledger_row  # noqa: E402
from test_promote import (INVEST_NAME, PLAN_FOLDER, PROJECT, RecordingRunner,
                          codes, expect, moved_for, repo_root, seed_ledger,
                          staged)  # noqa: E402


def applied(run: Path, records=None, **kw):
    fake = kw.pop("runner", None) or RecordingRunner()
    intents = intent_records.load_all(run) if records is None else records
    return tracker_intents.apply_intents(intents, repo_root(run),
                                         runner=fake, **kw), fake


def mutating(fake) -> list:
    return [argv for argv, _ in fake.calls if argv[1] in ("create", "update", "dep")]


def promoted_investigation_intent(run: Path) -> list:
    """The run reduced to one investigation intent for `proj-p9`, promoted.

    Both investigation cases need the same thing: a ledger that gives `proj-p9`
    the staged artifact, then a real move so the intent carries a promoted path
    rather than a staged one.
    """
    (intent_records.store_dir(run) / "proj-a1.json").unlink()
    intent_records.save(run, "proj-p9", [
        {"key": "invest-p9", "kind": "investigation", "bead": "proj-p9",
         "investigation": str(run / "investigations" / INVEST_NAME)}])
    seed_ledger(run, [ledger_row(
        bead="proj-p9", wave=2, worker="invest-p9",
        dispatched="2026-08-28T10:04:00Z", returned="2026-08-28T10:05:00Z",
        artifact=run / "investigations" / INVEST_NAME, final="planned")])
    moved, _, _ = moved_for(run)
    return promote.remap(intent_records.load_all(run), moved)


# --- ordering ----------------------------------------------------------------


def case_epic_created_before_children(tmp: Path) -> None:
    result, fake = applied(staged(tmp))
    creates = [argv for argv in mutating(fake) if argv[1] == "create"]
    expect([argv[2] for argv in creates],
           ["Demo thing", "Phase 1: Demo slice", "Phase 2: Demo slice"])
    expect(result.findings, [])


def case_create_before_dep_add(tmp: Path) -> None:
    _, fake = applied(staged(tmp))
    calls = mutating(fake)
    dep = next(i for i, argv in enumerate(calls) if argv[1] == "dep")
    assert max(i for i, argv in enumerate(calls) if argv[1] == "create") < dep, calls


def case_source_flip_is_last(tmp: Path) -> None:
    _, fake = applied(staged(tmp))
    last = mutating(fake)[-1]
    expect(last[:3], ["bd", "update", "proj-a1"])
    assert "--notes" in last, last


# --- what the notes carry ----------------------------------------------------


def case_every_notes_carries_absolute_path(tmp: Path) -> None:
    _, fake = applied(staged(tmp))
    seen = 0
    for argv in mutating(fake):
        if "--notes" in argv:
            seen += 1
            first = argv[argv.index("--notes") + 1].splitlines()[0]
            assert first.split(": ", 1)[1].startswith("/"), argv
        if "--description" in argv:
            assert "/" not in argv[argv.index("--description") + 1], argv
    expect(seen, 4)


def case_notes_use_promoted_not_staged_paths(tmp: Path) -> None:
    run = staged(tmp)
    moved, _, _ = moved_for(run)
    result = tracker_intents.apply_intents(
        promote.remap(intent_records.load_all(run), moved),
        repo_root(run), runner=RecordingRunner())
    joined = " ".join(" ".join(argv) for argv in result.commands)
    assert str(run) not in joined, joined
    assert f"{tmp}/plans/{PROJECT}/todo/{PLAN_FOLDER}/plan.md" in joined, joined


def case_source_flip_keeps_existing_notes(tmp: Path) -> None:
    run = staged(tmp)
    fake = RecordingRunner(responses={"bd show proj-a1 --json": '[{"id": "proj-a1", '
                                      '"notes": "Investigation: /old.md\\nkeep me"}]'})
    _, fake = applied(run, runner=fake)
    notes = mutating(fake)[-1][-1]
    assert notes.startswith("Plan: /"), notes
    assert "keep me" in notes and "/old.md" not in notes, notes


def case_investigation_intent_writes_needs_plan(tmp: Path) -> None:
    """`investigate` Step 5d: an investigated bead stays needs-plan carrying
    the promoted artifact path — planning, not promote, is what opens it."""
    run = staged(tmp)
    result = tracker_intents.apply_intents(promoted_investigation_intent(run),
                                           repo_root(run), runner=RecordingRunner())
    expect(result.findings, [])
    argv = result.commands[0]
    expect(argv[:5], ["bd", "update", "proj-p9", "--status", "needs-plan"])
    assert argv[-1].startswith(f"Investigation: {tmp}/plans/{PROJECT}/"), argv[-1]


def case_investigation_intent_keeps_existing_notes(tmp: Path) -> None:
    """`bd update --notes` replaces, so an intent that does not carry the
    bead's existing notes forward destroys them — and a human's context on a
    bead is not recoverable."""
    run = staged(tmp)
    intents = promoted_investigation_intent(run)
    fake = RecordingRunner(responses={
        "bd show proj-p9 --json":
            '[{"id": "proj-p9", "notes": "Investigation: /old.md\\n'
            'asked Mike about the OPDS timeout"}]'})
    result = tracker_intents.apply_intents(intents, repo_root(run), runner=fake)
    expect(result.findings, [])
    notes = result.commands[0][-1]
    assert notes.startswith(f"Investigation: {tmp}/plans/{PROJECT}/"), notes
    assert "asked Mike about the OPDS timeout" in notes, notes
    assert "/old.md" not in notes, notes


def case_single_phase_plan_uses_the_plan_notes_form(tmp: Path) -> None:
    intent = {"key": "solo", "kind": "create-task", "ref": "solo",
              "title": "Solo", "plan": "/plans/p/todo/solo.md"}
    notes = tracker_intents.notes_for(intent)
    assert notes.startswith("Plan: /plans/p/todo/solo.md"), notes
    assert "Slice:" not in notes, notes


def case_unknown_intent_kind_is_a_usage_error(tmp: Path) -> None:
    try:
        tracker_intents.apply_intents([{"key": "x", "kind": "teleport"}], "/tmp",
                                      runner=RecordingRunner())
    except tracker_intents.Usage:
        return
    raise AssertionError("expected Usage")


# --- retiring a source bead the run's own epic replaced ----------------------


SUPERSEDE = {"key": "supersede-proj-a1", "kind": "supersede",
             "bead": "proj-a1", "by": "epic", "master": "/p/todo/f/plan.md"}


def supersedes(run: Path, bead: str = "proj-a1") -> list:
    """The staged run with `bead`'s flip traded for a supersede on its epic.

    No bead is ever both flipped open and closed, so the fixture makes the
    same swap `derive_intents` makes rather than stacking the two records.

    It writes through the store rather than appending to what `load_all`
    returned: `by` names a ref in the same file, and `load_all` is what
    qualifies both by their owner. A record appended afterwards carries a bare
    `epic` no qualified id map answers - which is the shape a fixture can hold
    and production cannot.
    """
    for path in sorted(intent_records.store_dir(run).glob("*.json")):
        owner = path.stem
        kept = [r for r in intent_records.load(run, owner)
                if r["kind"] != "flip-source"]
        if owner == bead:
            kept.append({**SUPERSEDE, "bead": bead,
                         "master": str(run / "todo" / PLAN_FOLDER / "plan.md")})
        intent_records.save(run, owner, kept)
    return intent_records.load_all(run)


def case_supersede_renders_a_closing_update_on_the_source_bead(tmp: Path) -> None:
    """The `update` / `--status` shape is the contract, not a style choice:
    `staged_run_checks.SOURCE_KINDS` is derived from this argv and
    `applied_states` recovers the status by indexing `--status` out of it."""
    call = tracker_intents.render(SUPERSEDE, {"epic": "proj-t1"}, {})
    expect(call.argv, ["bd", "update", "proj-a1", "--status", "closed",
                       "--notes", "{notes}"])
    expect(call.bead, "proj-a1")
    expect(call.path, "/p/todo/f/plan.md")


def case_supersede_is_applied_after_everything_that_replaces_it(tmp: Path) -> None:
    """A source bead is retired only once everything replacing it exists and is
    workable — so every `create-*`, `dep` and `open` goes out first."""
    run = staged(tmp)
    result, fake = applied(run, records=supersedes(run))
    expect(result.findings, [])
    order = mutating(fake)
    expect(order[-1][:5], ["bd", "update", "proj-a1", "--status", "closed"])
    opens = [i for i, argv in enumerate(order) if argv[-1] == "open"]
    deps = [i for i, argv in enumerate(order) if argv[1] == "dep"]
    assert opens and max(opens) < len(order) - 1, order
    assert deps and max(deps) < min(opens), order


def case_supersede_waits_for_the_epic_ref(tmp: Path) -> None:
    """`NEEDS["supersede"] = ("by",)` is what stops a bead being closed when the
    epic meant to replace it never got created."""
    result = tracker_intents.apply_intents([SUPERSEDE], str(tmp),
                                           runner=RecordingRunner())
    expect(result.commands, [])
    hits = [f for f in result.findings if f.code == "promote-intent-incomplete"]
    expect([f.subject for f in hits], ["supersede-proj-a1"])
    assert "epic" in hits[0].detail, hits


def case_supersede_keeps_the_beads_human_notes(tmp: Path) -> None:
    """Retiring a bead must destroy no context: the marker lines are replaced,
    the record's own `Master:` block leads, and everything a human wrote stays.

    The epic is named by its real bead id, resolved through the created-ids map
    — a note pointing at the symbolic ref `epic` sends its reader nowhere.
    """
    run = staged(tmp)
    master = str(run / "todo" / PLAN_FOLDER / "plan.md")
    fake = RecordingRunner(responses={
        "bd show proj-a1 --json": json.dumps(
            [{"id": "proj-a1", "status": "needs-plan",
              "notes": "Investigation: /old.md\nasked Mike about the timeout"}])})
    result, fake = applied(run, records=supersedes(run), runner=fake)
    expect(result.findings, [])
    notes = mutating(fake)[-1][-1]
    assert notes.startswith(f"Master: {master}"), notes
    assert "asked Mike about the timeout" in notes, notes
    assert "/old.md" not in notes, notes
    assert "Superseded by proj-t01" in notes, notes


# --- correcting a title, retiring a duplicate --------------------------------


RETITLE = {"key": "retitle-proj-a1", "kind": "retitle", "bead": "proj-a1",
           "title": "the corrected title"}
CLOSE = {"key": "close-proj-d3", "kind": "close", "bead": "proj-d3",
         "investigation": "/i/proj_invest_thing_goes_wrong.md"}


def closes(run: Path) -> list:
    """The staged run, its supersede, and a duplicate retired on top of both."""
    return supersedes(run) + [
        {**CLOSE, "investigation": str(run / "investigations" / INVEST_NAME)}]


def case_retitle_renders_a_title_update(tmp: Path) -> None:
    """A title is the whole write, and `Call.field` is what says so: verifying
    a retitle against notes would fail a correct write or pass a missing one."""
    call = tracker_intents.render(RETITLE, {}, {})
    expect(call.argv, ["bd", "update", "proj-a1", "--title",
                       "the corrected title"])
    expect(call.bead, "proj-a1")
    expect(call.path, "the corrected title")
    expect(call.field, "title")


def case_close_renders_a_closing_update_naming_its_investigation(tmp: Path) -> None:
    call = tracker_intents.render(CLOSE, {}, {})
    expect(call.argv, ["bd", "update", "proj-d3", "--status", "closed",
                       "--notes", "{notes}"])
    expect(call.bead, "proj-d3")
    expect(call.path, "/i/proj_invest_thing_goes_wrong.md")
    expect(call.field, "notes")


def case_close_is_applied_last(tmp: Path) -> None:
    """A retirement is the final act on a bead, so a failed pass leaves it
    un-retired rather than retired with its siblings unapplied — `supersede`
    included, which is why the order is asserted against it."""
    run = staged(tmp)
    result, fake = applied(run, records=closes(run))
    expect(result.findings, [])
    order = mutating(fake)
    expect(order[-1][:5], ["bd", "update", "proj-d3", "--status", "closed"])
    expect(order[-2][:5], ["bd", "update", "proj-a1", "--status", "closed"])


def case_retitle_is_verified_against_the_title_not_the_notes(tmp: Path) -> None:
    """`_verify` reads back the field the record names. A bead whose title did
    not change is reported, and its notes are neither read nor rewritten."""
    for title, subjects in (("the corrected title", []),
                            ("the old title", ["retitle-proj-a1"])):
        fake = RecordingRunner(responses={"bd show proj-a1 --json": json.dumps(
            [{"id": "proj-a1", "title": title, "notes": "keep me"}])})
        result = tracker_intents.apply_intents([RETITLE], str(tmp), runner=fake)
        expect([f.subject for f in result.findings], subjects)
        assert not [a for a, _ in fake.calls if "--notes" in a], fake.calls


def case_close_keeps_the_beads_human_notes(tmp: Path) -> None:
    """Retiring a duplicate destroys no context: the marker lines are replaced,
    the record's own `Investigation:` block leads, the human's lines stay."""
    run = staged(tmp)
    fake = RecordingRunner(responses={"bd show proj-d3 --json": json.dumps(
        [{"id": "proj-d3", "status": "needs-plan",
          "notes": "Investigation: /old.md\nasked Mike about the timeout"}])})
    result, fake = applied(run, records=closes(run), runner=fake)
    expect(result.findings, [])
    notes = mutating(fake)[-1][-1]
    assert notes.startswith(f"Investigation: {run}/investigations/"), notes
    assert "asked Mike about the timeout" in notes, notes
    assert "/old.md" not in notes, notes
    assert "Ruled a duplicate" in notes, notes


# --- the absolute-path guard -------------------------------------------------


PATH_KINDS = ("create-epic", "create-task", "investigation", "flip-source",
              "supersede", "close")


def case_relative_paths_names_every_offending_field_and_nothing_else(tmp: Path) -> None:
    intent = {"key": "phase-1", "kind": "create-task", "ref": "phase_1",
              "title": "Phase 1", "slice": "todo/f/phase_1.md",
              "master": "/plans/p/todo/f/plan.md"}
    expect(tracker_intents.relative_paths(intent),
           [("slice", "todo/f/phase_1.md")])


def case_render_refuses_a_relative_path_per_kind(tmp: Path) -> None:
    """`render` is the last refusal before a real `bd` write, and the claim
    `tracker_intents.py`'s docstring already makes."""
    for kind in PATH_KINDS:
        for field in tracker_intents.PATH_KEYS:
            intent = test_intent_records.record(kind)
            if not intent.get(field):
                continue
            intent[field] = test_intent_records.RELATIVE
            try:
                tracker_intents.render(intent, {"phase_1": "proj-t1"}, {})
            except tracker_intents.Usage as err:
                assert field in str(err), err
                assert "--notes path is not absolute" in str(err), err
            else:
                raise AssertionError(f"{kind}.{field} rendered")


def case_render_emits_the_argv_unchanged_for_absolute_paths(tmp: Path) -> None:
    """The guard is a refusal, not a rewrite: an absolute record renders the
    same argv and records the same notes path it did before this phase."""
    call = tracker_intents.render(test_intent_records.record("create-epic"), {}, {})
    expect(call.argv[:7], ["bd", "create", "Demo", "-t", "task", "-p", "2"])
    expect(call.argv[-3], "--notes")
    expect(call.argv[-1], "--json")
    expect(call.path, "/p/plan.md")
    flip = tracker_intents.render(test_intent_records.record("flip-source"), {}, {})
    expect(flip.argv[:5], ["bd", "update", "proj-a1", "--status", "open"])
    expect(flip.path, "/p/plan.md")


# --- verification ------------------------------------------------------------


def case_show_verification_runs_after_each_write(tmp: Path) -> None:
    # Both the note-preserving pre-read and the post-write read-back are
    # `bd show --json` now, so they cannot be told apart by argv. Position is
    # the discriminator that matters anyway: every write must be followed by a
    # read-back, whatever else surrounds it.
    _, fake = applied(staged(tmp))
    kinds = [argv[1] for argv, _ in fake.calls]
    for index, kind in enumerate(kinds):
        if kind in ("create", "update", "dep"):
            expect(kinds[index + 1], "show")


def case_notes_missing_after_write_fails(tmp: Path) -> None:
    result, _ = applied(staged(tmp), runner=RecordingRunner(notes="empty"))
    assert "promote-notes-unverified" in codes(result.findings), result.findings


def case_resumed_open_verifies_the_notes_path(tmp: Path) -> None:
    """A resumed `create-*` must repopulate the path its notes recorded, or the
    later `open` renders with no path and the read-back silently does not run —
    on exactly the branch where tracker state is least certain.

    The `completed` key is the qualified one the promote log carries, because
    `apply_intents` reads that log back through the same names
    `intent_records.load_all` produced.
    """
    result, _ = applied(staged(tmp),
                        completed={"proj-a1/phase-1": "proj-t50"},
                        runner=RecordingRunner(notes="empty"))
    subjects = [f.subject for f in result.findings
                if f.code == "promote-notes-unverified"]
    assert "proj-a1/open-1" in subjects, result.findings


def case_resumed_open_passes_when_notes_carry_the_path(tmp: Path) -> None:
    run = staged(tmp)
    slice_path = f"{run}/todo/{PLAN_FOLDER}/phase_1_demo_slice.md"
    fake = RecordingRunner(responses={
        "bd show proj-t50 --json":
            json.dumps([{"id": "proj-t50", "notes": f"Slice: {slice_path}"}])})
    result, _ = applied(run, completed={"phase-1": "proj-t50"}, runner=fake)
    expect(result.findings, [])


def case_verification_reads_json_never_the_wrapped_human_form(tmp: Path) -> None:
    """`skills-p1j`: promote never verified a note, and never promoted.

    `bd show` renders notes into a padded column and breaks mid-token, so an
    absolute path comes back split across lines. The old check substring-matched
    the rendered form, which no real path can satisfy — every promote emitted
    `promote-notes-unverified`, exited 1, and left the run staged. Two halves
    are pinned here: the read-back asks for `--json`, and the human form really
    does break the path, so a fake that stops wrapping fails this case rather
    than quietly restoring the blind spot.
    """
    _, fake = applied(staged(tmp))
    shows = [argv for argv, _ in fake.calls if argv[1] == "show"]
    assert shows, "no read-back ran at all"
    for argv in shows:
        assert "--json" in argv, argv

    long_path = "/Users/demo/projects/project_plans/skills/todo/" \
                "skills_epic_triage_e2e_testbed/phase_3_qc_promote_lifecycle.md"
    rendered = test_promote._wrapped(long_path)
    assert long_path not in rendered, "the human form no longer wraps"
    assert "\n" in rendered.rstrip("\n"), rendered


def case_dep_needs_no_notes_path(tmp: Path) -> None:
    """`dep` is the one kind that legitimately writes no note, so the missing
    -path hard failure must leave it alone."""
    result, fake = applied(staged(tmp))
    expect(result.findings, [])
    calls = [argv for argv, _ in fake.calls]
    dep = next(i for i, argv in enumerate(calls) if argv[1] == "dep")
    expect(calls[dep + 1][:2], ["bd", "show"])


def case_a_dep_between_pre_existing_beads_applies(tmp: Path) -> None:
    """A ref absent from the created-ids map is already a real bead id. Every
    dep `collide.py` derives joins two beads that existed before the run, so
    without this they report `promote-intent-incomplete` forever."""
    intent = {"key": "dep-a-on-b", "kind": "dep", "bead": "proj-a1",
              "from": "proj-a1", "to": "proj-p9", "dep_type": "blocks"}
    result = tracker_intents.apply_intents([intent], str(tmp),
                                           runner=RecordingRunner())
    expect(result.findings, [])
    expect(result.commands,
           [["bd", "dep", "add", "proj-a1", "proj-p9", "-t", "blocks"]])


def case_a_dep_naming_a_created_ref_still_waits_for_it(tmp: Path) -> None:
    """The reason `_needs` takes the ref set rather than dropping the check:
    when the `create-task` producing `phase_1` fails, the dep on it must be
    reported, never emitted against the literal ref string."""
    fake = RecordingRunner(fail_on={"bd create Phase 1: Demo slice"})
    result, fake = applied(staged(tmp), runner=fake)
    assert "promote-intent-incomplete" in codes(result.findings), result.findings
    joined = " ".join(" ".join(argv) for argv in result.commands)
    assert "dep add phase_1" not in joined, joined
    assert "dep add phase_2" not in joined, joined



def case_a_create_task_parent_outside_the_run_is_reported(tmp: Path) -> None:
    """Only a `dep` endpoint may name a bead from outside this run.

    `NEEDS` gives `create-task` its `parent`, and the parent is always produced
    by one of this run's own `create-*` intents. When the ref filter was applied
    to every kind, an unresolvable parent stopped being reported and reached
    `_create`'s `ids[...]` subscript as an uncaught `KeyError` — which escapes
    `apply_intents`, skips the promote log, and so re-issues every `bd create`
    that already succeeded on the next rerun.
    """
    intents = [
        {"key": "epic", "kind": "create-epic", "ref": "epic", "type": "epic",
         "title": "Demo thing", "master": str(tmp / "plan.md")},
        {"key": "phase-1", "kind": "create-task", "ref": "phase_1",
         "parent": "proj-epic-legacy", "title": "Phase 1: Demo slice",
         "slice": str(tmp / "phase_1.md"), "master": str(tmp / "plan.md")},
    ]
    result = tracker_intents.apply_intents(intents, str(tmp),
                                           runner=RecordingRunner())
    keys = [f.subject for f in result.findings
            if f.code == "promote-intent-incomplete"]
    expect(keys, ["phase-1"])
    joined = " ".join(" ".join(argv) for argv in result.commands)
    assert "proj-epic-legacy" not in joined, joined
    assert "Phase 1: Demo slice" not in joined, joined


def case_two_epics_get_two_parents(tmp: Path) -> None:
    """The live failure this pins: one promote, two epic groups, five phases.

    Each planning worker names its own epic `epic` in its own bead's file, and
    `apply_intents` resolved refs in one flat namespace - so the second
    `bd create` overwrote the first's id, every phase task was created under
    the epic that happened to be created last, and the audiobook epic came out
    childless. `intent_records.load_all` qualifies each file's names, and this
    case runs through it rather than around it: records built by hand would
    prove the resolver correct on input the store never produces.
    """
    run = staged(tmp)
    for path in intent_records.store_dir(run).glob("*.json"):
        path.unlink()
    for bead, title in (("proj-a1", "First"), ("proj-p9", "Second")):
        intent_records.save(run, bead, [
            {"key": "epic", "kind": "create-epic", "ref": "epic",
             "type": "epic", "title": f"{title} epic",
             "master": str(tmp / bead / "plan.md")},
            {"key": "phase-1", "kind": "create-task", "ref": "phase-1",
             "parent": "epic", "title": f"Phase 1: {title}",
             "slice": str(tmp / bead / "phase_1.md"),
             "master": str(tmp / bead / "plan.md")}])
    result, fake = applied(run)
    expect([f for f in result.findings if f.severity == "error"], [])
    epics = [argv for argv in result.commands
             if argv[:2] == ["bd", "create"]
             and argv[argv.index("-t") + 1] == "epic"]
    expect(len(epics), 2)
    parents = [argv[argv.index("--parent") + 1] for argv in result.commands
               if "--parent" in argv]
    expect(len(parents), 2)
    assert parents[0] != parents[1], parents
    assert len(set(result.applied)) == 4, result.applied


def case_a_relative_path_reached_at_apply_time_is_reported(tmp: Path) -> None:
    """`render`'s refusal must not escape the loop either, for the reason the
    case above gives: an exception here skips the promote log and re-issues
    every `bd create` that already succeeded on the next rerun.

    `promote.remap` is what produces this shape past the pre-flight, which
    validated the store before the move: a relative `--plans-dir` makes
    `target_for` build a relative promoted path, and `stale_intents` passes it
    because it no longer names the run directory. The `dep` that applied before
    it stays applied.
    """
    intents = [
        {"key": "dep-a-on-b", "kind": "dep", "bead": "proj-a1",
         "from": "proj-a1", "to": "proj-p9", "dep_type": "blocks"},
        {"key": "flip-a1", "kind": "flip-source", "bead": "proj-a1",
         "plan": "plans/proj/todo/skills_epic_demo_thing/plan.md"},
    ]
    result = tracker_intents.apply_intents(intents, str(tmp),
                                           runner=RecordingRunner())
    hits = [f for f in result.findings
            if f.code == "promote-intent-incomplete"]
    expect([f.subject for f in hits], ["flip-a1"])
    assert "path is not absolute" in hits[0].detail, hits
    expect(result.commands,
           [["bd", "dep", "add", "proj-a1", "proj-p9", "-t", "blocks"]])

def case_bd_runs_from_repo_root(tmp: Path) -> None:
    _, fake = applied(staged(tmp))
    expect({cwd for _, cwd in fake.calls}, {str(tmp / PROJECT)})


# --- roll forward, never compensate -----------------------------------------


def case_failed_child_create_reports_incomplete_set(tmp: Path) -> None:
    fake = RecordingRunner(fail_on={"bd create Phase 2: Demo slice"})
    result, fake = applied(staged(tmp), runner=fake)
    assert ("proj-a1/epic" in result.ids
            and "proj-a1/phase_2" not in result.ids), result.ids
    keys = [f.subject for f in result.findings
            if f.code == "promote-intent-incomplete"]
    assert "proj-a1/phase-2" in keys, keys
    assert {"proj-a1/dep-2-on-1", "proj-a1/open-2"} <= set(keys), keys
    assert not [argv for argv in mutating(fake) if "delete" in argv], fake.calls
    assert result.applied["proj-a1/epic"].startswith("proj-t"), result.applied


def case_rerun_skips_completed_steps(tmp: Path) -> None:
    result, fake = applied(staged(tmp),
                           completed={"proj-a1/epic": "proj-t99"})
    creates = [argv for argv in mutating(fake) if argv[1] == "create"]
    expect([argv[2] for argv in creates],
           ["Phase 1: Demo slice", "Phase 2: Demo slice"])
    assert "--parent" in creates[0] and "proj-t99" in creates[0], creates[0]
    expect(result.applied["proj-a1/epic"], "proj-t99")


def case_dry_run_makes_no_runner_calls(tmp: Path) -> None:
    result, fake = applied(staged(tmp), dry_run=True)
    expect(fake.calls, [])
    joined = " ".join(" ".join(argv) for argv in result.commands)
    assert "${proj-a1/epic}" in joined, joined
    expect(result.findings, [])


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
