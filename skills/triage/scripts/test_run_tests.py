"""Tests for run_tests.py — discovery depth and exit codes.

Run with `python3 test_run_tests.py` (no pytest dependency).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

RUNNER = Path(__file__).resolve().parent / "run_tests.py"

PASSING = "import sys\nsys.exit(0)\n"
FAILING = "import sys\nsys.exit(1)\n"


def stage(tmp: Path, *files: tuple[str, str]) -> Path:
    """Copy run_tests.py into tmp beside the given (filename, body) fake tests."""
    shutil.copy(RUNNER, tmp / "run_tests.py")
    for name, body in files:
        (tmp / name).write_text(body, encoding="utf-8")
    return tmp / "run_tests.py"


def run(runner: Path) -> tuple[int, str]:
    proc = subprocess.run([sys.executable, str(runner)], capture_output=True, text=True)
    return proc.returncode, proc.stdout


def case_single_passing_file_exits_zero(tmp: Path) -> None:
    code, out = run(stage(tmp, ("test_alpha.py", PASSING)))
    assert code == 0, (code, out)
    assert "PASS  test_alpha.py" in out, out


def case_one_failing_file_exits_one(tmp: Path) -> None:
    code, out = run(stage(tmp, ("test_alpha.py", PASSING), ("test_beta.py", FAILING)))
    assert code == 1, (code, out)
    assert "PASS  test_alpha.py" in out, out
    assert "FAIL  test_beta.py" in out, out


def case_summary_counts_passing_files(tmp: Path) -> None:
    code, out = run(stage(tmp, ("test_alpha.py", PASSING), ("test_beta.py", FAILING)))
    assert "1/2 test files passed" in out, out
    assert code == 1, (code, out)


def case_fixtures_subdir_is_not_discovered(tmp: Path) -> None:
    runner = stage(tmp, ("test_alpha.py", PASSING))
    (tmp / "fixtures").mkdir()
    (tmp / "fixtures" / "test_decoy.py").write_text(FAILING, encoding="utf-8")
    code, out = run(runner)
    assert code == 0, (code, out)
    assert "test_decoy.py" not in out, out


def case_no_test_files_exits_zero(tmp: Path) -> None:
    code, out = run(stage(tmp))
    assert code == 0, (code, out)
    assert "0/0 test files passed" in out, out


def case_discovery_is_relative_to_script_not_cwd(tmp: Path) -> None:
    runner = stage(tmp, ("test_alpha.py", FAILING))
    elsewhere = tmp / "elsewhere"
    elsewhere.mkdir()
    proc = subprocess.run(
        [sys.executable, str(runner)],
        capture_output=True,
        text=True,
        cwd=str(elsewhere),
    )
    assert proc.returncode == 1, (proc.returncode, proc.stdout)
    assert "FAIL  test_alpha.py" in proc.stdout, proc.stdout


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
