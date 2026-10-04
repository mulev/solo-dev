#!/usr/bin/env python3
"""Validate the Wave 1 judge's ruling on one dedup cluster, and read the drops.

A cluster used to carry a single verdict over a flat member list, so the judge
had to rule on every member together. Clustering is deliberately loose —
`dedup.py`'s threshold is 0.35 and the first live run grouped four beads at
0.468 because they shared the word "OPDS" — and that only stays cheap if the
judge can say "these two are the same bug, those two are not". With one verdict
the only safe answer for a mixed cluster was to keep everything, which turns a
partial duplicate into no duplicate at all.

So a ruling is a **partition**: every member lands in exactly one group, and
each group carries its own verdict. A cluster ruled one way collapses to a
single group, so the common case reads exactly as it did before.

Pure functions over plain data. The judge decides; this file only refuses a
ruling that is malformed — a member ruled twice or not at all is not a
judgment call, it is an incomplete answer.
"""

from __future__ import annotations

VERDICTS = ("duplicate", "distinct", "related-not-duplicate")


def identify(cluster_id: str, groups: list) -> list:
    """The ruling's groups, each named `{cluster_id}-g{n}`, stamped in place.

    `references/ledger.md` keys a Wave 1 row by its group ID, and `collide.py`
    names its own groups — but a judge's ruling arrived without names, so the
    orchestrator minted them and three live runs produced three formats for
    rows nothing else in the run could be matched to.

    The name is the orchestrator's, not the judge's, which is why `validate`
    does not ask for it: a ruling is well formed or not on its members and
    verdicts alone. An ID already present is kept, because a resumed run
    re-identifies groups the ledger has already written rows against and
    renumbering would orphan every one of them.
    """
    for index, group in enumerate(groups, start=1):
        group.setdefault("group_id", f"{cluster_id}-g{index}")
    return groups


def validate(members: list, groups: list) -> list[str]:
    """Findings against one cluster's ruling. Empty list means well formed."""
    if not groups:
        return ["no groups: the cluster was not ruled on"]

    known, seen, out = set(members), [], []
    for index, group in enumerate(groups):
        where = f"groups[{index}]"
        listed = group.get("members") or []
        if not listed:
            out.append(f"{where}: empty group")
        seen += listed
        for bead in listed:
            if bead not in known:
                out.append(f"{where}: {bead} is not a member of this cluster")

        verdict = group.get("verdict")
        if verdict not in VERDICTS:
            out.append(f"{where}: unknown verdict {verdict!r}")
        elif verdict == "duplicate":
            out += _duplicate_findings(group, listed, where)
    return out + _coverage_findings(members, seen)


def _duplicate_findings(group: dict, listed: list, where: str) -> list[str]:
    """What a `duplicate` group owes beyond its verdict.

    Duplication is a relation, so a group of one has nothing to duplicate —
    and a representative is what tells promote which bead survives.
    """
    if len(listed) < 2:
        return [f"{where}: duplicate needs more than one member"]
    representative = group.get("representative")
    if not representative:
        return [f"{where}: duplicate carries no representative"]
    if representative not in listed:
        return [f"{where}: representative {representative} is not in this group"]
    return []


def _coverage_findings(members: list, seen: list) -> list[str]:
    """Exactly once, each. Both failures silently lose a bead.

    `seen` is the judge's, so it can hold anything. A nameless member is
    already a finding above — `is not a member of this cluster` — and it is
    excluded here so sorting a mixed set cannot raise out of the validator
    written to reject it. `plan_coverage.validate_coverage` had the same hole,
    and a live run found it.
    """
    out = []
    twice = sorted({bead for bead in seen
                    if bead is not None and seen.count(bead) > 1})
    if twice:
        out.append(f"ruled more than once: {', '.join(twice)}")
    missing = [bead for bead in members if bead not in seen]
    if missing:
        out.append(f"not ruled on: {', '.join(missing)}")
    return out


def dropped(groups: list) -> list:
    """Every bead a ruling retires — a duplicate group's non-representatives.

    Nothing else drops. `distinct` and `related-not-duplicate` both mean the
    beads keep their own plans, and the representative is what the survivors
    are folded into.
    """
    out = []
    for group in groups:
        if group.get("verdict") != "duplicate":
            continue
        representative = group.get("representative")
        out += [bead for bead in group.get("members") or []
                if bead != representative]
    return sorted(out)
