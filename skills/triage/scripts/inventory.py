#!/usr/bin/env python3
"""Route a project's beads to investigate, plan, or skip.

Reads bd (read-only) and writes a manifest. Never mutates the tracker.
Exit 0 = clean, 1 = drift beads found, 2 = usage error, unknown project, or a
tracker read that failed.

The rubric this file executes is documented in ../references/classification.md.

TRIAGE_PROJECTS_ROOT names the workspace root and is required; there is no
default, and an unset variable is exit 2. The tests set it and put a fake `bd`
on PATH. Those two seams are the only injection points.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import manifest as manifest_io
from staged_run import PLAN_MARKERS

TERMINAL_STATUSES = ("blocked", "deferred", "closed", "pinned")
# The routing half's own reading of `PLAN_MARKERS` is the definition the
# promote half now shares: a plan path makes a bead workable, an
# `Investigation:` line does not. Retyped here once, the two halves disagreed
# for a release.
INVESTIGATION_MARKER = "Investigation:"
ROUTES = ("investigate", "plan", "skip", "drift-report")
TABLE_HEADER = ("ID", "ROUTE", "REASON", "STATUS", "TITLE")

USAGE = ("usage: inventory.py --project NAME [--json] [--table] [--out PATH]\n"
         "                    [--ids a,b,c] [--only investigate|plan] [--max N]\n"
         "  env: TRIAGE_PROJECTS_ROOT=DIR (required) — the directory holding NAME")


class UsageError(Exception):
    """Bad invocation or a project name that does not resolve to a bd repo."""


def _is_epic_or_child(bead: dict) -> bool:
    """True when this bead is an epic or a child of one.

    Epic membership alone carries no plan information, so `classify` pairs
    this with `has_plan` — see references/classification.md, precedence
    rule 2. `plan` Step 8b gives every phase a `Slice:`+`Master:` note at
    creation; a followup parented under the workspace Scope RULE carries no
    plan path, because no plan covers it.

    `bd list --json` carries both `parent` and `dependencies`; `bd show --json`
    carries neither, which is why classification reads the listing entry.
    """
    if bead.get("issue_type") == "epic" or bead.get("parent"):
        return True
    return any(
        dep.get("type") == "parent-child" and dep.get("issue_id") == bead.get("id")
        for dep in bead.get("dependencies") or []
    )


def classify(bead: dict, notes: str) -> tuple[str, str]:
    """Return (route, reason). Pure: no I/O, no globals, total over any input."""
    status = bead.get("status", "")
    has_plan = any(marker in notes for marker in PLAN_MARKERS)

    if status in TERMINAL_STATUSES:
        return "skip", f"status: {status}"
    if _is_epic_or_child(bead) and has_plan:
        return "skip", "owned by its master plan"
    if status == "needs-plan":
        if has_plan:
            return "skip", "already planned"
        if INVESTIGATION_MARKER in notes:
            return "plan", "investigation on record"
        return "investigate", "no investigation on record"
    if status == "open":
        if has_plan:
            return "skip", "already planned"
        return "drift-report", "open with no plan path"
    return "skip", f"status not routed in v1: {status}"


def resolve_repo_root(project: str) -> Path:
    """Map a project name onto its repo root, which must hold a `.beads/` dir.

    `TRIAGE_PROJECTS_ROOT` has no default on purpose: the constant that used to
    stand in for it named one developer's home directory, so a caller who
    forgot the variable read the real tracker believing it was a sandbox.
    """
    if not project or "/" in project or os.sep in project:
        raise UsageError(f"not a project name: {project!r}")
    workspace = os.environ.get("TRIAGE_PROJECTS_ROOT")
    if not workspace:
        raise UsageError("TRIAGE_PROJECTS_ROOT is not set: it names the directory "
                         f"holding {project!r}\n{USAGE}")
    root = Path(workspace) / project
    if not (root / ".beads").is_dir():
        raise UsageError(f"no bd database for {project!r}: looked for {root / '.beads'}")
    return root


def _bd(root: Path, *args: str) -> list:
    """One read-only bd query. Any failure here is an environment error.

    Exit 2, never exit 1: a tracker this script cannot read produced no
    findings, and reporting "no drift" from a failed read is the same class of
    lie as dropping a bead silently. `dedup.py::_bd_json` is the sibling of
    this function and has always done it this way.
    """
    query = " ".join(["bd", *args])
    try:
        proc = subprocess.run(
            ["bd", *args], capture_output=True, text=True, cwd=str(root)
        )
    except OSError as err:
        raise UsageError(f"cannot run bd: {err}") from err
    if proc.returncode != 0:
        raise UsageError(f"{query} failed: {proc.stderr.strip()}")
    try:
        return json.loads(proc.stdout or "[]")
    except ValueError as err:
        raise UsageError(f"{query} returned non-JSON: {err}") from err


def _entry(bead: dict, notes: str) -> dict:
    route, reason = classify(bead, notes)
    return {
        "id": bead["id"],
        "title": bead.get("title", ""),
        "status": bead.get("status", ""),
        "issue_type": bead.get("issue_type", ""),
        "priority": bead.get("priority"),
        "route": route,
        "reason": reason,
    }


ROSTER_QUERY = ("list", "--limit", "0", "--json")


def collect(root: Path) -> list[dict]:
    """One `bd list`, then one batched `bd show` for the notes each bead carries.

    `--all` is deliberately absent, so closed beads never reach the manifest.
    That is a choice, not an oversight: a project's closed beads outnumber its
    open ones and every one of them would route `skip`, after being clustered
    and coverage-scanned. The cost of the choice is that `classify`'s `closed`
    branch is unreachable from here — `references/classification.md`,
    precedence rule 1, says so, and `test_inventory.py` pins this query so the
    two cannot drift apart silently.
    """
    listing = _bd(root, *ROSTER_QUERY)
    ids = [bead["id"] for bead in listing]
    notes: dict[str, str] = {}
    if ids:
        shown = _bd(root, "show", *ids, "--json")
        notes = {record["id"]: record.get("notes") or "" for record in shown}
    return [_entry(bead, notes.get(bead["id"], "")) for bead in listing]


SPEND_ROUTES = ("investigate", "plan")


def select(entries: list[dict], ids, only, max_beads: int) -> list[dict]:
    """Mark which entries this run works on. Never removes one.

    `triage/SKILL.md` Wave 0: the filter applies to the manifest, not to the
    tracker query, and an excluded bead is *marked* rather than deleted — a
    later run has to be able to tell "not selected" from "not seen", and a
    deleted entry destroys exactly that. This is the executable form of that
    paragraph; it used to be prose an orchestrator applied by hand, which meant
    two orchestrators marked exclusions two different ways.

    `max_beads` counts only the routes that cost a worker. Capping the whole
    roster would let `skip` rows eat the budget and shrink the run for no
    saving.
    """
    if only is not None and only not in ROUTES:
        raise UsageError(f"--only must be one of {', '.join(ROUTES)}")
    known = {e["id"] for e in entries}
    if ids is not None:
        unknown = [i for i in ids if i not in known]
        if unknown:
            raise UsageError(f"--ids names beads not in the backlog: "
                             f"{', '.join(sorted(unknown))}")
    wanted = set(ids) if ids is not None else None
    spent, out = 0, []
    for entry in entries:
        marked = dict(entry)
        reason = None
        if wanted is not None and entry["id"] not in wanted:
            reason = "not in --ids"
        elif only is not None and entry["route"] != only:
            reason = f"route is not {only}"
        elif entry["route"] not in SPEND_ROUTES:
            reason = f"route {entry['route']} costs no worker"
        elif max_beads and spent >= max_beads:
            reason = f"over --max {max_beads}"
        if reason is None:
            spent += 1
        marked["selected"] = reason is None
        if reason is not None:
            marked["excluded"] = reason
        out.append(marked)
    return out


def build_manifest(project: str, entries: list[dict]) -> dict:
    counts = {route: 0 for route in ROUTES}
    selected_counts = {route: 0 for route in ROUTES}
    for entry in entries:
        counts[entry["route"]] += 1
        if entry.get("selected", True):
            selected_counts[entry["route"]] += 1
    # Totals are carried, not left to the reader. `counts` is a tally per route
    # and the Wave 6 close-out leads with the sum, so without these the
    # orchestrator adds four numbers by hand — which two live runs did, both
    # reaching 24 over a table of 23.
    return {
        "project": project,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "counts": counts,
        "selected_counts": selected_counts,
        "total": len(entries),
        "selected_total": sum(selected_counts.values()),
        "beads": entries,
    }


def render_table(manifest: dict) -> str:
    """Every column but the title is padded; the title runs last and free."""
    rows = [TABLE_HEADER]
    rows += [
        (b["id"], b["route"], b["reason"], b["status"], b["title"][:60])
        for b in manifest["beads"]
    ]
    padded_columns = range(len(TABLE_HEADER) - 1)
    widths = [max(len(row[col]) for row in rows) for col in padded_columns]
    lines = [
        "  ".join([row[col].ljust(widths[col]) for col in padded_columns] + [row[-1]])
        for row in rows
    ]
    counts = manifest["counts"]
    tally = "  ".join(f"{route}={counts[route]}" for route in ROUTES)
    return "\n".join(lines) + (
        f"\n\n{manifest['project']}: {manifest['total']} beads  {tally}"
        f"  selected={manifest['selected_total']}")


def parse_args(argv: list[str]) -> dict:
    opts = {"project": None, "json": False, "table": False, "out": None,
            "ids": None, "only": None, "max": 0}
    rest = list(argv)
    while rest:
        arg = rest.pop(0)
        if arg in ("--project", "--out", "--ids", "--only", "--max"):
            if not rest:
                raise UsageError(f"{arg} needs a value\n{USAGE}")
            opts[arg.removeprefix("--")] = rest.pop(0)
        elif arg in ("--json", "--table"):
            opts[arg.removeprefix("--")] = True
        else:
            raise UsageError(f"unknown argument: {arg}\n{USAGE}")
    if not opts["project"]:
        raise UsageError(f"--project is required\n{USAGE}")
    if not opts["json"]:
        opts["table"] = True  # the table is the default output
    if opts["ids"] is not None:
        opts["ids"] = [i.strip() for i in opts["ids"].split(",") if i.strip()]
        if not opts["ids"]:
            raise UsageError(f"--ids needs at least one bead\n{USAGE}")
    try:
        opts["max"] = int(opts["max"])
    except (TypeError, ValueError) as err:
        raise UsageError(f"--max must be a whole number\n{USAGE}") from err
    if opts["max"] < 0:
        raise UsageError(f"--max must not be negative\n{USAGE}")
    return opts


def main(argv: list[str]) -> int:
    try:
        opts = parse_args(argv)
        root = resolve_repo_root(opts["project"])
        manifest = build_manifest(opts["project"], select(
            collect(root), opts["ids"], opts["only"], opts["max"]))
    except UsageError as err:
        print(err, file=sys.stderr)
        return 2

    # Only `--out` writes. The default used to be `manifest.json` in the
    # caller's working directory, which put a 23KB file in whatever repo a
    # human happened to be standing in — the run directory is the only write
    # target this system has, and a default cannot know where that is.
    if opts["out"]:
        out = Path(opts["out"])
        out.parent.mkdir(parents=True, exist_ok=True)
        manifest_io.save(out, manifest)

    if opts["table"]:
        print(render_table(manifest))
    if opts["json"]:
        print(json.dumps(manifest, indent=2))
    return 1 if manifest["counts"]["drift-report"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
