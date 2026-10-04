#!/usr/bin/env python3
"""Tests for promote.py's command line — run resolution, the exit-code
contract, what lands on disk after a clean promote, and `--dry-run`.

Split from test_promote.py, which covers the model in process. The seam is
the harness: everything here runs promote.py as a subprocess against a fake
`bd` on PATH, exactly as test_collide_cli.py stands beside test_collide.py.

Run with `python3 test_promote_cli.py` (no pytest dependency).
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

import intent_records  # noqa: E402
import manifest as manifest_io  # noqa: E402
from staged_run import ledger_row  # noqa: E402
from test_promote import (INVEST_NAME, LEDGER, PLAN_FOLDER, PROJECT,  # noqa: E402
                          RUNID, expect, manifest_bead, manifest_data,
                          outcome_rows, seed_ledger, staged)

SCRIPT = HERE / "promote.py"
SIBLING = "proj-b2"
SIBLING_INVEST = "proj_invest_retry_never_resends.md"

FAKE_BD = """#!/usr/bin/env python3
import json, os, pathlib, sys
here = pathlib.Path(__file__).resolve().parent
argv = sys.argv[1:]
log = here / "bd.log"
fail = os.environ.get("BD_FAIL_ON")
record = {"argv": argv, "cwd": str(pathlib.Path.cwd())}
if fail and fail in " ".join(argv):
    record["ok"] = False
with log.open("a") as fh:
    fh.write(json.dumps(record) + "\\n")
if record.get("ok") is False:
    sys.exit(1)
records = [json.loads(l) for l in log.read_text().splitlines()]
if argv[0] == "create":
    sys.stdout.write(json.dumps({"id": "proj-t%02d" % len(records)}))
elif argv[0] == "show":
    status = "needs-plan"
    for other in records:
        call = other["argv"]
        if (other.get("ok") is not False and call[:2] == ["update", argv[1]]
                and "--status" in call):
            status = call[call.index("--status") + 1]
    # Notes belong to the bead that received them, never to every bead: a
    # parked bead whose notes carried someone else's plan path would read as
    # re-planned. A `create` names no id, so replay the log and give it the id
    # that create returned.
    owned = {}
    for index, other in enumerate(records):
        call = other["argv"]
        if other.get("ok") is False or "--notes" not in call:
            continue
        value = call[call.index("--notes") + 1]
        if call[0] == "create":
            owned["proj-t%02d" % (index + 1)] = value
        elif len(call) > 1:
            owned[call[1]] = value
    notes = owned.get(argv[1], "").splitlines()
    if "--json" in argv:
        sys.stdout.write(json.dumps([{"id": argv[1], "status": status,
                                      "notes": "\\n".join(notes)}]))
    else:
        # The real `bd show` pads to a column and breaks mid-token. Keeping
        # that here is what stops a reader "simplifying" the JSON read-back
        # back into a substring match on this output.
        body = "".join(("  %s" % n)[:78].ljust(78) + "\\n" for n in notes)
        sys.stdout.write(argv[1] + "\\nNOTES\\n" + body)
"""


def logged(bindir: Path) -> list:
    path = bindir / "bd.log"
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def cli(tmp: Path, *args: str, env_extra=None) -> tuple[int, str, Path]:
    bindir = tmp / "bin"
    bindir.mkdir(exist_ok=True)
    fake = bindir / "bd"
    fake.write_text(FAKE_BD, encoding="utf-8")
    fake.chmod(0o755)
    env = dict(os.environ)
    env["PATH"] = f"{bindir}:{env['PATH']}"
    env.update(env_extra or {})
    proc = subprocess.run([sys.executable, str(SCRIPT), *args],
                          capture_output=True, text=True, cwd=str(tmp), env=env)
    return proc.returncode, proc.stdout + proc.stderr, bindir


def runs_dir(tmp: Path) -> str:
    return str(tmp / "plans" / PROJECT / "triage")


def env_flags(tmp: Path) -> tuple[str, ...]:
    return ("--plans-dir", str(tmp / "plans"),
            "--repo-root", str(tmp / PROJECT),
            "--system-plan-dir", str(tmp / "system_plans"))


def empty_run(tmp: Path) -> Path:
    run = tmp / "plans" / PROJECT / "triage" / "2026-08-28_zz99"
    (run / "todo").mkdir(parents=True)
    (run / "investigations").mkdir()
    (run / "ledger.md").write_text(LEDGER, encoding="utf-8")
    (tmp / "system_plans").mkdir(exist_ok=True)
    manifest_io.save(run / "manifest.json", manifest_data([]))
    return run


def with_sibling(tmp: Path) -> Path:
    """`staged()` plus a second investigate-route bead, the shape
    `triage/e2e/staged_fixture.py` builds for the harness: its own manifest
    entry, its own ledger row, its own staged artifact, its own store file.

    Without it every record in the run belongs to one bead, so quarantining
    that bead hands `apply_intents` an empty list and a quarantine case proves
    nothing about what still promotes.
    """
    run = staged(tmp, records=[manifest_bead("proj-a1", "plan"),
                               manifest_bead("proj-p9", "investigate"),
                               manifest_bead(SIBLING, "investigate")])
    invest = run / "investigations"
    artifact = invest / SIBLING_INVEST
    artifact.write_text((invest / INVEST_NAME).read_text(encoding="utf-8"),
                        encoding="utf-8")
    seed_ledger(run, outcome_rows(run) + [
        ledger_row(bead=SIBLING, wave=2, worker="invest-b2",
                   dispatched="2026-08-28T10:06:00Z",
                   returned="2026-08-28T10:07:00Z",
                   artifact=artifact, final="planned")])
    intent_records.save(run, SIBLING, [
        {"key": "invest-b2", "kind": "investigation", "bead": SIBLING,
         "investigation": str(artifact)}])
    return run


# --- exit code 2: usage and environment only --------------------------------


def case_missing_run_id_exits_2(tmp: Path) -> None:
    code, out, _ = cli(tmp, "--runs-dir", str(tmp))
    expect(code, 2)
    assert "--run-id" in out, out


def case_missing_plans_dir_exits_2(tmp: Path) -> None:
    code, out, _ = cli(tmp, "--run-id", RUNID, "--runs-dir", runs_dir(tmp),
                       "--repo-root", str(tmp / PROJECT))
    expect(code, 2)
    assert "--plans-dir" in out, out


def case_missing_repo_root_exits_2(tmp: Path) -> None:
    code, out, _ = cli(tmp, "--run-id", RUNID, "--runs-dir", runs_dir(tmp),
                       "--plans-dir", str(tmp / "plans"))
    expect(code, 2)
    assert "--repo-root" in out, out


def case_missing_system_plan_dir_exits_2(tmp: Path) -> None:
    code, out, _ = cli(tmp, "--run-id", RUNID, "--runs-dir", runs_dir(tmp),
                       "--plans-dir", str(tmp / "plans"),
                       "--repo-root", str(tmp / PROJECT))
    expect(code, 2)
    assert "--system-plan-dir" in out, out


def case_unknown_run_exits_2(tmp: Path) -> None:
    staged(tmp)
    code, out, _ = cli(tmp, "--run-id", "nope", "--runs-dir", runs_dir(tmp),
                       *env_flags(tmp))
    expect(code, 2)
    assert "nope" in out, out


def case_unknown_flag_exits_2(tmp: Path) -> None:
    code, out, _ = cli(tmp, "--run-id", RUNID, "--wat", *env_flags(tmp))
    expect(code, 2)
    assert "--wat" in out, out


def case_ambiguous_run_id_exits_2(tmp: Path) -> None:
    staged(tmp)
    (Path(runs_dir(tmp)) / "2026-08-29_ab12").mkdir()
    code, out, _ = cli(tmp, "--run-id", "ab12", "--runs-dir", runs_dir(tmp),
                       *env_flags(tmp))
    expect(code, 2)
    assert "ab12" in out, out


def case_an_unreadable_intent_store_exits_2(tmp: Path) -> None:
    """`intent_records`' own docstring gives an unreadable store to exit 2, and
    EPILOG reserves 2 for environment faults. Exit 1 means "findings to act on",
    so a half-written store reported as 1 reads as a reviewable result instead of
    a stop-and-fix — and it arrived as a raw traceback, which is not a report.
    """
    run = staged(tmp)
    store = run / "intents"
    store.mkdir(exist_ok=True)
    (store / "proj-a1.json").write_text('[{"key": "x"', encoding="utf-8")
    code, out, _ = cli(tmp, "--run-id", RUNID, "--runs-dir", runs_dir(tmp),
                       *env_flags(tmp))
    expect(code, 2)
    assert "Traceback" not in out, out
    assert "proj-a1.json" in out, out


# --- exit code 0: a clean promote -------------------------------------------


def case_clean_run_exits_0(tmp: Path) -> None:
    staged(tmp)
    code, out, _ = cli(tmp, "--run-id", RUNID, "--runs-dir", runs_dir(tmp),
                       *env_flags(tmp))
    expect(code, 0)
    plans = tmp / "plans" / PROJECT
    assert (plans / "investigations" / INVEST_NAME).is_file(), out
    assert (plans / "todo" / PLAN_FOLDER / "plan.md").is_file(), out
    assert (tmp / "system_plans" / f"{PLAN_FOLDER}.md").is_file(), out
    assert (plans / "triage" / "promoted" / RUNID).is_dir(), out
    assert not (plans / "triage" / RUNID).exists(), out


def case_short_run_id_resolves(tmp: Path) -> None:
    staged(tmp)
    code, out, _ = cli(tmp, "--run-id", "ab12", "--runs-dir", runs_dir(tmp),
                       *env_flags(tmp))
    expect(code, 0)


def case_empty_run_exits_0(tmp: Path) -> None:
    empty_run(tmp)
    code, out, _ = cli(tmp, "--run-id", "zz99", "--runs-dir", runs_dir(tmp),
                       *env_flags(tmp))
    expect(code, 0)
    assert (tmp / "plans" / PROJECT / "triage" / "promoted" / "2026-08-28_zz99").is_dir()


def case_bd_calls_run_from_the_repo_root(tmp: Path) -> None:
    staged(tmp)
    code, out, bindir = cli(tmp, "--run-id", RUNID, "--runs-dir", runs_dir(tmp),
                            *env_flags(tmp))
    expect(code, 0)
    calls = logged(bindir)
    expect({str(Path(call["cwd"]).resolve()) for call in calls},
           {str((tmp / PROJECT).resolve())})
    creates = [c["argv"] for c in calls if c["argv"][0] == "create"]
    expect([argv[1] for argv in creates],
           ["Demo thing", "Phase 1: Demo slice", "Phase 2: Demo slice"])


# --- exit code 1: findings ---------------------------------------------------


def case_preflight_stop_exits_1_and_moves_nothing(tmp: Path) -> None:
    run = staged(tmp)
    (tmp / "plans" / PROJECT / "todo" / PLAN_FOLDER).mkdir()
    code, out, _ = cli(tmp, "--run-id", RUNID, "--runs-dir", runs_dir(tmp),
                       *env_flags(tmp))
    expect(code, 1)
    assert "promote-target-exists" in out, out
    assert (run / "investigations" / INVEST_NAME).is_file(), out
    assert not (tmp / "plans" / PROJECT / "triage" / "promoted").exists(), out


def case_json_mode_emits_findings(tmp: Path) -> None:
    staged(tmp)
    (tmp / "plans" / PROJECT / "todo" / PLAN_FOLDER).mkdir()
    code, out, _ = cli(tmp, "--run-id", RUNID, "--runs-dir", runs_dir(tmp),
                       "--json", *env_flags(tmp))
    expect(code, 1)
    payload = json.loads(out.strip().splitlines()[-1])
    expect(payload["errors"], len([f for f in payload["findings"]
                                   if f["severity"] == "error"]))
    assert payload["errors"] >= 1, payload


def case_quarantining_a_bead_skips_only_its_own_records(tmp: Path) -> None:
    """A quarantine stops that bead's records, never the run's.

    The defect: the three worker kinds carry no `bead`, so a quarantined
    bead's `create-epic`, `create-task` and `open` records answered `None`,
    `None` was never in the quarantine set, and the records survived the
    filter still holding that bead's staged paths — `promote-stale-path` then
    stopped the whole promote before a single tracker write. The in-process
    counterpart of `triage/e2e/suite_promote.py:196`.
    """
    run = with_sibling(tmp)
    data = manifest_io.load(run / "manifest.json")
    data["beads"][0]["status"] = "blocked"   # the fake bd still answers needs-plan
    manifest_io.save(run / "manifest.json", data)
    code, out, bindir = cli(tmp, "--run-id", RUNID, "--runs-dir", runs_dir(tmp),
                            *env_flags(tmp))
    expect(code, 1)
    assert "promote-bead-state-changed" in out, out
    assert "promote-stale-path" not in out, out
    updates = [r["argv"] for r in logged(bindir)
               if r["argv"][:2] == ["update", SIBLING]]
    expect(len(updates), 1)
    promoted = tmp / "plans" / PROJECT / "investigations" / SIBLING_INVEST
    assert str(promoted) in " ".join(updates[0]), updates
    assert (run / "todo" / PLAN_FOLDER).is_dir(), out
    assert not (tmp / "plans" / PROJECT / "todo" / PLAN_FOLDER).exists(), out


# --- rerunning after a partial failure ---------------------------------------


def notes_of(record: dict):
    argv = record["argv"]
    return argv[argv.index("--notes") + 1] if "--notes" in argv else None


def creates_of(records: list, title: str) -> list:
    return [r for r in records if r["argv"][0] == "create" and r["argv"][1] == title]


def case_rerun_after_failed_create_writes_only_promoted_paths(tmp: Path) -> None:
    """The whole point of the ledger's move rows: after a partial apply, the
    rerun's intents must still carry promoted paths. A `Plan:` note pointing
    into a run directory is a note `discard` can invalidate."""
    run = staged(tmp)
    code, out, bindir = cli(tmp, "--run-id", RUNID, "--runs-dir", runs_dir(tmp),
                            *env_flags(tmp), env_extra={"BD_FAIL_ON": "Phase 2: Demo slice"})
    expect(code, 1)
    assert "promote-intent-incomplete" in out, out
    plans = tmp / "plans" / PROJECT
    assert (plans / "triage" / RUNID).is_dir(), out
    assert not (plans / "triage" / "promoted" / RUNID).exists(), out
    assert (plans / "todo" / PLAN_FOLDER / "plan.md").is_file(), out

    code, out, bindir = cli(tmp, "--run-id", RUNID, "--runs-dir", runs_dir(tmp),
                            *env_flags(tmp))
    expect(code, 0)
    assert (plans / "triage" / "promoted" / RUNID).is_dir(), out

    records = logged(bindir)
    for record in records:
        notes = notes_of(record)
        assert notes is None or str(run) not in notes, record
    landed = creates_of(records, "Phase 2: Demo slice")
    expect([r.get("ok") for r in landed], [False, None])
    assert f"{plans}/todo/{PLAN_FOLDER}/phase_2_demo_slice.md" in notes_of(landed[1])
    expect(len(creates_of(records, "Demo thing")), 1)
    expect(len(creates_of(records, "Phase 1: Demo slice")), 1)
    investigations = plans / "investigations"
    expect(sorted(p.name for p in investigations.glob("*.md")), [INVEST_NAME])
    plan = (plans / "todo" / PLAN_FOLDER / "plan.md").read_text(encoding="utf-8")
    expect(plan.count("**System plan file:**"), 1)


def case_rerun_after_the_source_flip_landed_closes_out(tmp: Path) -> None:
    """The roll-forward story failing on its own success.

    A foreign mirror stops the first pass *after* every intent has been applied,
    so the source bead is left `open` while the manifest still records
    `needs-plan`. Read against the manifest alone that looks like drift, the
    bead is quarantined, and `_close` never closes a run out while one is set —
    the run is stranded in staging over a change the run itself made.
    """
    staged(tmp)
    mirror = tmp / "system_plans" / f"{PLAN_FOLDER}.md"
    mirror.write_text("# Someone else\n\nFull plan: `/elsewhere/plan.md`\n",
                      encoding="utf-8")
    code, out, bindir = cli(tmp, "--run-id", RUNID, "--runs-dir", runs_dir(tmp),
                            *env_flags(tmp))
    expect(code, 1)
    assert "promote-mirror-exists" in out, out
    flips = [r for r in logged(bindir) if r["argv"][:2] == ["update", "proj-a1"]]
    expect([r["argv"][2:4] for r in flips], [["--status", "open"]])

    mirror.unlink()
    code, out, _ = cli(tmp, "--run-id", RUNID, "--runs-dir", runs_dir(tmp),
                       *env_flags(tmp))
    expect(code, 0)
    assert "promote-bead-state-changed" not in out, out
    assert (tmp / "plans" / PROJECT / "triage" / "promoted" / RUNID).is_dir(), out
    assert mirror.is_file(), out


# --- --dry-run ---------------------------------------------------------------


def case_dry_run_lists_commands_and_writes_nothing(tmp: Path) -> None:
    run = staged(tmp)
    code, out, bindir = cli(tmp, "--run-id", RUNID, "--runs-dir", runs_dir(tmp),
                            "--dry-run", *env_flags(tmp))
    expect(code, 0)
    assert "bd create" in out, out
    assert "${proj-a1/epic}" in out, out
    assert not [c for c in logged(bindir) if c["argv"][0] != "show"], logged(bindir)
    assert (run / "todo" / PLAN_FOLDER / "plan.md").is_file(), out
    assert not (tmp / "plans" / PROJECT / "todo" / PLAN_FOLDER).exists(), out


def without_move_lines(out: str) -> str:
    return "\n".join(line for line in out.splitlines() if not line.startswith("MOVE"))


def case_dry_run_lists_commands_when_a_bead_is_quarantined(tmp: Path) -> None:
    """A quarantine stops that bead, not the report. The real promote goes
    ahead for every other bead, so a dry run that returns before rendering a
    single command describes a promote that will not happen."""
    run = staged(tmp)
    data = manifest_io.load(run / "manifest.json")
    data["beads"][1]["status"] = "open"      # the fake bd still answers needs-plan
    manifest_io.save(run / "manifest.json", data)
    code, out, _ = cli(tmp, "--run-id", RUNID, "--runs-dir", runs_dir(tmp),
                       "--dry-run", *env_flags(tmp))
    expect(code, 1)
    assert "promote-parked-bead-moved" in out, out
    assert "bd create Demo thing" in out, out
    assert str(run) not in without_move_lines(out), out


def case_dry_run_notes_carry_promoted_paths(tmp: Path) -> None:
    run = staged(tmp)
    code, out, _ = cli(tmp, "--run-id", RUNID, "--runs-dir", runs_dir(tmp),
                       "--dry-run", *env_flags(tmp))
    expect(code, 0)
    assert str(run) not in without_move_lines(out), out
    assert f"{tmp}/plans/{PROJECT}/todo/{PLAN_FOLDER}/plan.md" in out, out


def case_help_names_the_exit_codes(tmp: Path) -> None:
    code, out, _ = cli(tmp, "--help")
    expect(code, 0)
    for token in ("--run-id", "--runs-dir", "--plans-dir", "--repo-root",
                  "--system-plan-dir", "--dry-run", "--json",
                  "promote-target-exists", "exit codes"):
        assert token in out, (token, out)


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
