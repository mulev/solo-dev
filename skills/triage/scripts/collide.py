#!/usr/bin/env python3
"""Group beads whose planned work touches the same code.

Two beads planned in isolation can be planned into contradictory rewrites of
the same code: one changes a method's signature while the other plans against
the old one, and both plans look correct on their own. This script is the net.

It is pure over its inputs — a manifest plus a footprints file — makes no LLM
call, never infers a cause, and never mutates the tracker: ordering comes out
as `bd dep add` text intents for a human or Phase 10 to run.

Exit 0 = groups written with no merge, no late duplicate and every run bead
accounted for; 1 = a MERGE, a late duplicate, or a bead in the run that carries
no footprint; 2 = usage or environment error. Bad input data is never a 2: a
footprints file with zero footprints exits 0, and a manifest bead with no
footprint is a finding, not a usage error.

The model this file executes is documented in ../references/collision-model.md.

**Why this is one module:** 249 code lines by `run_arch_gate.py`'s count, plus
92 of doc prose — under the 300 signal, so no waiver is owed. The file builds
one overlap graph and then decides over it, and every function reads the same
four footprint accessors (`_paths`, `_symbols`,
`_modules`, `_moves_a_signature`) over the same records — one model, the one
written down in `references/collision-model.md`. Three splits were considered
and all three fail the Meaningfulness Test. A graph-construction module
(`_pairs`, `build_graph`, `module_overlaps`, `group`) would have `main` as its
only caller and the cases `test_collide.py` already runs through `decide()` as
its only test — the single-caller satellite the principles name as the
dominant smell. An ordering module (`_order`, `_dep_intents`, `_describe`)
moves no coupling, because the ordering rule reads `_moves_a_signature` and
`_modules` itself, and it would leave the two halves of one documented rule —
order first, then emit the edge — in two files free to disagree, which is the
disagreement `from`/`to` exists to prevent. A decision module (`decide`,
`_identical`, `_evidence`) fails on its name alone: `decide` is what this file
is for. The one genuinely separable responsibility, report rendering, is
already `collision_report.py`, which is why what remains reads as one model
rather than two.
"""

from __future__ import annotations

import json
import posixpath
import sys
from pathlib import Path

import manifest as manifest_io
from collision_report import render_report

USAGE = (
    "usage: collide.py --manifest PATH --footprints PATH\n"
    "                  [--causes PATH] [--report PATH]"
)
DEFAULT_REPORT = "collision_report.md"
UNCLASSIFIED = "UNCLASSIFIED"
RUN_ROUTES = ("investigate", "plan")


class UsageError(Exception):
    """Bad invocation, or an input file that cannot be read."""


# --- reading a footprint -----------------------------------------------------


def _bead_id(footprint: dict) -> str:
    return str(footprint.get("bead") or "").strip()


def _paths(footprint: dict) -> set:
    """File paths, normalised so `./a/b` and `a/b` compare as one path."""
    raw = (str(f.get("path") or "").strip() for f in footprint.get("files") or [])
    return {posixpath.normpath(path) for path in raw if path}


def _symbols(footprint: dict) -> set:
    raw = (str(s.get("name") or "").strip() for s in footprint.get("symbols") or [])
    return {name for name in raw if name}


def _modules(footprint: dict) -> set:
    named = [str(m or "").strip() for m in footprint.get("modules") or []]
    derived = [str(f.get("module") or "").strip() for f in footprint.get("files") or []]
    return {m for m in named + derived if m}


def _moves_a_signature(footprint: dict) -> bool:
    return any(s.get("change") == "signature" for s in footprint.get("symbols") or [])


# --- the collision graph -----------------------------------------------------


def _pairs(footprints: list):
    """Each unordered pair of distinct, identified footprints, in input order."""
    entries = [(_bead_id(f), f) for f in footprints if _bead_id(f)]
    for index, (a, left) in enumerate(entries):
        for b, right in entries[index + 1 :]:
            if a != b:
                yield a, b, left, right


def build_graph(footprints: list) -> dict:
    """Adjacency over bead IDs, each edge carrying the evidence that made it.

    An edge exists when two footprints share a file path **or** a symbol name.
    Module overlap is reported by `module_overlaps` and never creates an edge:
    the same neighbourhood is not the same thing, and grouping on it would
    collapse a backlog into one unmanageable epic.
    """
    graph = {_bead_id(f): {} for f in footprints if _bead_id(f)}
    for a, b, left, right in _pairs(footprints):
        files = sorted(_paths(left) & _paths(right))
        symbols = sorted(_symbols(left) & _symbols(right))
        if files or symbols:
            graph[a][b] = {"files": files, "symbols": symbols}
            graph[b][a] = {"files": files, "symbols": symbols}
    return graph


def module_overlaps(footprints: list, graph: dict) -> list:
    """Bead pairs sharing a module that the graph did *not* join.

    Reported so a reviewer can see what the model considered and declined to
    group, which is the only way the negative rule is auditable.
    """
    overlaps = []
    for a, b, left, right in _pairs(footprints):
        shared = sorted(_modules(left) & _modules(right))
        if shared and b not in graph.get(a, {}):
            overlaps.append({"beads": sorted([a, b]), "modules": shared})
    return sorted(overlaps, key=lambda record: record["beads"])


def group(graph: dict, footprints: list) -> list:
    """Connected components, each carrying its members' edges and footprints.

    Members are sorted lexicographically and components ordered by their
    smallest member, because a resumed run must rebuild the identical group
    set from the same manifest or it plans a different shape than it staged.

    Transitivity is the point of components over pairs: if A overlaps B and B
    overlaps C, whatever B does to reconcile A's work is the same edit C must
    plan against.
    """
    by_id = {_bead_id(f): f for f in footprints if _bead_id(f)}
    parent = {node: node for node in graph}

    def find(node: str) -> str:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    for node, neighbours in graph.items():
        for other in neighbours:
            if other in parent:
                parent[find(node)] = find(other)

    buckets: dict = {}
    for node in graph:
        buckets.setdefault(find(node), []).append(node)

    components = sorted((sorted(m) for m in buckets.values()), key=lambda m: m[0])
    groups = []
    for index, members in enumerate(components, start=1):
        keep = set(members)
        edges = {a: {b: ev for b, ev in graph[a].items() if b in keep} for a in members}
        groups.append({
            "group_id": f"g{index}",
            "members": members,
            "edges": edges,
            "footprints": {m: by_id[m] for m in members if m in by_id},
        })
    return groups


# --- the decision ------------------------------------------------------------


def _evidence(component: dict) -> dict:
    files, symbols = set(), set()
    for neighbours in (component.get("edges") or {}).values():
        for edge in neighbours.values():
            files |= set(edge.get("files") or [])
            symbols |= set(edge.get("symbols") or [])
    return {"files": sorted(files), "symbols": sorted(symbols)}


def _describe(evidence: dict) -> str:
    parts = [
        f"shared {kind}: {', '.join(evidence[kind])}"
        for kind in ("files", "symbols")
        if evidence.get(kind)
    ]
    return "; ".join(parts) or "no shared file or symbol on record"


def _identical(members: list, footprints: dict) -> bool:
    """True when every member touches exactly the same files and symbols.

    Empty footprints are excluded on purpose: two beads that describe no work
    are identical only in the trivial sense, and merging on the strength of no
    evidence is exactly the wrong-merge this model exists to avoid.
    """
    if any(member not in footprints for member in members):
        return False
    shapes = {
        (frozenset(_paths(footprints[m])), frozenset(_symbols(footprints[m])))
        for m in members
    }
    if len(shapes) != 1:
        return False
    paths, symbols = next(iter(shapes))
    return bool(paths or symbols)


def _order(members: list, footprints: dict) -> list:
    """A bead that moves a symbol contract goes first — everything else in the
    group must be planned against the new contract, not the old one. Ties
    break on the narrower change, then on bead ID for determinism."""

    def key(bead: str):
        footprint = footprints.get(bead) or {}
        moves_first = 0 if _moves_a_signature(footprint) else 1
        return moves_first, len(_modules(footprint)), bead

    return sorted(members, key=key)


def _dep_intents(order: list, component: dict) -> list:
    """One text intent per overlapping pair, with its endpoints. Never a
    tracker write.

    `from` is the dependent bead — the one `bd dep add` names first — and `to`
    is the bead that must land before it. Both are emitted as fields as well
    as inside the command text, because `derive_intents` builds a `dep` record
    from the pair and reading it back out of the string would be a parser for
    a shape this function controls.
    """
    rank = {bead: index for index, bead in enumerate(order)}
    intents, seen = [], set()
    for a, neighbours in (component.get("edges") or {}).items():
        for b, edge in neighbours.items():
            pair = tuple(sorted((a, b)))
            if pair in seen or a not in rank or b not in rank:
                continue
            seen.add(pair)
            first, second = (a, b) if rank[a] < rank[b] else (b, a)
            command = f"bd dep add {second} {first}"
            intents.append({"command": command, "why": _describe(edge),
                            "from": second, "to": first})
    return sorted(intents, key=lambda intent: intent["command"])


def _record(group_id: str, members: list, decision: str, reason: str) -> dict:
    """The shape every group carries into the manifest, before any evidence —
    written once so a grouped and an unclassified entry can never drift apart."""
    return {
        "group_id": group_id,
        "members": list(members),
        "decision": decision,
        "reason": reason,
        "late_duplicate": False,
        "order": list(members),
        "evidence": {"files": [], "symbols": []},
        "dep_intents": [],
    }


def decide(component: dict, causes: dict) -> dict:
    """MERGE, SEQUENCE or INDEPENDENT for one connected component.

    `causes` maps bead ID to cause key. Keys are compared by exact equality
    and never inferred — inference is an LLM judgment and no script in this
    epic makes one. A bead absent from the map gets its own ID as its key, so
    two unknown causes are never equal and the pair sequences rather than
    merging. That is the conservative side on purpose: a wrong merge fuses two
    unrelated beads into one epic, while a redundant ordering edge costs only
    ordering.
    """
    members = component["members"]
    footprints = component.get("footprints") or {}
    record = _record(component["group_id"], members, "INDEPENDENT", "no overlap")
    if len(members) < 2:
        return record

    record["evidence"] = _evidence(component)
    record["order"] = _order(members, footprints)
    shared = _describe(record["evidence"])

    if _identical(members, footprints):
        record["decision"] = "MERGE"
        record["late_duplicate"] = True
        record["reason"] = (
            f"identical footprints — the duplicate Phase 2 dedup missed; {shared}"
        )
        return record

    keys = {causes.get(member, member) for member in members}
    if len(keys) == 1:
        record["decision"] = "MERGE"
        record["reason"] = f"{shared}; same cause key {next(iter(keys))}"
        return record

    record["decision"] = "SEQUENCE"
    record["reason"] = f"{shared}; distinct cause keys"
    record["dep_intents"] = _dep_intents(record["order"], component)
    return record


# --- the manifest roster -----------------------------------------------------


def _run_beads(data: dict) -> set:
    """IDs the manifest says this run is planning.

    A `skip` or `drift-report` bead is not in the run, a bead `--ids`/`--only`/
    `--max` excluded is not either, and a bead dedup dropped left it by an
    explicit, reported decision. Everything else is expected to
    carry a footprint, and its absence is a finding rather than a silence.
    """
    live = set()
    for entry in data.get("beads") or []:
        if entry.get("route") not in RUN_ROUTES:
            continue
        # An excluded bead keeps its manifest entry, so route alone would put
        # beads this run never touched into collision groups.
        if not manifest_io.in_run(entry):
            continue
        if (entry.get("dedup") or {}).get("action") == "drop":
            continue
        bead = str(entry.get("id") or "").strip()
        if bead:
            live.add(bead)
    return live


def unclassified(data: dict, groups: list) -> list:
    """One record per run bead the footprints never accounted for.

    A bead whose worker parked, or whose `footprint:` block was malformed, used
    to appear in no group, no decision and no report line while the run exited
    0. It leaves the run only by a decision somebody can read.
    """
    grouped = {member for entry in groups for member in entry["members"]}
    return [
        _record(
            f"u{index}",
            [bead],
            UNCLASSIFIED,
            "no footprint on record — collisions could not be checked",
        )
        for index, bead in enumerate(sorted(_run_beads(data) - grouped), start=1)
    ]


# --- the CLI -----------------------------------------------------------------


def _read_json(path: str, what: str):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as err:
        raise UsageError(f"cannot read {what} {path}: {err}") from err


def _read_footprints(path: str) -> list:
    payload = _read_json(path, "footprints")
    if isinstance(payload, dict):
        payload = payload.get("footprints") or []
    if not isinstance(payload, list):
        raise UsageError(f"cannot read footprints {path}: expected a list")
    return [entry for entry in payload if isinstance(entry, dict)]


def _read_causes(path) -> dict:
    if not path:
        return {}
    payload = _read_json(path, "causes")
    if not isinstance(payload, dict):
        raise UsageError(f"cannot read causes {path}: expected an object")
    return payload


def parse_args(argv: list) -> dict:
    opts = {"manifest": None, "footprints": None, "causes": None, "report": None}
    rest = list(argv)
    while rest:
        arg = rest.pop(0)
        name = arg.removeprefix("--")
        if not arg.startswith("--") or name not in opts:
            raise UsageError(f"unknown argument: {arg}\n{USAGE}")
        if not rest:
            raise UsageError(f"{arg} needs a value\n{USAGE}")
        opts[name] = rest.pop(0)
    for required in ("manifest", "footprints"):
        if not opts[required]:
            raise UsageError(f"--{required} is required\n{USAGE}")
    return opts


def main(argv: list) -> int:
    try:
        opts = parse_args(argv)
        footprints = _read_footprints(opts["footprints"])
        causes = _read_causes(opts["causes"])
        data = manifest_io.load(opts["manifest"])
    except (UsageError, manifest_io.ManifestError) as err:
        print(err, file=sys.stderr)
        return 2

    graph = build_graph(footprints)
    groups = [decide(component, causes) for component in group(graph, footprints)]
    groups += unclassified(data, groups)

    data["schema_version"] = manifest_io.schema_version
    data["groups"] = groups
    manifest_io.save(opts["manifest"], data)

    report = Path(opts["report"] or Path(opts["manifest"]).parent / DEFAULT_REPORT)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        render_report(groups, module_overlaps(footprints, graph)), encoding="utf-8"
    )

    tally = {"MERGE": 0, "SEQUENCE": 0, "INDEPENDENT": 0, UNCLASSIFIED: 0}
    for entry in groups:
        tally[entry["decision"]] += 1
    late = sum(1 for entry in groups if entry["late_duplicate"])
    counted = ", ".join(f"{name.lower()}={count}" for name, count in tally.items())
    print(
        f"{len(groups)} group(s): {counted}"
        f" — {late} late duplicate(s), report at {report}"
    )
    return 1 if tally["MERGE"] or late or tally[UNCLASSIFIED] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
