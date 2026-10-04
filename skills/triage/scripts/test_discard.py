#!/usr/bin/env python3
"""Cases for the guarded delete.

Every case builds a staging directory with more than one run in it, because
the failure that matters is not "did it delete the run" but "did it delete
only that run". A case with a single run on disk cannot tell those apart.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import discard  # noqa: E402

RUNS = "runs"
RUN = "2026-08-29_ab12"
OTHER = "2026-08-29_cd34"


def staging(tmp: Path) -> Path:
    """Two runs and a promoted one, so a delete has neighbours to spare."""
    root = tmp / RUNS
    for name in (RUN, OTHER):
        (root / name / "todo").mkdir(parents=True)
        (root / name / "ledger.md").write_text("# ledger\n", encoding="utf-8")
        (root / name / "todo" / "plan.md").write_text("x\n", encoding="utf-8")
    (root / "promoted" / "2026-08-28_ee55").mkdir(parents=True)
    (root / "promoted" / "2026-08-28_ee55" / "ledger.md").write_text(
        "# done\n", encoding="utf-8")
    return root


def survivors(root: Path) -> set:
    return {p.name for p in root.iterdir()}


def cli(root: Path, *args: str) -> int:
    return discard.main(["--runs-dir", str(root), *args])


def case_a_short_suffix_resolves_and_deletes_one_run(tmp: Path) -> None:
    root = staging(tmp)
    assert cli(root, "--run-id", "ab12") == 0
    assert survivors(root) == {OTHER, "promoted"}, survivors(root)


def case_the_full_name_also_resolves(tmp: Path) -> None:
    root = staging(tmp)
    assert cli(root, "--run-id", RUN) == 0
    assert survivors(root) == {OTHER, "promoted"}, survivors(root)


def case_artifacts_on_disk_are_removed_with_the_run(tmp: Path) -> None:
    root = staging(tmp)
    cli(root, "--run-id", "ab12")
    assert not (root / RUN).exists()
    assert (root / OTHER / "todo" / "plan.md").is_file(), "a sibling lost files"


def case_zero_matches_is_exit_2_and_deletes_nothing(tmp: Path) -> None:
    root = staging(tmp)
    assert cli(root, "--run-id", "nope") == 2
    assert survivors(root) == {RUN, OTHER, "promoted"}


def case_many_matches_is_exit_2_and_deletes_nothing(tmp: Path) -> None:
    root = staging(tmp)
    (root / "2026-08-30_ab12").mkdir()
    assert cli(root, "--run-id", "ab12") == 2
    assert (root / RUN).is_dir() and (root / "2026-08-30_ab12").is_dir()


def case_a_promoted_run_is_refused(tmp: Path) -> None:
    """Past the point where deleting is an undo: its artifacts are in the real
    tree, so removing the directory destroys the record without undoing it.

    `resolve_run` is what refuses it — it skips `promoted/`, so the id matches
    zero runs. Asserting the message as well as the code is the difference
    between testing that and testing nothing.
    """
    root = staging(tmp)
    code, message, run = discard.plan(root, "ee55")
    assert (code, run) == (2, None), (code, run)
    assert "matches 0 runs" in message, message
    assert (root / "promoted" / "2026-08-28_ee55").is_dir()


def case_a_symlinked_run_is_refused(tmp: Path) -> None:
    """A link planted in staging must not redirect the delete somewhere real."""
    root = staging(tmp)
    real = tmp / "precious"
    real.mkdir()
    (real / "keep.md").write_text("do not delete\n", encoding="utf-8")
    (root / "2026-08-29_ff99").symlink_to(real, target_is_directory=True)
    code, message, run = discard.plan(root, "ff99")
    assert (code, run) == (1, None), (code, run)
    # The reason matters: without the symlink guard the parent-directory check
    # also refuses this, so asserting only the exit code passes either way.
    assert "symlink" in message, message
    assert (real / "keep.md").is_file(), "the symlink target was deleted"


def case_dry_run_prints_the_path_and_deletes_nothing(tmp: Path) -> None:
    root = staging(tmp)
    assert cli(root, "--run-id", "ab12", "--dry-run") == 0
    assert survivors(root) == {RUN, OTHER, "promoted"}


def case_a_missing_runs_directory_is_exit_2(tmp: Path) -> None:
    assert discard.main(["--runs-dir", str(tmp / "nope"),
                         "--run-id", "ab12"]) == 2


def case_the_target_is_always_a_direct_child_of_the_runs_directory(tmp: Path) -> None:
    """`resolve_run` is the single resolution point, and this pins what it
    guarantees — the reason `discard.plan` re-checks none of it."""
    root = staging(tmp)
    code, _, run = discard.plan(root, RUN)
    assert code == 0, code
    assert run.resolve().parent == root.resolve(), run
    assert run.resolve() != root.resolve(), run


def case_the_cli_exits_2_without_a_run_id(tmp: Path) -> None:
    proc = subprocess.run(
        [sys.executable, str(Path(__file__).with_name("discard.py"))],
        capture_output=True, text=True)
    assert proc.returncode == 2, proc.returncode


CASES = [v for k, v in sorted(globals().items()) if k.startswith("case_")]


def main() -> int:
    failed = 0
    for case in CASES:
        with tempfile.TemporaryDirectory() as td:
            try:
                case(Path(td))
                print(f"PASS  {case.__name__}")
            except AssertionError as err:
                failed += 1
                print(f"FAIL  {case.__name__}: {err}")
            except Exception:
                failed += 1
                print(f"ERROR {case.__name__}")
                traceback.print_exc()
    print(f"\n{len(CASES) - failed}/{len(CASES)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
