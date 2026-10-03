#!/usr/bin/env python3
"""Decide whether a staged triage run is still safe to promote.

Every check here is a call into the module that already owns it —
`lint_investigation`, `lint_plan`, `plan_coverage` and `collide`. Two copies
of a check drift, and a promote-time check that disagrees with the run-time
check is worse than no check at all: it teaches the user that the gates are
advisory.

The checks run in two granularities. A stale artifact or a new collision
stops the whole run, because both mean the run's picture of the world is
wrong. A bead whose tracker state moved since the run stops only itself —
that bead is quarantined, its artifacts stay in staging, and every other bead
still promotes.

Every check is scoped to what this run will actually do. A bead the run
routed `skip` cannot block a promote, and a file the run itself already
landed is not a foreign collision — both are `run_scope` and
`promoted_targets` below, and both are what let a partially applied run be
promoted again instead of stranded.
"""

from __future__ import annotations

import contextlib
import importlib
import io
import json
import re
from datetime import datetime
from pathlib import Path

import collide
import intent_records
import manifest as manifest_io
import plan_coverage
import plan_markdown
import tracker_intents
from plan_slice_checks import FILE_HEADING, FILE_PATH
from staged_run import (Finding, PLAN_MARKERS, Usage, bead_outcomes,
                        completed_steps, ledger_rows, load_run, real_dir,
                        recorded_moves, relative_artifact, run_start,
                        staged_investigations, staged_plans, target_for)

BACKTICKED = re.compile(r"`([^`]+)`")
RUN_ROUTES = ("investigate", "plan")
# The one form `references/ledger.md` accepts, and what `date -u` prints.
STAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

# The intent kinds whose `bd` call moves the manifest bead's status, rather
# than that of one this run created — which is what the sole consumer,
# `applied_states`, extracts. `open` also runs `bd update --status`, but
# against a bead born in this promote, which no manifest row records, and
# `retitle` writes no status at all.
# `test_staged_run_checks.case_source_kinds_matches_the_intents_that_update_a_manifest_bead`
# derives this list from `tracker_intents.render` and fails when it drifts.
SOURCE_KINDS = ("investigation", "flip-source", "supersede", "close")


def run_scope(data: dict) -> list:
    """The manifest beads this run formed an intent for.

    A run decides something it will act on for exactly the two spend routes, a
    parked verdict included. A `skip` bead left the run before Wave 1 and a
    `drift-report` bead is a reporting line, so neither can be stale in a way
    that concerns a promote — and neither may block one or be quarantined by
    one.

    `dedup.SPEND_ROUTES` names the same two strings for a different question,
    where Wave 1 spends budget. Kept separate on purpose: the two answers may
    diverge, and a promote preflight has no business importing the dedup CLI.

    A bead `--ids`, `--only` or `--max` excluded keeps its manifest entry and
    its route, so the route alone is not the question — `manifest.in_run` is.
    Without it an excluded bead cost a `bd show` this docstring says it must
    not, and an unrelated tracker move on it quarantined the bead and stranded
    the whole promote.
    """
    return [b for b in data.get("beads", []) or []
            if b.get("id") and b.get("route") in RUN_ROUTES
            and manifest_io.in_run(b)]


def promoted_targets(outcomes: dict, plans_dir, project: str) -> set:
    """Where this run's own artifacts land, `_vN` siblings included.

    A resumed promote sees its own first-pass output sitting in `todo/`: newer
    than `run_start` because `shutil.move` preserves mtime, and full of the
    source paths the staged footprints name. Nothing on disk marks those files
    as ours, so they are derived the way the move derives them — `target_for`
    per artifact, plus the `_vN` names `promote.unique_target` picks when a
    sibling already exists.
    """
    out = set()
    for outcome in outcomes.values():
        for raw in outcome.get("artifacts") or []:
            target = target_for(plans_dir, project, Path(raw))
            out.add(target)
            out.update(target.parent.glob(f"{target.stem}_v[0-9]*{target.suffix}"))
    return out


def is_ours(path: Path, targets: set) -> bool:
    """True when `path` is one of this run's promoted targets, or inside one."""
    return any(target == path or target in path.parents for target in targets)


def _lint(module_name: str, argv: list) -> dict:
    """Run a sibling linter in process and read its `--json` payload."""
    module = importlib.import_module(module_name)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = module.main(argv + ["--json"])
    if code == 2:
        raise Usage(f"{module_name} could not read {argv[0]}")
    return json.loads(buf.getvalue() or "{}")


def relint(run_dir: Path, repo_root) -> list:
    """Re-run tier 1 over the staged artifacts, reusing the linters as they are.

    A run that passed quality control days ago may have gone stale: the code
    its citations point at moves, and a plan's parent link can be broken by an
    unrelated edit.

    `--root` names the *staging* directory, because the artifact has not moved
    yet — judging its location against the promoted home would fail every
    healthy run, and the promoted home is judged by `target_collisions`
    instead. `--no-tree-check` for the same reason: a working tree the user
    edited since the run is not evidence that a staged artifact went stale,
    while its citations, which are, are still checked.
    """
    out = []
    repo = str(repo_root)
    invest = run_dir / "investigations"
    if staged_investigations(run_dir):
        payload = _lint("lint_investigation", [str(invest), "--repo", repo,
                                               "--root", str(invest), "--no-tree-check"])
        out += [Finding(f["severity"], f["code"], f["artifact"], f["detail"])
                for f in payload.get("findings", [])]
    for artifact in staged_plans(run_dir):
        payload = _lint("lint_plan", [str(artifact), "--project-root", repo])
        out += [Finding("error" if f["severity"] == "error" else "warning",
                        f["check"], str(artifact), f["reason"])
                for f in payload.get("findings", []) if f["severity"] != "skip"]
    return out


def target_collisions(run_dir: Path, plans_dir, project: str) -> list:
    """A plan landed under the promoted name while this run sat staged."""
    return [Finding("error", "promote-target-exists", str(staged),
                    f"{target_for(plans_dir, project, staged)} already exists")
            for staged in staged_plans(run_dir)
            if target_for(plans_dir, project, staged).exists()]


def coverage_collisions(data: dict, outcomes: dict, plans_dir) -> list:
    """A bead this run planned that a plan already in todo/ or done/ claims."""
    ids = [b["id"] for b in run_scope(data)]
    known = {(record.get("id"), cite.get("path"))
             for record in data.get("covered", []) or []
             for cite in record.get("citations", []) or []}
    own = promoted_targets(outcomes, plans_dir, data["project"])
    out = []
    for bead, citations in plan_coverage.scan_plan_coverage(
            plans_dir, data["project"], ids).items():
        fresh = [c for c in citations
                 if (bead, c["path"]) not in known
                 and not is_ours(Path(c["path"]), own)]
        if not fresh:
            continue
        if plan_coverage.coverage_action(fresh) == "drop":
            severity, code = "error", "promote-bead-already-planned"
        else:
            severity, code = "warning", "promote-bead-mentioned"
        out.append(Finding(severity, code, bead,
                           f"{fresh[0]['path']} — {fresh[0]['how']}"))
    return out


def declared_files(text: str) -> list:
    """The files a plan says it touches — never the ones it merely cites.

    Three sources, unioned: the Component Decomposition table's component
    column, the `## Files Created` / `## Files Modified` record, and a slice's
    `### File:` headings. The plan corpus states its work in those and quotes
    evidence everywhere else, so the union is what the plan claims and the rest
    of the file is what it argues from. `plan_slice_checks.check_phase_thresholds`
    counts the same two latter sources for its re-slice threshold; the component
    table is added here because it is the one source a plan carries *before*
    execution fills the record in, which is the state every landed plan a
    promote meets is in.

    A file declaring nothing contributes nothing. A master plan holds its
    phases' work rather than its own, and a plan whose paths live only in prose
    is making an argument, not a claim.
    """
    lines = text.splitlines()
    out = set()
    found = plan_markdown.section(lines, "Component Decomposition")
    if found:
        grid = plan_markdown.table(lines, found[0], found[1],
                                   ("component", "responsib"))
        if grid:
            head, rows = grid
            for _, cells in rows:
                out.update(BACKTICKED.findall(
                    plan_markdown.cell(head, cells, "component")))
    for name in ("Files Created", "Files Modified"):
        out.update(BACKTICKED.findall("\n".join(plan_markdown.body(lines, name))))
    for line in plan_markdown.body(lines, "Implementation"):
        heading = FILE_HEADING.match(line)
        if heading:
            out.add(heading.group(1))
    return sorted(p for p in out if FILE_PATH.match(p))


def footprint_collisions(run_dir: Path, data: dict, outcomes: dict, plans_dir) -> list:
    """Staged footprints against plans that landed in todo/ after the run began.

    The comparison is `collide.build_graph`, not a second implementation of
    it: a landed plan becomes a footprint whose files are the ones it declares
    it touches, and an edge to a staged bead is the collision. A new collision
    is a hard stop, never a merge — merging is a Wave 3 decision made with
    every footprint in hand, and one made here would have exactly one.

    Both halves of the graph therefore mean the same thing. A Wave 3 footprint
    is the file set a bead's approved fix touches, so a landed half assembled
    from every path token in the file compared approved work against prose:
    four collisions on one live promote, all of them against a plan that
    declared ten files and none of the three it was accused of sharing.
    """
    path = run_dir / "footprints.json"
    staged = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []
    if not staged:
        return []
    ours = {collide._bead_id(f) for f in staged}
    start = run_start(run_dir, data)
    own = promoted_targets(outcomes, plans_dir, data["project"])
    landed = []
    for plan in sorted(real_dir(plans_dir, data["project"], "todo").rglob("*.md")):
        if plan.stat().st_mtime <= start or is_ours(plan, own):
            continue
        text = plan.read_text(encoding="utf-8", errors="replace")
        files = declared_files(text)
        if files:
            landed.append({"bead": str(plan), "files": [{"path": p} for p in files]})
    graph = collide.build_graph(staged + landed)
    return [Finding("error", "promote-footprint-collision", bead,
                    f"{other} shares {', '.join(edge['files'])}")
            for bead in ours for other, edge in graph.get(bead, {}).items()
            if other not in ours]


def applied_states(intents: list, done: dict) -> dict:
    """The state this run's own already-applied intents left each source bead in.

    A first pass that flipped its source bead and then died leaves that bead
    `open` while the manifest still records `needs-plan`. Compared against the
    manifest alone that reads as drift, so the rerun quarantines the bead — and
    `promote._close` never closes out while one is set. The run is then stranded
    over a change the run itself made, which is the one thing resumability
    cannot survive.

    The status is read back off `tracker_intents.render` rather than restated
    here. A second copy of "flip-source means open" drifts from the renderer
    that actually writes it, and this check would then excuse the wrong status.

    Three record shapes are skipped rather than raised on, and all three are
    `invalid_intents` above to report — it runs first, so the finding is
    already computed by the time this reader would have died on the record.
    One is not an object, one names no key, and one carries a relative path
    that `render` now refuses; none of them can be an intent this run already
    applied, because a first pass wrote none of them. Without the guards a
    store holding one crashed `preflight` — `AttributeError`, `KeyError`, and
    a `Usage` that `promote.main` turns into exit 2, the code reserved for a
    usage or environment error and never a bad artifact. A report replaced by
    a traceback is the failure `intent_records.py:12-20` states the rule
    against.
    """
    out = {}
    for intent in intents or []:
        if not isinstance(intent, dict) or intent.get("kind") not in SOURCE_KINDS \
                or intent.get("key") not in done \
                or tracker_intents.relative_paths(intent):
            continue
        argv = tracker_intents.render(intent, {}, {}).argv
        out[intent["bead"]] = argv[argv.index("--status") + 1]
    return out


def bead_states(data: dict, intents: list, outcomes: dict, repo_root, runner,
                done: dict) -> tuple:
    """The one per-bead stop: a bead whose state moved without this run.

    Someone closed it, or re-planned it by hand, and either way this run's
    intent for it is stale. Quarantine is recorded in the ledger, so a rerun
    after the human resolves it finishes the job.

    The comparison is against what the run has already applied, not the
    manifest snapshot alone — see `applied_states`. The excuse is one exact
    status, so a bead someone else moved *after* our write is still caught.

    `replanned` needs no such excuse: a parked bead is one whose worker produced
    nothing, so the run holds no intent for it and cannot have written the
    marker it looks for.

    Only the beads in `run_scope` are asked about. A quarantine strands the
    whole run, so a bead the run has no intent for must not be able to raise
    one, and must not cost a `bd show` either.
    """
    findings, quarantined = [], set()
    applied = applied_states(intents, done)
    for bead in run_scope(data):
        code, out = runner(["bd", "show", bead["id"], "--json"], repo_root)
        records = json.loads(out or "[]") if code == 0 else []
        if not records:
            findings.append(Finding("error", "promote-bead-missing", bead["id"],
                                    "no longer in the tracker"))
            quarantined.add(bead["id"])
            continue
        record = records[0]
        expected = applied.get(bead["id"], bead.get("status"))
        parked = outcomes.get(bead["id"], {}).get("final") == "parked"
        notes = record.get("notes") or ""
        replanned = parked and any(marker in notes for marker in PLAN_MARKERS)
        if record.get("status") == expected and not replanned:
            continue
        findings.append(Finding(
            "error",
            "promote-parked-bead-moved" if parked else "promote-bead-state-changed",
            bead["id"],
            f"recorded {expected}, now {record.get('status')}"))
        quarantined.add(bead["id"])
    return findings, quarantined


def intentless_artifacts(data: dict, outcomes: dict, intents: list,
                         done: dict) -> tuple:
    """A bead whose pending artifacts no record of ours would ever name.

    The mirror of `promote.missing_artifacts`: that one asks whether every
    artifact an outcome names exists on disk, and nothing asked whether
    anything in the tracker will point at it once it lands. So a duplicate
    bead's investigation landed in the user's real `investigations/` with
    nothing pointing at it, and the run reported success.

    Keyed on the bead rather than the artifact, because a `planned` bead's
    Wave 2 investigation legitimately moves under a `flip-source` record that
    names its plan instead — measured, six of the one real promote's twelve
    moves. Scoped to `run_scope`, because a quarantine strands the whole run
    and a bead this run formed no intent for must not be able to raise one.

    A recorded move clears it: the promote log is already the run's memory of
    an artifact that landed, so a promoter who elects to keep the file moves
    that one file, records the move, and the rerun passes.

    Reading the store is strictly stronger than reading
    `derive_intents.OUTCOME_KIND`: it also catches a bead whose outcome does
    map to a kind but whose artifact `derive_intents._artifact` could not
    match, so no record was written at all.
    """
    recorded = recorded_moves(done)
    # The beads some record of ours already names, read in one pass over the
    # store rather than one scan per bead — the shape `applied_states` uses,
    # and it skips a member that is not an object for the same reason:
    # `invalid_intents` runs first and has already named it.
    sourced = {record["bead"] for record in intents or []
               if isinstance(record, dict)
               and record.get("kind") in SOURCE_KINDS and record.get("bead")}
    findings, beads = [], set()
    for bead in run_scope(data):
        bid = bead["id"]
        pending = [a for a in outcomes.get(bid, {}).get("artifacts") or []
                   if a not in recorded]
        if not pending or bid in sourced:
            continue
        findings.append(Finding("error", "promote-intentless-artifact", bid,
                                f"{pending[0]} would move with no record"
                                " retiring, parking or planning this bead"))
        beads.add(bid)
    return findings, beads


def _stamp(value: str):
    """The row's UTC timestamp, or `None` when the cell does not hold one."""
    try:
        return datetime.strptime(value, STAMP_FORMAT)
    except ValueError:
        return None


def ledger_times(run_dir: Path) -> list:
    """Rows whose two timestamps cannot both be believed.

    `references/ledger.md` rests the ledger's audit value on these two columns:
    a `returned` before its own `dispatched` means the row's artifact was not
    produced by that dispatch, and that reading holds only while the values are
    measured rather than typed.

    This cannot catch an invented stamp that happens to be ordered — nothing
    can, from outside the run. It catches the two shapes typing actually
    produces: a reversed pair, and a cell in the wrong format, which is the bare
    date the same reference already forbids. A cell that fails to parse is
    reported rather than skipped; skipping is how a rule stops binding while the
    check still reports green.
    """
    out = []
    for row in ledger_rows(run_dir):
        subject = f"{row.get('bead') or '?'} wave {row.get('wave')}"
        stamps, bad = {}, None
        for column in ("dispatched", "returned"):
            value = (row.get(column) or "").strip()
            # An empty `returned` is a row still in flight — the shape the
            # resume protocol reads, never a promote-time defect.
            if column == "returned" and not value:
                continue
            stamps[column] = _stamp(value)
            if stamps[column] is None and bad is None:
                bad = (column, value)
        if bad:
            out.append(Finding("error", "promote-ledger-bad-timestamp", subject,
                               f"{bad[0]} is {bad[1]!r}, not {STAMP_FORMAT}"))
        elif len(stamps) == 2 and stamps["returned"] < stamps["dispatched"]:
            out.append(Finding("error", "promote-ledger-out-of-order", subject,
                               f"returned {row['returned']} precedes dispatched "
                               f"{row['dispatched']}"))
    return out


def ledger_artifacts(run_dir: Path) -> list:
    """Rows whose `artifact` cell is not the absolute path the ledger says.

    `references/ledger.md`'s column table specifies "absolute path inside the
    run directory", and `ledger_row` now refuses to write anything else — but
    a cell typed straight into `ledger.md` never passes through `ledger_row`
    at all, and that is the shape this incident had: `derive_intents` read a
    run-relative cell and the path reached a bead note as
    `Plan: todo/....md`, which resolves from neither the repo root nor any
    documented base.

    Shape only, never location. An absolute path inside the run directory is
    correct before the move and stale after it, and the second question is
    `promote.stale_intents`', not this one.

    An unfilled cell and `—` pass, through the one reader of that sentinel: a
    Wave 4 decision record writes `artifact` `—` deliberately, and reading it
    as a relative path is how a check breaks the row kind that already
    stranded a resume once. Everything else is reported rather than skipped;
    skipping is how a rule stops binding while the check still reports green.
    """
    out = []
    for row in ledger_rows(run_dir):
        bad = relative_artifact(row)
        if bad:
            out.append(Finding(
                "error", "promote-ledger-relative-artifact",
                f"{row.get('bead') or '?'} wave {row.get('wave')}",
                f"artifact path is not absolute: {bad}"))
    return out


def invalid_intents(run_dir: Path) -> list:
    """Every finding the record schema has against the run's stored intents.

    Not "what `render` cannot consume", which is the narrower set: `validate`
    is deliberately stricter — `REQUIRED["create-epic"]` demands `master`
    while `notes_for` would still render a record carrying only `plan`. The
    schema is the single answer to what a stored record may look like, so a
    record it reports stops the run even where the renderer would have coped.
    The store is read here rather than passed in, for the reason `preflight`'s
    docstring gives: what an earlier pass already applied is part of the run's
    state on disk, and a caller that forgot to hand it over would quietly get
    the pre-resume answer. It costs a second read of a handful of small JSON
    files and keeps this check callable on its own.

    `validate`'s finding strings are carried through verbatim — they already
    name the offending field in the wording `intent_records` chose, and
    re-cutting them here would be a second copy of that vocabulary. The
    `<no key>` placeholder is `validate`'s own, so the two agree on what an
    unkeyed record is called.
    """
    out = []
    for record in intent_records.load_all(run_dir):
        key = record.get("key") if isinstance(record, dict) else None
        for problem in intent_records.validate(record):
            out.append(Finding("error", "promote-intent-invalid",
                               key or "<no key>", problem))
    return out


def preflight(run_dir, plans_dir, repo_root, runner=None) -> tuple:
    """Every check that must pass before anything moves.

    Returns `(findings, quarantined)`. Per-bead stops are separated out
    because a changed bead quarantines only itself.

    The ledger and the intent store are read here rather than passed in, the
    way `footprint_collisions` reads `footprints.json`: what an earlier pass
    already applied is part of the run's state on disk, and a caller that
    forgot to hand it over would quietly get the pre-resume answer. Both are
    read once and handed to the two per-bead stops.
    """
    run_dir = Path(run_dir)
    data = load_run(run_dir)
    outcomes = bead_outcomes(run_dir, data)
    intents = intent_records.load_all(run_dir)
    done = completed_steps(run_dir)
    findings = (relint(run_dir, repo_root)
                + target_collisions(run_dir, plans_dir, data["project"])
                + coverage_collisions(data, outcomes, plans_dir)
                + footprint_collisions(run_dir, data, outcomes, plans_dir)
                + ledger_times(run_dir)
                + ledger_artifacts(run_dir)
                + invalid_intents(run_dir))
    state, quarantined = bead_states(
        data, intents, outcomes, repo_root,
        runner or tracker_intents.default_runner, done)
    orphan_findings, orphans = intentless_artifacts(data, outcomes, intents, done)
    return findings + state + orphan_findings, quarantined | orphans
