"""The footprint example brief_invest.sh prints must parse into the shape
collide.py reads.

The brief's example is a contract, not an illustration: a worker reproduces
what it is shown, so a field missing from the example is a field missing from
every real footprint. Before this file existed the example carried no
`change:` and no `bead:` at all — the first silently disabled collide's
"signature-mover goes first" ordering rule (every bead scored moves_first = 1,
so SEQUENCE groups were ordered by module count and bead ID), the second
dropped the footprint out of the graph entirely.

Assertions run through collide's own readers (`_bead_id`, `_paths`,
`_symbols`, `_modules`, `_moves_a_signature`, `_order`). Comparing the example
against a pinned string would pass forever on a stale copy, which is how the
defect survived the test file next door.

The block grammar is not this file's: `footprints.parse_block` owns it, and
Wave 3 step 2 invokes the same reader on real artifacts. What is calibrated
here is the *example* — a second copy of the parser would let the two drift
in exactly the direction this file exists to catch.

Run with `python3 test_footprint_contract.py` (no pytest dependency).
"""

from __future__ import annotations

import sys
import tempfile
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import collide  # noqa: E402
import footprints  # noqa: E402
import test_briefs  # noqa: E402

READER_PAGE = "lib/features/reader/reader_page.dart"
PROGRESS_STORE = "lib/core/storage/progress_store.dart"
RESTORE = "ProgressStore.restore"


def expect(got, want) -> None:
    assert got == want, f"got {got!r}, want {want!r}"


def example_block(tmp: Path) -> str:
    """The `footprint:` block of the real generator's stdout: the bare anchor
    line plus every indented line under it.

    The generator runs against the temp skills tree test_briefs builds.
    Anchored on a line that is exactly `footprint:` — the report section ends
    with `footprint: counts of ...`, which is a field, not the block.
    """
    lines = test_briefs.brief(tmp, "brief_invest.sh").splitlines()
    starts = [i for i, line in enumerate(lines) if line.rstrip() == "footprint:"]
    assert len(starts) == 1, f"want one `footprint:` anchor line, found {len(starts)}"
    start = starts[0]
    end = start + 1
    while end < len(lines) and lines[end].startswith(" "):
        end += 1
    return "\n".join(lines[start:end])


def example(tmp: Path) -> dict:
    """The brief's example, assembled into the dict shape collide reads."""
    return footprints.parse_block(example_block(tmp))


def records(footprint: dict, key: str) -> list[dict]:
    value = footprint.get(key)
    assert isinstance(value, list), f"{key} must open a list of records, got {value!r}"
    return value


def without_change(entries: list[dict]) -> list[dict]:
    """The same records with their `change:` field dropped."""
    return [{k: v for k, v in entry.items() if k != "change"} for entry in entries]


def decide_one(footprints: list[dict]) -> dict:
    """build_graph -> group -> decide, asserting the pair forms one component."""
    graph = collide.build_graph(footprints)
    components = collide.group(graph, footprints)
    assert len(components) == 1, f"want one component, got {len(components)}"
    return collide.decide(components[0], {})


def pair(with_change: bool = True) -> list[dict]:
    """Two beads colliding on one symbol.

    The IDs and module counts are chosen so both fallback sort keys point the
    wrong way: without `change`, the behaviour bead wins on bead ID *and* on
    module count. The signature bead carries an extra file so `_identical`
    cannot short-circuit the component to MERGE before `_order` is consulted.
    """
    sig = {
        "bead": "b-z-signature",
        "files": [
            {"path": READER_PAGE, "module": "lib/features/reader", "change": "modify"},
            {"path": PROGRESS_STORE, "module": "lib/core/storage", "change": "modify"},
        ],
        "symbols": [{"name": RESTORE, "kind": "method", "change": "signature"}],
        "modules": ["lib/core/storage", "lib/features/reader"],
    }
    beh = {
        "bead": "b-a-behavior",
        "files": [
            {"path": READER_PAGE, "module": "lib/features/reader", "change": "modify"},
        ],
        "symbols": [{"name": RESTORE, "kind": "method", "change": "behavior"}],
        "modules": ["lib/features/reader"],
    }
    if with_change:
        return [sig, beh]
    stripped = []
    for footprint in (sig, beh):
        files = without_change(footprint["files"])
        symbols = without_change(footprint["symbols"])
        stripped.append(dict(footprint, files=files, symbols=symbols))
    return stripped


# --- the example the generator prints ----------------------------------------


def case_the_brief_example_parses_into_a_footprint_collide_can_read(tmp: Path) -> None:
    footprint = example(tmp)
    expect(collide._bead_id(footprint), "b-1")
    assert collide._paths(footprint), "no file paths in the example"
    assert collide._symbols(footprint), "no symbol names in the example"
    assert collide._modules(footprint), "no modules in the example"


def case_the_brief_example_shows_a_signature_change(tmp: Path) -> None:
    """The field the ordering rule keys off must be demonstrated, not merely
    permitted. An example showing only `change: behavior` teaches workers a
    vocabulary they will never use for the one case that matters.

    The second half mutates the parsed example rather than a fixture, so this
    case cannot pass by reading the nesting instead of the field.
    """
    footprint = example(tmp)
    symbols = records(footprint, "symbols")
    assert collide._moves_a_signature(footprint), symbols
    stripped = dict(footprint, symbols=without_change(symbols))
    assert not collide._moves_a_signature(stripped), "the check above ignores `change:`"


def case_every_file_and_symbol_entry_carries_a_change(tmp: Path) -> None:
    footprint = example(tmp)
    for entry in records(footprint, "files"):
        assert entry.get("change") in {"add", "modify", "delete"}, entry
    for entry in records(footprint, "symbols"):
        assert entry.get("change") in {"add", "signature", "behavior", "remove"}, entry


def case_the_brief_example_names_the_bead_it_was_generated_for(tmp: Path) -> None:
    """`_pairs` filters on `_bead_id`, so a footprint without one leaves the
    graph silently instead of failing loudly."""
    block = example_block(tmp)
    assert "bead:" in block, block
    expect(collide.build_graph([footprints.parse_block(block)]), {"b-1": {}})


# --- the ordering rule the example has to teach ------------------------------


def case_the_signature_mover_is_planned_first(tmp: Path) -> None:
    record = decide_one(pair())
    expect(record["decision"], "SEQUENCE")
    expect(record["order"], ["b-z-signature", "b-a-behavior"])
    expect([intent["command"] for intent in record["dep_intents"]],
           ["bd dep add b-a-behavior b-z-signature"])
    expect([(i["from"], i["to"]) for i in record["dep_intents"]],
           [("b-a-behavior", "b-z-signature")])


def case_stripping_change_reverses_the_order(tmp: Path) -> None:
    """The negative half of the calibration: this is what the flat example
    produced. Kept so a future edit that drops `change:` again fails loudly
    instead of quietly reordering."""
    record = decide_one(pair(with_change=False))
    expect(record["decision"], "SEQUENCE")
    expect(record["order"], ["b-a-behavior", "b-z-signature"])
    expect([intent["command"] for intent in record["dep_intents"]],
           ["bd dep add b-z-signature b-a-behavior"])
    expect([(i["from"], i["to"]) for i in record["dep_intents"]],
           [("b-z-signature", "b-a-behavior")])


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
