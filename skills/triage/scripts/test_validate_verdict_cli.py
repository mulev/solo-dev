"""Tests for validate_verdict.py's command line — its exit codes and output.

Split from test_validate_verdict.py, which covers the pure model in process.
The seam is the harness: everything here runs validate_verdict.py as a
subprocess, exactly as test_collide_cli.py stands beside test_collide.py.

The exit contract under test: `0` clean, `1` findings, `2` usage or
configuration error — and `2` is never produced by bad input data.

Run with `python3 test_validate_verdict_cli.py` (no pytest dependency).
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from test_validate_verdict import defect, expect, revise, verdict  # noqa: E402

SCRIPT = HERE / "validate_verdict.py"


def cli(*argv: str, stdin: str = ""):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *argv],
        capture_output=True,
        text=True,
        input=stdin,
    )


def write(tmp: Path, name: str, payload) -> str:
    path = tmp / name
    body = payload if isinstance(payload, str) else json.dumps(payload)
    path.write_text(body, encoding="utf-8")
    return str(path)


def case_valid_file_exits_zero(tmp: Path) -> None:
    proc = cli(write(tmp, "v.json", verdict()))
    expect(proc.returncode, 0, proc.stderr)


def case_invalid_file_exits_one(tmp: Path) -> None:
    proc = cli(write(tmp, "v.json", verdict(verdict="APPROVE")))
    expect(proc.returncode, 1, proc.stdout)
    assert "APPROVE" in proc.stderr, proc.stderr


def case_stdin_dash_reads_a_verdict(tmp: Path) -> None:
    proc = cli("-", stdin=json.dumps(verdict()))
    expect(proc.returncode, 0, proc.stderr)


def case_malformed_json_is_a_finding_not_a_usage_error(tmp: Path) -> None:
    proc = cli(write(tmp, "v.json", "{not json"))
    expect(proc.returncode, 1, proc.stdout)


def case_array_without_history_is_a_finding(tmp: Path) -> None:
    proc = cli(write(tmp, "v.json", [verdict()]))
    expect(proc.returncode, 1, proc.stdout)


def case_history_prints_next_action(tmp: Path) -> None:
    path = write(tmp, "h.json", [revise(["a.md:1", "b.md:9"])])
    proc = cli("--history", path)
    expect(proc.returncode, 0, proc.stderr)
    expect(proc.stdout.strip(), "next_action: REVISE")


def case_history_park_and_pass_print_their_action(tmp: Path) -> None:
    parked = verdict(
        verdict="PARK",
        defect_class="stop-list",
        defects=[defect("a.md", "critical", "touches auth")],
    )
    expect(cli("--history", write(tmp, "p.json", [parked])).stdout.strip(),
           "next_action: PARK")
    expect(cli("--history", write(tmp, "q.json", [verdict()])).stdout.strip(),
           "next_action: PASS")


def case_history_with_one_invalid_round_exits_one(tmp: Path) -> None:
    path = write(tmp, "h.json", [revise(["a.md:1"]), verdict(verdict="APPROVE")])
    proc = cli("--history", path)
    expect(proc.returncode, 1, proc.stdout)
    assert "next_action:" not in proc.stdout, proc.stdout


def case_history_on_a_non_array_is_a_finding(tmp: Path) -> None:
    proc = cli("--history", write(tmp, "h.json", verdict()))
    expect(proc.returncode, 1, proc.stdout)


def case_history_on_an_empty_array_is_a_finding(tmp: Path) -> None:
    proc = cli("--history", write(tmp, "h.json", []))
    expect(proc.returncode, 1, proc.stdout)


def case_no_arguments_is_a_usage_error(tmp: Path) -> None:
    expect(cli().returncode, 2)


def case_unknown_flag_is_a_usage_error(tmp: Path) -> None:
    expect(cli("--bogus").returncode, 2)


def case_history_without_a_path_is_a_usage_error(tmp: Path) -> None:
    expect(cli("--history").returncode, 2)


def case_extra_arguments_are_a_usage_error(tmp: Path) -> None:
    path = write(tmp, "v.json", verdict())
    expect(cli(path, path).returncode, 2)


def case_missing_path_is_a_usage_error(tmp: Path) -> None:
    expect(cli(str(tmp / "absent.json")).returncode, 2)
    expect(cli("--history", str(tmp / "absent.json")).returncode, 2)


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
    if not failed:
        print("ALL TESTS PASSED")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
