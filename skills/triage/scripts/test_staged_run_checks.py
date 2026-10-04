#!/usr/bin/env python3
"""Tests for staged_run_checks.py — the promote preflight, one case per rule.

The two directions matter equally. A clean staged run must pass: a preflight
that refuses a healthy run is as broken as one that waves a bad one through,
and `case_clean_staged_run_passes_preflight` is the anchor that catches any
new check firing on valid input. A seeded defect must stop the run — and the
changed-bead case proves the stop is per bead, not per run.

Fixtures come from `test_promote.py`. Run with `python3 test_staged_run_checks.py`.

The ledger-row lane went to `test_staged_run_ledger_checks.py`: its cases judge
one row's own shape against `references/ledger.md`, and its artifact cases call
`ledger_artifacts` directly rather than through `preflight`. The intent store's
own records went to `test_staged_run_store_checks.py`: a malformed record has to
come back as a finding rather than a traceback, and the readers that used to
crash on one sit downstream of the check that names it.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import dedup  # noqa: E402
import intent_records  # noqa: E402
import manifest as manifest_io  # noqa: E402
import staged_run  # noqa: E402
import staged_run_checks  # noqa: E402
import tracker_intents  # noqa: E402
from test_promote import (INVEST_NAME, PLAN_FOLDER, PROJECT,  # noqa: E402
                          RecordingRunner, codes, expect, plans_dir, repo_root,
                          staged)


def check(run: Path, runner=None, **kw):
    """The preflight against a fake tracker. Pass `runner` when the case also
    asserts on the argv the fake recorded; otherwise `**kw` builds one."""
    return staged_run_checks.preflight(run, plans_dir(run), repo_root(run),
                                       runner=runner or RecordingRunner(**kw))


def covered_record(landed: Path, bead: str = "proj-a1") -> dict:
    """One `dedup._covered_records` record, written the way the producer writes it.

    A fixture that invents its own shape proves nothing about the code it
    stands in for — F1 lived behind exactly that, a `{"path": ...}` dict no
    producer has ever emitted. `case_covered_record_shape_matches_dedup_producer`
    holds this helper to the producer mechanically.
    """
    return {
        "id": bead,
        "action": "drop",
        "covered_by": str(landed),
        "citations": [{"path": str(landed), "how": "beads-task",
                       "line": f"**Beads task:** `{bead}`"}],
    }


def land(run: Path, tmp: Path) -> Path:
    """A promote that moved the plan folder, then died before any bd write.

    `shutil.move` preserves mtime, so the landed files are newer than the
    manifest's `generated_at` without anyone touching them — which is exactly
    the condition F4 tripped on. `os.utime` makes that premise explicit
    instead of implicit.
    """
    src = run / "todo" / PLAN_FOLDER
    dst = tmp / "plans" / PROJECT / "todo" / PLAN_FOLDER
    shutil.move(str(src), str(dst))
    for path in dst.rglob("*.md"):
        os.utime(path, None)
    return dst


def add_bead(run: Path, bid: str, route: str, selected: bool = True) -> None:
    """A manifest bead the run formed no intent for: no artifacts, no verdict."""
    data = manifest_io.load(run / "manifest.json")
    entry = {"id": bid, "title": "Unrelated", "status": "needs-plan",
             "issue_type": "bug", "priority": 3, "route": route,
             "reason": "fixture", "selected": selected}
    if not selected:
        entry["excluded"] = "not in --ids"
    data["beads"].append(entry)
    manifest_io.save(run / "manifest.json", data)


def footprint(run: Path) -> None:
    """The staged footprint a first-pass run leaves behind."""
    (run / "footprints.json").write_text(json.dumps(
        [{"bead": "proj-a1", "files": [{"path": "lib/reader.dart"}]}]),
        encoding="utf-8")


def plan_text(*declared: str, cites: tuple = ()) -> str:
    """A landed plan the way the plan skill writes one: the files it touches are
    declared, and anything it merely cites is prose.

    Both halves are the fixture's point. A plan states its work in its
    Component Decomposition and its file record; it also quotes evidence, line
    numbers and neighbouring code it never edits. A fixture carrying only the
    first proves nothing about the second, which is how a promote-time check
    that read every path token in the file shipped: its landed-plan fixtures
    were one prose line each, so no test ever presented it a citation.
    """
    rows = "".join(f"| `{p}` | Does one thing | 40 |\n" for p in declared)
    prose = "".join(f"The fix is proven against `{p}`, which stays as it is.\n"
                    for p in cites)
    return ("# Phase 1: Late plan\n\n## Component Decomposition\n\n"
            "| Component | Responsibility | Projected LOC |\n|---|---|---|\n"
            f"{rows}\n## Background\n\n{prose}\n")


def late_plan(tmp: Path, text: str) -> Path:
    """A foreign plan that landed in the real todo/ after the run was staged."""
    path = tmp / "plans" / PROJECT / "todo" / "late_plan.md"
    path.write_text(text, encoding="utf-8")
    return path


def append(path: Path, text: str) -> None:
    path.write_text(path.read_text(encoding="utf-8") + text, encoding="utf-8")


# --- the healthy run ---------------------------------------------------------


def case_clean_staged_run_passes_preflight(tmp: Path) -> None:
    findings, quarantined = check(staged(tmp))
    expect([f for f in findings if f.severity == "error"], [])
    expect(quarantined, set())


def case_parked_bead_still_parked_passes(tmp: Path) -> None:
    run = staged(tmp)
    fake = RecordingRunner()
    findings, quarantined = check(run, fake)
    expect(quarantined, set())
    assert not [f for f in findings if f.subject == "proj-p9"], findings
    expect([argv for argv, _ in fake.calls if argv[1] != "show"], [])


def case_preflight_takes_environment_as_arguments(tmp: Path) -> None:
    findings, quarantined = staged_run_checks.preflight(
        staged(tmp), tmp / "plans", tmp / PROJECT, runner=RecordingRunner())
    expect([f for f in findings if f.severity == "error"], [])
    expect(quarantined, set())


# --- step 1: the artifacts went stale ---------------------------------------


def case_stale_artifact_fails_preflight(tmp: Path) -> None:
    run = staged(tmp)
    art = run / "investigations" / INVEST_NAME
    art.write_text(art.read_text(encoding="utf-8").replace(
        "`lib/reader.dart:2`", "`lib/reader.dart:99`"), encoding="utf-8")
    findings, _ = check(run)
    assert "citation-line-out-of-range" in codes(findings), codes(findings)
    assert art.is_file(), "a preflight stop moves nothing"


def case_broken_plan_fails_preflight(tmp: Path) -> None:
    run = staged(tmp)
    slice_file = run / "todo" / PLAN_FOLDER / "phase_1_demo_slice.md"
    slice_file.write_text(slice_file.read_text(encoding="utf-8").replace(
        "**Parent plan:** [plan.md](plan.md)\n", ""), encoding="utf-8")
    findings, _ = check(run)
    assert "headers" in codes(findings), codes(findings)


# --- step 2: collision against todo/ as it exists now -----------------------


def case_new_plan_in_todo_collides(tmp: Path) -> None:
    run = staged(tmp)
    (tmp / "plans" / PROJECT / "todo" / PLAN_FOLDER).mkdir()
    findings, _ = check(run)
    assert "promote-target-exists" in codes(findings), codes(findings)


def case_bead_already_planned_collides(tmp: Path) -> None:
    run = staged(tmp)
    late_plan(tmp, "**Beads task:** `proj-a1`\n")
    findings, _ = check(run)
    assert "promote-bead-already-planned" in codes(findings), codes(findings)
    assert [f for f in findings if f.severity == "error"], findings


def case_bare_mention_only_warns(tmp: Path) -> None:
    """A mere mention is not an ownership claim, so it must not stop the run."""
    run = staged(tmp)
    late_plan(tmp, "Related to proj-a1 somehow.\n")
    findings, _ = check(run)
    hits = [f for f in findings if f.code == "promote-bead-mentioned"]
    expect([f.severity for f in hits], ["warning"])


def case_coverage_already_known_is_not_a_collision(tmp: Path) -> None:
    run = staged(tmp)
    landed = late_plan(tmp, "**Beads task:** `proj-a1`\n")
    data = manifest_io.load(run / "manifest.json")
    data["covered"] = [covered_record(landed)]
    manifest_io.save(run / "manifest.json", data)
    findings, _ = check(run)
    assert "promote-bead-already-planned" not in codes(findings), codes(findings)


def case_covered_record_shape_matches_dedup_producer(tmp: Path) -> None:
    """The fixture above must mirror its producer, or it guards nothing."""
    landed = tmp / "late_plan.md"
    record = covered_record(landed)
    produced = dedup._covered_records({"proj-a1": record["citations"]})
    expect(sorted(produced[0]), sorted(record))
    expect(produced[0]["covered_by"], record["covered_by"])


def case_skip_route_bead_is_out_of_coverage_scope(tmp: Path) -> None:
    """A bead the run skipped cannot be "already planned" — it planned nothing."""
    run = staged(tmp)
    add_bead(run, "proj-s3", "skip")
    late_plan(tmp, "**Beads task:** `proj-s3`\n")
    findings, _ = check(run)
    assert not [f for f in findings if f.subject == "proj-s3"], findings


def case_footprint_collision_with_late_plan(tmp: Path) -> None:
    run = staged(tmp)
    footprint(run)
    late_plan(tmp, plan_text("lib/reader.dart"))
    findings, _ = check(run)
    assert "promote-footprint-collision" in codes(findings), codes(findings)


def case_disjoint_late_plan_is_not_a_footprint_collision(tmp: Path) -> None:
    run = staged(tmp)
    footprint(run)
    late_plan(tmp, plan_text("lib/catalog.dart"))
    findings, _ = check(run)
    assert "promote-footprint-collision" not in codes(findings), codes(findings)


def case_cited_file_in_a_late_plan_is_not_a_footprint_collision(tmp: Path) -> None:
    """A path a landed plan quotes as evidence is not work it will do.

    Both sides of this graph are approved-work footprints: a Wave 3 footprint
    is the file set a bead's fix touches, and the landed half has to mean the
    same thing or the comparison is between two different vocabularies. It
    stopped a live promote with four collisions against a plan that declared
    ten files and none of the three it was accused of sharing - two of them
    quoted inside doc comments, one in a table's description cell.
    """
    run = staged(tmp)
    footprint(run)
    late_plan(tmp, plan_text("lib/catalog.dart", cites=("lib/reader.dart",)))
    findings, _ = check(run)
    assert "promote-footprint-collision" not in codes(findings), codes(findings)


def case_landed_master_plan_declaring_nothing_is_not_a_collision(tmp: Path) -> None:
    """A master plan states its phases' work, not its own: it has no component
    table and its file record stays empty until execution fills it. Reading its
    prose as a footprint made every epic in `todo/` collide with everything."""
    run = staged(tmp)
    footprint(run)
    late_plan(tmp, "# Master plan\n\n## Background\n\n"
                   "Phase 1 reworks `lib/reader.dart` end to end.\n")
    findings, _ = check(run)
    assert "promote-footprint-collision" not in codes(findings), codes(findings)



# --- the resumed promote: our own landed artifacts are not foreign ----------


def case_resumed_promote_ignores_its_own_landed_plan(tmp: Path) -> None:
    run = staged(tmp)
    footprint(run)
    append(land(run, tmp) / "plan.md", "\nTouches `lib/reader.dart`.\n")
    findings, _ = check(run)
    assert "promote-footprint-collision" not in codes(findings), codes(findings)


def case_resumed_promote_still_catches_a_foreign_plan(tmp: Path) -> None:
    """The exclusion is targeted, not "ignore everything newer than the run"."""
    run = staged(tmp)
    footprint(run)
    append(land(run, tmp) / "plan.md", "\nTouches `lib/reader.dart`.\n")
    late_plan(tmp, plan_text("lib/reader.dart"))
    findings, _ = check(run)
    hits = [f for f in findings if f.code == "promote-footprint-collision"]
    expect(len(hits), 1)
    assert "late_plan.md" in hits[0].detail, hits
    assert PLAN_FOLDER not in hits[0].detail, hits


def case_resumed_promote_ignores_its_own_landed_coverage(tmp: Path) -> None:
    run = staged(tmp)
    append(land(run, tmp) / "plan.md", "\n**Beads task:** `proj-a1`\n")
    findings, _ = check(run)
    assert "promote-bead-already-planned" not in codes(findings), codes(findings)


# --- step 3: the one per-bead stop ------------------------------------------


def case_changed_bead_is_quarantined_alone(tmp: Path) -> None:
    run = staged(tmp)
    findings, quarantined = check(run, responses={"bd show proj-a1 --json": json.dumps(
        [{"id": "proj-a1", "status": "closed", "notes": ""}])})
    expect(quarantined, {"proj-a1"})
    assert "promote-bead-state-changed" in codes(findings), codes(findings)
    assert not [f for f in findings if f.subject == "proj-p9"], findings


def case_parked_bead_moved_is_a_finding(tmp: Path) -> None:
    run = staged(tmp)
    findings, quarantined = check(run, responses={
        "bd show proj-p9 --json": json.dumps(
            [{"id": "proj-p9", "status": "needs-plan", "notes": "Plan: /x.md"}])})
    expect(quarantined, {"proj-p9"})
    assert "promote-parked-bead-moved" in codes(findings), codes(findings)


def case_parked_bead_carrying_our_investigation_note_passes(tmp: Path) -> None:
    """`Investigation:` on a parked bead is this system's own writing.

    A park promotes an `investigation` record, and that record writes exactly
    this line onto the bead. So every bead any earlier run parked carries one,
    and reading it as "someone re-planned this by hand" quarantines a bead for
    having been parked before - which is the state a re-park starts from. The
    marker that means re-planned is a plan path; `inventory.select` has always
    drawn that line, and the skill's bead rules state it outright.
    """
    run = staged(tmp)
    findings, quarantined = check(run, responses={
        "bd show proj-p9 --json": json.dumps(
            [{"id": "proj-p9", "status": "needs-plan",
              "notes": "Investigation: /plans/proj/investigations/x.md\n"
                       "Kept by a human: ask about the toast copy."}])})
    expect(quarantined, set())
    assert not [f for f in findings if f.subject == "proj-p9"], findings


def case_missing_bead_is_a_finding(tmp: Path) -> None:
    run = staged(tmp)
    findings, quarantined = check(run, responses={"bd show proj-a1 --json": "[]"})
    expect(quarantined, {"proj-a1"})
    assert "promote-bead-missing" in codes(findings), codes(findings)


def case_an_excluded_bead_is_out_of_run_scope(tmp: Path) -> None:
    """`inventory.select` marks an excluded bead and leaves its entry in place.

    Reading `route` alone put a bead this run was told not to touch back into
    scope, so an unrelated tracker move on it quarantined the bead and — per
    `run_scope`'s own docstring — stranded the whole promote. It also cost a
    `bd show` the same docstring says it must not.
    """
    run = staged(tmp)
    add_bead(run, "proj-x9", "plan", selected=False)
    fake = RecordingRunner(responses={"bd show proj-x9 --json": json.dumps(
        [{"id": "proj-x9", "status": "closed", "notes": ""}])})
    findings, quarantined = check(run, fake)
    expect(quarantined, set())
    assert not [f for f in findings if f.subject == "proj-x9"], findings
    assert not [a for a, _ in fake.calls if "proj-x9" in a], fake.calls


def case_skip_route_bead_state_change_does_not_quarantine(tmp: Path) -> None:
    """An unrelated skipped bead moving must not strand the run in staging."""
    run = staged(tmp)
    add_bead(run, "proj-s3", "skip")
    fake = RecordingRunner(responses={"bd show proj-s3 --json": json.dumps(
        [{"id": "proj-s3", "status": "closed", "notes": ""}])})
    findings, quarantined = check(run, fake)
    expect(quarantined, set())
    assert not [f for f in findings if f.subject == "proj-s3"], findings
    assert not [a for a, _ in fake.calls if "proj-s3" in a], fake.calls


def case_drift_report_bead_is_out_of_scope(tmp: Path) -> None:
    run = staged(tmp)
    add_bead(run, "proj-d4", "drift-report")
    fake = RecordingRunner(responses={"bd show proj-d4 --json": json.dumps(
        [{"id": "proj-d4", "status": "closed", "notes": ""}])})
    findings, quarantined = check(run, fake)
    expect(quarantined, set())
    assert not [f for f in findings if f.subject == "proj-d4"], findings
    assert not [a for a, _ in fake.calls if "proj-d4" in a], fake.calls


# --- the run's own applied flip is not drift --------------------------------


def flipped(run: Path) -> None:
    """The ledger row an earlier pass leaves once `flip-a1` has been applied.

    Keyed the way `promote` writes it: the record's key under the bead whose
    store file holds it, which is what `intent_records.load_all` hands
    `apply_intents` and what `applied_states` therefore reads back.
    """
    staged_run.record_step(run, "proj-a1/flip-a1", "proj-a1")


def shows(bead: str, status: str, notes: str = "") -> dict:
    return {f"bd show {bead} --json": json.dumps(
        [{"id": bead, "status": status, "notes": notes}])}


def case_our_own_applied_flip_is_not_drift(tmp: Path) -> None:
    """The source bead a first pass already flipped reads back `open` while the
    manifest still records `needs-plan`. Quarantining it strands the run over a
    change the run itself made, and no rerun can ever clear it."""
    run = staged(tmp)
    flipped(run)
    findings, quarantined = check(run, responses=shows("proj-a1", "open"))
    expect(quarantined, set())
    assert not [f for f in findings if f.subject == "proj-a1"], findings


def case_foreign_change_after_our_flip_still_quarantines(tmp: Path) -> None:
    """The excuse is one status, not a blanket pardon: someone closing the bead
    after our flip is still drift this run's intents must not be applied over."""
    run = staged(tmp)
    flipped(run)
    findings, quarantined = check(run, responses=shows("proj-a1", "closed"))
    expect(quarantined, {"proj-a1"})
    assert "promote-bead-state-changed" in codes(findings), codes(findings)
    hit = [f for f in findings if f.subject == "proj-a1"][0]
    expect(hit.detail, "recorded open, now closed")


def case_unapplied_flip_does_not_excuse_a_status_change(tmp: Path) -> None:
    """What excuses the bead is the ledger row, not the intent's existence — a
    flip nobody applied means an `open` source bead is somebody else's edit."""
    run = staged(tmp)
    findings, quarantined = check(run, responses=shows("proj-a1", "open"))
    expect(quarantined, {"proj-a1"})
    assert "promote-bead-state-changed" in codes(findings), codes(findings)


def closed_itself(run: Path) -> None:
    """The store and ledger row an earlier pass leaves once this run retired
    `proj-a1` as a duplicate. The flip is traded for the close rather than
    stacked on it — no bead is ever both flipped open and closed."""
    kept = [r for r in intent_records.load(run, "proj-a1")
            if r["kind"] != "flip-source"]
    intent_records.save(run, "proj-a1", kept + [
        {"key": "close-a1", "kind": "close", "bead": "proj-a1",
         "investigation": str(run / "investigations" / INVEST_NAME)}])
    staged_run.record_step(run, "proj-a1/close-a1", "proj-a1")


def case_our_own_applied_close_is_not_drift(tmp: Path) -> None:
    """Why `close` is in `SOURCE_KINDS`: a bead this run retired reads back
    `closed` while the manifest still records `needs-plan`, and a rerun that
    read its own write as somebody else's edit would quarantine the bead
    forever."""
    run = staged(tmp)
    closed_itself(run)
    findings, quarantined = check(run, responses=shows("proj-a1", "closed"))
    expect(quarantined, set())
    assert not [f for f in findings if f.subject == "proj-a1"], findings


def _updates_its_own_bead(intent: dict, ids: dict) -> bool:
    """`--status` is part of the predicate, not decoration: `applied_states`
    recovers a bead's state by indexing `--status` out of this argv, so a kind
    that writes no status — `retitle` — belongs outside `SOURCE_KINDS` and
    would raise there rather than being read back."""
    argv = tracker_intents.render(intent, ids, {}).argv
    return (argv[1] == "update" and argv[2] == intent["bead"]
            and "--status" in argv)


def case_source_kinds_matches_the_intents_that_update_a_manifest_bead(tmp: Path) -> None:
    """`SOURCE_KINDS` names the kinds whose `bd` call rewrites the bead the
    manifest already knows. A hand-kept list drifts from the renderer that
    actually writes, so it is derived from `tracker_intents.render` here."""
    fields = {"bead": "proj-a1", "title": "t", "ref": "r", "parent": "p",
              "from": "r", "to": "p", "plan": "/p.md", "investigation": "/i.md",
              "by": "r", "master": "/m.md"}
    ids = {"r": "proj-r1", "p": "proj-p1"}
    derived = [kind for kind in tracker_intents.KIND_ORDER
               if _updates_its_own_bead(dict(fields, kind=kind), ids)]
    expect(sorted(derived), sorted(staged_run_checks.SOURCE_KINDS))


# --- the artifact no record names -------------------------------------------


def orphan_row(run: Path, bid: str) -> Path:
    """A Wave 2 row whose artifact landed and whose `final` says nothing yet.

    One of the populations `SOURCE_KINDS` still leaves recordless: the bead is
    in flight, so `derive_intents` writes it no record at all. Deliberately
    not a `duplicate` — that outcome derives a `close`, so such a bead now
    carries a record and passes this gate correctly.

    The caller decides whether the bead is in the manifest, because that is
    what `run_scope` asks and one case is about a bead that is not.
    """
    artifact = run / "investigations" / f"{PROJECT}_invest_{bid[-2:]}.md"
    append(run / "ledger.md", staged_run.ledger_row(
        bead=bid, wave=2, worker=f"invest-{bid}",
        dispatched="2026-08-28T10:06:00Z", returned="2026-08-28T10:07:00Z",
        artifact=artifact))
    return artifact


def intentless(run: Path, done: dict = None):
    """The new check over the run's own state on disk."""
    data = staged_run.load_run(run)
    return staged_run_checks.intentless_artifacts(
        data, staged_run.bead_outcomes(run, data),
        intent_records.load_all(run), done or {})


def case_a_bead_with_no_source_record_is_quarantined_alone(tmp: Path) -> None:
    """The mirror of `promote-artifact-missing`: an artifact would land with
    nothing in the tracker ever pointing at it. The subject must be the bead,
    because `promote.promote` tolerates an error whose subject is quarantined
    and stops the whole run on one that is not."""
    run = staged(tmp)
    add_bead(run, "proj-o7", "investigate")
    artifact = orphan_row(run, "proj-o7")
    findings, beads = intentless(run)
    expect(codes(findings), ["promote-intentless-artifact"])
    expect(findings[0].subject, "proj-o7")
    assert str(artifact) in findings[0].detail, findings[0].detail
    expect(beads, {"proj-o7"})
    findings, quarantined = check(run)
    assert "promote-intentless-artifact" in codes(findings), codes(findings)
    expect(quarantined, {"proj-o7"})


def case_a_planned_beads_investigation_moves_under_its_flip_source(tmp: Path) -> None:
    """The 6-of-12 false-positive guard, and the case that fails the day
    someone keys this check per artifact: `proj-a1`'s Wave 2 investigation
    moves under a `flip-source` record that names its plan instead, and no
    record in the store names the investigation at all."""
    run = staged(tmp)
    invest = str(run / "investigations" / INVEST_NAME)
    assert invest not in json.dumps(intent_records.load_all(run)), invest
    expect(intentless(run), ([], set()))


def case_a_recorded_move_clears_the_finding(tmp: Path) -> None:
    """The clearing path: the promoter who elects to keep the file moves that
    one file and records the move, and the rerun is a no-op."""
    run = staged(tmp)
    add_bead(run, "proj-o7", "investigate")
    artifact = orphan_row(run, "proj-o7")
    landed = tmp / "plans" / PROJECT / "investigations" / artifact.name
    key = staged_run.MOVE_PREFIX + str(artifact)
    expect(intentless(run, {key: str(landed)}), ([], set()))
    staged_run.record_step(run, key, str(landed))
    findings, quarantined = check(run)
    assert "promote-intentless-artifact" not in codes(findings), codes(findings)
    expect(quarantined, set())


def case_a_bead_outside_run_scope_raises_nothing(tmp: Path) -> None:
    """A quarantine strands the whole run, so a bead this run formed no intent
    for must not be able to raise one. Unscoped, the vendored real ledger over
    a `proj-*` manifest flags nine beads —
    `test_staged_run_ledger_checks.case_the_stalled_runs_ledger_adds_no_finding`."""
    run = staged(tmp)
    orphan_row(run, "demo-y0k")
    expect(intentless(run), ([], set()))


# --- the run that today can never finish ------------------------------------


def case_partially_applied_run_promotes_on_rerun(tmp: Path) -> None:
    """All three defects in one fixture: a move that landed, a bead already
    planned by that move, and an unrelated skipped bead whose status changed."""
    run = staged(tmp)
    add_bead(run, "proj-s3", "skip")
    footprint(run)
    append(land(run, tmp) / "plan.md",
           "\nTouches `lib/reader.dart`.\n**Beads task:** `proj-a1`\n")
    findings, quarantined = check(run, responses={
        "bd show proj-s3 --json": json.dumps(
            [{"id": "proj-s3", "status": "closed", "notes": ""}])})
    expect([f for f in findings if f.severity == "error"], [])
    expect(quarantined, set())
    assert (run / "investigations" / INVEST_NAME).is_file(), "a preflight moves nothing"



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
