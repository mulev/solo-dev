#!/usr/bin/env python3
"""Read the markdown structures a plan artifact is built from.

Every check in the plan linter is anchored on one of these — a section found
by its own heading, a table found by its header row, a checkbox found under a
named section. Phase 3's linter measured the cost of the alternative: reading
adjacent prose as if it were structured content produced most of its false
positives, and a tier 1 gate that cries wolf gets switched off.

`Finding` lives here because this is the lowest module, so the check modules
import downward and nothing imports back.
"""

from __future__ import annotations

import collections
import re

Finding = collections.namedtuple("Finding", "check severity location reason")

ERROR, WARN, SKIP = "error", "warn", "skip"

CHECKBOX = re.compile(r"^\s*-\s*\[[ xX]\]\s*(.+)$")
TITLE_TAIL = ("—", "-", ":", "(", ",")   # a `## Name — tail` is still `## Name`


def section(lines: list[str], name: str) -> tuple[int, int] | None:
    """(heading index, first index past the body) for `## name`.

    The title must be `name` itself, optionally trailed past a punctuation
    separator — a following *word* makes it a different section, which is what
    keeps `## Implementation Progress` out of a lookup for `## Implementation`.
    The body runs to the next `## `, so `###` sub-headings stay inside it.
    """
    want = name.lower()
    for i, line in enumerate(lines):
        if not line.startswith("## "):
            continue
        title = line[3:].strip().lower()
        if not title.startswith(want):
            continue
        tail = title[len(want):].lstrip()
        if tail and tail[0] not in TITLE_TAIL:
            continue
        end = next((j for j in range(i + 1, len(lines))
                    if lines[j].startswith("## ")), len(lines))
        return i, end
    return None


def body(lines: list[str], name: str) -> list[str]:
    """The lines under `## name`, heading excluded. Empty when it is absent."""
    found = section(lines, name)
    return lines[found[0] + 1:found[1]] if found else []


def cells_of(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def table(lines: list[str], lo: int, hi: int,
          required: tuple[str, ...]) -> tuple[list[str], list[tuple[int, list[str]]]] | None:
    """Header cells and numbered rows of the first table carrying `required`.

    Rows are located by the header row's own keywords rather than by column
    position, so an artifact that adds a column — a real one in the corpus
    carries `Repo` between `Phase` and `Scope` — still parses.
    """
    for i in range(lo, hi):
        if not lines[i].lstrip().startswith("|"):
            continue
        head = cells_of(lines[i])
        low = [c.lower() for c in head]
        if not all(any(key in c for c in low) for key in required):
            continue
        rows = []
        for j in range(i + 2, hi):
            if not lines[j].lstrip().startswith("|"):
                break
            rows.append((j, cells_of(lines[j])))
        return head, rows
    return None


def column(head: list[str], key: str) -> int:
    """Index of the first header cell holding `key`, or -1."""
    return next((k for k, c in enumerate(head) if key in c.lower()), -1)


def cell(head: list[str], cells: list[str], key: str) -> str:
    """The row cell under the header holding `key`, or "" when there is none.

    The counterpart to `table` finding rows by keyword: a column the artifact
    never wrote, and a row that ran short of cells, both read as empty rather
    than raising on an index the header promised.
    """
    k = column(head, key)
    return cells[k] if 0 <= k < len(cells) else ""


def checkboxes(lines: list[str], name: str) -> list[str]:
    """Checkbox bodies under `## name`, in document order.

    A step wrapped over several indented lines is one step, and the wrapped
    lines routinely carry the file path the step is about — reading only the
    first line reports a phase as having written no test when its test path
    sits on line two.
    """
    out: list[str] = []
    open_step = False
    for line in body(lines, name):
        m = CHECKBOX.match(line)
        if m:
            out.append(m.group(1))
            open_step = True
        elif (open_step and line.strip() and line.startswith((" ", "\t"))
              and not line.lstrip().startswith(("-", "*", "|", "#"))):
            out[-1] += " " + line.strip()
        else:
            open_step = False
    return out


def waived(text: str, kind: str) -> set[str]:
    """Component paths named by a `**{kind}:**` line or the bullets under it."""
    names, grab = set(), False
    for line in text.splitlines():
        if re.search(r"\*\*" + kind + r"s?:?\*\*", line, re.IGNORECASE):
            names.update(re.findall(r"`([^`]+)`", line))
            grab = True
        elif grab and line.lstrip().startswith("-"):
            names.update(re.findall(r"`([^`]+)`", line))
        elif line.strip():
            grab = False
    return names
