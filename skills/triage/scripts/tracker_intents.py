#!/usr/bin/env python3
"""Apply a triage run's tracker intents serially, in dependency order.

A worker never writes to the tracker. It emits an *intent* carrying staged
paths and no notes text, because it cannot know where its artifacts will
land. This module turns intents into `bd` calls once the paths are real.

The notes templates are not invented here: the epic, task and single-phase
formats come from `plan` Step 8b's `<tracker-notes-requirement>`, the source
flip from `plan` Step 8c, and the investigation outcome from `investigate`
Step 5d. `--description` carries the step checklist and `--notes` carries the
absolute paths — merging them is what orphans a task from its plan. The
absoluteness half is enforced rather than assumed: `relative_paths` names the
offending fields, `intent_records.validate` reports them, and `render` refuses
to build an argv from one.

The runner is injected, which is what lets ordering, notes formatting,
absolute-path enforcement and post-write verification be tested without a
beads database.
"""

from __future__ import annotations

import json
import subprocess
from collections import namedtuple
from pathlib import Path

from staged_run import Finding, OWNED_MARKERS, Usage

Apply = namedtuple("Apply", "commands findings ids applied")
# `field` is the bead field the write records, and the one `_verify` reads
# back: a `retitle` writes a title and nothing else, so checking it against
# notes would fail a correct write or pass a missing one.
Call = namedtuple("Call", "argv bead path field", defaults=("notes",))

# `supersede` is late and `close` last: a bead is retired only once everything
# replacing or explaining it exists and is workable, so a failed pass leaves it
# un-retired rather than retired with that work unapplied. `retitle` writes only
# a title, so nothing depends on where it sits.
KIND_ORDER = {"create-epic": 0, "create-task": 1, "dep": 2, "open": 3,
              "investigation": 4, "flip-source": 5, "supersede": 6,
              "retitle": 7, "close": 8}
NEEDS = {"create-task": ("parent",), "dep": ("from", "to"), "open": ("ref",),
         "supersede": ("by",)}
PATH_KEYS = ("plan", "slice", "master", "investigation")


def relative_paths(intent: dict) -> list:
    """The `PATH_KEYS` fields this record carries whose value is not absolute.

    Shape, never location. An absolute path inside the run directory is
    correct *before* promote — every worker artifact is one — and wrong only
    after, which is `promote.stale_intents`' question and not this one. A
    check that demanded the promoted location would fire on every correct
    pre-promote intent, and a check that demanded the run directory would
    fire on every correct promoted one.

    Absent and empty fields are not this rule's business: whether a field is
    required at all is `intent_records.REQUIRED`'s, and reporting both here
    would name one mistake twice.
    """
    return [(key, str(intent[key])) for key in PATH_KEYS
            if str(intent.get(key) or "").strip()
            and not Path(str(intent[key])).is_absolute()]


EPIC_NOTES = ("Plan: {master}\nThis epic's master plan contains the dependency table,"
              " cross-cutting concerns, and success criteria. Each child task has its"
              " own slice file with full implementation detail. Use the execution"
              " skill to implement.")
TASK_NOTES = ("Slice: {slice}\nMaster: {master}\nFull implementation detail (code"
              " snippets, insertion points, done-when criteria) is in the slice file."
              " Use the execution skill to implement.")
SINGLE_NOTES = ("Plan: {plan}\nFull detail: see plan file. Use the execution skill"
                " when implementing.")
INVEST_NOTES = ("Investigation: {investigation}\nRoot cause confirmed and fix"
                " approved. Use the planning skill to create the implementation plan.")
FLIP_NOTES = "Plan: {plan}"
SUPERSEDE_NOTES = ("Master: {master}\nSuperseded by {by}, the epic this run planned"
                   " from this bead's own investigation. Work it there.")
CLOSE_NOTES = ("Investigation: {investigation}\nRuled a duplicate by this run's"
               " Wave 2 investigation. The reasoning is in that file.")


# --- the injected command runner --------------------------------------------


def runner_key(argv: list) -> str:
    """A stable key for one `bd` call, which is what test fakes respond to."""
    core = " ".join(argv[:3])
    return core + (" --json" if argv[1:2] == ["show"] and "--json" in argv else "")


def default_runner(argv: list, cwd: str):
    """`bd` walks up from its working directory, so every call names the repo
    root that owns the bead — never the skills repo, never a parent."""
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, cwd=cwd)
    except OSError as exc:
        raise Usage(f"cannot run {argv[0]}: {exc}") from exc
    return proc.returncode, proc.stdout


# --- rendering one intent ----------------------------------------------------


def notes_for(intent: dict, ids: dict | None = None) -> str:
    """The `--notes` text one intent writes.

    `ids` is the created-ref map, and only `supersede` reads it: its `by` is a
    ref until the epic exists, and a note telling a human their bead was
    "superseded by epic" names nothing they can open. Every other kind's notes
    are paths, which are already real by the time they are rendered — so the
    argument stays optional and `_notes_path` needs none of it.
    """
    kind = intent["kind"]
    if kind == "create-epic":
        return EPIC_NOTES.format(master=intent.get("master") or intent.get("plan"))
    if kind == "create-task":
        if intent.get("slice"):
            return TASK_NOTES.format(**{"slice": intent["slice"],
                                        "master": intent.get("master")})
        return SINGLE_NOTES.format(plan=intent.get("plan"))
    if kind == "investigation":
        return INVEST_NOTES.format(investigation=intent.get("investigation"))
    if kind == "flip-source":
        return FLIP_NOTES.format(plan=intent.get("plan"))
    if kind == "supersede":
        by = intent.get("by")
        return SUPERSEDE_NOTES.format(master=intent.get("master"),
                                      by=(ids or {}).get(by, by))
    if kind == "close":
        return CLOSE_NOTES.format(investigation=intent.get("investigation"))
    return ""


def _notes_path(intent: dict) -> str | None:
    """The path an intent's notes record — the value `open` later verifies.

    Recomputed on resume from the intent that produced it, because the ledger
    records the created bead id and not the path it carried.
    """
    rendered = notes_for(intent)
    if not rendered:
        return None
    return rendered.splitlines()[0].split(": ", 1)[1]


def _create(intent: dict, ids: dict) -> list:
    argv = ["bd", "create", intent["title"], "-t", intent.get("type", "task"),
            "-p", str(intent.get("priority", 2))]
    if intent.get("parent"):
        argv += ["--parent", ids[intent["parent"]]]
    if intent.get("description"):
        argv += ["--description", intent["description"]]
    if intent.get("labels"):
        argv += ["--labels", ",".join(intent["labels"])]
    return argv + ["--notes", notes_for(intent), "--json"]


def render(intent: dict, ids: dict, notes: dict) -> Call:
    """One intent as the `bd` argv it becomes, plus the path its write records.

    A relative path *raises* here rather than being reported, which is the
    deliberate asymmetry with `intent_records.validate`: a validation pass
    lists everything wrong with a whole store, while a builder one step from a
    real `bd` write has nothing useful to return and must refuse. `Usage` is
    this module's exit-2 signal (see `default_runner`).

    `dep` carries no path, and `open` carries its path through the `notes` map
    keyed by ref rather than in the record — it was already checked when the
    `create-*` that produced that ref was rendered. So the guard finds nothing
    for either, which is correct and not an oversight.
    """
    bad = relative_paths(intent)
    if bad:
        field, value = bad[0]
        raise Usage(f"{intent.get('key')}: {field} --notes path is not"
                    f" absolute: {value}")
    kind = intent["kind"]
    if kind in ("create-epic", "create-task"):
        return Call(_create(intent, ids), ids.get(intent.get("ref")),
                    _notes_path(intent))
    if kind == "dep":
        # A ref absent from the created-ids map is already a real bead id —
        # that is the whole distinction. A dep `collide.py` derived joins two
        # beads that existed before this run; a dep between two tasks this run
        # creates names their refs. Both resolve here.
        dependent = ids.get(intent["from"], intent["from"])
        return Call(["bd", "dep", "add", dependent,
                     ids.get(intent["to"], intent["to"]),
                     "-t", intent.get("dep_type", "blocks")],
                    dependent, None)
    if kind == "open":
        bead = ids[intent["ref"]]
        return Call(["bd", "update", bead, "--status", "open"], bead,
                    notes.get(intent["ref"]))
    if kind == "investigation":
        return Call(["bd", "update", intent["bead"], "--status", "needs-plan",
                     "--notes", "{notes}"], intent["bead"],
                    intent["investigation"])
    if kind == "flip-source":
        return Call(["bd", "update", intent["bead"], "--status", "open",
                     "--notes", "{notes}"], intent["bead"], intent["plan"])
    if kind == "supersede":
        # The `update` / `--status` shape is required, not stylistic:
        # `staged_run_checks.SOURCE_KINDS` is derived from this argv and
        # `applied_states` recovers the status by indexing `--status` out of
        # it. A kind that retired a bead any other way would be invisible to a
        # resumed promote, which then reads its own write as somebody else's
        # edit and quarantines the bead. `close` carries the same shape for the
        # same reason, in its own branch: the two retire a bead over different
        # evidence, and one argv they happen to share is not a contract.
        return Call(["bd", "update", intent["bead"], "--status", "closed",
                     "--notes", "{notes}"], intent["bead"], intent["master"])
    if kind == "close":
        return Call(["bd", "update", intent["bead"], "--status", "closed",
                     "--notes", "{notes}"], intent["bead"],
                    intent["investigation"])
    if kind == "retitle":
        # No `{notes}`, so `_preserved_notes` never runs for a title change and
        # it cannot race the `investigation` or `flip-source` write on the same
        # bead.
        return Call(["bd", "update", intent["bead"], "--title", intent["title"]],
                    intent["bead"], intent["title"], field="title")
    raise Usage(f"unknown intent kind: {kind}")


def _preserved_notes(intent: dict, repo_root: str, runner, ids: dict) -> str:
    """The intent's marker block, keeping whatever notes the bead already had.

    `bd update --notes` replaces, so anything not carried forward here is
    destroyed — and a human's context on a bead is not recoverable.

    Every marker line this system authors is dropped and rewritten, which is
    the wider `OWNED_MARKERS` set and not the plan-path one: a re-park has to
    replace the `Investigation:` line its last park wrote instead of stacking a
    second one under it.
    """
    code, out = runner(["bd", "show", intent["bead"], "--json"], repo_root)
    records = json.loads(out or "[]") if code == 0 else []
    existing = (records[0].get("notes") or "") if records else ""
    kept = [line for line in existing.splitlines()
            if not line.startswith(OWNED_MARKERS)]
    return "\n".join([notes_for(intent, ids)] + kept).strip()


def _needs(intent: dict, refs=()) -> list:
    """The refs an intent consumes — never the ref it produces.

    `refs` is the set of refs this run's `create-*` intents produce, and only a
    `dep` endpoint may sit outside it: `collide.py` derives deps between beads
    that existed before the run, and blocking on those would stop a dependency
    that is already satisfiable.

    Every other kind's need is always one of this run's own refs. Filtering
    those against `refs` too would drop the check instead of the block, and an
    unresolvable `create-task` parent would reach `_create`'s `ids[...]`
    subscript as a `KeyError` — escaping `apply_intents`, skipping the promote
    log, and re-issuing every `bd create` that already succeeded on the rerun.
    """
    needs = [intent[key] for key in NEEDS.get(intent["kind"], ())
             if intent.get(key)]
    if intent["kind"] != "dep":
        return needs
    return [need for need in needs if need in refs]


# --- applying the ordered set -----------------------------------------------


def apply_intents(intents, repo_root, dry_run=False, runner=None, completed=None):
    """Apply tracker intents serially. `runner(argv, cwd) -> (returncode, stdout)`.

    Order is the dependency order and each edge earns itself: the epic exists
    before anything names it, both endpoints exist before `bd dep add`, and
    the source flip is last because a source bead is only workable once
    everything its plan references exists.

    Under `dry_run` no runner call is made at all — created IDs are unknown,
    so the commands carry symbolic references. A failure rolls forward: what
    landed stays landed, what did not is reported by key, and no compensating
    command is ever emitted.
    """
    runner = runner or default_runner
    done = dict(completed or {})
    ids, notes, commands, findings, applied = {}, {}, [], [], {}
    refs = {i["ref"] for i in intents if i.get("ref")}
    for intent in sorted(intents, key=lambda i: KIND_ORDER.get(i["kind"], 9)):
        key, ref = intent["key"], intent.get("ref")
        if key in done:
            applied[key] = done[key]
            if ref:
                ids[ref] = done[key]
                # A kind that records no path of its own (`open`) must not
                # erase the one the `create-*` that produced this ref recorded.
                notes[ref] = _notes_path(intent) or notes.get(ref)
            continue
        if ref and dry_run:
            ids.setdefault(ref, f"${{{ref}}}")
        missing = [need for need in _needs(intent, refs) if need not in ids]
        if missing:
            findings.append(Finding("error", "promote-intent-incomplete", key,
                                    f"needs {', '.join(missing)}"))
            continue
        # A relative path is reported the way an unresolvable `need` is, four
        # lines above, rather than raised through the loop: an exception here
        # skips the promote log, and so re-issues every `bd create` that already
        # succeeded on the next rerun. `render` still raises for a direct
        # caller, which is where the refusal belongs, and its other `Usage` —
        # an unknown kind — still propagates: that is a store the schema should
        # have rejected, and `promote` answers it with exit 2.
        try:
            call = render(intent, ids, notes)
        except Usage as err:
            if not relative_paths(intent):
                raise
            findings.append(Finding("error", "promote-intent-incomplete", key,
                                    str(err)))
            continue
        # A `{notes}` placeholder is what marks a kind that updates an existing
        # bead, and `bd update --notes` replaces the whole field — so the text
        # has to be that bead's own notes with this intent's marker block folded
        # in. Under `dry_run` nothing is read back, so the block stands alone.
        text = notes_for(intent, ids)
        if "{notes}" in call.argv and not dry_run:
            text = _preserved_notes(intent, repo_root, runner, ids)
        argv = [a.replace("{notes}", text) for a in call.argv]
        commands.append(argv)
        if ref:
            notes[ref] = call.path
        if not dry_run:
            findings += _run_one(argv, call, key, ref, repo_root, runner, ids, applied)
    return Apply(commands, findings, ids, applied)


def _run_one(argv, call, key, ref, repo_root, runner, ids, applied) -> list:
    code, out = runner(argv, repo_root)
    if code != 0:
        return [Finding("error", "promote-intent-incomplete", key,
                        f"bd {argv[1]} failed; a rerun promotes what is missing")]
    bead = call.bead
    if argv[1] == "create":
        payload = json.loads(out or "{}")
        record = payload[0] if isinstance(payload, list) and payload else payload
        bead = record.get("id") if isinstance(record, dict) else None
        if not bead:
            return [Finding("error", "promote-intent-incomplete", key,
                            "bd create returned no id")]
        if ref:
            ids[ref] = bead
    applied[key] = bead
    # `dep` legitimately writes no note. For every other kind a missing path
    # means a bug upstream, and a guard that degrades to "no check" on missing
    # data is worse than a hard failure.
    if argv[1] != "dep" and not call.path:
        return [Finding("error", "promote-notes-unverified", key,
                        f"no {call.field} to verify for {bead}")]
    return _verify(bead, call.path, key, repo_root, runner, call.field)


def _verify(bead: str, path, key: str, repo_root: str, runner, field: str) -> list:
    """Every write is read back — the check `plan` Step 8c names.

    `--json`, never the human format. `bd show` renders notes into a padded
    column and breaks mid-token, so an absolute path comes back split across
    lines and no substring match can find it. Reading the rendered form made
    this check fail for every real path it was given, which meant promote
    never verified a note and never moved a run under `promoted/`. The unit
    fake did not wrap, so nothing caught it until the e2e testbed ran the real
    CLI. `inventory.collect` already read notes the right way.
    """
    code, out = runner(["bd", "show", bead, "--json"], repo_root)
    if code != 0:
        return [Finding("error", "promote-notes-unverified", key,
                        f"bd show {bead} --json failed")]
    try:
        payload = json.loads(out or "null")
    except ValueError:
        return [Finding("error", "promote-notes-unverified", key,
                        f"bd show {bead} --json returned non-JSON")]
    records = payload if isinstance(payload, list) else [payload]
    written = "".join((r or {}).get(field) or "" for r in records
                      if isinstance(r, dict))
    if path and path not in written:
        return [Finding("error", "promote-notes-unverified", key,
                        f"{bead} does not carry {path}")]
    return []
