#!/usr/bin/env python3
"""Move a staged triage run into the real plan directories.

This is the only code in the triage system that writes outside a run
directory, and it is never automatic in v1: a human invokes it after reading
the run's report.

Everything a run produces stays discardable until this script runs, which is
why the system-plan mirrors and every tracker note are deferred to here. Both
embed absolute paths: a mirror written during the run would point into a
temporary directory, and a bead note written during the run would send
`execute` to a path `discard` can delete. Deferring both is what keeps the
discard invariant true.

The run is resumable. Each step records its completion in the run's
`ledger.md` under a stable key, and a rerun skips what already landed — that
is the whole resume mechanism, and there is no `--resume` flag.

The sequence: preflight (`staged_run_checks`), move, rewrite, mirrors, apply
tracker intents (`tracker_intents`), write the created IDs back into the
promoted plans, close out.

The run's intents are read from `{run}/intents/` (`intent_records`), never
from the manifest: `manifest.json` is what the run decided, and an intent is
something it did.

**Why this is one module:** 300 code lines by `run_arch_gate.py`'s count, plus
123 of doc prose — at the 300 signal exactly, which passes and owes no waiver,
but leaves nothing: the next code line added here owes either a split or a
`**LOC waiver:**`. What once put it over was argument plumbing — `plans_dir`,
`repo_root` and the mirror root became command arguments, each threaded
through the sequence rather than read out of the run's manifest. That is one
responsibility's worth of parameters, not a second responsibility. One
candidate split was considered and rejected: moving `write_mirrors` and
`_backlink` into their own module gives a ~40-line file whose only caller is
`promote()` and whose only test runs through it — the single-caller satellite
`_shared/architecture-principles.md` names as the dominant smell.

The write-back spent the headroom, and it is the block to move when that next
line arrives: five functions under one section banner, called from one place,
with cases in `test_promote.py` that already address them directly rather than
through `promote()`. That makes it the one split here whose new module would
pass the Meaningfulness Test on the `single-caller + own test` form, and it
would take `test_promote.py` back under the signal with it. It is left inline
because nothing needs the room yet and this epic's approved plan put it here —
not because the numbers still argue for it.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import intent_records  # noqa: E402
import plan_coverage  # noqa: E402
import staged_run  # noqa: E402
import tracker_intents  # noqa: E402
from staged_run import Finding, Usage, real_dir, target_for  # noqa: E402
from staged_run_checks import preflight  # noqa: E402

EPILOG = """\
finding codes (error stops the promote, warning only reports):
  error    promote-target-exists, promote-bead-already-planned,
           promote-footprint-collision, promote-bead-state-changed,
           promote-parked-bead-moved, promote-bead-missing,
           promote-artifact-missing, promote-stale-path, promote-mirror-exists,
           promote-notes-unverified, promote-intent-incomplete,
           promote-intentless-artifact, promote-writeback-incomplete
           plus every error lint_investigation.py and lint_plan.py report
  warning  promote-bead-mentioned, and every linter warning

exit codes:
  0  promoted clean, or --dry-run with nothing to report
  1  findings: a preflight stop, a quarantined bead, or an incomplete apply
  2  usage or environment error only — never a bad artifact
"""

MIRROR = "# {title}\n\nFull plan: `{plan}`\n"
BACKLINK = "**System plan file:** {mirror}"


# --- steps 4 and 5: move, then rewrite --------------------------------------


def rewrite_paths(text: str, old_root: str, new_root: str) -> str:
    """Replace `old_root` only where it is a genuine path prefix, so that
    `/runs/r1/todo` never rewrites inside `/runs/r1/todo_backup`."""
    pattern = re.escape(old_root.rstrip("/")) + r"(?=/|[^A-Za-z0-9_./-]|$)"
    return re.sub(pattern, new_root.rstrip("/"), text)


def unique_target(target: Path) -> Path:
    """`investigate` Step 5a's rule, applied against the real directory — the
    only place that can see every sibling. Prior investigations are evidence,
    so a colliding name takes `_v2`, `_v3`, … and never overwrites."""
    if not target.exists():
        return target
    version = 2
    while (target.parent / f"{target.stem}_v{version}{target.suffix}").exists():
        version += 1
    return target.parent / f"{target.stem}_v{version}{target.suffix}"


def _artifacts_to_promote(outcomes: dict, quarantined: set):
    """Every artifact a still-promoting bead names, with the bead that names it."""
    for bead, outcome in outcomes.items():
        if bead in quarantined:
            continue
        for raw in outcome.get("artifacts") or []:
            yield bead, Path(raw)


def move_map(outcomes: dict, quarantined: set, plans_dir, project: str,
             done: dict = None) -> list:
    """Staged artifact to promoted target, for every bead that still promotes.

    A rerun finds the staged file gone because the first pass moved it. The
    ledger is what remembers where, so a recorded move is replayed as a pair
    instead of dropped — dropping it is what let a rerun write a run-directory
    path into a bead note.

    The replay is checked before `exists`, which is also what stops
    `unique_target` inventing a `_v2` target for an artifact that already
    promoted under its own name.

    Longest source first, so a specific renamed file is substituted before the
    directory prefix that contains it. The map is keyed by the staged path, so
    a group plan several beads own yields one pair rather than one per owner.
    """
    recorded = staged_run.recorded_moves(done)
    pairs = {}
    for _, staged in _artifacts_to_promote(outcomes, quarantined):
        old = str(staged)
        if old in recorded:
            pairs[old] = recorded[old]
        elif staged.exists():
            pairs[old] = str(unique_target(target_for(plans_dir, project, staged)))
    return sorted(pairs.items(), key=lambda pair: len(pair[0]), reverse=True)


def missing_artifacts(outcomes: dict, quarantined: set, moved: list) -> list:
    """Every artifact a promoting bead names that neither exists on disk nor
    carries a recorded move. Skipping one silently leaves its intents holding
    run-directory paths, which is the failure this module exists to prevent."""
    mapped = {old for old, _ in moved}
    return [Finding("error", "promote-artifact-missing", bead,
                    f"no such staged artifact: {staged}")
            for bead, staged in _artifacts_to_promote(outcomes, quarantined)
            if str(staged) not in mapped]


def stale_intents(intents: list, run_dir: Path) -> list:
    """`_rewrite_file`'s guarantee, applied to what the intents carry.

    The moved files and the intents are two independent copies of the same
    paths. Checking only the files is what let a rerun write a run-directory
    path into a bead note with every file on disk correct.
    """
    findings = []
    for intent in intents:
        for key in tracker_intents.PATH_KEYS:
            value = intent.get(key)
            if value and str(run_dir) in str(value):
                findings.append(Finding("error", "promote-stale-path",
                                        f"{intent.get('key')}.{key}",
                                        f"still names {run_dir}"))
    return findings


def remap(intents: list, moved: list) -> list:
    """Rewrite the staged paths an intent carries into their promoted homes."""
    out = []
    for intent in intents:
        copy = dict(intent)
        for key in tracker_intents.PATH_KEYS:
            for old, new in moved:
                if copy.get(key):
                    copy[key] = rewrite_paths(copy[key], old, new)
        out.append(copy)
    return out


def promote_artifacts(run_dir, outcomes: dict, quarantined: set, plans_dir,
                      project: str, done: dict = None) -> tuple:
    """Move the staged artifacts, then rewrite every absolute path inside them.

    The move map is the only source of pairs. There is deliberately no
    catch-all — not for the run root, and not scoped to `investigations/` or
    `todo/` either, which is the form that slipped through: a quarantined
    bead's file stays staged, so a sibling's citation to it maps nowhere, and
    a subdirectory pair rewrote it to a real directory that never received it.
    A catch-all invents a target for a path nothing moved, and the rewritten
    text no longer names the run root, so the guard below cannot see it.
    Anything still naming the run root after the rewrite is
    `promote-stale-path`, which stops the run before any `bd` write — a bead
    note pointing into a run directory is exactly the failure this command
    exists to prevent.

    Nothing moves until every artifact has a pair, and a move already in the
    ledger is not repeated: that is what makes a rerun a no-op on disk rather
    than a move of an already-moved path.
    """
    run_dir = Path(run_dir)
    moved = move_map(outcomes, quarantined, plans_dir, project, done)
    missing = missing_artifacts(outcomes, quarantined, moved)
    if missing:
        return [], missing
    recorded = staged_run.recorded_moves(done)
    for old, new in moved:
        if old in recorded:
            continue
        Path(new).parent.mkdir(parents=True, exist_ok=True)
        shutil.move(old, new)
        staged_run.record_step(run_dir, staged_run.MOVE_PREFIX + old, new)
    findings = []
    for path in promoted_md(moved):
        findings += _rewrite_file(path, moved, run_dir)
    return moved, findings


def promoted_md(moved: list) -> list:
    """Every promoted markdown file the move produced.

    One expansion, two readers: the path rewrite below and the write-back's
    own sweep. A target is a file or a plan folder, and only the folder case
    needs walking — which is exactly the distinction a second copy of this
    loop got wrong once already.
    """
    out = []
    for _, new in moved:
        target = Path(new)
        out += sorted(target.rglob("*.md")) if target.is_dir() else [target]
    return [path for path in out if path.suffix == ".md"]


def _rewrite_file(path: Path, pairs: list, run_dir: Path) -> list:
    text = original = path.read_text(encoding="utf-8")
    for old, new in pairs:
        text = rewrite_paths(text, old, new)
    if text != original:
        path.write_text(text, encoding="utf-8")
    if str(run_dir) in text:
        return [Finding("error", "promote-stale-path", str(path),
                        f"still names {run_dir}")]
    return []


# --- step 6: the system-plan mirrors ----------------------------------------


def write_mirrors(moved: list, plans_dir, project: str, system_plan_dir) -> list:
    """`~/.claude/plans/{slug}.md` plus the plan's back-link to it, per
    `plan/references/conventions.md`. Written here and not during the run
    because the mirror records an absolute path, and during the run the only
    absolute path available points inside a discardable directory."""
    system = Path(system_plan_dir)
    todo, findings = real_dir(plans_dir, project, "todo"), []
    for _, new in moved:
        target = Path(new)
        plan = target / "plan.md" if target.is_dir() else target
        if target.parent != todo or not plan.is_file():
            continue
        mirror = system / f"{target.stem if target.is_file() else target.name}.md"
        if mirror.is_file() and str(plan) not in mirror.read_text(encoding="utf-8"):
            findings.append(Finding("error", "promote-mirror-exists", str(mirror),
                                    "points at another plan"))
            continue
        system.mkdir(parents=True, exist_ok=True)
        mirror.write_text(MIRROR.format(title=mirror.stem.replace("_", " "),
                                        plan=plan), encoding="utf-8")
        _backlink(plan, mirror)
    return findings


def _backlink(plan: Path, mirror: Path) -> None:
    """One back-link per plan: an existing line is replaced, never duplicated —
    a plan drafted from a template carries a placeholder mirror path."""
    text = plan.read_text(encoding="utf-8")
    link = BACKLINK.format(mirror=mirror)
    if link in text:
        return
    lines = text.splitlines(keepends=True)
    old = next((i for i, line in enumerate(lines)
                if line.startswith("**System plan file:**")), None)
    if old is not None:
        lines[old] = link + "\n"
    else:
        cut = next((i + 1 for i, line in enumerate(lines)
                    if line.startswith("**Status:**")), 1)
        lines.insert(cut, link + "\n")
    plan.write_text("".join(lines), encoding="utf-8")


# --- step 8: the write-back -------------------------------------------------


WRITE_BACK = re.compile(r"<bead:([A-Za-z0-9][A-Za-z0-9_.-]*)>")
CREATE_KINDS = ("create-epic", "create-task")


def write_back(intents: list, applied: dict, moved: list) -> list:
    """Substitute each created bead ID into the plan files its intent names.

    `plan` Step 8c's `**Update plan files:**` half, which moved nowhere when
    the `bd create` half moved into this module. It runs after the apply
    because the IDs do not exist before it, and before `_close` because an
    unresolved token has to leave the run staged.

    Names are grouped by owning bead: `intent_records.load_all` qualifies a
    `ref` as `<bead>/<name>`, while the token in the file carries the local
    name the planning worker wrote, so two groups may each own an `epic`.

    `moved` is required rather than defaulted: the sweep it drives is the only
    reader of a promoted file no intent names, and a caller that omitted it
    would ship exactly the token this function exists to catch.
    """
    owners: dict = {}
    for intent in intents:
        if intent.get("kind") not in CREATE_KINDS or not applied.get(intent["key"]):
            continue
        ids, paths = owners.setdefault(intent.get("bead", ""), ({}, set()))
        ids[intent["ref"].rpartition(intent_records.QUALIFIER)[2]] = applied[intent["key"]]
        paths.update(str(p) for p in (intent.get("master"), intent.get("slice"),
                                      intent.get("plan")) if p)
    findings, seen = [], set()
    for ids, paths in owners.values():
        for path in sorted(paths):
            seen.add(str(Path(path)))
            findings += _substitute(Path(path), ids)
    return findings + _unnamed(intents, applied) + _orphans(moved, seen)


def _substitute(path: Path, ids: dict) -> list:
    """Resolve every token in one promoted file. Rewriting a resolved file is
    a no-op, which is what makes a rerun idempotent without a ledger key."""
    if not path.is_file():
        return [Finding("error", "promote-writeback-incomplete", str(path),
                        "an intent names a file that does not exist")]
    text = original = path.read_text(encoding="utf-8")
    text = WRITE_BACK.sub(lambda m: ids.get(m.group(1)) or m.group(0), text)
    if text != original:
        path.write_text(text, encoding="utf-8")
    left = sorted(set(WRITE_BACK.findall(text)))
    if left:
        return [Finding("error", "promote-writeback-incomplete", str(path),
                        "unresolved token(s): " + ", ".join(left))]
    return []


def _unnamed(intents: list, applied: dict) -> list:
    """Per intent, the file it names must now carry its ID — a token nobody
    wrote is silent under the pass above, and that is the original defect."""
    out = []
    for intent in intents:
        bead = applied.get(intent["key"]) if intent.get("kind") in CREATE_KINDS else None
        target = Path(intent.get("slice") or intent.get("master")
                      or intent.get("plan") or "")
        if not bead or not target.is_file():
            continue
        text = target.read_text(encoding="utf-8")
        # A slice's ownership field is the one `plan_coverage` reads, so for a
        # task the ID has to sit there and not merely somewhere. Reading it
        # through that module rather than matching the field here is what keeps
        # one grammar: `plan_slice_checks` asks only that `**Beads task:**`
        # appear in the slice, so a dressed or indented field lints clean and
        # a second stricter reader would stop the promote on a sound artifact.
        found = (any(plan_coverage.citation_form(line, bead) == "beads-task"
                     for line in text.splitlines())
                 if intent.get("slice") else bead in text)
        if not found:
            out.append(Finding("error", "promote-writeback-incomplete", str(target),
                               f"never names {bead}"))
    return out


def _orphans(moved: list, seen: set) -> list:
    """A leftover token in a promoted plan file no `create-*` intent names.

    Reported, never substituted: the ids belong to an owning bead, and a file
    outside every intent has no owner to borrow them from. Without this pass
    the token ships — nothing resolves it and nothing complains — which is the
    same silent exit 0 the write-back exists to end, one file over.

    Investigations are out of scope, by the same `parent.name` test
    `staged_run.target_for` sorts promoted artifacts with. `investigation` is a
    `PATH_KEYS` field but not one the substitution runs over, so a token in an
    investigation can never resolve — in this run or in a rerun — and the only
    reachable case is prose: an investigation whose subject is this tooling
    quoting the filled-in token form. Reporting it would stop a sound promote
    with no escape but hand-editing the evidence artifact.
    """
    out = []
    for path in promoted_md(moved):
        if (path.parent.name == "investigations" or str(path) in seen
                or not path.is_file()):
            continue
        left = sorted(set(WRITE_BACK.findall(path.read_text(encoding="utf-8"))))
        if left:
            out.append(Finding("error", "promote-writeback-incomplete", str(path),
                               "unresolved token(s): " + ", ".join(left)))
    return out


# --- the sequence and the command line --------------------------------------


def promote(args) -> tuple:
    run_dir = staged_run.resolve_run(args.runs_dir, args.run_id)
    data = staged_run.load_run(run_dir)
    project = data["project"]
    outcomes = staged_run.bead_outcomes(run_dir, data)
    done = staged_run.completed_steps(run_dir)
    findings, quarantined = preflight(run_dir, args.plans_dir, args.repo_root)
    if [f for f in findings if f.severity == "error" and f.subject not in quarantined]:
        return findings, [], []
    if args.dry_run:
        moved = move_map(outcomes, quarantined, args.plans_dir, project, done)
        # Only the move's own errors stop here. `findings` still carries the
        # preflight errors belonging to quarantined beads, and those stop that
        # bead, not the report — the real branch promotes every other bead, so
        # a dry run must still render what it would do.
        move_findings = missing_artifacts(outcomes, quarantined, moved)
        findings += move_findings
        if move_findings:
            return findings, [], moved
    else:
        moved, move_findings = promote_artifacts(
            run_dir, outcomes, quarantined, args.plans_dir, project, done)
        findings += move_findings
        if [f for f in move_findings if f.severity == "error"]:
            return findings, [], moved
        findings += write_mirrors(moved, args.plans_dir, project,
                                  args.system_plan_dir)
        staged_run.record_step(run_dir, "move", f"{len(moved)} artifact(s)")
    intents = [i for i in remap(intent_records.load_all(run_dir), moved)
               if i.get("bead") not in quarantined]
    stale = stale_intents(intents, run_dir)
    if stale:
        return findings + stale, [], moved
    keys = {i["key"] for i in intents}
    result = tracker_intents.apply_intents(
        intents, args.repo_root, dry_run=args.dry_run,
        completed={k: v for k, v in done.items() if k in keys})
    findings += result.findings
    if not args.dry_run:
        findings += write_back(intents, result.applied, moved)
        _close(run_dir, args, done, result, findings, quarantined)
    return findings, result.commands, moved


def _close(run_dir, args, done, result, findings, quarantined) -> None:
    for key, bead in result.applied.items():
        if key not in done:
            staged_run.record_step(run_dir, key, bead or "")
    if not quarantined and not [f for f in findings if f.severity == "error"]:
        staged_run.close_out(run_dir, Path(args.runs_dir))


def report(findings: list, commands: list, moved: list, as_json: bool) -> int:
    errors = [f for f in findings if f.severity == "error"]
    if as_json:
        print(json.dumps({
            "errors": len(errors),
            "warnings": len(findings) - len(errors),
            "moves": [f"{old} -> {new}" for old, new in moved],
            "commands": [" ".join(argv) for argv in commands],
            "findings": [f._asdict() for f in findings]}, ensure_ascii=False))
        return 1 if errors else 0
    for old, new in moved:
        print(f"MOVE   {old} -> {new}")
    for argv in commands:
        print(" ".join(argv))
    for f in sorted(findings, key=lambda f: (f.severity, f.code, str(f.subject))):
        print(f"{'ERROR' if f.severity == 'error' else 'WARN':<5}  "
              f"{f.code:<32}  {f.subject}  {f.detail}")
    print(f"\npromote: {len(errors)} error(s), {len(findings) - len(errors)} warning(s)")
    return 1 if errors else 0


def parse_args(argv: list):
    parser = argparse.ArgumentParser(
        prog="promote.py", epilog=EPILOG,
        description="Move a staged triage run into the real plan directories.",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run-id", required=True,
                        help="run directory name, or its short random suffix")
    parser.add_argument("--runs-dir", default=".", help="the project's staging folder")
    parser.add_argument("--plans-dir", required=True,
                        help="the plans root holding {project}/todo and {project}/investigations")
    parser.add_argument("--repo-root", required=True,
                        help="the project's repository, where every bd call runs")
    parser.add_argument("--system-plan-dir", required=True,
                        help="the system plan mirror directory, e.g. ~/.claude/plans")
    parser.add_argument("--dry-run", action="store_true",
                        help="report the ordered bd commands and move nothing")
    parser.add_argument("--json", action="store_true", dest="as_json",
                        help="emit one JSON object instead of the human report")
    return parser.parse_args(argv)


def main(argv: list) -> int:
    try:
        args = parse_args(argv)
        findings, commands, moved = promote(args)
    except (Usage, intent_records.IntentStoreError) as exc:
        # A store that will not parse is an environment fault, not a finding:
        # `intent_records` gives it exit 2 and EPILOG reserves 2 for exactly
        # this. Reported as 1 it reads as a reviewable result, and it arrived
        # as a traceback, which is not a report at all.
        print(f"promote: {exc}", file=sys.stderr)
        return 2
    return report(findings, commands, moved, args.as_json)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
