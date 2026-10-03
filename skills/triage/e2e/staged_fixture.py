"""Build one promotable staged run inside the testbed, against the real tracker.

Every promote and lifecycle case starts here, and that is deliberate: the
`system_plan_dir` guard below has to be unskippable. `--system-plan-dir` is
required, so no promote resolves `~/.claude/plans` by omission — but
`stage_run` takes the mirror root as an argument, and a fixture that handed it
the operator's real tree would make an e2e run write into the user's real plan
mirrors — outside the testbed, outside `discard`'s reach, and not recoverable
by re-running anything. The guard therefore lives in the one builder every case
calls rather than in a `case_*` a new case could forget to copy.

The run is built from the committed artifact fixtures rather than a second copy
of them: `investigation_ok/` and `plan_ok/` already lint clean against the
testbed's own source tree, which is exactly what a promotable run needs.

Two real beads, because promote's two interesting shapes differ. The plan-route
bead carries the plan folder and the seven intents that turn it into an epic;
the investigate-route bead carries the investigation and one intent. Quarantine
needs both — a run where quarantining the only bead promotes nothing cannot
show that everything else still promotes.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import harness

sys.path.insert(0, str(harness.SCRIPTS))

import intent_records  # noqa: E402
import manifest as manifest_io  # noqa: E402
import staged_run  # noqa: E402

RUN_ID = "2026-08-29_ab12"
PLAN_FOLDER = "triage-testbed_feat_config_override"
INVEST_NAME = "triage-testbed_invest_retry_client_backoff.md"
STAGING = "triage"

LEDGER = staged_run.ledger_header("full run")


@dataclass(frozen=True)
class Fixture:
    run: Path        # the staged run directory itself
    runs_dir: Path   # the staging directory the run sits in
    plans: Path      # this fixture's own plans tree, never the testbed corpus
    real: Path       # plans/<project>/ — where a promote lands artifacts
    system: Path     # the mirror tree, guarded to stay inside the testbed
    plan_bead: str   # the plan-route bead, carrying the plan folder
    invest_bead: str  # the investigate-route bead, carrying the investigation
    data: dict       # the manifest as written to run/manifest.json


def bd(testbed, *args: str) -> str:
    """One `bd` call against the testbed's own database, never a discovered one."""
    proc = subprocess.run(["bd", "-C", str(testbed.path), *args],
                          capture_output=True, text=True)
    if proc.returncode != 0:
        raise AssertionError(f"bd {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout


def bd_create(testbed, title: str) -> str:
    """A real bead, left in `needs-plan` — the state a triage run finds it in.

    `bd create` takes no `--status`, so the status is a second call. A run's
    manifest records `needs-plan` for a source bead, and `staged_run_checks`
    compares the tracker against exactly that; creating at the default `open`
    would quarantine every bead this fixture builds.
    """
    payload = json.loads(bd(testbed, "create", title, "-t", "bug", "-p", "2",
                            "--json"))
    record = payload[0] if isinstance(payload, list) else payload
    bd(testbed, "update", record["id"], "--status", "needs-plan")
    return record["id"]


def bd_notes(testbed, bead: str) -> str:
    """The bead's notes, read unwrapped.

    `bd show` without `--json` hard-wraps the notes block at ~60 columns and
    breaks absolute paths mid-token, which is `skills-p1j`. Reading the field
    is what lets a case assert which path landed rather than which fragment of
    one survived the wrap.
    """
    payload = json.loads(bd(testbed, "show", bead, "--json") or "[]")
    return (payload[0].get("notes") or "") if payload else ""


def bd_list(testbed) -> list:
    """Every bead in the testbed tracker as a record, closed ones included.

    `--all` is what includes them, and both readers below depend on that, so
    the flag lives in one place rather than in each caller's argv.
    """
    return json.loads(bd(testbed, "list", "--all", "--limit", "0", "--json")
                      or "[]")


def bead_ids(testbed) -> set:
    """Every bead ID in the testbed tracker, closed ones included."""
    return {row["id"] for row in bd_list(testbed)}


def assert_inside_testbed(testbed, system_plan_dir: Path) -> None:
    """Guard 3 of plan.md's Cross-Cutting Concerns. Raises, never warns."""
    resolved = Path(system_plan_dir).expanduser().resolve()
    if not str(resolved).startswith(str(testbed.scratch.resolve()) + "/"):
        raise AssertionError(
            f"system_plan_dir {resolved} is outside {testbed.scratch} — a "
            f"promote against this fixture would write mirrors into the user's "
            f"real plans tree, typically ~/.claude/plans, and no discard can "
            f"take them back")


TOKENS = {"tb-clean1.1": "<bead:phase_1>", "tb-clean1.2": "<bead:phase_2>"}


def _tokenize(folder: Path) -> None:
    """The staged plan as `brief_plan.sh` now prescribes it: a bead this run
    has not created yet is named by a `<bead:{ref}>` token and never by an
    invented ID, so `promote.write_back` has somewhere to put the created one.

    Only the staged copy is rewritten. The corpus fixture keeps its literal
    IDs: it is `lint_plan.py`'s exit-0 subject and the QC suite's input, and
    neither of those promotes it.
    """
    for path in sorted(folder.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        for invented, token in TOKENS.items():
            text = text.replace(invented, token)
        path.write_text(
            text.replace("A fixture plan folder",
                         "Epic `<bead:epic>`. A fixture plan folder"),
            encoding="utf-8")


def intents(run: Path, plan_bead: str, invest_bead: str) -> list:
    """One epic, two phases, one dep, two opens, the source flip, and the
    investigate-route bead's own note — the full `tracker_intents.KIND_ORDER`.

    The three worker kinds name no `bead`: `brief_plan.sh` asks a planning
    worker for the array and no producer writes one — `intent_records.load_all`
    owns that rule. `dep`, `flip-source` and `investigation` keep theirs.
    """
    folder = run / "todo" / PLAN_FOLDER
    master = str(folder / "plan.md")
    common = {"type": "feature", "priority": 2, "labels": ["e2e"],
              "master": master}
    return [
        {"key": "epic", "kind": "create-epic", "ref": "epic",
         "title": "Config override flag", "type": "epic", "priority": 2,
         "description": "Deliver the config override flag.", "labels": ["e2e"],
         "master": master},
        {"key": "phase-1", "kind": "create-task", "ref": "phase_1",
         "title": "Phase 1: Read the override", "parent": "epic",
         "description": "Step 1.1 read the environment.",
         "slice": str(folder / "phase_1_read_the_override.md"), **common},
        {"key": "phase-2", "kind": "create-task", "ref": "phase_2",
         "title": "Phase 2: Wire the settings screen", "parent": "epic",
         "description": "Step 2.1 call the reader.",
         "slice": str(folder / "phase_2_wire_the_settings_screen.md"), **common},
        {"key": "dep-2-on-1", "kind": "dep", "bead": plan_bead,
         "from": "phase_2", "to": "phase_1", "dep_type": "blocks"},
        {"key": "open-1", "kind": "open", "ref": "phase_1"},
        {"key": "open-2", "kind": "open", "ref": "phase_2"},
        {"key": "flip", "kind": "flip-source", "bead": plan_bead, "plan": master},
        {"key": "invest", "kind": "investigation", "bead": invest_bead,
         "investigation": str(run / "investigations" / INVEST_NAME)},
    ]


def stage_run(testbed, name: str, *, system_plan_dir=None, beads=None,
              run_id: str = RUN_ID) -> Fixture:
    """A run that is ready to promote, in its own isolated plans tree.

    `plans_dir` is fresh per fixture rather than the testbed's corpus: the
    corpus carries plans citing `tb-cov1`–`tb-cov3`, and a promote preflight
    scans the real `todo/` for exactly that, so sharing it would hand every
    case a coverage collision it never asked for.

    `beads` takes an existing `(plan_bead, invest_bead)` pair instead of
    creating one. A caller fingerprinting the tracker needs the two `bd create`
    calls outside the window it measures — creating a bead is this fixture's
    setup, not something a triage run ever does.
    """
    harness.assert_db_inside(testbed)
    base = testbed.scratch / name
    system = Path(system_plan_dir) if system_plan_dir else base / "system_plans"
    assert_inside_testbed(testbed, system)
    if base.exists():
        shutil.rmtree(base)
    plans = base / "plans"
    real = plans / testbed.path.name
    (real / "investigations").mkdir(parents=True)
    (real / "todo").mkdir(parents=True)
    system.mkdir(parents=True, exist_ok=True)

    runs_dir = real / STAGING
    run = staged_run.create_run(runs_dir, run_id)
    (run / "investigations").mkdir(exist_ok=True)
    (run / "todo").mkdir(exist_ok=True)
    shutil.copyfile(harness.FIXTURES / "investigation_ok" / INVEST_NAME,
                    run / "investigations" / INVEST_NAME)
    shutil.copytree(harness.FIXTURES / "plan_ok" / PLAN_FOLDER,
                    run / "todo" / PLAN_FOLDER)
    _tokenize(run / "todo" / PLAN_FOLDER)
    if beads:
        plan_bead, invest_bead = beads
    else:
        plan_bead = bd_create(testbed, f"e2e {name}: config override flag")
        invest_bead = bd_create(testbed, f"e2e {name}: retry client never resends")
    rows = [
        staged_run.ledger_row(
            bead=invest_bead, wave=2, worker="invest",
            dispatched="2026-08-29T10:00:00Z", returned="2026-08-29T10:01:00Z",
            artifact=run / "investigations" / INVEST_NAME, final="planned"),
        staged_run.ledger_row(
            bead=plan_bead, wave=4, worker="plan",
            dispatched="2026-08-29T10:02:00Z", returned="2026-08-29T10:03:00Z",
            artifact=run / "todo" / PLAN_FOLDER, final="planned"),
    ]
    (run / "ledger.md").write_text(LEDGER + "".join(rows), encoding="utf-8")
    data = {
        "schema_version": 1, "project": testbed.path.name,
        "generated_at": "2020-01-01T00:00:00Z",
        "beads": [
            {"id": plan_bead, "title": "config override flag",
             "status": "needs-plan", "issue_type": "task", "priority": 3,
             "route": "plan", "reason": "fixture", "selected": True},
            {"id": invest_bead, "title": "retry client never resends",
             "status": "needs-plan", "issue_type": "bug", "priority": 3,
             "route": "investigate", "reason": "fixture", "selected": True},
        ],
        "clusters": [], "counts": {}, "covered": [], "groups": [],
        "selected_counts": {}, "selected_total": 2, "total": 2,
    }
    manifest_io.save(run / "manifest.json", data)
    # The run's intents live in `{run}/intents/<bead>.json`, one list per bead.
    # Promote reads that store, never the manifest: `manifest.json` is what the
    # run decided, and an intent is something it did.
    #
    # A record that names no `bead` is a worker record, and the orchestrator
    # files those under the bead it briefed the worker for — the plan bead.
    # That filing is the owner.
    by_bead: dict = {}
    for intent in intents(run, plan_bead, invest_bead):
        by_bead.setdefault(intent.get("bead", plan_bead), []).append(intent)
    for bead, records in by_bead.items():
        intent_records.save(run, bead, records)
    return Fixture(run=run, runs_dir=runs_dir, plans=plans, real=real,
                   system=system, plan_bead=plan_bead, invest_bead=invest_bead,
                   data=data)
