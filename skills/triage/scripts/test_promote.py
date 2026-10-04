#!/usr/bin/env python3
"""Tests for promote.py's own half — the move, the path rewrite, the `_v2`
uniqueness rule, the mirrors, and the run's promote log.

This file also owns the staged-run fixture the other four promote test files
build on: `test_staged_run_checks.py`, `test_tracker_intents.py`,
`test_promote_paths.py` and `test_promote_cli.py` all import `staged` and
`RecordingRunner` from here, the way `test_collide_cli.py` imports its
fixtures from `test_collide.py`.

Run with `python3 test_promote.py` (no pytest dependency).

**LOC waiver:** 414 code lines by `run_arch_gate.py`'s count against a 300
signal, plus 74 of doc prose the count no longer charges. It is one case list
plus the fixture the four suites above
import, read one case at a time. Lifting that fixture into a module of its own
was considered and rejected: the import graph named above is this repo's
convention, and the move would edit five files to lower one number.
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

import intent_records  # noqa: E402
import manifest as manifest_io  # noqa: E402
import promote  # noqa: E402
import staged_run  # noqa: E402
import tracker_intents  # noqa: E402
from staged_run import ledger_row  # noqa: E402
from test_lint_investigation import scaffold  # noqa: E402
from test_lint_plan import plan_tree, slice_text  # noqa: E402

RUNID = "2026-08-28_ab12"
PROJECT = "proj"
INVEST_NAME = "proj_invest_thing_goes_wrong.md"
PLAN_FOLDER = "skills_epic_demo_thing"
LEDGER = staged_run.ledger_header("full run")


def expect(got, want) -> None:
    assert got == want, f"got {got!r}, want {want!r}"


def codes(findings) -> list:
    return sorted(f.code for f in findings)


# --- the staged-run fixture --------------------------------------------------


def intents(run: Path) -> list:
    """One epic, two phases, one dep, two opens and the source flip.

    The three worker kinds name no `bead` — `intent_records.load_all` owns
    that rule and attaches the owner from the store filename. `dep`,
    `investigation` and `flip-source` keep theirs.
    """
    folder = run / "todo" / PLAN_FOLDER
    master = str(folder / "plan.md")
    common = {"type": "feature", "priority": 2, "labels": ["demo"],
              "master": master}
    return [
        {"key": "epic", "kind": "create-epic", "ref": "epic",
         "title": "Demo thing", "type": "epic", "priority": 2,
         "description": "Deliver the demo thing.", "labels": ["demo"],
         "master": master},
        {"key": "phase-1", "kind": "create-task", "ref": "phase_1",
         "title": "Phase 1: Demo slice", "parent": "epic",
         "description": "Step 1.1 ...", "slice": str(folder / "phase_1_demo_slice.md"),
         **common},
        {"key": "phase-2", "kind": "create-task", "ref": "phase_2",
         "title": "Phase 2: Demo slice", "parent": "epic",
         "description": "Step 2.1 ...", "slice": str(folder / "phase_2_demo_slice.md"),
         **common},
        {"key": "dep-2-on-1", "kind": "dep", "bead": "proj-a1",
         "from": "phase_2", "to": "phase_1", "dep_type": "blocks"},
        {"key": "open-1", "kind": "open", "ref": "phase_1"},
        {"key": "open-2", "kind": "open", "ref": "phase_2"},
        {"key": "flip-a1", "kind": "flip-source", "bead": "proj-a1", "plan": master},
    ]


def plans_dir(run: Path) -> Path:
    """The `--plans-dir` this fixture staged `run` under."""
    return run.parents[2]


def repo_root(run: Path) -> str:
    """The `--repo-root` this fixture built beside the plans tree."""
    return str(run.parents[3] / PROJECT)



def outcome_rows(run: Path) -> list[str]:
    artifact = run / "investigations" / INVEST_NAME
    folder = run / "todo" / PLAN_FOLDER
    return [
        ledger_row(bead="proj-a1", wave=2, worker="invest-a1",
                   dispatched="2026-08-28T10:00:00Z", returned="2026-08-28T10:01:00Z",
                   artifact=artifact, final="planned"),
        ledger_row(bead="proj-a1", wave=4, worker="plan-a1",
                   dispatched="2026-08-28T10:02:00Z", returned="2026-08-28T10:03:00Z",
                   artifact=folder, final="planned"),
        ledger_row(bead="proj-p9", wave=2, worker="invest-p9",
                   dispatched="2026-08-28T10:04:00Z", returned="2026-08-28T10:05:00Z",
                   final="parked"),
    ]


def seed_ledger(run: Path, rows: list[str]) -> None:
    (run / "ledger.md").write_text(LEDGER + "".join(rows), encoding="utf-8")


def manifest_bead(bid: str, route: str, *, selected: bool = True) -> dict:
    out = {"id": bid, "title": "Demo thing", "status": "needs-plan",
           "issue_type": "bug", "priority": 3, "route": route, "reason": "fixture",
           "selected": selected}
    if not selected:
        out["excluded"] = "not in --ids"
    return out


def manifest_data(beads: list) -> dict:
    """The manifest shape `inventory.py` and `dedup.py` write between them.

    A fixture that names only the keys the code under test reads proves
    nothing about the manifests promote actually meets, so the empty
    collections are here rather than omitted.
    """
    return {"schema_version": 1, "project": PROJECT,
            "generated_at": "2020-01-01T00:00:00Z",
            "beads": beads,
            "clusters": [], "counts": {}, "covered": [], "groups": [],
            "selected_counts": {}, "selected_total": len(beads),
            "total": len(beads)}


def _tokenize(folder: Path) -> None:
    """The staged plan as a planning worker now writes it: every bead the run
    creates is named by the `<bead:{ref}>` token `brief_plan.sh` prescribes,
    and never by an invented ID, so `promote.write_back` has something to
    substitute the created ID into."""
    for path in sorted(folder.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        for n in (1, 2):
            text = text.replace(f"skills-demo.{n}", f"<bead:phase_{n}>")
        path.write_text(
            text.replace("A demo master plan",
                         "Epic `<bead:epic>`. A demo master plan"),
            encoding="utf-8")


def staged(tmp: Path, *, slices=None, records=None) -> Path:
    """A run directory that promotes clean, plus the real tree it promotes into."""
    run_rel = f"triage/{RUNID}"
    scaffold(tmp, subdir=f"{run_rel}/investigations")
    plans = tmp / "plans" / PROJECT
    (plans / "investigations").mkdir(parents=True, exist_ok=True)
    (plans / "todo").mkdir(parents=True, exist_ok=True)
    (tmp / "system_plans").mkdir(exist_ok=True)
    run = plans / run_rel
    (run / "todo").mkdir(parents=True, exist_ok=True)
    plan_tree(run / "todo", slices=slices)
    _tokenize(run / "todo" / PLAN_FOLDER)
    seed_ledger(run, outcome_rows(run))
    beads = records if records is not None else [
        manifest_bead("proj-a1", "plan"),
        manifest_bead("proj-p9", "investigate"),
    ]
    manifest_io.save(run / "manifest.json", manifest_data(beads))
    # The run's intents live in the store, not the manifest — every record
    # this fixture builds belongs to `proj-a1`, so that is one save.
    intent_records.save(run, "proj-a1", intents(run))
    return run


def _wrapped(path: str, width: int = 78) -> str:
    """`bd show` renders notes in a padded column and breaks mid-token."""
    body, out = f"  {path}", []
    while body:
        out.append(body[:width].ljust(width) + "\n")
        body = body[width:]
    return "".join(out)


class RecordingRunner:
    """Captures the argv it would have run. `responses` is keyed by `runner_key`.

    Its `bd show` echoes back every notes path written so far, which is what
    lets the post-write verification be exercised without a beads database.

    The human-format branch **wraps at 78 columns, like the real thing**. It
    used to emit each path on one long line, and that difference is the entire
    reason `skills-p1j` shipped: `_verify` substring-matched an absolute path
    against output that never wrapped in a test and always wrapped in life.
    A fake that is easier to satisfy than production is not a fake, it is a
    second implementation with no defects.
    """

    def __init__(self, responses=None, fail_on=None, notes="carry"):
        self.calls = []
        self.responses = responses or {}
        self.fail_on = set(fail_on or ())
        self.notes = notes
        self._n = 0

    def __call__(self, argv, cwd):
        self.calls.append((list(argv), cwd))
        key = tracker_intents.runner_key(argv)
        if key in self.fail_on:
            return 1, ""
        if key in self.responses and not (argv[1] == "show" and "--json" in argv):
            return 0, self.responses[key]
        if argv[1] == "create":
            self._n += 1
            return 0, json.dumps({"id": f"proj-t{self._n:02d}"})
        if argv[1] == "show":
            return 0, self._show(argv)
        return 0, ""

    def _show(self, argv):
        paths = [] if self.notes == "empty" else self._paths()
        if "--json" in argv:
            # A canned response is the bead's *pre-existing* notes; whatever
            # has been written since is appended, because that is what a real
            # `bd show` would return by the time the read-back runs.
            canned, status, title = "", "needs-plan", ""
            record = self.responses.get(tracker_intents.runner_key(argv))
            if record:
                payload = json.loads(record)
                rows = payload if isinstance(payload, list) else [payload]
                if not rows:
                    return record  # an absent bead stays absent
                canned = "".join(r.get("notes") or "" for r in rows)
                # The canned status and title are what the case is usually
                # about — a quarantine check reads one, a retitle's read-back
                # reads the other. Only the notes accumulate.
                status = next((r.get("status") for r in rows
                               if r.get("status")), status)
                title = next((r.get("title") for r in rows
                              if r.get("title")), title)
            notes = "\n".join([canned] + [f"Slice: {p}" for p in paths]).strip()
            return json.dumps([{"id": argv[2], "status": status,
                                "title": title, "notes": notes}])
        if self.notes == "empty":
            return f"{argv[2]}\nDESCRIPTION\n\n"
        return f"{argv[2]}\nNOTES\n" + "".join(_wrapped(p) for p in paths)

    def _paths(self) -> list:
        out = []
        for argv, _ in self.calls:
            if "--notes" in argv:
                for line in argv[argv.index("--notes") + 1].splitlines():
                    if ": /" in line:
                        out.append(line.split(": ", 1)[1])
        return out


def pairs_for(run: Path, quarantined=()) -> list:
    """`move_map` against the fixture, which moves nothing."""
    data = manifest_io.load(run / "manifest.json")
    return promote.move_map(staged_run.bead_outcomes(run, data),
                            set(quarantined), plans_dir(run), data["project"])


def moved_for(run: Path, quarantined=(), done=None):
    """`promote_artifacts` against the fixture, plus the manifest it read."""
    data = manifest_io.load(run / "manifest.json")
    return promote.promote_artifacts(
        run, staged_run.bead_outcomes(run, data), set(quarantined),
        plans_dir(run), data["project"], done) + (data,)


def mirrors_for(tmp: Path, moved: list) -> list:
    """`write_mirrors` against the fixture's plans tree and mirror root."""
    return promote.write_mirrors(moved, tmp / "plans", PROJECT,
                                 tmp / "system_plans")


# --- the move ----------------------------------------------------------------


def case_manifest_without_plans_dir_still_promotes(tmp: Path) -> None:
    run = staged(tmp)
    moved, findings, _ = moved_for(run)
    expect(codes(findings), [])
    expect(sorted(Path(new).name for _, new in moved), [INVEST_NAME, PLAN_FOLDER])


def case_a_group_plan_folder_moves_once(tmp: Path) -> None:
    run = staged(tmp)
    data = manifest_io.load(run / "manifest.json")
    data["beads"].append(manifest_bead("proj-b2", "plan"))
    data["groups"] = [{"group_id": "g1", "members": ["proj-a1", "proj-b2"]}]
    manifest_io.save(run / "manifest.json", data)
    seed_ledger(run, [
        ledger_row(bead="proj-a1", wave=2, worker="invest-a1",
                   dispatched="2026-08-28T10:00:00Z", returned="2026-08-28T10:01:00Z",
                   artifact=run / "investigations" / INVEST_NAME, final="planned"),
        ledger_row(bead="g1", wave=4, worker="plan-g1",
                   dispatched="2026-08-28T10:02:00Z", returned="2026-08-28T10:03:00Z",
                   artifact=run / "todo" / PLAN_FOLDER, final="planned"),
    ])
    pairs = pairs_for(run)
    expect([old for old, _ in pairs].count(str(run / "todo" / PLAN_FOLDER)), 1)
    moved, findings, _ = moved_for(run)
    expect(codes(findings), [])
    expect([Path(new).name for old, new in moved
            if old == str(run / "todo" / PLAN_FOLDER)], [PLAN_FOLDER])


def case_parked_final_is_not_promoted_as_planned(tmp: Path) -> None:
    pairs = pairs_for(staged(tmp))
    assert not [pair for pair in pairs if "proj-p9" in pair[0]], pairs


def case_v2_uniqueness_applied_against_real_directory(tmp: Path) -> None:
    run = staged(tmp)
    real = tmp / "plans" / PROJECT / "investigations"
    (real / INVEST_NAME).write_text("# prior evidence\n", encoding="utf-8")
    body = f"### File: `demo/thing_1.py`\n\nSee {run}/investigations/{INVEST_NAME}\n"
    (run / "todo" / PLAN_FOLDER / "phase_1_demo_slice.md").write_text(
        slice_text(1, files=body), encoding="utf-8")
    moved_for(run)
    expect((real / INVEST_NAME).read_text(encoding="utf-8"), "# prior evidence\n")
    assert (real / "proj_invest_thing_goes_wrong_v2.md").is_file()
    text = (tmp / "plans" / PROJECT / "todo" / PLAN_FOLDER /
            "phase_1_demo_slice.md").read_text(encoding="utf-8")
    assert str(real / "proj_invest_thing_goes_wrong_v2.md") in text, text


def case_v3_when_v2_also_exists(tmp: Path) -> None:
    run = staged(tmp)
    real = tmp / "plans" / PROJECT / "investigations"
    for name in (INVEST_NAME, "proj_invest_thing_goes_wrong_v2.md"):
        (real / name).write_text("# prior\n", encoding="utf-8")
    moved_for(run)
    assert (real / "proj_invest_thing_goes_wrong_v3.md").is_file()


def case_quarantined_bead_artifacts_stay_in_staging(tmp: Path) -> None:
    run = staged(tmp)
    art = run / "investigations" / INVEST_NAME
    data = manifest_io.load(run / "manifest.json")
    data["beads"].append(manifest_bead("proj-b2", "investigate"))
    manifest_io.save(run / "manifest.json", data)
    seed_ledger(run, [
        ledger_row(bead="proj-a1", wave=4, worker="plan-a1",
                   dispatched="2026-08-28T10:02:00Z", returned="2026-08-28T10:03:00Z",
                   artifact=run / "todo" / PLAN_FOLDER, final="planned"),
        ledger_row(bead="proj-b2", wave=2, worker="invest-b2",
                   dispatched="2026-08-28T10:04:00Z", returned="2026-08-28T10:05:00Z",
                   artifact=art, final="planned"),
    ])
    moved, _, _ = moved_for(run, quarantined={"proj-b2"})
    expect([Path(new).name for _, new in moved], [PLAN_FOLDER])
    assert (tmp / "plans" / PROJECT / "todo" / PLAN_FOLDER).is_dir()
    assert (run / "investigations" / INVEST_NAME).is_file()
    assert not (tmp / "plans" / PROJECT / "investigations" / INVEST_NAME).exists()


def case_rerun_replays_recorded_moves(tmp: Path) -> None:
    """A rerun finds the staged files gone. The ledger is what remembers where
    they went, so the second pass must produce the same pairs the first did —
    dropping them is what let a rerun's intents keep run-directory paths."""
    run = staged(tmp)
    first, findings, _ = moved_for(run)
    expect(codes(findings), [])
    second, findings, _ = moved_for(run, done=staged_run.completed_steps(run))
    expect(codes(findings), [])
    expect(sorted(second), sorted(first))
    real = tmp / "plans" / PROJECT / "investigations"
    expect(sorted(p.name for p in real.glob("*.md")), [INVEST_NAME])
    joined = json.dumps(promote.remap(intent_records.load_all(run), second))
    assert str(run) not in joined, joined


def case_missing_artifact_stops_before_any_move(tmp: Path) -> None:
    """An artifact that is neither on disk nor recorded is an error. Skipping
    it silently leaves its intents holding run-directory paths."""
    run = staged(tmp)
    seed_ledger(run, outcome_rows(run) + [
        ledger_row(bead="proj-a1", wave=4, worker="plan-a1",
                   dispatched="2026-08-28T10:06:00Z", returned="2026-08-28T10:07:00Z",
                   artifact=run / "todo" / "ghost.md", final="planned"),
    ])
    moved, findings, _ = moved_for(run)
    assert "promote-artifact-missing" in codes(findings), codes(findings)
    expect(moved, [])
    assert (run / "todo" / PLAN_FOLDER).is_dir()
    assert (run / "investigations" / INVEST_NAME).is_file()
    assert not (tmp / "plans" / PROJECT / "todo" / PLAN_FOLDER).exists()


def case_a_revised_missing_artifact_is_one_finding(tmp: Path) -> None:
    """One absent file is one finding, however many review rounds its row took.

    A `REVISE` round owes a second dispatch row at the same assigned path
    (`references/ledger.md`), and `missing_artifacts` yields one finding per
    list entry — so the promote report printed the same path on two
    consecutive lines and stated twice the number of missing files. Measured
    as four findings for two files on a real run.
    """
    run = staged(tmp)
    ghost = run / "todo" / "ghost.md"
    seed_ledger(run, outcome_rows(run) + [
        ledger_row(bead="proj-a1", wave=4, worker="plan-a1",
                   dispatched="2026-08-28T10:06:00Z", returned="2026-08-28T10:07:00Z",
                   artifact=ghost, verdict="REVISE", round=1, final="planned"),
        ledger_row(bead="proj-a1", wave=4, worker="plan-a1",
                   dispatched="2026-08-28T10:08:00Z", returned="2026-08-28T10:09:00Z",
                   artifact=ghost, verdict="PASS", round=2, final="planned"),
    ])
    moved, findings, _ = moved_for(run)
    expect(codes(findings), ["promote-artifact-missing"])
    expect(moved, [])


# --- mirrors -----------------------------------------------------------------


def case_mirror_written_with_backlink(tmp: Path) -> None:
    moved, _, _ = moved_for(staged(tmp))
    expect(codes(mirrors_for(tmp, moved)), [])
    mirror = tmp / "system_plans" / f"{PLAN_FOLDER}.md"
    assert "Full plan:" in mirror.read_text(encoding="utf-8")
    plan = tmp / "plans" / PROJECT / "todo" / PLAN_FOLDER / "plan.md"
    assert f"**System plan file:** {mirror}" in plan.read_text(encoding="utf-8")


def case_mirror_is_written_once(tmp: Path) -> None:
    moved, _, _ = moved_for(staged(tmp))
    mirrors_for(tmp, moved)
    expect(codes(mirrors_for(tmp, moved)), [])
    plan = (tmp / "plans" / PROJECT / "todo" / PLAN_FOLDER /
            "plan.md").read_text(encoding="utf-8")
    expect(plan.count("**System plan file:**"), 1)


def case_foreign_mirror_is_a_finding(tmp: Path) -> None:
    run = staged(tmp)
    (tmp / "system_plans" / f"{PLAN_FOLDER}.md").write_text(
        "# Someone else\n\nFull plan: `/elsewhere/plan.md`\n", encoding="utf-8")
    moved, _, _ = moved_for(run)
    assert "promote-mirror-exists" in codes(mirrors_for(tmp, moved))


# --- the write-back ---------------------------------------------------------

APPLIED = {"proj-a1/epic": "proj-x1", "proj-a1/phase-1": "proj-x1.1"}


def _create(ref: str, master: Path, slice_: Path = None) -> dict:
    out = {"bead": "proj-a1", "key": f"proj-a1/{ref}", "title": "t",
           "kind": "create-task" if slice_ else "create-epic",
           "ref": f"proj-a1/{ref}", "master": str(master)}
    return {**out, "slice": str(slice_)} if slice_ else out


def promoted_pair(tmp: Path, task_id: str = "<bead:phase-1>") -> tuple:
    """A promoted master and slice carrying the tokens a planner wrote, plus
    the two `create-*` intents whose refs those tokens name."""
    folder = tmp / "todo" / PLAN_FOLDER
    folder.mkdir(parents=True)
    master, slice_ = folder / "plan.md", folder / "phase_1_thing.md"
    master.write_text("| Epic | <bead:epic> |\n- [ ] Phase 1 — <bead:phase-1>\n",
                      encoding="utf-8")
    slice_.write_text(f"**Beads task:** `{task_id}`\n", encoding="utf-8")
    return master, slice_, [_create("epic", master),
                            _create("phase-1", master, slice_)]


def case_write_back_substitutes_the_applied_ids(tmp: Path) -> None:
    master, slice_, intents = promoted_pair(tmp)
    expect(promote.write_back(intents, APPLIED, []), [])
    expect(slice_.read_text(encoding="utf-8"), "**Beads task:** `proj-x1.1`\n")
    text = master.read_text(encoding="utf-8")
    assert "<bead:" not in text, text
    assert "| Epic | proj-x1 |" in text, text


def case_a_token_naming_no_created_ref_is_one_finding(tmp: Path) -> None:
    master, _, intents = promoted_pair(tmp)
    with master.open("a", encoding="utf-8") as fh:
        fh.write("- [ ] Phase 9 — <bead:phase-9>\n")
    findings = promote.write_back(intents, APPLIED, [])
    expect(codes(findings), ["promote-writeback-incomplete"])
    expect(findings[0].subject, str(master))
    assert "phase-9" in findings[0].detail, findings


def case_a_created_task_whose_slice_never_names_it_is_a_finding(tmp: Path) -> None:
    """The substitution pass cannot see this: a token nobody wrote resolves
    silently, which is the defect the write-back exists to stop."""
    _, slice_, intents = promoted_pair(tmp, task_id="TBD")
    findings = promote.write_back(intents, APPLIED, [])
    expect(codes(findings), ["promote-writeback-incomplete"])
    expect(findings[0].subject, str(slice_))
    assert "proj-x1.1" in findings[0].detail, findings


def case_a_rerun_rewrites_identical_bytes(tmp: Path) -> None:
    """A rerun rebuilds `applied` from the ledger and passes again; an
    already-resolved file carries no token, so the second pass writes nothing."""
    master, slice_, intents = promoted_pair(tmp)
    expect(promote.write_back(intents, APPLIED, []), [])
    before = (master.read_bytes(), slice_.read_bytes())
    expect(promote.write_back(intents, APPLIED, []), [])
    expect((master.read_bytes(), slice_.read_bytes()), before)


def case_an_intent_naming_a_missing_file_is_a_finding(tmp: Path) -> None:
    """A named file that is not on disk is reported, not raised: an exception
    here escapes the sequence and skips `_close`, which is what re-issues
    every `bd create` that already succeeded on the rerun."""
    master, _, intents = promoted_pair(tmp)
    master.unlink()
    findings = promote.write_back(intents, APPLIED, [])
    expect(codes(findings), ["promote-writeback-incomplete"])
    expect(findings[0].subject, str(master))


def case_a_create_task_naming_only_plan_is_written_back(tmp: Path) -> None:
    """`intent_records._task_paths` accepts `slice`+`master` or `plan` alone,
    and `PATH_KEYS` carries `plan` through `remap` like the other two, so a
    single-phase task's file has to be substituted like any other."""
    folder = tmp / "todo"
    folder.mkdir(parents=True)
    plan = folder / "proj_fix_thing.md"
    plan.write_text("**Beads task:** `<bead:task>`\n", encoding="utf-8")
    intents = [{"bead": "proj-a1", "key": "proj-a1/task", "kind": "create-task",
                "ref": "proj-a1/task", "title": "t", "plan": str(plan)}]
    expect(promote.write_back(intents, {"proj-a1/task": "proj-x2"}, []), [])
    expect(plan.read_text(encoding="utf-8"), "**Beads task:** `proj-x2`\n")


def case_a_dressed_ownership_field_is_not_a_finding(tmp: Path) -> None:
    """`plan_slice_checks` requires only that `**Beads task:**` appear in the
    slice, and `plan_coverage` reads it case-insensitively through whatever
    markdown dresses it — so a slice that lints clean must not be reported."""
    _, slice_, intents = promoted_pair(tmp)
    slice_.write_text("- **Beads task:** <bead:phase-1>\n", encoding="utf-8")
    expect(promote.write_back(intents, APPLIED, []), [])
    expect(slice_.read_text(encoding="utf-8"), "- **Beads task:** proj-x1.1\n")


def case_a_token_in_a_promoted_file_no_intent_names_is_a_finding(tmp: Path) -> None:
    """The substitution pass visits only the paths the run's own `create-*`
    intents carry, so a slice a planning worker wrote without a matching
    record would ship its raw token at exit 0. The sweep over the moved
    targets — the same expansion `promote_artifacts` rewrites paths over — is
    what makes that a finding instead."""
    master, _, intents = promoted_pair(tmp)
    orphan = master.parent / "phase_2_thing.md"
    orphan.write_text("**Beads task:** `<bead:phase-2>`\n", encoding="utf-8")
    moved = [(str(tmp / "staged" / PLAN_FOLDER), str(master.parent))]
    findings = promote.write_back(intents, APPLIED, moved)
    expect(codes(findings), ["promote-writeback-incomplete"])
    expect(findings[0].subject, str(orphan))
    assert "phase-2" in findings[0].detail, findings


def case_an_unresolved_token_under_a_moved_target_is_reported_once(tmp: Path) -> None:
    """The sweep and the substitution pass overlap on every intent-named file,
    and one unresolved token is one defect: a second copy of the finding would
    double every report the promote prints."""
    master, _, intents = promoted_pair(tmp)
    with master.open("a", encoding="utf-8") as fh:
        fh.write("- [ ] Phase 9 — <bead:phase-9>\n")
    moved = [(str(tmp / "staged" / PLAN_FOLDER), str(master.parent))]
    findings = promote.write_back(intents, APPLIED, moved)
    expect(codes(findings), ["promote-writeback-incomplete"])
    expect(findings[0].subject, str(master))


def case_a_token_quoted_in_a_promoted_investigation_is_not_a_finding(tmp: Path) -> None:
    """An investigation is never a write-back target — `investigation` is
    outside the `master`/`slice`/`plan` set the substitution runs over — so a
    token there can never resolve, in this run or a rerun. One whose subject is
    this tooling quotes the filled-in form in prose, and stopping the promote
    on that would leave hand-editing the evidence as the only recovery."""
    investigations = tmp / "investigations"
    investigations.mkdir(parents=True)
    quoting = investigations / "proj_invest_thing.md"
    quoting.write_text("The brief prescribes `<bead:epic>` once the ref is filled in.\n",
                       encoding="utf-8")
    moved = [(str(tmp / "staged" / "proj_invest_thing.md"), str(quoting))]
    expect(promote.write_back([], {}, moved), [])


# --- the promote log in the run's ledger ------------------------------------


def case_ledger_records_and_replays_steps(tmp: Path) -> None:
    run = staged(tmp)
    staged_run.record_step(run, "preflight", "clean")
    staged_run.record_step(run, "intent:epic", "proj-t01")
    expect(staged_run.completed_steps(run),
           {"preflight": "clean", "intent:epic": "proj-t01"})
    assert LEDGER in (run / "ledger.md").read_text(encoding="utf-8")


def case_ledger_without_a_promote_log_replays_nothing(tmp: Path) -> None:
    run = staged(tmp)
    expect(staged_run.completed_steps(run), {})
    expect(staged_run.completed_steps(run / "nope"), {})


def run_promote(run: Path, tmp: Path, fake) -> int:
    """`promote.main` end to end against a fake tracker, the way the run does
    it. `default_runner` is the seam — `apply_intents` builds its own."""
    real, tracker_intents.default_runner = tracker_intents.default_runner, fake
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            return promote.main([
                "--run-id", run.name, "--runs-dir", str(run.parent),
                "--plans-dir", str(plans_dir(run)), "--repo-root", repo_root(run),
                "--system-plan-dir", str(tmp / "system_plans"), "--json"])
    finally:
        tracker_intents.default_runner = real


def case_a_retitle_gets_its_own_promote_log_row(tmp: Path) -> None:
    """Every mechanism that makes a promote resumable is keyed on the record's
    own `key`. Without the row a rerun replays a write that already landed —
    which is the whole defect this kind exists to close."""
    run = staged(tmp)
    intent_records.save(run, "proj-a1", intents(run) + [
        {"key": "retitle-a1", "kind": "retitle", "bead": "proj-a1",
         "title": "the corrected title"}])
    fake = RecordingRunner(responses={"bd show proj-a1 --json": json.dumps(
        [{"id": "proj-a1", "status": "needs-plan",
          "title": "the corrected title"}])})
    expect(run_promote(run, tmp, fake), 0)
    log = staged_run.completed_steps(run.parent / "promoted" / run.name)
    # The log is keyed by the name `intent_records.load_all` produced, which is
    # the record's own key under the bead whose file holds it.
    expect(log["proj-a1/retitle-a1"], "proj-a1")


def case_remap_rewrites_a_close_records_investigation_path(tmp: Path) -> None:
    """A `close` names the staged investigation that argues the retirement, so
    the record must carry its promoted home once the run has moved."""
    run = staged(tmp)
    intent_records.save(run, "proj-d3", [
        {"key": "close-d3", "kind": "close", "bead": "proj-d3",
         "investigation": str(run / "investigations" / INVEST_NAME)}])
    moved, _, _ = moved_for(run)
    record = [r for r in promote.remap(intent_records.load_all(run), moved)
              if r["kind"] == "close"][0]
    expect(record["investigation"],
           str(tmp / "plans" / PROJECT / "investigations" / INVEST_NAME))


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
