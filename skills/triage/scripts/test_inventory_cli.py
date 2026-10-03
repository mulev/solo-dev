"""Tests for inventory.py's command line — its exit codes, the bd calls it
makes, and the manifest it writes.

Split from test_inventory.py, which covers the rubric in process. The seam is
the harness: everything here runs inventory.py as a subprocess, exactly as
test_dedup_cli.py stands beside test_dedup.py.

Run with `python3 test_inventory_cli.py` (no pytest dependency).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from test_inventory import bead, expect, workspace  # noqa: E402

FIXTURES = HERE / "fixtures"
REASONS = {
    "no investigation on record",
    "investigation on record",
    "already planned",
    "open with no plan path",
    "owned by its master plan",
}

FAKE_BD = """#!/usr/bin/env python3
import pathlib, sys
here = pathlib.Path(__file__).resolve().parent
with (here / "bd.log").open("a") as log:
    log.write(" ".join(sys.argv[1:]) + "\\n")
name = "list" if sys.argv[1] == "list" else "show"
sys.stdout.write((here / (name + ".json")).read_text())
"""


FAILING_BD = """#!/usr/bin/env python3
import sys
sys.stderr.write("bd: cannot open database\\n")
sys.exit(1)
"""

NON_JSON_BD = """#!/usr/bin/env python3
import sys
sys.stdout.write("not json\\n")
"""


def cli(
    tmp: Path, listing: list, shown: list, *args: str, script: str = FAKE_BD
) -> tuple[int, str, Path]:
    """Run inventory.py against a fake `bd` on PATH. Returns (code, stdout, bindir)."""
    bindir = tmp / "bin"
    bindir.mkdir(exist_ok=True)
    fake = bindir / "bd"
    fake.write_text(script, encoding="utf-8")
    fake.chmod(0o755)
    (bindir / "list.json").write_text(json.dumps(listing), encoding="utf-8")
    (bindir / "show.json").write_text(json.dumps(shown), encoding="utf-8")
    env = dict(os.environ)
    env["PATH"] = f"{bindir}:{env['PATH']}"
    env["TRIAGE_PROJECTS_ROOT"] = str(workspace(tmp))
    proc = subprocess.run(
        [sys.executable, str(HERE / "inventory.py"), *args],
        capture_output=True,
        text=True,
        cwd=str(tmp),
        env=env,
    )
    return proc.returncode, proc.stdout + proc.stderr, bindir


def case_unknown_project_exits_two(tmp: Path) -> None:
    code, out, _ = cli(tmp, [], [], "--project", "nosuch")
    assert code == 2, (code, out)
    assert "nosuch" in out, out


def case_missing_project_flag_exits_two(tmp: Path) -> None:
    code, out, _ = cli(tmp, [], [])
    assert code == 2, (code, out)


def case_missing_projects_root_exits_two(tmp: Path) -> None:
    """The documented invocation cannot resolve a project without the seam, so
    omitting it is exit 2 with a usage line — not a read of the real tracker."""
    env = dict(os.environ)
    env.pop("TRIAGE_PROJECTS_ROOT", None)
    proc = subprocess.run(
        [sys.executable, str(HERE / "inventory.py"), "--project", "demo"],
        capture_output=True, text=True, cwd=str(tmp), env=env,
    )
    expect(proc.returncode, 2)
    assert "TRIAGE_PROJECTS_ROOT" in proc.stderr, proc.stderr


def case_unknown_flag_exits_two(tmp: Path) -> None:
    code, out, _ = cli(tmp, [], [], "--project", "demo", "--wat")
    assert code == 2, (code, out)


def case_empty_backlog_exits_zero_and_never_calls_show(tmp: Path) -> None:
    dest = tmp / "run" / "manifest.json"
    code, out, bindir = cli(tmp, [], [], "--project", "demo", "--out", str(dest))
    assert code == 0, (code, out)
    log = (bindir / "bd.log").read_text()
    assert "show" not in log, log
    manifest = json.loads(dest.read_text())
    expect(manifest["beads"], [])
    expect(set(manifest["counts"].values()), {0})


def case_drift_bead_exits_one(tmp: Path) -> None:
    listing = [bead(id="d-1", status="open")]
    code, out, _ = cli(tmp, listing, [{"id": "d-1"}], "--project", "demo")
    assert code == 1, (code, out)


def case_backlog_without_drift_exits_zero(tmp: Path) -> None:
    listing = [bead(id="d-1", status="needs-plan")]
    code, out, _ = cli(tmp, listing, [{"id": "d-1"}], "--project", "demo")
    assert code == 0, (code, out)


def case_out_flag_writes_manifest_to_named_path(tmp: Path) -> None:
    listing = [bead(id="d-1", status="needs-plan")]
    dest = tmp / "sub" / "m.json"
    code, out, _ = cli(
        tmp, listing, [{"id": "d-1"}], "--project", "demo", "--out", str(dest)
    )
    assert code == 0, (code, out)
    assert dest.exists(), out
    assert not (tmp / "manifest.json").exists(), "wrote the default path too"


def case_notes_come_from_show_not_from_list(tmp: Path) -> None:
    listing = [bead(id="d-1", status="needs-plan", notes="Plan: /stale.md")]
    shown = [{"id": "d-1", "notes": "Investigation: /real.md"}]
    dest = tmp / "run" / "manifest.json"
    code, out, bindir = cli(tmp, listing, shown, "--project", "demo", "--json",
                            "--out", str(dest))
    assert code == 0, (code, out)
    manifest = json.loads(dest.read_text())
    expect(manifest["beads"][0]["route"], "plan")
    log = (bindir / "bd.log").read_text().splitlines()
    expect([line.split()[0] for line in log], ["list", "show"])
    assert "--limit 0" in log[0], log[0]
    assert "d-1" in log[1], log[1]


def case_batched_show_carries_every_id(tmp: Path) -> None:
    listing = [bead(id=f"d-{n}", status="needs-plan") for n in range(3)]
    shown = [{"id": f"d-{n}"} for n in range(3)]
    code, out, bindir = cli(tmp, listing, shown, "--project", "demo")
    assert code == 0, (code, out)
    show_line = (bindir / "bd.log").read_text().splitlines()[1]
    for n in range(3):
        assert f"d-{n}" in show_line, show_line


def case_a_failing_bd_exits_two_not_one(tmp: Path) -> None:
    """A tracker this script cannot read produced no findings.

    Exit 1 means "drift beads found"; reporting that from a failed read is the
    same class of lie as dropping a bead silently. `dedup.py::_bd_json` has
    always raised `UsageError` here, and the two scripts must agree.
    """
    code, out, _ = cli(tmp, [], [], "--project", "demo", script=FAILING_BD)
    assert code == 2, (code, out)
    assert "Traceback" not in out, out
    assert "bd list" in out, out
    assert not (tmp / "manifest.json").exists(), "wrote a manifest from a failed read"


def case_non_json_from_bd_exits_two(tmp: Path) -> None:
    code, out, _ = cli(tmp, [], [], "--project", "demo", script=NON_JSON_BD)
    assert code == 2, (code, out)
    assert "Traceback" not in out, out


def case_captured_demo_fixtures_route_every_bead(tmp: Path) -> None:
    listing = json.loads((FIXTURES / "bd_list_demo.json").read_text())
    shown = json.loads((FIXTURES / "bd_show_demo.json").read_text())
    dest = tmp / "run" / "manifest.json"
    code, out, _ = cli(tmp, listing, shown, "--project", "demo", "--table",
                       "--out", str(dest))
    assert code == 1, (code, out)  # the live backlog carries drift beads
    manifest = json.loads(dest.read_text())
    expect(len(manifest["beads"]), len(listing))
    for entry in manifest["beads"]:
        assert entry["route"] in ("investigate", "plan", "skip", "drift-report"), entry
        reason = entry["reason"]
        assert reason in REASONS or reason.startswith("status"), reason
    needs_plan = [b for b in manifest["beads"] if b["status"] == "needs-plan"]
    expect(len(needs_plan), 9)
    expect({b["route"] for b in needs_plan}, {"investigate"})


def case_without_out_nothing_is_written_to_the_working_directory(tmp: Path) -> None:
    """The run directory is the only write target, so a hand-run that names no
    target writes nothing. The old default dropped a manifest.json into
    whatever directory the caller stood in — a source repo, in practice."""
    code, out, _ = cli(tmp, [], [], "--project", "demo", "--table")
    expect(code, 0)
    assert "demo:" in out, out
    assert not (tmp / "manifest.json").exists(), sorted(p.name for p in tmp.iterdir())


def case_out_writes_exactly_where_it_says(tmp: Path) -> None:
    code, out, _ = cli(tmp, [], [], "--project", "demo",
                       "--out", str(tmp / "run" / "manifest.json"))
    expect(code, 0)
    manifest = json.loads((tmp / "run" / "manifest.json").read_text())
    expect(manifest["beads"], [])


def case_the_table_prints_the_total_beside_the_tally(tmp: Path) -> None:
    """The human-facing surface carries it too, so a reader of `--table` never
    has to add the routes up either."""
    listing = json.loads((FIXTURES / "bd_list_demo.json").read_text())
    shown = json.loads((FIXTURES / "bd_show_demo.json").read_text())
    _, out, _ = cli(tmp, listing, shown, "--project", "demo", "--table")
    assert f"demo: {len(listing)} beads" in out, out.splitlines()[-1]


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
