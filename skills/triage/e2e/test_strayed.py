#!/usr/bin/env python3
"""Unit cases for `live_dispatch.strayed` — which corpus paths a worker
changed that sit outside its own run directory.

Split out of `test_live_dispatch.py` when the bracket's fakes grew to cover
every guarded tree and pushed that file past the architecture gate's length
signal. The seam is clean rather than convenient: `strayed` is a pure function
over two path-to-hash maps, these cases need one scratch corpus and no stub at
all, and nothing here is shared with the bracket harness next door — no
fixture crosses the seam in either direction.

The red path is the deliverable. Until these existed `strayed` had never
rejected anything except by hand, and a guard that has never reported a leak
is indistinguishable from one that cannot.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import live_dispatch as ld  # noqa: E402
import suite_invariant as inv  # noqa: E402


def _corpus(files: dict) -> Path:
    """A scratch plan corpus, in the two pieces `strayed` reads: root and
    files."""
    root = Path(tempfile.mkdtemp(prefix="ld-corpus-"))
    for name, text in files.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return root


def case_strayed_allows_a_write_inside_the_run() -> None:
    corpus = _corpus({"runs/r1/ledger.md": "x"})
    run = corpus / "runs" / "r1"
    before = inv.content_map(corpus)
    (run / "artifact.md").write_text("written", encoding="utf-8")
    assert ld.strayed(before, inv.content_map(corpus), run, corpus) == []


def case_strayed_catches_a_write_outside_the_run() -> None:
    """The whole point: a file the worker never reported, in the live backlog."""
    corpus = _corpus({"runs/r1/ledger.md": "x"})
    run = corpus / "runs" / "r1"
    before = inv.content_map(corpus)
    (corpus / "todo").mkdir()
    (corpus / "todo" / "plan.md").write_text("leaked", encoding="utf-8")
    assert ld.strayed(before, inv.content_map(corpus), run, corpus) == [
        "todo/plan.md"]


def case_strayed_catches_an_edit_to_a_file_outside_the_run() -> None:
    corpus = _corpus({"runs/r1/ledger.md": "x", "todo/plan.md": "original"})
    run = corpus / "runs" / "r1"
    before = inv.content_map(corpus)
    (corpus / "todo" / "plan.md").write_text("rewritten", encoding="utf-8")
    assert ld.strayed(before, inv.content_map(corpus), run, corpus) == [
        "todo/plan.md"]


def case_strayed_catches_a_deletion_outside_the_run() -> None:
    corpus = _corpus({"runs/r1/ledger.md": "x", "todo/plan.md": "original"})
    run = corpus / "runs" / "r1"
    before = inv.content_map(corpus)
    (corpus / "todo" / "plan.md").unlink()
    assert ld.strayed(before, inv.content_map(corpus), run, corpus) == [
        "todo/plan.md"]


def case_strayed_does_not_confuse_a_sibling_run_for_its_own() -> None:
    """Sibling run directories share a name prefix by construction, so this is
    path arithmetic rather than a string comparison."""
    corpus = _corpus({"runs/2026-08-29_abc/ledger.md": "x"})
    run = corpus / "runs" / "2026-08-29_abc"
    before = inv.content_map(corpus)
    other = corpus / "runs" / "2026-08-29_abcdef"
    other.mkdir(parents=True)
    (other / "plan.md").write_text("another run", encoding="utf-8")
    assert ld.strayed(before, inv.content_map(corpus), run, corpus) == [
        "runs/2026-08-29_abcdef/plan.md"]


def case_strayed_is_silent_when_nothing_moved() -> None:
    corpus = _corpus({"runs/r1/ledger.md": "x", "todo/plan.md": "original"})
    before = inv.content_map(corpus)
    assert ld.strayed(before, inv.content_map(corpus),
                      corpus / "runs" / "r1", corpus) == []


CASES = [v for k, v in sorted(globals().items()) if k.startswith("case_")]


def main() -> int:
    failed = 0
    for case in CASES:
        try:
            case()
            print(f"PASS  {case.__name__}")
        except AssertionError as err:
            failed += 1
            print(f"FAIL  {case.__name__}: {err}")
        except Exception as err:
            failed += 1
            print(f"ERROR {case.__name__}: {type(err).__name__}: {err}")
    print(f"\n{len(CASES) - failed}/{len(CASES)} cases passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
