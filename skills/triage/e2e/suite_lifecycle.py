"""Assert that discard is a complete undo and that resume reads the ledger.

**Neither command has a script behind it — `skills-w7z`.** `promote` is the
reversible command and it is an eight-step fail-closed program; `discard`, the
one that actually deletes, is a paragraph in `SKILL.md` that an orchestrator
has to remember, and `staged_run.resolve_run()` implements only its lookup
half. `--resume` is the same shape: `promote.py`'s own docstring says the
ledger is the whole resume mechanism and there is no flag.

`skills-w7z` landed, so both now have production code and this suite targets
it: `discard.py` as a real subprocess through `harness.run`, and
`staged_run.first_incomplete_wave` imported directly. The local
reimplementations were deleted rather than kept — two implementations of one
rule means the tested one can drift from the shipped one, and only the shipped
one runs.

`~/.claude/plans` is not fingerprinted here. Nothing in this suite promotes,
and `promote.write_mirrors` is the only code in the triage system that can
write there; `suite_promote.case_the_home_plans_mirror_is_never_written` covers
it where the risk actually is.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

import harness
import staged_fixture

sys.path.insert(0, str(harness.SCRIPTS))

import staged_run  # noqa: E402

# The row kinds `references/ledger.md` says carry a `final`. Waves 0, 1, 3 and
# 6 write cluster and wave rows, whose `final` the same file says stays empty
# by design — testing every row against `final` would make Wave 1 permanently
# incomplete and no resumed run could ever pass it. Tracked as `skills-j4q`.

# The same ten columns `staged_fixture` writes into a real run's ledger. Shared
# rather than copied: a header that drifted from the one under test would make
# `staged_run.ledger_rows` parse a table no run ever produces.
WAVE_HEADER = staged_fixture.LEDGER


def _row(bead, wave, *, returned="", final="", artifact="", worker="—") -> str:
    return (f"| {bead} | {wave} | {worker} | 2026-08-29T10:00:00Z | {returned} "
            f"| {artifact} | — | — | 1 | {final} |\n")




def _discard(testbed, runs_dir, run_id: str, *extra) -> int:
    """The real `discard.py`, as a subprocess. Its exit code is the answer."""
    code, _, _ = harness.run("discard.py", "--runs-dir", str(runs_dir),
                             "--run-id", run_id, *extra, testbed=testbed)
    return code


# --- the fingerprint ---------------------------------------------------------


def _digest(root: Path) -> list:
    """Path and content hash for every file under `root`. Content, not mtime:
    a rewrite that restored the same bytes is not a change a discard needs to
    undo, and a copy that preserved mtime while changing bytes is."""
    if not root.is_dir():
        return []
    return sorted((str(p.relative_to(root)),
                   hashlib.sha256(p.read_bytes()).hexdigest())
                  for p in root.rglob("*") if p.is_file())


def _tracker(testbed) -> list:
    """ID, status and notes for every bead, closed ones included."""
    return sorted((row["id"], row.get("status"), row.get("notes") or "")
                  for row in staged_fixture.bd_list(testbed))


def _source(testbed) -> str:
    proc = subprocess.run(["git", "-C", str(testbed.path), "status", "--porcelain"],
                          capture_output=True, text=True)
    return proc.stdout


def _fingerprint(testbed) -> dict:
    """Every tree staging and discarding must leave exactly as they found it.

    Compared before against after, never asserted clean in isolation: the
    testbed's tracker and corpus are never empty, so "unchanged" is the only
    claim either one can support.
    """
    return {
        "tracker": _tracker(testbed),
        "corpus": _digest(testbed.corpus / testbed.path.name),
        "source": _source(testbed),
    }


# --- discard -----------------------------------------------------------------


def case_discard_is_a_complete_undo(testbed) -> None:
    """A run with real artifacts on disk, fingerprinted either side.

    The two beads are created before the fingerprint on purpose: `bd create` is
    this fixture's setup and a triage run never makes one. What is measured is
    the window a run actually owns — stage, then delete.
    """
    beads = (staged_fixture.bd_create(testbed, "e2e discard: plan route"),
             staged_fixture.bd_create(testbed, "e2e discard: investigate route"))
    before = _fingerprint(testbed)
    fixture = staged_fixture.stage_run(testbed, "discard", beads=beads)
    assert (fixture.run / "todo" / staged_fixture.PLAN_FOLDER / "plan.md").is_file()
    assert (fixture.run / "investigations" / staged_fixture.INVEST_NAME).is_file()
    assert _fingerprint(testbed) == before, "staging wrote outside the run directory"

    assert _discard(testbed, fixture.runs_dir, "ab12", "--dry-run") == 0
    assert fixture.run.is_dir(), "a dry run deleted the run"
    assert _discard(testbed, fixture.runs_dir, "ab12") == 0
    assert not fixture.run.exists()
    assert _fingerprint(testbed) == before, "discard left something behind"


def case_discard_refuses_zero_matches(testbed) -> None:
    runs = harness.scratch_path(testbed, "discard_zero")
    runs.mkdir(parents=True, exist_ok=True)
    assert _discard(testbed, runs, "nosuchrun") == 2


def case_discard_refuses_more_than_one_match(testbed) -> None:
    runs = harness.scratch_path(testbed, "discard_many")
    names = ("2026-08-29_a_same", "2026-08-29_b_same")
    for name in names:
        (runs / name).mkdir(parents=True, exist_ok=True)
    assert _discard(testbed, runs, "same") == 2
    for name in names:
        assert (runs / name).is_dir(), "an ambiguous resolve deleted a run"


def case_discard_never_touches_a_sibling_run_or_promoted(testbed) -> None:
    """`rm -rf` of exactly one run directory — never a glob, never the parent,
    and never a run that already promoted, which is past the point of undo."""
    fixture = staged_fixture.stage_run(testbed, "sibling")
    sibling = staged_run.create_run(fixture.runs_dir, "2026-08-29_zz99")
    (sibling / "keep.md").write_text("sibling", encoding="utf-8")
    promoted = fixture.runs_dir / "promoted" / "2026-08-01_old"
    promoted.mkdir(parents=True, exist_ok=True)
    (promoted / "keep.md").write_text("promoted", encoding="utf-8")

    assert _discard(testbed, fixture.runs_dir, "old") == 2, (
        "discard reached inside promoted/")
    assert _discard(testbed, fixture.runs_dir, "ab12") == 0
    assert not fixture.run.exists()
    assert (sibling / "keep.md").is_file(), "a sibling run was deleted"
    assert (promoted / "keep.md").is_file(), "a promoted run was deleted"


# --- resume ------------------------------------------------------------------


def case_resume_continues_from_the_first_incomplete_wave(testbed) -> None:
    fixture = staged_fixture.stage_run(testbed, "resume_first")
    ledger = (WAVE_HEADER
              + _row("all", 0, returned="2026-08-29T10:00:01Z")
              + _row("c1", 1, returned="2026-08-29T10:01:00Z", worker="dup-judge")
              + _row("tb-inv1", 2, returned="2026-08-29T10:20:00Z", final="planned",
                     worker="invest-1")
              + _row("tb-inv2", 2, worker="invest-2")
              + _row("tb-pln1", 4, worker="plan-1"))
    (fixture.run / "ledger.md").write_text(ledger, encoding="utf-8")
    assert len(staged_run.ledger_rows(fixture.run)) == 5
    assert staged_run.first_incomplete_wave(fixture.run) == 2


def case_resume_reads_the_ledger_not_the_artifacts_on_disk(testbed) -> None:
    """`references/ledger.md` — a worker that died mid-write leaves a file
    behind, so completeness is never inferred from disk.

    The wave-2 row is the hard shape: its artifact is on disk *and* its `final`
    is written, and it is still incomplete because `returned` is empty. That is
    a return stamped half-way — the row's own `final` cell written before the
    timestamp that says the dispatch came back. Every other row in this suite
    has both cells empty together, which would let a resume that dropped the
    `returned` half of the rule pass unnoticed.
    """
    fixture = staged_fixture.stage_run(testbed, "resume")
    artifact = fixture.run / "investigations" / staged_fixture.INVEST_NAME
    assert artifact.is_file()
    ledger = (WAVE_HEADER
              + _row("all", 0, returned="2026-08-29T10:00:01Z")
              + _row(fixture.invest_bead, 2, worker="invest-1", final="planned",
                     artifact=str(artifact)))
    (fixture.run / "ledger.md").write_text(ledger, encoding="utf-8")
    rows = staged_run.ledger_rows(fixture.run)
    assert rows[1]["final"] == "planned" and not rows[1]["returned"], rows
    assert staged_run.first_incomplete_wave(fixture.run) == 2, (
        "a row with no `returned` was read as complete because its artifact "
        "exists and its outcome was already written")


def case_resume_survives_a_promote_log_in_the_same_file(testbed) -> None:
    """The promote log is a second section of `ledger.md` with three columns.
    A resume that read those as wave rows would crash on `int(row['wave'])`.

    Stated as "the wave rows are unchanged" rather than "there are none": the
    fixture seeds the outcome rows promote reads, so a parser that swallowed
    the log's rows would be caught here instead of matching an empty list.
    """
    fixture = staged_fixture.stage_run(testbed, "resume_log")
    waves = staged_run.ledger_rows(fixture.run)
    assert waves, "the fixture seeds no wave rows — this case proves nothing"
    staged_run.record_step(fixture.run, "move", "2 artifact(s)")
    text = (fixture.run / "ledger.md").read_text(encoding="utf-8")
    assert staged_run.PROMOTE_LOG in text, text
    assert staged_run.ledger_rows(fixture.run) == waves, text
    assert staged_run.completed_steps(fixture.run) == {"move": "2 artifact(s)"}


def case_a_complete_wave_one_cluster_row_is_not_incomplete(testbed) -> None:
    """`skills-j4q`, pinned. `ledger.md`'s resume paragraph says a wave is
    incomplete when any of its rows has an empty `final`, while its row-kind
    table says a cluster row's `final` stays empty by design. Read literally,
    Wave 1 is incomplete forever and no run resumes past it."""
    fixture = staged_fixture.stage_run(testbed, "resume_cluster")
    (fixture.run / "ledger.md").write_text(
        WAVE_HEADER
        + _row("all", 0, returned="2026-08-29T10:00:01Z")
        + _row("c1", 1, returned="2026-08-29T10:01:00Z", worker="dup-judge")
        + _row("tb-inv2", 2, worker="invest-2"), encoding="utf-8")
    rows = staged_run.ledger_rows(fixture.run)
    assert all(not row["final"] for row in rows if row["wave"] in ("0", "1"))
    assert staged_run.first_incomplete_wave(fixture.run) == 2, (
        "the literal reading of the resume rule is in force — a run can never "
        "resume past Wave 1")


def case_resume_on_an_unknown_runid_exits_2(testbed) -> None:
    fixture = staged_fixture.stage_run(testbed, "resume_unknown")
    assert _discard(testbed, fixture.runs_dir, "ab12", "--dry-run") == 0
    assert _discard(testbed, fixture.runs_dir, "doesnotexist") == 2


CASES = [v for k, v in sorted(globals().items()) if k.startswith("case_")]
