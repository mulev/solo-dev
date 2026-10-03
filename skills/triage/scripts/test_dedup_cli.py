"""Tests for dedup.py's command-line contract — exit codes, the judge brief,
and the promise that write-back never disturbs what Phase 1 owns.

Every case shells out with a fake `bd` on PATH and TRIAGE_PROJECTS_ROOT
pointed at a temp workspace; the real tracker is never touched. The pure
functions are tested next door in test_dedup.py.

Run with `python3 test_dedup_cli.py` (no pytest dependency).
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

FAKE_BD = """#!/usr/bin/env python3
import pathlib, sys
here = pathlib.Path(__file__).resolve().parent
name = "find_duplicates" if sys.argv[1] == "find-duplicates" else "list"
sys.stdout.write((here / (name + ".json")).read_text())
"""


def expect(got, want) -> None:
    assert got == want, f"got {got!r}, want {want!r}"


def bead(bid: str, **kw) -> dict:
    """A manifest bead entry enriched the way main() enriches it."""
    base = {
        "id": bid,
        "title": f"title {bid}",
        "status": "needs-plan",
        "issue_type": "bug",
        "priority": 2,
        "route": "investigate",
        "reason": "no investigation on record",
        "notes": "",
        "description": f"body {bid}",
        "created_at": "2026-01-01T00:00:00Z",
        "dependencies": [],
    }
    base.update(kw)
    return base


def dep(issue_id: str, depends_on_id: str, kind: str) -> dict:
    return {"issue_id": issue_id, "depends_on_id": depends_on_id, "type": kind}


def dup_json(*pairs) -> dict:
    """Shape captured verbatim from `bd find-duplicates --json`."""
    return {
        "count": len(pairs),
        "method": "mechanical",
        "schema_version": 1,
        "threshold": 0.35,
        "pairs": [
            {
                "issue_a_id": a,
                "issue_a_title": f"title {a}",
                "issue_b_id": b,
                "issue_b_title": f"title {b}",
                "method": "mechanical",
                "similarity": score,
            }
            for a, b, score in pairs
        ],
    }


def manifest_of(*beads) -> dict:
    """A Phase 1 manifest: entries carry only the fields inventory.py writes."""
    keep = ("id", "title", "status", "issue_type", "priority", "route", "reason")
    entries = [{k: b[k] for k in keep} for b in beads]
    counts = {"investigate": 0, "plan": 0, "skip": 0, "drift-report": 0}
    for entry in entries:
        counts[entry["route"]] += 1
    return {
        "project": "demo",
        "generated_at": "2026-08-28T09:14:22Z",
        "counts": counts,
        "beads": entries,
    }


def plan_tree(tmp: Path, files: dict[str, str]) -> Path:
    """files maps 'todo/foo/plan.md' -> body. Returns the plans-dir root."""
    plans = tmp / "plans"
    for rel, body in files.items():
        path = plans / "demo" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    (plans / "demo" / "todo").mkdir(parents=True, exist_ok=True)
    (plans / "demo" / "done").mkdir(parents=True, exist_ok=True)
    return plans


def cli(tmp: Path, manifest: dict, dups: dict, listing: list, *args: str):
    """End-to-end run with a fake `bd` on PATH and TRIAGE_PROJECTS_ROOT set."""
    binp = tmp / "bin"
    binp.mkdir(exist_ok=True)
    (binp / "bd").write_text(FAKE_BD)
    (binp / "bd").chmod(0o755)
    (binp / "find_duplicates.json").write_text(json.dumps(dups))
    (binp / "list.json").write_text(json.dumps(listing))

    (tmp / "projects" / "demo" / ".beads").mkdir(parents=True, exist_ok=True)
    mpath = tmp / "manifest.json"
    mpath.write_text(json.dumps(manifest, indent=2) + "\n")

    env = dict(os.environ)
    env["PATH"] = f"{binp}{os.pathsep}{env['PATH']}"
    env["TRIAGE_PROJECTS_ROOT"] = str(tmp / "projects")
    argv = [sys.executable, str(HERE / "dedup.py"), *args]
    if "--manifest" not in args:
        argv += ["--manifest", str(mpath)]
    if "--project" not in args:
        argv += ["--project", "demo"]
    if "--plans-dir" not in args:
        argv += ["--plans-dir", str(tmp / "plans")]
    proc = subprocess.run(argv, capture_output=True, text=True, env=env, cwd=str(tmp))
    return proc.returncode, proc.stdout, proc.stderr, mpath


# --- exit codes and the write-back contract ----------------------------------


def case_no_findings_exits_zero_and_writes_no_brief(tmp: Path) -> None:
    m = manifest_of(bead("d-1"), bead("d-2"))
    plan_tree(tmp, {"todo/x/plan.md": "nothing\n"})
    code, out, err, mpath = cli(
        tmp, m, dup_json(), [bead("d-1"), bead("d-2")], "--plans-dir", str(tmp / "plans")
    )
    expect(code, 0)
    after = json.loads(mpath.read_text())
    expect(after["clusters"], [])
    expect(after["covered"], [])
    assert not (tmp / "judge_brief.md").exists(), out + err


def case_clusters_exit_one_and_the_brief_names_both_beads(tmp: Path) -> None:
    beads = [bead("d-1"), bead("d-2")]
    m = manifest_of(*beads)
    plan_tree(tmp, {"todo/x/plan.md": "nothing\n"})
    code, out, err, mpath = cli(
        tmp, m, dup_json(("d-1", "d-2", 0.41)), beads, "--plans-dir", str(tmp / "plans")
    )
    expect(code, 1)
    after = json.loads(mpath.read_text())
    expect(after["clusters"][0]["members"], ["d-1", "d-2"])
    brief = (tmp / "judge_brief.md").read_text()
    assert "d-1" in brief and "d-2" in brief, brief
    assert "duplicate / distinct / related-not-duplicate" in brief, brief


def case_covered_bead_exits_one_and_gets_a_dedup_object(tmp: Path) -> None:
    beads = [bead("d-1")]
    m = manifest_of(*beads)
    plan_tree(tmp, {"done/x/plan.md": "**Beads task:** `d-1`\n"})
    code, out, err, mpath = cli(
        tmp, m, dup_json(), beads, "--plans-dir", str(tmp / "plans")
    )
    expect(code, 1)
    after = json.loads(mpath.read_text())
    expect(after["covered"][0]["id"], "d-1")
    expect(after["beads"][0]["dedup"]["action"], "drop")
    assert after["beads"][0]["dedup"]["covered_by"].endswith("plan.md")


def case_zero_bead_manifest_exits_zero_not_two(tmp: Path) -> None:
    code, out, err, mpath = cli(tmp, manifest_of(), dup_json(), [])
    expect(code, 0)
    expect(json.loads(mpath.read_text())["clusters"], [])


def case_manifest_with_only_skipped_beads_exits_zero(tmp: Path) -> None:
    m = manifest_of(bead("d-1", route="skip", reason="already planned"))
    code, out, err, mpath = cli(tmp, m, dup_json(("d-1", "d-2", 0.9)), [])
    expect(code, 0)


def case_missing_manifest_flag_exits_two(tmp: Path) -> None:
    code, out, err, _ = cli(tmp, manifest_of(), dup_json(), [], "--manifest")
    expect(code, 2)
    assert "--manifest" in err, err


def case_unreadable_manifest_exits_two(tmp: Path) -> None:
    code, out, err, _ = cli(
        tmp, manifest_of(), dup_json(), [], "--manifest", str(tmp / "gone.json")
    )
    expect(code, 2)


def case_malformed_manifest_json_exits_two(tmp: Path) -> None:
    bad = tmp / "bad.json"
    bad.write_text("{not json")
    code, out, err, _ = cli(tmp, manifest_of(), dup_json(), [], "--manifest", str(bad))
    expect(code, 2)


def case_unknown_flag_exits_two(tmp: Path) -> None:
    code, out, err, _ = cli(tmp, manifest_of(), dup_json(), [], "--nope")
    expect(code, 2)


def case_non_numeric_threshold_exits_two(tmp: Path) -> None:
    code, out, err, _ = cli(tmp, manifest_of(), dup_json(), [], "--threshold", "high")
    expect(code, 2)


def case_unknown_project_exits_two(tmp: Path) -> None:
    code, out, err, _ = cli(
        tmp, manifest_of(bead("d-1")), dup_json(), [], "--project", "ghost"
    )
    expect(code, 2)


def case_bd_missing_from_path_exits_two(tmp: Path) -> None:
    m = manifest_of(bead("d-1"))
    mpath = tmp / "manifest.json"
    mpath.write_text(json.dumps(m))
    (tmp / "projects" / "demo" / ".beads").mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["PATH"] = str(tmp / "empty")
    env["TRIAGE_PROJECTS_ROOT"] = str(tmp / "projects")
    proc = subprocess.run(
        [sys.executable, str(HERE / "dedup.py"), "--manifest", str(mpath),
         "--project", "demo", "--plans-dir", str(tmp / "plans")],
        capture_output=True, text=True, env=env, cwd=str(tmp),
    )
    expect(proc.returncode, 2)
    assert "bd" in proc.stderr, proc.stderr


def case_missing_plans_dir_exits_two(tmp: Path) -> None:
    """No --plans-dir, no run. The default used to be one machine's real corpus."""
    mpath = tmp / "manifest.json"
    mpath.write_text(json.dumps(manifest_of(bead("d-1"))))
    proc = subprocess.run(
        [sys.executable, str(HERE / "dedup.py"), "--manifest", str(mpath),
         "--project", "demo"],
        capture_output=True, text=True, cwd=str(tmp),
    )
    expect(proc.returncode, 2)
    assert "--plans-dir" in proc.stderr, proc.stderr


# --- regression: the Phase 1 manifest survives untouched ---------------------


def case_phase1_manifest_fields_are_byte_identical_after_dedup(tmp: Path) -> None:
    beads = [bead("d-1"), bead("d-2")]
    m = manifest_of(*beads)
    before = json.loads(json.dumps(m))
    plan_tree(tmp, {"todo/x/plan.md": "nothing\n"})
    code, out, err, mpath = cli(
        tmp, m, dup_json(("d-1", "d-2", 0.41)), beads, "--plans-dir", str(tmp / "plans")
    )
    expect(code, 1)
    after = json.loads(mpath.read_text())
    for key in before:
        if key != "beads":
            expect(after[key], before[key])
    expect(sorted(set(after) - set(before)), ["clusters", "covered"])
    for old, new in zip(before["beads"], after["beads"]):
        expect({k: v for k, v in new.items() if k != "dedup"}, old)


def case_dedup_never_rewrites_the_route_of_a_covered_bead(tmp: Path) -> None:
    beads = [bead("d-1")]
    m = manifest_of(*beads)
    plan_tree(tmp, {"todo/x/plan.md": "**Beads task:** `d-1`\n"})
    code, out, err, mpath = cli(
        tmp, m, dup_json(), beads, "--plans-dir", str(tmp / "plans")
    )
    expect(code, 1)
    expect(json.loads(mpath.read_text())["beads"][0]["route"], "investigate")


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
