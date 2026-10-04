#!/usr/bin/env python3
"""Render the collision report markdown from already-decided group records.

Pure presentation over the records `collide.py` hands it: no filesystem, no
imports, no knowledge of how a group was formed or why a decision was taken.
It reads only the fields a record carries, which is what lets an
`UNCLASSIFIED` entry print through the same loop as a `MERGE`.

The report itself is a named artifact of the model documented in
../references/collision-model.md.
"""

from __future__ import annotations


def render_report(groups: list, overlaps: list) -> str:
    lines = ["# Collision report", ""]
    for entry in groups:
        lines += [
            f"## {entry['group_id']} — {entry['decision']}",
            "",
            f"- Members: {', '.join(entry['members'])}",
            f"- Reason: {entry['reason']}",
            f"- Planning order: {' -> '.join(entry['order'])}",
        ]
        if entry["evidence"]["files"]:
            lines.append(f"- Shared files: {', '.join(entry['evidence']['files'])}")
        if entry["evidence"]["symbols"]:
            lines.append(f"- Shared symbols: {', '.join(entry['evidence']['symbols'])}")
        for intent in entry["dep_intents"]:
            lines.append(f"- Dependency intent: `{intent['command']}` — {intent['why']}")
        lines.append("")

    lines += ["## Module-only overlaps (did not group)", ""]
    lines += [
        f"- {' + '.join(record['beads'])}: {', '.join(record['modules'])}"
        for record in overlaps
    ] or ["_none_"]

    lines += ["", "## Late duplicates (missed by dedup)", ""]
    lines += [
        f"- {entry['group_id']}: {', '.join(entry['members'])}"
        for entry in groups
        if entry["late_duplicate"]
    ] or ["_none_"]
    return "\n".join(lines) + "\n"
