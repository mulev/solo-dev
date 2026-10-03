#!/usr/bin/env python3
"""Read a staged triage run: where it lives, what it recorded, and where each
of its artifacts belongs once promoted.

Every module in the promote sequence needs these three answers, and none of
them is a decision — a run directory's shape is fixed by `triage/SKILL.md`,
and this file is the one place that knows it.

The promote log is a separate section of the run's own `ledger.md`. It shares
the file because a run has one state on disk, and it stays out of the wave
table because those ten columns are the wave rows' contract, not a general
key-value store.
"""

from __future__ import annotations

import contextlib
import shutil
from collections import namedtuple
from datetime import datetime, timezone
from pathlib import Path

import manifest as manifest_io

Finding = namedtuple("Finding", "severity code subject detail")

# What makes a bead workable: a plan path in its notes. `inventory.select`
# routes on exactly these three, and the skill's bead rules say an
# `Investigation:` line is not a plan reference.
PLAN_MARKERS = ("Plan:", "Slice:", "Master:")
# Every marker line this system writes, and therefore the ones a note rewrite
# replaces rather than duplicates. The two tuples were one, and the join cost a
# live promote five false quarantines: a parked bead carries the
# `Investigation:` line a *previous* run's own park wrote, so testing this
# wider set for "someone re-planned it by hand" indicts every bead the system
# has ever parked. A marker we author is not evidence of a human's edit.
OWNED_MARKERS = PLAN_MARKERS + ("Investigation:",)
# The wave table's contract. Every rule in `references/ledger.md` is stated in
# terms of these names, so they are seeded from here rather than retyped by
# whichever session opens the run.
LEDGER_COLUMNS = ("bead", "wave", "worker", "dispatched", "returned",
                  "artifact", "tier-1", "verdict", "round", "final")
LEDGER_TABLE = ("| " + " | ".join(LEDGER_COLUMNS) + " |\n"
                + "|" + "|".join("---" for _ in LEDGER_COLUMNS) + "|\n")
# `unrecorded` rather than a default of `full run`: a caller that forgot would
# otherwise produce a ledger asserting the wrong mode, and a resumed dry run
# that believes it is a full one walks into Wave 2 and dispatches.
UNRECORDED_MODE = "unrecorded — the run did not say"
PROMOTE_LOG = "## Promote log"
LOG_HEADER = f"\n{PROMOTE_LOG}\n\n| key | at | detail |\n|---|---|---|\n"
STAMP = "%Y-%m-%dT%H:%M:%SZ"


class Usage(Exception):
    """Bad invocation or an unreadable run. Always exit 2."""


# --- creating the run --------------------------------------------------------


STAGING_GITIGNORE = """\
# Triage runs are staging: discardable, and never committed.
# A run swept into a commit is permanent, and `discard` then deletes a
# directory whose contents are already in history — the invariant reads as
# true while being false.
#
# `*` covers this file too, deliberately. Negating it back would leave one
# un-ignored file here, and git then reports the whole staging directory as
# untracked — the exact noise this is here to remove.
*
"""


def ledger_header(mode: str | None = None) -> str:
    """The seeded ledger: title, the run's mode, and the wave table's columns."""
    stated = f"`{mode}`" if mode else UNRECORDED_MODE
    return f"# Triage run ledger\n\nMode: {stated}\n\n{LEDGER_TABLE}"


def ledger_row(**cells) -> str:
    """One wave-table row, newline included: cells named by `LEDGER_COLUMNS`,
    the rest left empty. The column order is the header's, for the same reason
    the header is seeded from here — a row typed by hand drifts from it.

    A relative `artifact` cell raises rather than being reported. This is the
    writer: nobody has yet claimed the row is valid, and the caller is holding
    the wrong value right now. `references/ledger.md` specifies the cell as an
    absolute path inside the run directory, and a relative one travelled from
    a cell like this to a bead note reading `Plan: todo/....md` (`skills-xfu`).
    """
    values = {c: str(cells.get(c, "")) for c in LEDGER_COLUMNS}
    bad = relative_artifact(values)
    if bad:
        raise Usage(f"{values['bead'] or '?'} wave {values['wave']}: "
                    f"artifact path is not absolute: {bad}")
    return "| " + " | ".join(values[c] for c in LEDGER_COLUMNS) + " |\n"


def create_run(runs_dir, run_id: str, mode: str | None = None) -> Path:
    """The run directory, with the staging root marked uncommittable and the
    run's ledger opened on its canonical header.

    The marker goes in the staging root rather than the run, so it covers
    every run the project will ever stage, and an existing one is never
    overwritten — a plans repo that wrote its own rules keeps them.

    The ledger is seeded for the same reason the column list lives in this
    module: those ten names are what every rule in `references/ledger.md` is
    written against, and a header retyped per run makes the schema whatever
    that session remembered. Seeding it also means "read `ledger.md`" is true
    from the moment a run exists rather than from its first row. An existing
    ledger is never touched, so a resumed or re-created run keeps its rows.

    `mode` is what the run was invoked as — `--dry-run` or a full run. It is
    seeded rather than left to the close-out because a resume has to know which
    one it is continuing before it dispatches anything.
    """
    root = Path(runs_dir)
    root.mkdir(parents=True, exist_ok=True)
    marker = root / ".gitignore"
    if not marker.exists():
        marker.write_text(STAGING_GITIGNORE, encoding="utf-8")
    run = root / run_id
    run.mkdir(parents=True, exist_ok=True)
    # Every directory a wave writes into, made before any wave dispatches.
    # The four brief generators print to stdout, so their output needs a home
    # inside the run or the orchestrator picks one — and a brief written to
    # `/tmp` is a dispatched instruction `discard` cannot reach. That reason
    # covers artifacts and verdicts unchanged: a live run dispatched Wave 2
    # against an `investigations/` that did not exist and created it mid-flight,
    # and wrote Wave 5's verdicts to `/tmp` before inventing `verdicts/`.
    # `intents/` is created empty and stays empty until the intent writer fills
    # it — an empty directory here is the contract, not a leftover. And
    # `reports/`: a worker's return has to outlive its job leg, which the
    # harness retains five minutes past settlement, so a report kept only there
    # is one a `REVISE` verdict can never reach.
    for name in ("briefs", "investigations", "todo", "verdicts", "intents",
                 "reports"):
        (run / name).mkdir(exist_ok=True)
    ledger = run / "ledger.md"
    if not ledger.exists():
        ledger.write_text(ledger_header(mode), encoding="utf-8")
    return run


# --- locating the run --------------------------------------------------------


def resolve_run(runs_dir, run_id: str) -> Path:
    """The single run directory `run_id` names, by full name or short suffix.

    Zero or more than one match is a usage error, never a guess: `discard`
    holds the same rule, and promoting the wrong run is not recoverable.
    """
    root = Path(runs_dir)
    if not root.is_dir():
        raise Usage(f"no such runs directory: {root}")
    hits = [p for p in sorted(root.iterdir())
            if p.is_dir() and p.name != "promoted"
            and (p.name == run_id or p.name.endswith(f"_{run_id}"))]
    if len(hits) != 1:
        raise Usage(f"--run-id {run_id} matches {len(hits)} runs under {root}")
    return hits[0]


def load_run(run_dir: Path) -> dict:
    try:
        return manifest_io.load(Path(run_dir) / "manifest.json")
    except manifest_io.ManifestError as exc:
        raise Usage(str(exc)) from exc


def run_start(run_dir: Path, data: dict) -> float:
    """When the run began, which is what makes "landed since" answerable."""
    stamp = data.get("generated_at")
    if stamp:
        with contextlib.suppress(ValueError):
            return datetime.strptime(stamp, STAMP).replace(
                tzinfo=timezone.utc).timestamp()
    return Path(run_dir).stat().st_mtime


# --- the promote log ---------------------------------------------------------


def completed_steps(run_dir) -> dict:
    """Every step key the ledger records, mapped to the detail it recorded."""
    ledger = Path(run_dir) / "ledger.md"
    if not ledger.is_file():
        return {}
    out, seen = {}, False
    for line in ledger.read_text(encoding="utf-8").splitlines():
        if line.strip() == PROMOTE_LOG:
            seen = True
        elif seen and line.startswith("| ") and not line.startswith("| key "):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) == 3 and set(cells[0]) != {"-"}:
                out[cells[0]] = cells[2]
    return out


# One ledger row per moved artifact, keyed by its staged path. The row is a
# markdown table cell and `completed_steps` above splits on `|`, so neither
# key nor detail may contain `|` or a newline — absolute plan paths contain
# neither, which is what makes the staged path usable as a step key.
# It lives here, beside the writer and the reader of the same promote log,
# because `staged_run_checks.intentless_artifacts` asks which moves are
# already recorded and `promote.py` imports `staged_run_checks`: keeping the
# prefix in `promote.py` means either an import cycle or a second copy of it.
MOVE_PREFIX = "move:"


def recorded_moves(done: dict) -> dict:
    """The moves an earlier pass already made, staged path to promoted path."""
    return {key[len(MOVE_PREFIX):]: value for key, value in (done or {}).items()
            if key.startswith(MOVE_PREFIX)}


# The waves that produce an artifact. Wave 5 is not one of them — it gates an
# artifact produced earlier, which is why it is named separately below.
ARTIFACT_WAVES = (2, 4)
GATE_WAVE = 5
# The two outcomes that end an artifact's review. `REVISE` owes another round,
# and `—` is a tier-1 bounce or a reviewer that died without returning one.
TERMINAL_VERDICTS = ("PASS", "PARK")


def ledger_rows(run_dir) -> list:
    """The wave table's rows as dicts, keyed by its own header.

    The promote log is a separate two-column section and is skipped: only rows
    whose width matches the wave header are wave rows.
    """
    ledger = Path(run_dir) / "ledger.md"
    if not ledger.is_file():
        return []
    header, out = None, []
    for line in ledger.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if set("".join(cells)) == {"-"} or not cells:
            continue
        if header is None or len(cells) != len(header):
            if header is None:
                header = cells
            continue
        out.append(dict(zip(header, cells)))
    return [r for r in out if r.get("wave", "").isdigit()]


def recorded(row: dict, column: str) -> str:
    """The value the row records in `column`, or `""` when it records none.

    `—` is the ledger's "this cell is not one this row kind can fill"
    (`references/ledger.md` § *The row kinds*): a Wave 4 row for a group nobody
    planned writes `worker` `—` and `artifact` `—` deliberately, so the run says
    the omission was a decision. It is a sentinel, not a value, and `"—"` is
    truthy — so every reader that tests a cell for content comes through here
    rather than repeating the pair and getting it wrong in one place.
    """
    value = row.get(column, "")
    return "" if value == "—" else value


def relative_artifact(row: dict) -> str:
    """The row's `artifact` cell when it is not the absolute path
    `references/ledger.md` specifies, or `""` when the cell is fine.

    One test, two surfaces: `ledger_row` refuses such a cell as it is written,
    and `staged_run_checks.ledger_artifacts` reports one typed straight into
    `ledger.md`. Neither an unfilled cell nor `—` is a relative path — an
    empty cell is a row that has not filled it yet, and `—` is the row kinds'
    "this cell is not one this row kind can fill", which `recorded` above is
    the only reader of.

    Shape, never location: an absolute path inside the run directory is
    correct here and stale only after the move, which is
    `promote.stale_intents`' question.

    It cannot live beside `tracker_intents.PATH_KEYS`, where the record-level
    predicate lives: `tracker_intents` imports this module, so the import back
    would be a cycle — and a ledger cell is not an intent record. The two
    lanes share the wording `path is not absolute`, which
    `plan_artifact_checks.py:216` also uses, so one grep finds all three.
    """
    cell = recorded(row, "artifact").strip()
    return "" if not cell or cell.startswith("/") else cell


def _gate_key(row: dict) -> str:
    """What a Wave 5 row and the artifact row it gates have in common.

    The artifact's own path when the row records one, and the bead or group ID
    otherwise — one rule applied to both sides, so the two can never be keyed
    differently.
    """
    return recorded(row, "artifact") or row.get("bead", "")


def first_incomplete_wave(run_dir):
    """The wave a `--resume` continues from, or `None` when the run finished.

    `references/ledger.md`'s resume rule, and `final` is no part of it. A row
    whose `returned` is empty makes its own wave incomplete — that is the whole
    dispatch test. An artifact row that returned and was never gated makes
    **Wave 5** incomplete, because the gate is the work that is missing; the
    investigation it names came back, and re-dispatching it would spend a worker
    on an artifact already on disk.

    `final` records an outcome once it is known, which for a Wave 2 row is not
    until Wave 4 or Wave 5 settles the bead. A column that fills in later cannot
    be a readiness test for the wave that wrote it: testing it here sent a live
    run correctly working Wave 5 back to Wave 2 with all nine of its
    investigations returned. That is the Wave 1 cluster-row bug (`skills-j4q`)
    one wave over — the carve-out this docstring used to argue for was a special
    case of the rule above.

    No ledger means nothing ran: resume from the start rather than guessing from
    files on disk, because a worker that died mid-write leaves one behind.

    A row with no worker and no recorded artifact is a **decision record**, not
    a dispatch: the Wave 4 row a run writes for a group nobody planned. It owes
    no gate, and reading it as an ungated artifact row strands the run at Wave 5
    forever. A planning dispatch that merely omitted its path still owes one,
    which is why the worker is tested too.
    """
    rows = ledger_rows(run_dir)
    if not rows:
        return 0
    gated = {_gate_key(row) for row in rows
             if int(row["wave"]) == GATE_WAVE
             and row.get("verdict") in TERMINAL_VERDICTS}
    outstanding = set()
    for row in rows:
        wave = int(row["wave"])
        if not row.get("returned"):
            outstanding.add(wave)
        elif (wave in ARTIFACT_WAVES
              and (recorded(row, "worker") or recorded(row, "artifact"))
              and _gate_key(row) not in gated):
            outstanding.add(GATE_WAVE)
    return min(outstanding, default=None)


def bead_outcomes(run_dir, manifest: dict) -> dict:
    """Each bead's settled `final` and artifacts, read from the ledger.

    A bead's artifacts stay in the order the rows first named them. `add`
    below holds the one-entry-per-path rule and its reason in one place;
    both artifact waves come through it.
    """
    members = {g["group_id"]: g.get("members", [])
               for g in (manifest.get("groups") or [])}
    out: dict = {}

    def slot(bead: str) -> dict:
        return out.setdefault(bead, {"final": "", "artifacts": []})

    def add(entry: dict, artifact: str) -> None:
        """One entry per artifact path, however many rows name it.

        A `REVISE` re-dispatch is a second dispatch, so the ledger owes it a
        second row — at the *same* assigned path, because a second path would
        orphan the first artifact. Two equal cells are therefore two
        references to one file, never two files. Per bead rather than global:
        a Wave 4 group plan legitimately belongs to every member.
        """
        if artifact and artifact not in entry["artifacts"]:
            entry["artifacts"].append(artifact)

    for row in ledger_rows(run_dir):
        wave, bead = int(row["wave"]), row.get("bead", "")
        artifact = recorded(row, "artifact")
        if not bead or bead == "all":
            continue
        if wave == 2:
            entry = slot(bead)
            entry["final"] = row.get("final", "")
            add(entry, artifact)
        elif wave == 4:
            # A group plan is owned by every member; a key the manifest does
            # not name owns itself, so its artifact is not lost. Wave 3 is a
            # wave row, not an artifact row — its `artifact` cell holds the
            # run's own collision report, which nothing promotes.
            for owner in members.get(bead, [bead]):
                entry = slot(owner)
                add(entry, artifact)
                # A decision record is the only outcome its members ever get:
                # a group whose beads are all parked or duplicate has no Wave 2
                # row anywhere, so dropping this `final` leaves every member
                # reading as still in flight and `derive_intents` exits 1 on a
                # run that followed the rule. Only fill what is still empty —
                # a member's own Wave 2 outcome is more specific than the
                # group's and is never overwritten.
                if not entry["final"]:
                    entry["final"] = recorded(row, "final")
    return out


def record_step(run_dir, key: str, detail: str = "") -> None:
    ledger = Path(run_dir) / "ledger.md"
    text = ledger.read_text(encoding="utf-8") if ledger.is_file() else ""
    if PROMOTE_LOG not in text:
        text = text.rstrip("\n") + "\n" + LOG_HEADER
    stamp = datetime.now(timezone.utc).strftime(STAMP)
    ledger.write_text(f"{text.rstrip(chr(10))}\n| {key} | {stamp} | {detail} |\n",
                      encoding="utf-8")


def close_out(run_dir: Path, runs_dir) -> Path:
    """The ledger is closed before the run moves, or the write lands nowhere."""
    promoted = Path(runs_dir) / "promoted" / Path(run_dir).name
    record_step(run_dir, "close", str(promoted))
    promoted.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(run_dir), str(promoted))
    return promoted


# --- where a staged artifact belongs -----------------------------------------


def real_dir(plans_dir, project: str, kind: str) -> Path:
    """The real directory a promoted artifact of `kind` belongs in."""
    return Path(plans_dir) / project / kind


def target_for(plans_dir, project: str, staged: Path) -> Path:
    kind = "investigations" if staged.parent.name == "investigations" else "todo"
    return real_dir(plans_dir, project, kind) / staged.name


def staged_investigations(run_dir) -> list:
    return sorted((Path(run_dir) / "investigations").glob("*.md"))


def staged_plans(run_dir) -> list:
    """Plan folders and single-phase plan files, directly under the run's todo."""
    todo = Path(run_dir) / "todo"
    if not todo.is_dir():
        return []
    return sorted(p for p in todo.iterdir() if p.is_dir() or p.suffix == ".md")
