#!/usr/bin/env python3
"""The intent records a run can build from its own record.

Five of the nine kinds are facts the run already holds: a parked bead's
investigation, a planned or merged bead's plan, the ordering `collide.py`
decided, the source bead a group's own epic replaced, and a duplicate's
retirement. A worker cannot get wrong an intent it is never asked for, so
these are generated here instead of being requested in a brief.

**This module produces records, not prose.** The notes text belongs to
`tracker_intents.notes_for`, which already templates the epic, task,
single-phase, investigation, flip, supersede and close formats from the `plan`
and `investigate` skills' own contracts. Restating any of it here would be a
second copy of a contract that lives elsewhere.

`create-epic`, `create-task`, `open` and `retitle` are not derivable — only the
worker that wrote the plan knows its phases, and only the worker that disproved
a title knows the right one. Those arrive from the worker, into the same store.

Exit 0 = every bead in the run yielded the records its outcome implies;
1 = findings, which includes a bead whose outcome no kind covers and a bead in
the run's scope the ledger holds no outcome for at all; 2 = usage or
an unreadable run.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import intent_records  # noqa: E402
import manifest as manifest_io  # noqa: E402
import plan_artifact_checks  # noqa: E402
import staged_run  # noqa: E402
import staged_run_checks  # noqa: E402
from intent_records import DERIVED_KINDS  # noqa: E402

USAGE = "usage: derive_intents.py --run-dir PATH [--manifest PATH] [--json]"

# The outcomes that map onto a kind. Everything else is reported.
# `duplicate` is one of them because the ruling is a cell in this run's own
# ledger and its reasoning is an artifact the run already staged. `merged` is
# `planned` for this purpose: `references/ledger.md` lists both in the `final`
# vocabulary, and a merged group's members are exactly the population
# `supersede` was added for — mapped to nothing, they got no record, and the
# promote gate then quarantined every one of them.
OUTCOME_KIND = {"parked": "investigation", "planned": "flip-source",
                "merged": "flip-source", "duplicate": "close"}
NO_KIND = {"": "no outcome recorded — the bead is still in flight"}


class UsageError(Exception):
    """Bad command line. Exit 2, never a finding."""


# --- what a settled outcome implies ------------------------------------------


def _artifact(outcome: dict, kind: str):
    """The staged artifact this kind's record points at, or None.

    An investigation is the file under the run's `investigations/`; a plan is
    anything else. `staged_run.target_for` keys the same distinction off the
    parent directory name, so the rule is stated once for both. `close` names
    the investigation too: it is the artifact that argues the retirement,
    exactly as `investigation` is the one that argues a park.
    """
    for raw in outcome.get("artifacts") or []:
        staged = Path(raw)
        is_investigation = staged.parent.name == "investigations"
        if is_investigation == (kind in ("investigation", "close")):
            return _plan_path(staged) if kind == "flip-source" else str(staged)
    return None


def _plan_path(staged: Path) -> str:
    """A multi-phase plan is a folder; the path a bead note carries is its
    `plan.md`. `promote.write_mirrors` applies the same rule to the same
    artifacts, and the two must not disagree about what "the plan" is."""
    return str(staged / "plan.md") if staged.is_dir() else str(staged)


def _outcome_records(outcomes: dict, superseded=()) -> tuple:
    """One record per bead whose outcome maps to a kind, in sorted bead order.

    A bead whose outcome maps to nothing is a finding naming it and its
    `final` — never a silent drop, which is the defect class this module
    exists to close.

    A superseded bead is skipped rather than flipped: the choice between
    making a source bead workable and retiring it is taken once, per bead, so
    no bead ever comes out of a derivation both flipped open and closed.
    """
    records, findings = {}, []
    for bead in sorted(outcomes):
        if bead in superseded:
            continue
        final = outcomes[bead].get("final") or ""
        kind = OUTCOME_KIND.get(final)
        if not kind:
            reason = NO_KIND.get(final, f"outcome {final!r} maps to no kind")
            findings.append(f"{bead}: {reason}")
            continue
        field = intent_records.REQUIRED[kind][-1]
        path = _artifact(outcomes[bead], kind)
        if not path:
            findings.append(f"{bead}: {final} but the run staged no {field}"
                            " artifact for it")
            continue
        records[bead] = [{"key": f"{kind}-{bead}", "kind": kind, "bead": bead,
                          field: path}]
    return records, findings


def _roster_findings(manifest: dict, outcomes: dict) -> list:
    """One finding per in-scope manifest bead the ledger holds no outcome for.

    `staged_run.bead_outcomes` builds its dict from the ledger's Wave 2 and
    Wave 4 rows, so a bead the run selected and routed but never returned one
    for yields no outcome at all — and `_outcome_records` can only report the
    beads it is given. `staged_run_checks.run_scope` is already "the manifest
    beads this run formed an intent for", and reusing it keeps one definition
    of in-the-run.

    The absent row is named rather than "no outcome recorded", which `NO_KIND`
    already spends on the in-flight bead — that one has a Wave 2 row and no
    verdict in it, which is a different thing to go and look at.
    """
    return [f"{bead['id']}: routed {bead['route']} but the ledger holds no"
            " outcome row for it"
            for bead in staged_run_checks.run_scope(manifest)
            if bead["id"] not in outcomes]


def _group_master(members: list, outcomes: dict) -> str | None:
    """The `plan.md` of the folder this group was planned into, or None.

    A multi-phase plan is a folder and `_plan_path` already names its
    `plan.md`, so being a folder is the whole extra rule here — a single-phase
    plan is one file, and so is an investigation, which is why neither can be
    mistaken for an epic's master.
    """
    for bead in members:
        for raw in outcomes[bead].get("artifacts") or []:
            staged = Path(raw)
            if staged.is_dir():
                return _plan_path(staged)
    return None


def _epic_groups(manifest: dict, outcomes: dict, stored: list) -> list:
    """Each group this run's own epic replaced: `(group_id, members, master, ref)`.

    The provenance is entirely inside the run: the members come from the
    manifest, the Wave-4 artifact from the ledger through
    `staged_run.bead_outcomes`, and the epic from the `create-epic` the
    planning worker stored under that artifact's own `plan.md`.

    Only a member the run actually planned counts. A member parked on its own
    Wave 2 verdict owes an `investigation` record instead, and retiring it
    would throw away the path that record carries.

    One planned member is enough. Every INDEPENDENT bead is a one-member
    group, and its plan is still an epic with phase tasks, so requiring two
    left exactly the workable duplicate this kind exists to prevent. The one
    self-limit is the absent `create-epic` below.
    """
    out = []
    for grp in manifest.get("groups") or []:
        members = [bead for bead in grp.get("members") or []
                   if OUTCOME_KIND.get((outcomes.get(bead) or {}).get("final"))
                   == "flip-source"]
        if not members:
            continue
        master = _group_master(members, outcomes)
        if not master:
            continue
        epic = next((r for r in stored if r.get("kind") == "create-epic"
                     and r.get("ref") and r.get("master") == master), None)
        if epic:
            out.append((grp.get("group_id"), members, master, epic["ref"]))
    return out


def _supersede_records(epic_groups: list) -> list:
    """One record per member of a group this run's own epic replaced.

    A group with no `create-epic` yields nothing, which is what leaves the
    single-phase case exactly as it is today — and is why this half reports
    nothing at all: every absence it can see is a state the run is allowed to
    be in, and a plan folder that does not parse is `lint_plan.py`'s finding.
    """
    return [{"key": f"supersede-{bead}", "kind": "supersede", "bead": bead,
             "by": ref, "master": master}
            for _, members, master, ref in epic_groups
            for bead in members]


def _phase_deps(group_id: str, master: str, stored: list) -> tuple:
    """The ordering a group's master-plan Dependency Table already states.

    Read with `plan_artifact_checks`' own table reader, which is the parser
    `lint_plan.py` runs as tier 1 on every triage plan: a table that does not
    parse fails that gate *before* promote, so this route inherits the gate
    instead of adding a failure mode. Its `cell` comes from the same module
    for the same reason — the table is read one way, in one place.

    The join is the row's Slice link against the `create-task` record's own
    staged slice path: the worker already carries that filename, so no phase
    title is parsed and no second numbering scheme exists. A row the join
    cannot resolve is a finding naming the group and the row — never a
    guessed edge.
    """
    tasks = {Path(r["slice"]).name: r for r in stored
             if r.get("kind") == "create-task" and r.get("slice")
             and r.get("ref") and r.get("bead") and r.get("master") == master}
    master_path = Path(master)
    text = (master_path.read_text(encoding="utf-8", errors="replace")
            if master_path.is_file() else "")
    found = plan_artifact_checks.dep_table(text.splitlines())
    if not found:
        return [], []
    head, rows = found
    name = master_path.name
    rowed, by_phase, records, findings = [], {}, [], []
    for line, cells in rows:
        number = re.search(r"\d+", plan_artifact_checks.cell(head, cells, "phase"))
        links = re.findall(r"\]\(([^)]+)\)",
                           plan_artifact_checks.cell(head, cells, "slice"))
        task = tasks.get(Path(links[0]).name) if links else None
        if not (number and task):
            findings.append(f"{group_id}: {name} row {line + 1} names no slice"
                            " file this run created a task for")
            continue
        by_phase[int(number.group())] = task
        rowed.append((line, task, plan_artifact_checks.parse_deps(
            plan_artifact_checks.cell(head, cells, "depends"))))
    for line, task, needs in rowed:
        for phase in sorted(needs):
            other = by_phase.get(phase)
            if not other:
                findings.append(f"{group_id}: {name} row {line + 1} depends on"
                                f" phase {phase}, which the table has no row for")
                continue
            records.append({"key": f"dep-{task['ref']}-on-{other['ref']}",
                            "kind": "dep", "bead": task["bead"],
                            "from": task["ref"], "to": other["ref"],
                            "dep_type": "blocks",
                            "why": f"phase order from {name}"})
    return records, findings


def _dep_records(manifest: dict, epic_groups: list, stored: list) -> tuple:
    """Both orderings this run holds — never recomputed, never re-parsed.

    The pre-merge pairs and their direction are `collide.py`'s decision, taken
    against the footprints this run collected. Re-deriving them from each
    group's `order` would be a second implementation of `collide._dep_intents`,
    free to disagree with the one whose reasoning the manifest records — and
    reading them back out of the command *text* would be a parser for a shape
    we control. So `collide` emits the endpoints as fields and this reads them.

    The second input is the phase chain of every group this run planned into
    an epic, from `_phase_deps`. A pre-merge edge whose two endpoints the same
    epic retired is dropped: the beads it ordered no longer carry the work, and
    the phase chain states that ordering between the tasks that do.

    `from` is the dependent, exactly as `tracker_intents.render` emits it.
    """
    records, findings = [], []
    retired = {bead: ref for _, members, _, ref in epic_groups
               for bead in members}
    for grp in manifest.get("groups") or []:
        for intent in grp.get("dep_intents") or []:
            first, second = intent.get("from"), intent.get("to")
            if not first or not second:
                findings.append(
                    f"{grp.get('group_id')}: dep intent carries no from/to —"
                    f" written before collide.py emitted them:"
                    f" {intent.get('command')!r}")
                continue
            if retired.get(first) and retired[first] == retired.get(second):
                continue
            records.append({"key": f"dep-{first}-on-{second}", "kind": "dep",
                            "bead": first, "from": first, "to": second,
                            "dep_type": "blocks",
                            "why": intent.get("why", "")})
    for group_id, _, master, _ in epic_groups:
        chain, chain_findings = _phase_deps(group_id, master, stored)
        records += chain
        findings += chain_findings
    return records, findings


def derive(run_dir, manifest: dict) -> tuple:
    """Every derivable record this run holds, grouped by the bead that owns it.

    A `dep` record lives in its `from` bead's file: a bead belongs to exactly
    one collision group, so that is unambiguous, and it reads as "this bead
    depends on that one". A phase-chain `dep` names two refs rather than two
    beads, so it lives with the `create-task` record it depends *from* —
    which is the bead the store's own filename already gives that record.

    The worker's records are read once, through `intent_records.load_all`, and
    both halves that need them take them from there: the epic a group's
    members were superseded by, and the tasks its phase chain orders.
    """
    outcomes = staged_run.bead_outcomes(run_dir, manifest)
    stored = intent_records.load_all(run_dir)
    epic_groups = _epic_groups(manifest, outcomes, stored)
    supersedes = _supersede_records(epic_groups)
    by_bead, findings = _outcome_records(
        outcomes, {record["bead"] for record in supersedes})
    findings += _roster_findings(manifest, outcomes)
    deps, dep_findings = _dep_records(manifest, epic_groups, stored)
    findings += dep_findings
    for record in supersedes + deps:
        by_bead.setdefault(record["bead"], []).append(record)
    # A finding here is a bug in this module, so it is reported rather than
    # written to disk — the store never holds a record `render` cannot consume.
    for bead in sorted(by_bead):
        bad = [f"{bead}: {problem}" for record in by_bead[bead]
               for problem in intent_records.validate(record)]
        if bad:
            findings += bad
            del by_bead[bead]
    return by_bead, findings


def _merged(existing: list, derived: list) -> list:
    """Derived kinds replace; everything else survives.

    A bead's file is one list, and the worker-written `create-*` and `open`
    records land in the same file. A rerun here must not delete them, and must
    not double the derived ones.
    """
    return [r for r in existing
            if r.get("kind") not in DERIVED_KINDS] + derived


def write(run_dir, by_bead: dict) -> dict:
    """One `intent_records.save` per bead. Returns what was written."""
    for bead, records in sorted(by_bead.items()):
        intent_records.save(run_dir, bead,
                            _merged(intent_records.load(run_dir, bead), records))
    return by_bead


# --- the CLI -----------------------------------------------------------------


def parse_args(argv: list) -> dict:
    opts = {"run-dir": None, "manifest": None, "json": False}
    rest = list(argv)
    while rest:
        arg = rest.pop(0)
        name = arg.removeprefix("--")
        if arg == "--json":
            opts["json"] = True
        elif arg.startswith("--") and name in ("run-dir", "manifest"):
            if not rest:
                raise UsageError(f"{arg} needs a value\n{USAGE}")
            opts[name] = rest.pop(0)
        else:
            raise UsageError(f"unknown argument: {arg}\n{USAGE}")
    if not opts["run-dir"]:
        raise UsageError(f"--run-dir is required\n{USAGE}")
    return opts


def report(by_bead: dict, findings: list, as_json: bool) -> None:
    tally = Counter(record["kind"] for records in by_bead.values()
                    for record in records)
    total = sum(tally.values())
    if as_json:
        print(json.dumps({"kinds": tally, "beads": len(by_bead),
                          "records": total, "findings": findings}, indent=2))
        return
    counted = ", ".join(f"{tally[kind]} {kind}" for kind in DERIVED_KINDS
                        if tally.get(kind))
    head = f"{counted} — " if counted else ""
    print(f"derive: {head}{total} record(s) across {len(by_bead)} bead(s)")
    for finding in findings:
        print(f"- {finding}")


def main(argv: list) -> int:
    try:
        opts = parse_args(argv)
        run_dir = Path(opts["run-dir"])
        # A run's manifest lives inside it — `staged_run.load_run` is the one
        # place that knows so. `--manifest` overrides it for a manifest under
        # review, and nothing else.
        data = (manifest_io.load(opts["manifest"]) if opts["manifest"]
                else staged_run.load_run(run_dir))
        by_bead, findings = derive(run_dir, data)
        write(run_dir, by_bead)
    except (UsageError, staged_run.Usage, manifest_io.ManifestError,
            intent_records.IntentStoreError) as err:
        print(err, file=sys.stderr)
        return 2
    report(by_bead, findings, opts["json"])
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
