#!/usr/bin/env python3
"""One tracker intent as a validated record on disk.

`tracker_intents.render` consumes a mapping with per-kind keys, and no schema
ever said which. This module is that schema, plus the store the records live
in: `{run}/intents/<bead>.json`, one JSON list per bead.

The required-key table is read off `tracker_intents` — `render`, `_create`,
`notes_for` and `apply_intents` — and nothing else. A key no `bd` call
consumes is not required here, however sensible it looks.

**A malformed record is reported, never raised on** — `validate` returns
findings the way `plan_coverage.validate_coverage` does, because the validator
written to reject a malformed ruling was the thing that crashed on one.

**An unreadable file is not a record, and it raises.** The rule above is about
the contents of a well-formed store; a file that is not a JSON list produced
no records at all, and returning `[]` for it reports an empty store where
there is an unreadable one. `manifest.load` draws the same line. Do not "fix"
this into a finding later.
"""

from __future__ import annotations

import json
from pathlib import Path

import tracker_intents

# The kind vocabulary is `tracker_intents`' own, never a second copy: a list
# retyped here is a lockstep pair, and the copy that drifts is this one.
KINDS = tuple(tracker_intents.KIND_ORDER)
# Who writes which kind. `derive_intents` replaces only DERIVED_KINDS in a
# bead's file; Phase 5's worker records are WORKER_KINDS and survive a rerun.
# Both halves live here so neither module can hold a private list that drifts.
DERIVED_KINDS = ("investigation", "flip-source", "dep", "supersede", "close")
WORKER_KINDS = ("create-epic", "create-task", "open", "retitle")
COMMON = ("key", "kind")
REQUIRED = {
    "create-epic": ("ref", "title", "master"),
    "create-task": ("ref", "title"),
    "open": ("ref",),
    "investigation": ("bead", "investigation"),
    "flip-source": ("bead", "plan"),
    "dep": ("from", "to"),
    # `by` is the epic ref `tracker_intents._needs` blocks on, and `master` is
    # the path the notes carry. `master` is already in `PATH_KEYS`, so the
    # absolute-path rule reaches this kind with no new code.
    "supersede": ("bead", "by", "master"),
    # `title` is deliberately not a `PATH_KEYS` field: it is a string a human
    # reads, and the absolute-path rule would demand a path of a title.
    "retitle": ("bead", "title"),
    "close": ("bead", "investigation"),
}
STORE = "intents"


class IntentStoreError(Exception):
    """The store could not be read as a store. Callers exit 2."""


def validate(record) -> list:
    """Findings against one record. Empty list means `render` can consume it."""
    if not isinstance(record, dict):
        return [f"record is {type(record).__name__}, not an object"]
    where = record.get("key") or "<no key>"
    kind = record.get("kind")
    # Naming the missing key is the whole finding — see plan_coverage.
    if kind is None:
        return [f"{where}: record carries no kind"]
    if kind not in KINDS:
        return [f"{where}: unknown kind {kind!r}"]
    out = [f"{where}: {kind} carries no {field}"
           for field in COMMON + REQUIRED[kind]
           if not str(record.get(field) or "").strip()]
    # Wording matches `plan_artifact_checks.py:216`, which enforces the same
    # rule in the plan-markdown lane, so one grep finds both. Shape, never
    # location — `tracker_intents.relative_paths` says why.
    out += [f"{where}: {field} --notes path is not absolute: {value}"
            for field, value in tracker_intents.relative_paths(record)]
    if kind == "create-task" and not _task_paths(record):
        out.append(f"{where}: create-task names neither slice+master nor plan")
    return out


def _task_paths(record: dict) -> bool:
    """`notes_for` picks TASK_NOTES on `slice` and SINGLE_NOTES otherwise, so
    one of the two shapes must be complete or the note names `None`."""
    if record.get("slice"):
        return bool(record.get("master"))
    return bool(record.get("plan"))


def store_dir(run_dir) -> Path:
    return Path(run_dir) / STORE


def save(run_dir, bead: str, records: list) -> Path:
    """Replace `bead`'s records. One file per bead, so no two beads ever race."""
    store = store_dir(run_dir)
    # A run created before `create_run` made `intents/` has no such directory.
    store.mkdir(parents=True, exist_ok=True)
    path = store / f"{bead}.json"
    path.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
    return path


def merge(run_dir, bead: str, records: list) -> Path:
    """Add `records` to `bead`'s file, replacing only the keys they name.

    Two waves write the same bead: Wave 2's investigation worker may return a
    `retitle`, and Wave 4's planning worker returns the epic's own records. A
    `save` from the second wave replaced the first wave's file, so the
    correction vanished before `derive_intents` ever ran its own merge — and
    nothing reported it, because a store missing a record it never saw is
    well-formed. The key is the identity here, exactly as it is in
    `derive_intents._merged`. A batch member that is not an object carries no
    key and replaces nothing: it is stored as it arrived, the way `save` and
    `load_all` already treat one, so the promote gate reports it rather than
    this writer raising on it mid-wave.
    """
    replaced = {r.get("key") for r in records
                if isinstance(r, dict) and r.get("key")}
    keep = [r for r in load(run_dir, bead)
            if not (isinstance(r, dict) and r.get("key") in replaced)]
    return save(run_dir, bead, keep + records)


def load(run_dir, bead: str) -> list:
    """One bead's records, or `[]` when it has no file yet."""
    path = store_dir(run_dir) / f"{bead}.json"
    return _read(path) if path.is_file() else []


QUALIFIER = "/"


def _qualified(owner: str, records: list) -> list:
    """One file's records with every name it defines or consumes prefixed by
    the bead that owns the file.

    A `key` and a `ref` are names inside one bead's file: `promoting.md` gives
    the phase titles, the parent links and the plan path to the planning
    worker, and the owner to the filename — so two workers both writing
    `ref: "epic"` for their own epic is correct authorship, not a mistake
    either of them could have avoided. Resolving those names in one flat
    namespace is what broke: the second `bd create` overwrote the first's id,
    every phase task landed under the epic created last, one epic came out
    childless, and a `supersede` retired its source bead naming the wrong one.

    A `NEEDS` field may name a local ref, a bead that existed before the run,
    or a ref in *another* bead's file — `derive_intents` stores a `supersede`
    under the member it retires while the `create-epic` it names belongs to
    whichever bead the planner wrote, so that one is cross-file by
    construction. Only a bare local name is prefixed: prefixing a `dep`
    endpoint `collide.py` derived between two pre-existing beads would hand
    `bd dep add` an id no tracker has, and prefixing an already-qualified one
    would bury the owner it already carries under a second copy.

    That makes qualifying idempotent, which it has to be: `derive_intents`
    reads the store through `load_all` and writes what it read back, so a
    re-derived run reads its own output.
    """
    local = {record["ref"] for record in records
             if isinstance(record, dict) and record.get("ref")}

    def qualify(name: str) -> str:
        return name if QUALIFIER in name else f"{owner}{QUALIFIER}{name}"

    out = []
    for record in records:
        if not isinstance(record, dict):
            out.append(record)
            continue
        named = dict(record)
        for field in ("key", "ref"):
            if named.get(field):
                named[field] = qualify(named[field])
        for field in tracker_intents.NEEDS.get(named.get("kind"), ()):
            if named.get(field) in local:
                named[field] = qualify(named[field])
        out.append(named)
    return out


def load_all(run_dir) -> list:
    """Every record in the store, files in sorted name order, each carrying
    the bead that owns it and the names it uses qualified by that bead.

    `save` is the only writer of a store file and names it `f"{bead}.json"`,
    so the filename is where the owner already lives — attaching it here gives
    the owner one source and nothing to drift. It is why the three worker
    kinds never write `bead`: no producer has to, and `promote`'s per-bead
    quarantine filter still gets an owner for every record it reads.

    `_qualified` above says why the same place owns the namespacing: every
    consumer reads the store through here, so the promote log, `applied_states`
    and `apply_intents` all speak one set of names. Doing it inside the
    resolver instead would leave the log's keys and the store's keys disagreeing
    — and `applied_states` reads a write of ours back off that log.

    A record's own value wins for `bead`, because an `investigation` or
    `flip-source` record's `bead` is the `bd` target and a filename must never
    retarget it. A member that is not an object passes through unchanged, so
    `staged_run_checks.invalid_intents` names it rather than this reader
    raising on it.

    `load` stays raw on purpose: its caller merges records back into the same
    file, and attaching there would write the owner into the store as a second
    copy on disk — and qualifying there would write the prefix in too, so the
    next merge would qualify it twice.

    A run with no `intents/` returns `[]`: a run that staged no intent is a
    real state — a `--dry-run` is one — and not an error. A file that is not a
    JSON list is an error, and raises.
    """
    store = store_dir(run_dir)
    if not store.is_dir():
        return []
    out = []
    for path in sorted(store.glob("*.json")):
        records = [{"bead": path.stem, **record} if isinstance(record, dict)
                   else record for record in _read(path)]
        out += _qualified(path.stem, records)
    return out


def _read(path: Path) -> list:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as err:
        raise IntentStoreError(f"cannot read intents {path}: {err}") from err
    if not isinstance(payload, list):
        raise IntentStoreError(
            f"cannot read intents {path}: top level is"
            f" {type(payload).__name__}, not a list")
    return payload
