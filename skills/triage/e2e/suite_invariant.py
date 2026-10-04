#!/usr/bin/env python3
"""Suite D — fingerprint every tree a triage run must not touch, before and after.

This is the only check in the epic that would catch a testbed run writing into
a real project, and the failure it guards is unrecoverable: a suite that edits
a real tracker leaves no marker saying it was the suite that did it.

**It compares before against after; it never asserts a tree is clean.** A repo
you work in routinely carries uncommitted work, and a sweep demanding
cleanliness would be red on an ordinary working day and then ignored — which is
worse than not having it.

Three trees are always guarded, and the reason each is listed matters more than
the mechanism:

* `testbed`      — the sandbox a run builds. `suite_promote` and
                   `suite_lifecycle` create beads in it by design, so one
                   worker's window is the only one it can be compared across.
* `home-plans`   — `~/.claude/plans`, the system plan mirror. A live worker
                   has write tools and a brief, and the brief is the only
                   thing standing between it and that tree.
* `project-plans`— the real plan tree the staging invariant promises not to
                   touch until an explicit promote.

Any sibling repository you also want guarded goes in `TRIAGE_GUARDED_EXTERNAL`
as a comma separated list of directory names under the workspace root. Those
are the blast radius, and they are `external`: this repo is not pinned to a
machine and cannot name the repos that happen to sit beside it, so the list is
empty unless you set it. An external tree that is absent is skipped and said
out loud, never demanded.

**One list, one window.** Every tree above is sampled inside the per-worker
bracket in `live_dispatch`, immediately before a worker's process and
immediately after it. That window holds exactly one writer, so a delta can be
attributed to the worker that produced it. The window this replaced — a
bracket around the whole run — could not: a filesystem before/after cannot say
*who* wrote, and across minutes of `project_plans` and `~/.claude/plans`,
which the operator writes to continuously, it reported a neighbouring session
in the words it would use for a leak. Same predicates, same comparison, an
answer that names a writer.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
from collections import namedtuple
from pathlib import Path

ABSENT = "absent"

# One file's place in a content map when the walk could read the directory but
# not the file. Distinct from `ABSENT`, which is the whole tree's answer: the
# difference is what keeps a single unreadable file from silencing the guard
# over everything beside it.
UNREADABLE = "unreadable"

# The workspace holding the project repos. This file sits at
# <workspace>/skills/triage/e2e/, so the root is three directories up: correct
# on any machine, with nothing to configure and no home directory written down.
# PROJECTS_ROOT still wins, for pointing the suite somewhere else on purpose.
PROJECTS = Path(os.environ.get("PROJECTS_ROOT")
                or Path(__file__).resolve().parents[3])

# What no run of this suite can write, so a fingerprint that counts it reports
# a neighbour's activity as a leak. `project_plans` is itself a git repo and
# 82% of its files are git internals; a bytecode cache is a product of
# executing source rather than editing it, and the tracked tree is
# byte-identical either side of one.
#
# Nothing is hidden by this: `live_dispatch.dispatch` still fires its tripwire
# on a testbed cache and writes a `noise/` row naming what moved. The real fix
# for that one is a `__pycache__/` line in the generated testbed's
# `.gitignore`, which lives in `make_testbed.sh`.
#
# Two predicates, because the two halves guard different things and the third
# exclusion was only ever measured on one of them. `.beads/dolt.gate.lock` is
# git-tracked in demo, so a settling Dolt server moved
# `sample_tracker(demo).fingerprint` 843728 -> ab490c -> 843728 across 60s
# with nothing guarded having changed — a fact about `git status --porcelain`
# and nothing else. Content-hashing that lock was never the measured problem,
# so excusing it in the content half bought no stability and forfeited leak
# detection: a lock file appearing under `project_plans` or `~/.claude/plans`
# is a real write, and the shared predicate this replaced matched it.
#
# Both halves are searched against a *path* only — the content half against a
# path relative to a tree root, the tracker half against a path
# `porcelain_noise` has taken out of a status line. That is what lets the
# anchor be `(?:^|/)`. The predicate this replaced anchored on `(?:^|[\s/])`
# because the narrow form matched neither `^` nor `/` before a bare
# `?? __pycache__/`, so a cache at a repo root slipped through the exclusion
# it was written for. Do not widen the anchor back: extract the path instead,
# which is also the only way a rename's two paths can be judged separately.
_PATH_NOISE = r"(?:^|/)(?:\.git|__pycache__)/|\.pyc$"

# One shared fragment rather than two spelled-out patterns, so the three
# exclusions the halves agree on cannot drift apart by a typo. The tracker
# half is a strict superset of the content half, which is the whole content of
# `skills-kld.4`.
CONTENT_NOISE_RE = re.compile(_PATH_NOISE)

TRACKER_NOISE_RE = re.compile(
    _PATH_NOISE + r"|(?:^|/)\.beads/dolt\.gate\.lock$")

_RENAME_SEP = " -> "


def porcelain_paths(line: str) -> list:
    """Every path a `git status --porcelain` line names.

    Two status characters, a space, then the path. A rename or a copy names
    two, as `old -> new`, and only those statuses are split on the separator —
    a filename containing ` -> ` is porcelain v1's own ambiguity, and reading
    an ordinary line whole is the safe side of it.

    `core.quotePath` wraps a path holding special characters in double quotes;
    the wrapping comes off and the escapes inside are left alone, because
    every token either predicate looks for is ASCII, so only the surrounding
    quotes can change whether one matches.
    """
    status, body = line[:2], line[3:]
    parts = (body.split(_RENAME_SEP, 1)
             if "R" in status or "C" in status else [body])
    return [p[1:-1] if len(p) > 1 and p[0] == p[-1] == '"' else p
            for p in parts if p]


def porcelain_noise(line: str) -> bool:
    """Whether a whole `git status --porcelain` line is somebody else's noise.

    **A line is noise only when every path it names is noise.** The next
    reader's instinct is to search the line itself, which is what this
    replaced: the shared predicate matched
    `"R  a.py -> lib/__pycache__/b.pyc"`, so a tracked file renamed *into* a
    cache path was excused. A line naming no path at all is kept, not excused.
    """
    paths = porcelain_paths(line)
    return bool(paths) and all(TRACKER_NOISE_RE.search(p) for p in paths)


Sample = namedtuple("Sample", "fingerprint detail")

# `_run`'s result, kept whole rather than glued into one string: the tracker
# fingerprint wants the exit code and stdout, the tracker facts want stdout and
# stderr, and one invocation now has to serve both.
Ran = namedtuple("Ran", "code out err")

Tree = namedtuple("Tree", "name path sample external")


def _hash(parts) -> str:
    digest = hashlib.sha256()
    for part in parts:
        digest.update(part.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def content_map(path) -> dict:
    """Relative path to content hash for every non-noise file under a tree.

    A map rather than `sample_content`'s single hash: that one answers "did
    anything move", and a fired guard needs "what moved". `CONTENT_NOISE_RE`
    is applied to the relative path, and `sample_content` builds its hash from
    this map, so the two cannot disagree about which files are guarded.

    An absent tree maps to `{}` rather than `ABSENT`. A declared tree never
    reaches that case: `missing()` has already failed an absent guarded tree
    before any sample is taken, and a tree deleted mid-bracket reports every
    file gone.

    A path this cannot read is recorded rather than dropped or raised, and the
    marker carries whatever `stat` could still see. Three failures land here,
    and each one used to be silent or fatal:

    * **A file whose bytes cannot be read** — an atomic save the walk raced,
      or a mode this process is not allowed. Dropping it would hide the file;
      raising took the whole tree with it, first as a traceback out of the
      sweep and then, when that was caught one level up, as `ABSENT` for the
      entire tree — which a *persistent* failure turns into "unchanged" on
      both samples and stops guarding in silence.
    * **A directory the walk cannot enter.** `rglob` answered by yielding
      nothing for that subtree, so a file planted inside it was invisible and
      the run still printed PASS. `os.walk`'s `onerror` is the only way to
      hear about it, and the directory's own `mtime` moves when its contents
      change, which is what makes a write *directly* inside it visible again.
    * **The tree's own root** — unreadable rather than absent. It used to hash
      as an empty directory, so a tree nothing could guard was
      indistinguishable from a tree with nothing in it.

    `st_size` and `st_mtime_ns` in the marker are what close the file half: a
    fixed string contributes the same bytes to both samples, so an in-place
    edit of a file unreadable in both would not move the hash. Neither value
    is hex, so no marker can be mistaken for a digest.

    **What this still cannot see, measured rather than assumed.** A
    directory's mtime moves only when its own entries change, so under a
    directory the walk cannot enter, a write one level deeper —
    `secret/sub/LEAK.md` — leaves the fingerprint unchanged. And where `stat`
    itself is denied, under a directory missing its execute bit, the marker
    degrades to the bare string and that subtree is stable whatever happens
    inside it. Neither is fixable from here: the kernel offers no way to list
    an unlistable directory or to stat through a missing execute bit. The
    guarded trees carry no such directory today, and a run that creates one is
    a run that changed a mode, which moves the parent's own entry.

    An entry that is not a regular file is recorded but never opened.
    `read_bytes` on a FIFO blocks until a writer appears and nothing here has
    a timeout, so a pipe in a guarded tree would wedge the sweep with no
    verdict at all — worse than any answer. Skipping it outright was the
    walk's first answer and it was also wrong: the key vanished from the map,
    so a socket, a device node or a symlink planted in a guarded tree changed
    no fingerprint at all. `stat` never blocks on any of them — measured at
    0.1ms on a FIFO — so the marker costs nothing and keeps the entry
    visible. Three answers, not two: read it, stat it, or say `stat` was
    denied.

    A symlink to a *directory* arrives in `os.walk`'s directory list rather
    than its file list, and the walk does not follow it, so it needs its own
    line or it is invisible the same way. The marker uses `lstat`, which
    describes the link itself: identical to `stat` for every ordinary file,
    and the only way a retargeted symlink moves the hash.
    """
    root = Path(path)
    out = {}

    def marker(item: Path) -> str:
        try:
            info = item.lstat()
        except OSError:
            return UNREADABLE
        return f"{UNREADABLE}:{info.st_size}:{info.st_mtime_ns}"

    def record(item: Path, suffix: str = "") -> None:
        """One entry, through the filter both halves share.

        `suffix` is `/` for a directory, because the noise pattern's anchor
        expects one — without it a cache at a tree root reads as an ordinary
        name, which is the slip the anchor comment above warns about.
        """
        name = str(item.relative_to(root))
        if not CONTENT_NOISE_RE.search(f"{name}{suffix}"):
            out[name] = marker(item)

    def blocked(err: OSError) -> None:
        # A directory the walk could not enter, or the root itself. Through
        # the same filter as everything else, or the two halves disagree about
        # what is guarded: an unreadable `.git/objects` or `__pycache__` would
        # be recorded with an mtime that git and bytecode churn move, which is
        # the noise the exclusion was measured to stop.
        record(Path(err.filename), "/")

    for parent, dirs, files in os.walk(root, onerror=blocked):
        for leaf in dirs:
            # Only the links. A real directory is walked into, and its own
            # entry says nothing the files below it do not already say.
            item = Path(parent) / leaf
            if item.is_symlink():
                record(item, "/")
        for leaf in files:
            item = Path(parent) / leaf
            name = str(item.relative_to(root))
            if CONTENT_NOISE_RE.search(name):
                continue
            try:
                if not stat.S_ISREG(item.stat().st_mode):
                    out[name] = marker(item)
                    continue
                out[name] = hashlib.sha256(item.read_bytes()).hexdigest()
            except OSError:
                out[name] = marker(item)
    return out


def sample_content(path) -> Sample:
    """One read of a content tree: its file map, and the hash built from it.

    Read once, answered twice. The hash decides whether anything moved and the
    map names what did, and taking them from one walk is what stops a write
    landing between the two — the whole defect this pairing removes.

    `ABSENT` rather than the hash of nothing, so a tree that was deleted
    outright cannot read as "unchanged" against a run that began with an empty
    directory there. The detail is `None` in that case and not `{}`, because an
    empty map cannot tell a deleted tree from an empty one; `None` is what the
    driver's unreadable branch reads.
    """
    root = Path(path)
    if not root.exists():
        return Sample(ABSENT, None)
    mapping = content_map(root)
    parts = []
    for name in sorted(mapping):
        parts.append(name)
        parts.append(mapping[name])
    return Sample(_hash(parts), mapping)


def _run(cmd: list, cwd: Path) -> Ran:
    """One command's exit code, stdout and stderr.

    Glued back as `f"{code}:{out}"` this is byte-identical to the string this
    used to return, `error` in the exit code's place included. That identity is
    load-bearing: the tracker fingerprint hashes it, so a change of shape here
    moves every guarded fingerprint on this machine for no reason at all.
    """
    try:
        proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    except OSError as err:
        return Ran("error", str(err), "")
    return Ran(proc.returncode, proc.stdout, proc.stderr)


def sample_tracker(path) -> Sample:
    """One read of a tracker tree: two commands, hashed and read as facts.

    `git status --porcelain` and `bd list --json` are the only reads either
    answer needs, so running them once serves both. The hash is the tripwire —
    it moves for anything those commands vary, row order included — and the
    facts adjudicate a fire, keeping sorted porcelain lines and
    `(id, status, updated_at)` per bead. The facts are lossy against the hash
    on purpose: `bd list --json` also carries title, priority and notes.

    The hashed parts are unchanged from the two-pass version, byte for byte,
    including the exit code split off as its own part so that dropping a
    porcelain line as noise cannot drop the exit status with it. That filter
    is `porcelain_noise`, applied once here, and the detail below is taken
    from the same list, so this half's tripwire and its adjudicator cannot
    disagree about what counts as noise. Both halves it absorbed are gone:
    `fingerprint_tracker` was the hash and `tracker_facts` was the detail, and
    a projection with no production caller is dead code rather than a public
    API (`skills-rjb.2`).

    `ABSENT` with no detail for a path that is not a directory, and that
    pairing is what makes the driver's crash impossible rather than merely
    caught. The two-pass version checked existence in one function and shelled
    out with `cwd=root` in the other, so a tree that vanished between them
    raised `FileNotFoundError` — after the `finally` block had torn the testbed
    down, which cost the whole sweep its output. Here the check and the
    commands are one read, and `_run` turns a root that vanished inside it into
    `Ran("error", …)`, so the verdict the tripwire earned always survives to be
    printed. That is `skills-kld.5`'s guarantee: a vanished tree reports
    `FAIL … tree unreadable`, never a traceback and never `NOISE`.
    """
    root = Path(path)
    if not root.is_dir():
        return Sample(ABSENT, None)
    git = _run(["git", "status", "--porcelain"], root)
    listing = _run(["bd", "-C", str(root), "list", "--limit", "0", "--all",
                    "--json"], root)
    worktree = [line for line in git.out.splitlines()
                if not porcelain_noise(line)]
    fingerprint = _hash([f"{listing.code}:{listing.out}", str(git.code),
                         *worktree])
    try:
        beads = sorted((b["id"], b.get("status"), b.get("updated_at"))
                       for b in json.loads(listing.out))
    except (ValueError, TypeError, KeyError):
        beads = [("unreadable", listing.code, listing.err[-80:])]
    return Sample(fingerprint, (tuple(sorted(worktree)), tuple(beads)))


def fact_delta(before: dict, after: dict) -> list:
    """One line per guarded repo whose worktree or tracker actually moved.

    Compared as **sets**, not sequences. `sample_tracker` already sorts both
    halves, so ordering cannot differ in practice — but a sequence comparison
    would report a reordering as a change and then print `appeared [], gone
    []`, which is the unreadable failure this adjudicator was written to
    replace. Entries are unique on both sides (porcelain lines, and beads
    keyed by id), so nothing is lost by ignoring order.
    """
    out = []
    for name in sorted(before):
        for half, was, now in (("worktree", before[name][0], after[name][0]),
                               ("tracker", before[name][1], after[name][1])):
            gained, lost = set(now) - set(was), set(was) - set(now)
            if gained or lost:
                out.append(f"{name} {half}: appeared {sorted(gained)}"
                           f", gone {sorted(lost)}")
    return out


def delta_lines(name: str, was, now) -> list:
    """The lines naming what moved inside one guarded tree.

    Empty when the detail can say nothing about a tree it *did* read, which is
    the caller's cue to print `NOISE` — a fire the detail cannot explain is
    forgiven as a diagnosis and never as a verdict. A detail of `None` is the
    other thing entirely: the sampler could not read the tree at all, so it
    gets a line of its own. `[]` there would print `NOISE` about a tree nobody
    read, and falling through to `fact_delta` subscripts the `None`, which is
    how the bracket used to answer a vanished tree with a `TypeError` after its
    worker had already returned.

    Dispatched on the detail's own shape: two dicts are a content map and get
    a file list, anything else is `sample_tracker`'s pair of tuples and goes
    to `fact_delta` rather than re-deriving a tracker delta here. Shape and
    not the identity check it replaces: a tree used to carry its own detail
    callable, and there is nothing left to compare one against now that a
    tree names one sampler instead of a fingerprint/detail pair — the shape
    is what the formatting actually depends on.
    """
    if was is None or now is None:
        how = {(True, True): "unreadable in both samples",
               (False, True): "vanished", (True, False): "appeared"}
        return [f"{name}: tree unreadable — {how[was is None, now is None]}"]
    if isinstance(was, dict) and isinstance(now, dict):
        moved = sorted(key for key in set(was) | set(now)
                       if was.get(key) != now.get(key))
        return [f"{name}: {len(moved)} file(s) moved — {moved}"] if moved else []
    return fact_delta({name: was}, {name: now})


SKILLS = PROJECTS / "skills"


EXTERNAL_ENV = "TRIAGE_GUARDED_EXTERNAL"


def external_names() -> tuple:
    """The sibling repositories this machine wants guarded, from the
    environment, empty by default.

    These are not part of this repo and this repo is not pinned to a machine,
    so the roster cannot name them. Set `TRIAGE_GUARDED_EXTERNAL` to a comma
    separated list of directory names under the workspace root to have them
    watched; leave it unset and only this repo's own trees are.

    Read on every call rather than frozen at import, for the same reason the
    testbed path is: a value fixed at import is one a caller cannot change,
    and the failure it produces is a guard that silently watches the wrong
    thing.
    """
    raw = os.environ.get(EXTERNAL_ENV, "")
    return tuple(name.strip() for name in raw.split(",") if name.strip())


def guarded_trees(root=None, external=None) -> list:
    """Every guarded tree, with the testbed resolved against `root`.

    The testbed's path is **not** a constant: `run_e2e.py --root DIR` builds it
    under `DIR`, and a hard-coded path then fingerprints a directory the run
    never touched — which either does not exist, so both samples read `ABSENT`
    and the comparison passes while guarding nothing, or is a stale tree from
    an earlier run, so the guard reports someone else's changes. A guard that
    silently stops guarding is worse than no guard, because the green output
    still reads as proof (`skills-yc7`).

    One list, one window. Every tree here is sampled inside the per-worker
    bracket, because that is the only window in which a write can be
    attributed to the run that took it: a bracket around a whole run, over
    directories the operator writes to continuously, reports a neighbouring
    session in the words it would use for a leak.

    The three internal trees are this repo's own and are always present in the
    roster. The external ones come from `external_names()`, or from the
    argument when a caller states them outright.
    """
    testbed = (Path(root) if root else SKILLS) / "triage-testbed"
    names = external_names() if external is None else tuple(external)
    return [
        Tree("testbed", testbed, sample_tracker, external=False),
        Tree("home-plans", Path.home() / ".claude" / "plans", sample_content,
             external=False),
        Tree("project-plans", PROJECTS / "project_plans", sample_content,
             external=False),
    ] + [Tree(name, PROJECTS / name, sample_tracker, external=True)
         for name in names]


def missing(specs) -> list:
    """Guarded trees that are not on disk, and are not excused.

    `_shared/validators.md`: a row that did not run is a failed row. That holds
    for every **internal** tree — the testbed and the two plan trees. An absent
    one means the run's own sandbox or the operator's plan tree is not where it
    should be, and no flag excuses it.

    An absent **external** repo is a different thing and is never reported.
    `skills` travels between machines; the repos beside it do not, and a repo
    that is not on this machine cannot be written into, so there is nothing for
    the guard to fail about. Demanding the checkout made the sweep red by
    default anywhere but the machine it was written on, and a guard that is red
    on an ordinary day is one nobody reads. `--skip-external` keeps its other
    meaning in `watched_trees`: it drops those repos from sampling even when
    they are present. It has no say here, which is why it is not a parameter.

    The testbed is asked about like every other tree, and the driver's order is
    what makes that right: `run_e2e.main` builds or reuses the sandbox and only
    then calls this, so nothing on disk here is a build that did not build —
    never a sandbox torn down at the end of a run.
    """
    return [f"{tree.name}: nothing at {tree.path}"
            for tree in specs
            if not tree.external and not tree.path.exists()]


def watched_trees(skip_external: bool = False, root=None, external=None) -> list:
    """The guarded trees a sample covers.

    One place, because a call site that restated this could watch an excused
    external tree here and skip it there.
    """
    return [tree for tree in guarded_trees(root, external)
            if not (tree.external and skip_external)]


def sample(skip_external: bool = False, root=None, external=None) -> dict:
    """One `Sample` per guarded tree, keyed by name.

    One read per tree: the fingerprint that decides whether anything moved and
    the detail that names what did come from the same bytes, so no other tree's
    work can land between them. Two passes over this set used to be separated
    by roughly a second per tree, and a write in that gap reached exactly one
    of them — the tripwire fired, the detail explained nothing, and a real
    tracker write was reported as `NOISE`.

    There is no wider sample to ask for. Every caller is one dispatch's
    bracket: `live_dispatch.sample_guarded_trees` takes this immediately
    before a worker's process and immediately after it, which is the only
    window holding exactly one known writer.
    """
    return {tree.name: tree.sample(tree.path)
            for tree in watched_trees(skip_external, root, external)}


def fingerprints(samples: dict) -> dict:
    """The hash half of a sample map, for a caller that compares nothing else."""
    return {name: taken.fingerprint for name, taken in samples.items()}


def compare(before: dict, after: dict) -> list:
    """One line per tree whose fingerprint moved. Empty means nothing moved.

    Keep the `{name}: ` prefix: `live_dispatch` splits the tree name off the
    first colon for the ledger row it writes when the detail forgives a fire.
    """
    findings = []
    for name in sorted(set(before) | set(after)):
        was, now = before.get(name, ABSENT), after.get(name, ABSENT)
        if was != now:
            findings.append(f"{name}: fingerprint changed during the run — "
                            f"before {was[:16]}, after {now[:16]}")
    return findings
