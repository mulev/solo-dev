#!/usr/bin/env python3
"""Assemble worker footprint blocks into the collision model's input.

Wave 3 step 2 orders a conversion — each worker's indented `footprint:` block
into the dicts `collide.py` reads — and until now no production script
performed it, so the orchestrator did it by hand. A footprint that arrives
with its `bead:` and without one of its paths is accounted for by the roster
check, grouped, and wrong at exit 0: measured, one omitted line turns one
SEQUENCE group into two INDEPENDENT ones.

**A malformed block is reported, never raised on** — `validate` returns
findings the way `intent_records.validate` does, because `collide._paths`
raising an `AttributeError` on a bare list item is the shape `collide.py`'s
own error contract forbids.

The output is a **bare list**, which is not a preference: the promote
pre-flight reads a bare list and only a bare list, while `collide.py` accepts
either. Emitting the list satisfies both readers with no change to either.

Shape, never completeness: a block that parses is written as it stands. What
a footprint *should* have said is a question about the worker's analysis, and
this module cannot see the analysis — the roster rule and the reviewer can.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

USAGE = "usage: footprints.py --run PATH [<bead>=<artifact> ...]"
OUTPUT = "footprints.json"
# The two record lists, and the field that identifies a record in each. The
# model reads them through `_paths` and `_symbols`; an entry missing its
# identifier is invisible there rather than wrong.
IDENTIFIER = {"files": "path", "symbols": "name"}
# The two `change:` vocabularies `brief_invest.sh` prints and
# `references/collision-model.md` documents. They differ: a file is added,
# modified or deleted, while a symbol's *contract* is what moves.
CHANGES = {
    "files": ("add", "modify", "delete"),
    "symbols": ("add", "signature", "behavior", "remove"),
}


class UsageError(Exception):
    """Bad invocation, or an artifact that cannot be read."""


class BlockError(Exception):
    """The text under the anchor is not the block grammar.

    Measured while this module was being written: a worker that drops the
    `files:` line and writes its records straight under `footprint:` used to
    take the whole run down with a bare `KeyError: ''` out of the parser. The
    promise this module makes is that a malformed block is reported, so the
    parser says which line it could not read and `main` turns that into one
    bead's finding.
    """


def parse_block(block: str) -> dict:
    """Assemble the block into the dict shape collide reads.

    The one implementation of the block grammar. `test_footprint_contract.py`
    calibrates it against the example `brief_invest.sh` prints, and the e2e
    harness reads live artifacts through it, so no second reader can drift
    from the grammar the brief teaches.
    """
    data: dict = {}
    key = ""
    for raw in block.splitlines()[1:]:
        line = raw.split("#", 1)[0].rstrip()
        text = line.strip()
        if not text:
            continue
        indent = len(line) - len(text)
        if text.startswith("- "):  # opens a record, or a bare list item
            item = text[2:].strip()
            name, colon, value = item.partition(":")
            if not isinstance(data.get(key), list):
                raise BlockError(f"`- {item}` sits under no list key")
            data[key].append({name.strip(): value.strip()} if colon else item)
        elif indent == 2:  # a top-level key: a scalar, or a list to fill
            name, _, value = text.partition(":")
            key = name.strip()
            data[key] = [] if value.strip() in ("", "[]") else value.strip()
        else:  # another field on the record the last `- ` opened
            name, _, value = text.partition(":")
            records = data.get(key)
            if not (isinstance(records, list) and records
                    and isinstance(records[-1], dict)):
                raise BlockError(f"`{text}` continues no record")
            records[-1][name.strip()] = value.strip()
    return data


def from_artifact(path, bead: str) -> dict:
    """One worker's artifact, read into the footprint it reported.

    The **last** anchor wins: the brief shows an example block, and a worker
    that echoes the example before writing its own would otherwise have the
    example parsed as its answer.

    An artifact with no block yields `{"bead": bead}` — absent, which
    `validate` reports and `main` keeps out of the written list, so the bead
    reaches the collision report as `UNCLASSIFIED` with the roster rule's own
    reason rather than as an exception or as an empty group.

    An unreadable artifact raises: no block was read, and returning an absent
    footprint for it would report a missing block where there is a missing
    file. `intent_records._read` draws the same line.
    """
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError as err:
        raise UsageError(f"cannot read artifact {path}: {err}") from err
    starts = [i for i, line in enumerate(lines) if line.rstrip() == "footprint:"]
    if not starts:
        return {"bead": bead}
    start = starts[-1]
    end = start + 1
    while end < len(lines) and (lines[end].startswith(" ") or not lines[end].strip()):
        end += 1
    footprint = parse_block("\n".join(lines[start:end]))
    footprint.setdefault("bead", bead)
    return footprint


def validate(footprint) -> list:
    """Findings against one footprint. Empty means the model can read it all.

    Shape only. A footprint naming one file and no symbols is a real answer
    and gets no finding; a footprint whose entries the model cannot read, or
    whose `change:` says nothing the ordering rule understands, gets one.
    """
    if not isinstance(footprint, dict):
        return [f"footprint is {type(footprint).__name__}, not an object"]
    where = str(footprint.get("bead") or "").strip() or "<no bead>"
    if not set(footprint) - {"bead"}:
        return [f"{where}: the artifact carries no `footprint:` block"]
    out = []
    for key, identifier in IDENTIFIER.items():
        entries = footprint.get(key) or []
        if not isinstance(entries, list):
            out.append(f"{where}: {key} is {type(entries).__name__},"
                       f" not a list of records")
            continue
        for entry in entries:
            out += _entry_findings(where, key, identifier, entry)
    return out


def _entry_findings(where: str, key: str, identifier: str, entry) -> list:
    if not isinstance(entry, dict):
        return [f"{where}: {key} entry {entry!r} is not a record —"
                f" write it as `- {identifier}: {entry}`"]
    out = []
    name = str(entry.get(identifier) or "").strip()
    if not name:
        out.append(f"{where}: a {key} entry carries no {identifier}, so the"
                   f" model cannot see it: {entry!r}")
    change = str(entry.get("change") or "").strip()
    subject = name or repr(entry)
    if not change:
        out.append(f"{where}: {key} entry {subject} carries no change, which"
                   f" costs the signature-ordering signal")
    elif change not in CHANGES[key]:
        out.append(f"{where}: {key} entry {subject} carries change {change!r},"
                   f" not one of {'/'.join(CHANGES[key])} — the"
                   f" signature-ordering rule reads nothing else")
    return out


def _readable(footprint: dict) -> bool:
    """Whether the model can read this footprint without raising.

    Not the same question as `validate`. An entry with no `change:` costs the
    ordering signal and nothing else, so the footprint is still written and
    its bead still groups. An entry that is not a record would raise inside
    `collide._paths`, and a bead the model cannot read is better named by the
    roster rule than handed over as a crash.
    """
    if not set(footprint) - {"bead"}:
        return False
    return all(isinstance(entry, dict)
               for key in IDENTIFIER
               for entry in footprint.get(key) or [])


def parse_args(argv: list) -> tuple:
    """`(run, pairs)` — the run directory and its `bead -> artifact` pairs."""
    run = None
    pairs = []
    rest = list(argv)
    while rest:
        arg = rest.pop(0)
        if arg == "--run":
            if not rest:
                raise UsageError(f"--run needs a value\n{USAGE}")
            run = rest.pop(0)
        elif arg.startswith("--"):
            raise UsageError(f"unknown argument: {arg}\n{USAGE}")
        else:
            bead, sep, artifact = arg.partition("=")
            if not sep or not bead.strip() or not artifact.strip():
                raise UsageError(f"not a <bead>=<artifact> pair: {arg}\n{USAGE}")
            pairs.append((bead.strip(), artifact.strip()))
    if not run:
        raise UsageError(f"--run is required\n{USAGE}")
    return run, pairs


def main(argv: list) -> int:
    try:
        run, pairs = parse_args(argv)
    except UsageError as err:
        print(err, file=sys.stderr)
        return 2

    parsed, findings = [], []
    for bead, artifact in pairs:
        # A block the grammar cannot read costs its own bead and no other, so
        # it is caught per pair: one worker's malformed answer must not take
        # the wave's whole conversion down with it.
        try:
            parsed.append(from_artifact(artifact, bead))
        except BlockError as err:
            findings.append(f"{bead}: {err}")
        except UsageError as err:
            print(err, file=sys.stderr)
            return 2

    findings += [finding for footprint in parsed for finding in validate(footprint)]
    written = [footprint for footprint in parsed if _readable(footprint)]

    path = Path(run) / OUTPUT
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(written, indent=2) + "\n", encoding="utf-8")

    for finding in findings:
        print(finding, file=sys.stderr)
    print(f"{len(written)} footprint(s) written to {path}"
          f" — {len(findings)} finding(s)")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
