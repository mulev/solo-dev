#!/usr/bin/env python3
"""Cases for the block-to-dict conversion Wave 3 orders.

The subject is the module that owns the conversion, so the parser is exercised
here rather than beside the brief's example: `test_footprint_contract.py` keeps
asking whether the *example* teaches the right fields, and this file asks
whether the *reader* turns a block into what `collide.py` consumes.

Assertions run through collide's own accessors wherever a parsed shape is the
question — comparing dicts would pass on a shape no reader can read, which is
the class of defect this module exists to close.

Two measured regressions are pinned by name: a bare list item under `files:`
is a finding rather than an `AttributeError` inside `collide._paths`, and a
block that parses is written as it stands, because this module validates shape
and never completeness.

Run with `python3 test_footprints.py` (no pytest dependency).
"""

from __future__ import annotations

import json
import sys
import tempfile
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import collide  # noqa: E402
import footprints  # noqa: E402

WELL_FORMED = """\
footprint:
  bead: b-1
  files:
    - path: lib/a.dart
      module: lib
      change: modify
  symbols:
    - name: A.run
      kind: method
      change: signature
  modules:
    - lib
"""

# The second shape: an empty list written `[]`, which the brief permits, and
# which must parse as a list rather than as the string "[]".
EMPTY_LISTS = """\
footprint:
  bead: b-2
  files:
    - path: lib/b.dart
      module: lib
      change: add
  symbols: []
  modules: []
"""

# A worker that echoes the brief's example before writing its own answer.
ARTIFACT = """\
# Investigation

The brief showed this example:

footprint:
  bead: EXAMPLE
  files:
    - path: lib/example.py
      module: lib
      change: modify

## My own answer

footprint:
  bead: tb-col1
  files:
    - path: lib/shared_render.py
      module: lib
      change: modify
  symbols:
    - name: render_card
      kind: function
      change: behavior
  modules:
    - lib
"""

# `- lib/a.dart` carries no `key: value`, so the parser appends the string
# itself. `collide._paths` calls `.get` on every entry.
BARE_ITEM = """\
footprint:
  bead: b-bare
  files:
    - lib/a.dart
"""

NO_CHANGE = """\
footprint:
  bead: b-nochange
  files:
    - path: lib/a.dart
      module: lib
  symbols:
    - name: A.run
      kind: method
"""

# A footprint carrying files and nothing else: complete enough to group on.
PARTIAL = """\
footprint:
  bead: b-partial
  files:
    - path: lib/a.dart
      module: lib
      change: modify
"""

# A worker that drops the `files:` line writes its records straight under the
# anchor. The parser used to leave with a bare `KeyError: ''`.
NO_LIST_KEY = """\
footprint:
  bead: b-nolist
  - path: lib/a.dart
"""


def expect(got, want) -> None:
    assert got == want, f"got {got!r}, want {want!r}"


def artifact(tmp: Path, text: str, name: str = "a.md") -> Path:
    path = tmp / name
    path.write_text(text, encoding="utf-8")
    return path


def written(run: Path) -> list:
    return json.loads((run / footprints.OUTPUT).read_text(encoding="utf-8"))


def run_dir(tmp: Path) -> Path:
    path = tmp / "run"
    path.mkdir(exist_ok=True)
    return path


# --- the parser ---------------------------------------------------------------


def case_a_well_formed_block_parses_to_the_models_dicts(tmp: Path) -> None:
    footprint = footprints.parse_block(WELL_FORMED)
    expect(collide._bead_id(footprint), "b-1")
    expect(collide._paths(footprint), {"lib/a.dart"})
    expect(collide._symbols(footprint), {"A.run"})
    expect(collide._modules(footprint), {"lib"})
    assert collide._moves_a_signature(footprint), footprint

    empty = footprints.parse_block(EMPTY_LISTS)
    expect(collide._paths(empty), {"lib/b.dart"})
    expect(collide._symbols(empty), set())
    # `modules: []` leaves the derived module, which is what the model reads.
    expect(collide._modules(empty), {"lib"})


def case_from_artifact_parses_into_the_shape_collide_reads(tmp: Path) -> None:
    footprint = footprints.from_artifact(artifact(tmp, ARTIFACT), "tb-col1")
    expect(collide._bead_id(footprint), "tb-col1")
    expect(collide._paths(footprint), {"lib/shared_render.py"})
    expect(collide._symbols(footprint), {"render_card"})
    expect(collide._modules(footprint), {"lib"})


def case_from_artifact_takes_the_last_footprint_anchor(tmp: Path) -> None:
    """The brief prints an example block. A worker that echoes it before
    writing its own would otherwise have the example parsed as its answer."""
    footprint = footprints.from_artifact(artifact(tmp, ARTIFACT), "tb-col1")
    assert collide._bead_id(footprint) != "EXAMPLE", footprint


def case_from_artifact_defaults_the_bead_to_the_assigned_id(tmp: Path) -> None:
    """`collide` drops a footprint with no `bead:`, so the orchestrator's own
    assignment stands in — it knows which bead it dispatched."""
    text = "footprint:\n  files:\n    - path: lib/a.py\n      change: modify\n"
    footprint = footprints.from_artifact(artifact(tmp, text), "tb-col2")
    expect(collide._bead_id(footprint), "tb-col2")


# --- the validator ------------------------------------------------------------


def case_a_bare_list_item_under_files_is_reported_not_raised(tmp: Path) -> None:
    """The measured regression: the parser appends a bare string, and the
    model's accessors call `.get` on it. A finding names it; nothing raises,
    and the CLI keeps the entry out of the file the model reads."""
    footprint = footprints.parse_block(BARE_ITEM)
    expect(footprint["files"], ["lib/a.dart"])
    findings = footprints.validate(footprint)
    assert any("not a record" in f for f in findings), findings
    assert all("b-bare" in f for f in findings), findings

    run = run_dir(tmp)
    expect(footprints.main(["--run", str(run), f"b-bare={artifact(tmp, BARE_ITEM)}"]), 1)
    expect(written(run), [])


def case_a_line_under_no_list_key_is_reported_not_raised(tmp: Path) -> None:
    """Bug round 1, found while simplifying this module and reproduced: a
    block whose records sit under no list key took the whole conversion down
    with `KeyError: ''`, which is precisely what this module promises never to
    do. The grammar now says which line it could not read, and the CLI charges
    it to the one bead whose block it was."""
    try:
        footprints.parse_block(NO_LIST_KEY)
    except footprints.BlockError as err:
        assert "sits under no list key" in str(err), err
    else:
        raise AssertionError("a record under no list key parsed")

    try:
        footprints.parse_block("footprint:\n  files:\n      path: lib/a.dart\n")
    except footprints.BlockError as err:
        assert "continues no record" in str(err), err
    else:
        raise AssertionError("a field continuing no record parsed")

    run = run_dir(tmp)
    pair = f"b-nolist={artifact(tmp, NO_LIST_KEY)}"
    expect(footprints.main(["--run", str(run), pair]), 1)
    expect(written(run), [])


def case_an_entry_with_no_change_is_reported(tmp: Path) -> None:
    """And the finding says what it costs. A missing `change:` loses the
    signature-ordering signal and nothing else — the path and the symbol are
    still read — so the footprint is still written and its bead still groups."""
    footprint = footprints.parse_block(NO_CHANGE)
    findings = footprints.validate(footprint)
    expect(len(findings), 2)
    assert all("ordering" in f for f in findings), findings
    expect(collide._paths(footprint), {"lib/a.dart"})
    expect(collide._symbols(footprint), {"A.run"})
    assert not collide._moves_a_signature(footprint), footprint

    run = run_dir(tmp)
    expect(footprints.main(["--run", str(run), f"b-nochange={artifact(tmp, NO_CHANGE)}"]), 1)
    expect([collide._bead_id(f) for f in written(run)], ["b-nochange"])


def case_an_absent_block_is_reported_as_absent(tmp: Path) -> None:
    """Distinct from malformed, which is the distinction
    `references/collision-model.md` section 6 already requires. A missing
    footprint means the bead cannot be grouped at all — a finding, never a
    silence, and never an exception either."""
    path = artifact(tmp, "# Investigation\n\nNo block here.\n")
    findings = footprints.validate(footprints.from_artifact(path, "tb-x"))
    expect(findings, ["tb-x: the artifact carries no `footprint:` block"])
    assert findings != footprints.validate(footprints.parse_block(BARE_ITEM))


def case_a_bead_preserving_partial_block_is_accepted_as_written(tmp: Path) -> None:
    """The second measured regression: a block that parses is written as it
    stands. This module validates shape, never completeness — a footprint with
    no `symbols:` is a real answer, not a defect."""
    expect(footprints.validate(footprints.parse_block(PARTIAL)), [])
    run = run_dir(tmp)
    expect(footprints.main(["--run", str(run), f"b-partial={artifact(tmp, PARTIAL)}"]), 0)
    expect(written(run), [footprints.parse_block(PARTIAL)])


# --- the CLI ------------------------------------------------------------------


def case_the_cli_exits_0_1_and_2(tmp: Path) -> None:
    run = run_dir(tmp)
    clean = artifact(tmp, ARTIFACT, "clean.md")
    bad = artifact(tmp, BARE_ITEM, "bad.md")
    expect(footprints.main(["--run", str(run), f"tb-col1={clean}"]), 0)
    expect(footprints.main(["--run", str(run), f"b-bare={bad}"]), 1)
    expect(footprints.main([]), 2)
    expect(footprints.main([f"tb-col1={clean}"]), 2)
    expect(footprints.main(["--run", str(run), "--report", "x"]), 2)
    expect(footprints.main(["--run", str(run), "tb-col1"]), 2)
    expect(footprints.main(["--run", str(run), f"tb-col1={tmp / 'absent.md'}"]), 2)


def case_no_pairs_writes_an_empty_list(tmp: Path) -> None:
    """The dry-run path: no worker, so no footprint, and the file the roster
    rule needs is written rather than hand-typed."""
    run = run_dir(tmp)
    expect(footprints.main(["--run", str(run)]), 0)
    expect(written(run), [])


def case_the_written_shape_is_a_bare_list(tmp: Path) -> None:
    """Read back the way `staged_run_checks.footprint_collisions` reads it —
    `json.loads`, then `collide._bead_id` over the members. That accessor path
    is the reader that crashes on a mapping, and only a bare list satisfies it
    (`staged_run_checks.py:189-191`)."""
    run = run_dir(tmp)
    expect(footprints.main(["--run", str(run), f"tb-col1={artifact(tmp, ARTIFACT)}"]), 0)
    staged = written(run)
    assert isinstance(staged, list), staged
    expect({collide._bead_id(f) for f in staged}, {"tb-col1"})


CASES = [v for k, v in sorted(globals().items()) if k.startswith("case_")]


def main() -> int:
    failed = 0
    for case in CASES:
        with tempfile.TemporaryDirectory() as td:
            try:
                case(Path(td))
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
