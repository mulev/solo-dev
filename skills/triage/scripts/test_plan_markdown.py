#!/usr/bin/env python3
"""Tests for plan_markdown.py — direct calls, no CLI in the way.

Run with `python3 test_plan_markdown.py` (no pytest dependency).
"""

from __future__ import annotations

import sys
import traceback

from plan_markdown import (body, cell, cells_of, checkboxes, column, section,
                           table, waived)

DOC = """# Title

## Implementation Progress

- [ ] Read `a.py` — understand it.
- [x] Create `test_a.py`.

## Implementation

### File: `a.py`

Prose.

## Component Decomposition

| Component | Responsibility | Projected LOC |
|---|---|---|
| `a.py` | Parses a | 90 |
| `b.py` | Parses b | 400 |

**LOC waiver:** `b.py` — projected 400 LOC. Reason: cohesive.

## Architecture Gate Results — Phase 4 — 2026-08-28

Banner.
"""

LINES = DOC.splitlines()


def case_section_does_not_match_a_longer_title() -> None:
    """`## Implementation Progress` must not answer a lookup for `## Implementation`."""
    progress = section(LINES, "Implementation Progress")
    impl = section(LINES, "Implementation")
    assert progress is not None and impl is not None
    assert progress[0] != impl[0], (progress, impl)
    assert any(l.startswith("### File:") for l in LINES[impl[0]:impl[1]]), LINES[impl[0]:impl[1]]


def case_section_matches_a_punctuation_tail() -> None:
    found = section(LINES, "Architecture Gate Results")
    assert found is not None and LINES[found[0]].startswith("## Architecture"), found


def case_section_body_keeps_sub_headings() -> None:
    lines = body(LINES, "Component Decomposition")
    assert any(l.startswith("| `a.py`") for l in lines), lines
    assert not any(l.startswith("## ") for l in lines), lines


def case_missing_section_yields_no_body() -> None:
    assert section(LINES, "Localization") is None
    assert body(LINES, "Localization") == []


def case_checkboxes_are_read_under_their_own_section() -> None:
    steps = checkboxes(LINES, "Implementation Progress")
    assert len(steps) == 2, steps
    assert steps[0].startswith("Read"), steps
    assert steps[1].startswith("Create"), steps


def case_a_wrapped_checkbox_is_one_step_carrying_its_whole_body() -> None:
    """The file path a step is about routinely sits on its wrapped line."""
    doc = """## Implementation Progress

- [ ] Add the three cases in **Testing** to
      `test/a_test.dart`. Done when the cross-resource case **fails**.
- [ ] Run the suite.

## Next
""".splitlines()
    steps = checkboxes(doc, "Implementation Progress")
    assert len(steps) == 2, steps
    assert "`test/a_test.dart`" in steps[0], steps
    assert steps[1] == "Run the suite.", steps


def case_table_is_found_by_its_header_keywords() -> None:
    found = section(LINES, "Component Decomposition")
    grid = table(LINES, found[0], found[1], ("component", "responsib"))
    assert grid is not None
    head, rows = grid
    assert column(head, "loc") == 2, head
    assert len(rows) == 2, rows
    assert rows[1][1][0] == "`b.py`", rows


def case_table_requiring_an_absent_column_is_not_found() -> None:
    found = section(LINES, "Component Decomposition")
    assert table(LINES, found[0], found[1], ("component", "depends")) is None


def case_cell_reads_a_row_by_its_header_keyword() -> None:
    """An absent column and a short row both read as empty, never as an index."""
    found = section(LINES, "Component Decomposition")
    head, rows = table(LINES, found[0], found[1], ("component", "responsib"))
    cells = rows[1][1]
    assert cell(head, cells, "loc") == "400", cells
    assert cell(head, cells, "foreign") == "", cells
    assert cell(head, ["`c.py`"], "loc") == "", head


def case_cells_of_strips_the_outer_pipes() -> None:
    assert cells_of("| a | b |  c |") == ["a", "b", "c"]


def case_waived_reads_the_component_path() -> None:
    assert waived(DOC, "LOC waiver") == {"b.py"}
    assert waived(DOC, "coupling waiver") == set()


CASES = [v for k, v in sorted(globals().items()) if k.startswith("case_")]


def main() -> int:
    failed = 0
    for case in CASES:
        try:
            case()
            print(f"PASS  {case.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL  {case.__name__}: {e}")
        except Exception:
            failed += 1
            print(f"ERROR {case.__name__}")
            traceback.print_exc()
    print(f"\n{len(CASES) - failed}/{len(CASES)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
