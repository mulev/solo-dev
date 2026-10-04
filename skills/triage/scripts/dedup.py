#!/usr/bin/env python3
"""Propose duplicate clusters over a routed manifest, before any budget is spent.

Reads bd (read-only) and writes findings back into the Phase 1 manifest.
Never mutates the tracker, never rules on sameness: it emits `candidate`
clusters plus a judge brief, and the Wave 1 judge agent decides.

Exit 0 = nothing found, 1 = clusters or covered beads found, 2 = usage or
environment error. Bad input data is never a 2.

The doctrine this file executes is documented in ../references/deduplication.md.

TRIAGE_PROJECTS_ROOT overrides the workspace root and PATH supplies `bd`;
the tests use those two seams and nothing else.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import manifest as manifest_io
from inventory import INVESTIGATION_MARKER, UsageError, resolve_repo_root
from plan_coverage import coverage_action, deciding_citation, scan_plan_coverage

DEFAULT_THRESHOLD = 0.35
SPEND_ROUTES = ("investigate", "plan")
LINK_EDGES = ("duplicate-of", "discovered-from")
VERDICT = "candidate"

USAGE = (
    "usage: dedup.py --manifest PATH --project NAME --plans-dir DIR\n"
    "                [--threshold 0.35] [--brief PATH]"
)


def _bd_json(root: Path, *args: str):
    """One read-only bd query. Any failure here is an environment error."""
    try:
        proc = subprocess.run(
            ["bd", *args], capture_output=True, text=True, cwd=str(root)
        )
    except OSError as err:
        raise UsageError(f"cannot run bd: {err}") from err
    if proc.returncode != 0:
        raise UsageError(f"bd {' '.join(args)} failed: {proc.stderr.strip()}")
    try:
        return json.loads(proc.stdout or "null")
    except ValueError as err:
        raise UsageError(f"bd {' '.join(args)} returned non-JSON: {err}") from err


def _bead_details(root: Path) -> dict:
    """`bd list` carries notes, created_at, description and dependencies.

    The Phase 1 manifest carries none of those, and all four are needed here:
    notes for the representative rule, dependencies for the link source.
    """
    return {b["id"]: b for b in _bd_json(root, "list", "--limit", "0", "--json") or []}


def _mechanical_pairs_from(payload: dict, threshold: float, beads: list) -> list:
    """Pure half of source 1 — parse `bd find-duplicates --json` into pairs."""
    by_id = {b["id"]: b for b in beads}
    pairs = []
    for record in (payload or {}).get("pairs") or []:
        a, b = record.get("issue_a_id"), record.get("issue_b_id")
        score = record.get("similarity")
        if a not in by_id or b not in by_id or score is None or score < threshold:
            continue
        pairs.append(
            {"a": by_id[a], "b": by_id[b], "source": "mechanical", "score": score}
        )
    return pairs


def _mechanical_pairs(root: Path, threshold: float, beads: list) -> list:
    """Source 1 — token similarity over titles and descriptions.

    `--method ai` is unavailable on this machine (no API key) and is never
    used; mechanical is the only supported method.
    """
    payload = _bd_json(
        root, "find-duplicates", "--method", "mechanical",
        "--threshold", str(threshold), "--status", "needs-plan", "--json",
    )
    return _mechanical_pairs_from(payload, threshold, beads)


def _dependency_pairs(beads: list) -> list:
    """Source 3 — pure. A tracker edge outranks any similarity score."""
    by_id = {b["id"]: b for b in beads}
    pairs, seen = [], set()
    for bead in beads:
        for edge in bead.get("dependencies") or []:
            if edge.get("type") not in LINK_EDGES:
                continue
            ends = {edge.get("issue_id"), edge.get("depends_on_id")} - {bead["id"]}
            if len(ends) != 1:  # a self-edge, or an edge naming neither end
                continue
            key = tuple(sorted((bead["id"], ends.pop())))
            if key[0] not in by_id or key[1] not in by_id or key in seen:
                continue
            seen.add(key)
            pairs.append({"a": by_id[key[0]], "b": by_id[key[1]],
                          "source": "dependency", "score": None})
    return pairs


def _pick_representative(members: list) -> tuple:
    """Deterministic, in this order: investigation, priority, age, then ID.

    The ID tie-break is not a formality — without it a rerun can pick a
    different representative and plan a bead the previous run had deduped.
    """
    tiers = (
        (lambda b: 0 if INVESTIGATION_MARKER in (b.get("notes") or "") else 1,
         lambda b: "carries Investigation: path"),
        (lambda b: b["priority"] if isinstance(b.get("priority"), int) else 99,
         lambda b: f"lowest priority number (P{b['priority']})"),
        (lambda b: b.get("created_at") or "9999",
         lambda b: f"oldest created_at ({b['created_at']})"),
        (lambda b: b["id"], lambda b: "lexicographically smallest id"),
    )
    pool = list(members)
    for rank, describe in tiers:
        best = min(rank(b) for b in pool)
        pool = [b for b in pool if rank(b) == best]
        if len(pool) == 1:
            break
    return pool[0]["id"], describe(pool[0])


def cluster(pairs: list, coverage: dict) -> list:
    """Union the pair edges, then describe each group. Pure and order-stable.

    Beads a plan already owns leave the run, so they are removed from the
    graph before the union — clustering something nobody will work on only
    costs the judge a paragraph.
    """
    dropped = {bid for bid, cites in coverage.items()
               if coverage_action(cites) == "drop"}
    live = [p for p in pairs
            if p["a"]["id"] not in dropped and p["b"]["id"] not in dropped]

    parent: dict = {}

    def find(node: str) -> str:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    beads: dict = {}
    for pair in live:
        for side in ("a", "b"):
            beads[pair[side]["id"]] = pair[side]
            parent.setdefault(pair[side]["id"], pair[side]["id"])
        parent[find(pair["a"]["id"])] = find(pair["b"]["id"])

    groups: dict = {}
    for bid in beads:
        groups.setdefault(find(bid), []).append(bid)

    clusters = []
    for members in sorted(sorted(g) for g in groups.values()):
        inside = [p for p in live
                  if p["a"]["id"] in members and p["b"]["id"] in members]
        scores = [p["score"] for p in inside if p["score"] is not None]
        rep, reason = _pick_representative([beads[m] for m in members])
        clusters.append({
            "cluster_id": f"c{len(clusters) + 1}",
            "members": members,
            "sources": sorted({p["source"] for p in inside}),
            "score": max(scores) if scores else None,
            "representative": rep,
            "representative_reason": reason,
            "verdict": VERDICT,
        })
    return clusters


def _covered_records(coverage: dict) -> list:
    return [
        {
            "id": bid,
            "action": coverage_action(coverage[bid]),
            "covered_by": deciding_citation(coverage[bid])["path"],
            "citations": coverage[bid],
        }
        for bid in sorted(coverage)
    ]


def _write_judge_brief(clusters: list, covered: list, beads: dict, path: Path) -> None:
    """One section per candidate, ready to hand over with no further assembly."""
    lines = [
        "# Duplicate judge brief",
        "",
        "Every item below is a *candidate*. Rule on each one; the script did not.",
        "",
    ]
    for entry in clusters:
        score = entry["score"]
        similarity = f"{score:.3f}" if score is not None else "n/a (tracker edge)"
        lines += [
            f"## {entry['cluster_id']} — {', '.join(entry['members'])}",
            "",
            f"- Sources: {', '.join(entry['sources'])}",
            f"- Similarity: {similarity}",
            f"- Proposed representative: `{entry['representative']}`"
            f" — {entry['representative_reason']}",
            "",
        ]
        for member in entry["members"]:
            bead = beads.get(member, {})
            lines += [
                f"### `{member}` — {bead.get('title', '')}",
                "",
                (bead.get("description") or "_no description_").strip(),
                "",
            ]
        lines += [
            "**Ruling:** partition the members — one group per answer, every member in\n"
            "exactly one group. Per group: `members — verdict — representative`, where\n"
            "verdict is duplicate / distinct / related-not-duplicate and a representative\n"
            "is required only for duplicate. One group holding every member is the normal\n"
            "answer; split only where the cluster genuinely splits.",
            "",
        ]

    if covered:
        lines += [
            "## Already covered by a plan",
            "",
            "**Ruling:** one line per bead — `id — covered — plan path`, or `id — not-covered`.\n"
            "The citation below is a mention, not proof: open the plan and decide whether it\n"
            "actually covers this bead's work. `covered` retires the bead and must name the plan;\n"
            "`not-covered` sends it to a worker exactly as if it had never been flagged. Every\n"
            "bead listed here needs a line — an unruled bead is investigated from scratch while a\n"
            "plan already covers it.",
            "",
        ]
        for record in covered:
            cite = deciding_citation(record["citations"])
            lines += [
                f"- `{record['id']}` — {record['action']} — {record['covered_by']}",
                f"  - cited as `{cite['how']}`: {cite['line']}",
            ]
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: list) -> dict:
    opts = {
        "manifest": None, "project": None, "plans_dir": None,
        "threshold": DEFAULT_THRESHOLD, "brief": None,
    }
    valued = ("--manifest", "--project", "--plans-dir", "--threshold", "--brief")
    rest = list(argv)
    while rest:
        arg = rest.pop(0)
        if arg not in valued:
            raise UsageError(f"unknown argument: {arg}\n{USAGE}")
        if not rest:
            raise UsageError(f"{arg} needs a value\n{USAGE}")
        opts[arg.removeprefix("--").replace("-", "_")] = rest.pop(0)
    for key in ("manifest", "project", "plans_dir"):
        if not opts[key]:
            raise UsageError(f"--{key.replace('_', '-')} is required\n{USAGE}")
    try:
        opts["threshold"] = float(opts["threshold"])
    except (TypeError, ValueError) as err:
        raise UsageError(f"--threshold must be a number\n{USAGE}") from err
    return opts


def main(argv: list) -> int:
    try:
        opts = parse_args(argv)
        manifest = manifest_io.load(opts["manifest"])
        # `manifest_io.in_run` and not the route alone: `inventory.select`
        # leaves an excluded bead's entry in place, so a run told to touch two
        # beads would otherwise cluster the whole backlog and spend a judge on
        # all of it.
        spend = [b for b in manifest.get("beads") or []
                 if b.get("route") in SPEND_ROUTES and manifest_io.in_run(b)]
        clusters, covered, beads = [], [], []
        if spend:
            root = resolve_repo_root(opts["project"])
            details = _bead_details(root)
            beads = [{**details.get(b["id"], {}), **b} for b in spend]
            coverage = scan_plan_coverage(
                opts["plans_dir"], opts["project"], [b["id"] for b in beads]
            )
            pairs = _mechanical_pairs(root, opts["threshold"], beads)
            pairs += _dependency_pairs(beads)
            clusters = cluster(pairs, coverage)
            covered = _covered_records(coverage)
    except (UsageError, manifest_io.ManifestError) as err:
        print(err, file=sys.stderr)
        return 2

    by_id = {record["id"]: record for record in covered}
    for entry in manifest.get("beads") or []:
        record = by_id.get(entry["id"])
        if record:
            entry["dedup"] = {"action": record["action"],
                              "covered_by": record["covered_by"]}
    manifest["clusters"] = clusters
    manifest["covered"] = covered
    manifest_io.save(opts["manifest"], manifest)

    if not clusters and not covered:
        print(f"{opts['project']}: no duplicate candidates, no covered beads")
        return 0

    brief = Path(opts["brief"] or Path(opts["manifest"]).parent / "judge_brief.md")
    _write_judge_brief(clusters, covered, {b["id"]: b for b in beads}, brief)
    print(
        f"{opts['project']}: {len(clusters)} candidate cluster(s),"
        f" {len(covered)} covered bead(s) — brief at {brief}"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
