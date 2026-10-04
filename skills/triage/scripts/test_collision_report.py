"""Tests for collision_report.py — what the rendered report says, and what it
says when there is nothing to say.

Hand-built group records, no filesystem and no collide.py: the renderer reads
only the fields a record carries, so it must be provable without the model
that produced them.

Run with `python3 test_collision_report.py` (no pytest dependency).
"""

from __future__ import annotations

import sys
import tempfile
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import collision_report  # noqa: E402


def expect(got, want) -> None:
    assert got == want, f"got {got!r}, want {want!r}"


def record(group_id: str, members: list, decision: str, reason: str, **kw) -> dict:
    base = {
        "group_id": group_id,
        "members": members,
        "decision": decision,
        "reason": reason,
        "late_duplicate": False,
        "order": list(members),
        "evidence": {"files": [], "symbols": []},
        "dep_intents": [],
    }
    base.update(kw)
    return base


def case_report_names_every_group_its_decision_and_its_reason(tmp: Path) -> None:
    groups = [
        record(
            "g1",
            ["d-1", "d-2"],
            "SEQUENCE",
            "shared files: a.dart; distinct cause keys",
            order=["d-2", "d-1"],
            evidence={"files": ["a.dart"], "symbols": ["load"]},
            dep_intents=[{"command": "bd dep add d-1 d-2", "why": "shared files: a.dart"}],
        ),
        record("g2", ["d-3"], "INDEPENDENT", "no overlap"),
    ]
    out = collision_report.render_report(groups, [])
    assert "## g1 — SEQUENCE" in out, out
    assert "## g2 — INDEPENDENT" in out, out
    assert "- Members: d-1, d-2" in out, out
    assert "- Reason: shared files: a.dart; distinct cause keys" in out, out
    assert "- Planning order: d-2 -> d-1" in out, out
    assert "- Shared files: a.dart" in out, out
    assert "- Shared symbols: load" in out, out
    assert "- Dependency intent: `bd dep add d-1 d-2` — shared files: a.dart" in out, out


def case_report_lists_module_only_overlaps_and_late_duplicates_or_says_none(
    tmp: Path,
) -> None:
    """Both sections always render. An empty one says `_none_` rather than
    disappearing — a missing section reads as "not checked"."""
    empty = collision_report.render_report([], [])
    assert "## Module-only overlaps (did not group)" in empty, empty
    assert "## Late duplicates (missed by dedup)" in empty, empty
    expect(empty.count("_none_"), 2)

    groups = [
        record("g1", ["d-1", "d-2"], "MERGE", "identical footprints", late_duplicate=True)
    ]
    overlaps = [{"beads": ["d-3", "d-4"], "modules": ["lib/features/opds"]}]
    filled = collision_report.render_report(groups, overlaps)
    assert "- d-3 + d-4: lib/features/opds" in filled, filled
    assert "- g1: d-1, d-2" in filled, filled
    assert "_none_" not in filled, filled


def case_an_unclassified_record_renders_with_its_reason(tmp: Path) -> None:
    """The roster check adds records with no evidence and no intents; they must
    print through the same loop rather than needing a branch of their own."""
    reason = "no footprint on record — collisions could not be checked"
    out = collision_report.render_report(
        [record("u1", ["d-9"], "UNCLASSIFIED", reason)], []
    )
    assert "## u1 — UNCLASSIFIED" in out, out
    assert "- Members: d-9" in out, out
    assert f"- Reason: {reason}" in out, out
    assert "- Shared files:" not in out, out


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
