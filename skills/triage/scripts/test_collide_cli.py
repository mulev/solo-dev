"""Tests for collide.py's command line — its exit codes, what it writes back
into the manifest, and the collision report it renders.

Split from test_collide.py, which covers the pure model in process. The seam
is the harness: everything here runs collide.py as a subprocess, exactly as
test_dedup_cli.py stands beside test_dedup.py.

Run with `python3 test_collide_cli.py` (no pytest dependency).
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

from test_collide import CATALOG, HARNESS, READER, expect, fp  # noqa: E402


def cli(tmp: Path, *argv: str):
    proc = subprocess.run(
        [sys.executable, str(HERE / "collide.py"), *argv],
        capture_output=True,
        text=True,
    )
    return proc


def run(tmp: Path, footprints, causes=None, manifest=None, extra=()):
    mpath = tmp / "manifest.json"
    payload = manifest if manifest is not None else {"project": "demo", "beads": []}
    mpath.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    fpath = tmp / "footprints.json"
    fpath.write_text(json.dumps(footprints), encoding="utf-8")
    argv = ["--manifest", str(mpath), "--footprints", str(fpath)]
    if causes is not None:
        cpath = tmp / "causes.json"
        cpath.write_text(json.dumps(causes), encoding="utf-8")
        argv += ["--causes", str(cpath)]
    return cli(tmp, *argv, *extra), mpath


def case_all_independent_run_exits_zero(tmp: Path) -> None:
    proc, mpath = run(tmp, [fp("d-1", [HARNESS]), fp("d-2", [READER])])
    expect(proc.returncode, 0)
    after = json.loads(mpath.read_text(encoding="utf-8"))
    expect([g["decision"] for g in after["groups"]], ["INDEPENDENT", "INDEPENDENT"])


def case_sequence_only_run_exits_zero(tmp: Path) -> None:
    proc, mpath = run(
        tmp,
        [fp("d-1", [HARNESS]), fp("d-2", [HARNESS, CATALOG])],
        causes={"d-1": "one", "d-2": "two"},
    )
    expect(proc.returncode, 0)
    expect(json.loads(mpath.read_text())["groups"][0]["decision"], "SEQUENCE")


def case_any_merge_exits_one(tmp: Path) -> None:
    proc, _ = run(
        tmp,
        [fp("d-1", [HARNESS]), fp("d-2", [HARNESS, CATALOG])],
        causes={"d-1": "same", "d-2": "same"},
    )
    expect(proc.returncode, 1)


def case_any_late_duplicate_exits_one(tmp: Path) -> None:
    proc, _ = run(tmp, [fp("d-1", [HARNESS]), fp("d-2", [HARNESS])],
                  causes={"d-1": "one", "d-2": "two"})
    # distinct causes but identical footprints — still a merge, still exit 1
    expect(proc.returncode, 1)


def case_missing_manifest_flag_exits_two(tmp: Path) -> None:
    fpath = tmp / "f.json"
    fpath.write_text("[]")
    proc = cli(tmp, "--footprints", str(fpath))
    expect(proc.returncode, 2)
    assert "--manifest" in proc.stderr, proc.stderr


def case_missing_footprints_flag_exits_two(tmp: Path) -> None:
    mpath = tmp / "manifest.json"
    mpath.write_text(json.dumps({"beads": []}, indent=2) + "\n")
    proc = cli(tmp, "--manifest", str(mpath))
    expect(proc.returncode, 2)
    assert "--footprints" in proc.stderr, proc.stderr


def case_unknown_flag_exits_two(tmp: Path) -> None:
    proc, _ = run(tmp, [], extra=("--nope",))
    expect(proc.returncode, 2)


def case_a_bare_undashed_flag_name_is_not_accepted(tmp: Path) -> None:
    """`removeprefix` is a no-op on undashed input, so `manifest x.json` used
    to be taken as `--manifest x.json`. A flag name is only a flag with the
    dashes on it."""
    fpath = tmp / "f.json"
    fpath.write_text("[]")
    mpath = tmp / "manifest.json"
    mpath.write_text(json.dumps({"beads": []}, indent=2) + "\n")
    proc = cli(tmp, "manifest", str(mpath), "--footprints", str(fpath))
    expect(proc.returncode, 2)
    assert "unknown argument: manifest" in proc.stderr, proc.stderr


def case_unreadable_footprints_file_exits_two(tmp: Path) -> None:
    mpath = tmp / "manifest.json"
    mpath.write_text(json.dumps({"beads": []}, indent=2) + "\n")
    proc = cli(tmp, "--manifest", str(mpath), "--footprints", str(tmp / "gone.json"))
    expect(proc.returncode, 2)


def case_unreadable_manifest_exits_two(tmp: Path) -> None:
    fpath = tmp / "f.json"
    fpath.write_text("[]")
    proc = cli(tmp, "--manifest", str(tmp / "gone.json"), "--footprints", str(fpath))
    expect(proc.returncode, 2)


def case_empty_footprints_file_exits_zero_with_no_groups(tmp: Path) -> None:
    """Bad or empty data is never a usage error."""
    proc, mpath = run(tmp, [])
    expect(proc.returncode, 0)
    expect(json.loads(mpath.read_text())["groups"], [])


def case_footprint_without_a_bead_id_is_ignored_not_a_usage_error(tmp: Path) -> None:
    proc, mpath = run(tmp, [{"files": [{"path": HARNESS}]}, fp("d-1", [HARNESS])])
    expect(proc.returncode, 0)
    expect(json.loads(mpath.read_text())["groups"][0]["members"], ["d-1"])


# --- what lands in the manifest and the report -------------------------------


def case_groups_are_written_additively_and_stamp_the_schema_version(
    tmp: Path,
) -> None:
    before = {
        "project": "demo",
        "beads": [{"id": "d-1", "route": "plan"}],
        "clusters": [{"cluster_id": "c1"}],
        "covered": [],
    }
    proc, mpath = run(tmp, [fp("d-1", [HARNESS])], manifest=before)
    after = json.loads(mpath.read_text(encoding="utf-8"))
    expect(proc.returncode, 0)
    for key in before:
        expect(after[key], before[key])
    expect(sorted(set(after) - set(before)), ["groups", "schema_version"])


def case_the_report_names_the_shared_file_and_the_module_that_did_not_group(
    tmp: Path,
) -> None:
    module = "demo/lib/features/opds"
    footprints = [
        fp("d-1", [HARNESS]),
        fp("d-2", [HARNESS]),
        fp("d-3", [f"{module}/a.dart"]),
        fp("d-4", [f"{module}/b.dart"]),
    ]
    proc, mpath = run(tmp, footprints, causes={"d-1": "same", "d-2": "same"})
    report = (mpath.parent / "collision_report.md").read_text(encoding="utf-8")
    assert HARNESS in report, report
    assert module in report, report
    assert "Module-only overlaps" in report, report
    assert "Late duplicates" in report, report


def case_a_footprintless_run_bead_exits_one_and_reaches_the_report(tmp: Path) -> None:
    """The whole point of the roster check, end to end: `d-2` is in the run,
    has no footprint, and must appear in the manifest, the report and the exit
    code rather than leaving the run at exit 0."""
    manifest = {
        "project": "demo",
        "beads": [{"id": "d-1", "route": "plan"}, {"id": "d-2", "route": "plan"}],
    }
    proc, mpath = run(tmp, [fp("d-1", [HARNESS])], manifest=manifest)
    expect(proc.returncode, 1)
    after = json.loads(mpath.read_text(encoding="utf-8"))
    stray = [g for g in after["groups"] if g["decision"] == "UNCLASSIFIED"]
    expect([g["members"] for g in stray], [["d-2"]])
    report = (mpath.parent / "collision_report.md").read_text(encoding="utf-8")
    assert "d-2" in report, report
    assert "unclassified=1" in proc.stdout, proc.stdout


def case_report_path_is_overridable(tmp: Path) -> None:
    out = tmp / "elsewhere" / "report.md"
    proc, _ = run(tmp, [fp("d-1", [HARNESS])], extra=("--report", str(out)))
    expect(proc.returncode, 0)
    assert out.is_file(), out


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
