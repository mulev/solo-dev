#!/usr/bin/env python3
"""Unit cases for what the content walk records — `content_map` and its hash.

Split out of `test_suite_invariant.py` and `test_suite_invariant_facts.py`
when both crossed the 300-line gate, and the subject is a real seam rather
than a metric one. `content_map` answers "what is in this tree",
`sample_content` folds that map into one fingerprint, and the two must never
disagree about which files are guarded. The failures below are the ones that
cost four review rounds: a file the walk cannot read, a directory it cannot
enter, a root that is unreadable rather than absent, and a FIFO — each of
which used to end as a traceback out of the sweep, as silence, or as a hang.

Sixteen cases moved with the split. Fourteen are verbatim; two had their
marker assertion relaxed from `== UNREADABLE` to a shape check, because the
marker gained `st_size` and `st_mtime_ns` in the same round. They assert the
full three-field form where `stat` is known to succeed, so neither accepts
the bare fallback the round before them was written to remove.

`_tree` and `_git_tree` are imported rather than redeclared; they live with the
roster cases that also use them.

Run with `python3 test_content_map.py` (no pytest dependency).
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import suite_invariant as inv  # noqa: E402
from test_suite_invariant import _git_tree, _tree  # noqa: E402


# --- content fingerprints -----------------------------------------------------


def case_identical_content_fingerprints_match() -> None:
    root = _tree({"a.txt": "one\n", "sub/b.txt": "two\n"})
    assert inv.sample_content(root).fingerprint == inv.sample_content(
        root).fingerprint


def case_a_new_file_changes_the_content_fingerprint() -> None:
    root = _tree({"a.txt": "one\n"})
    before = inv.sample_content(root).fingerprint
    (root / "b.txt").write_text("two\n", encoding="utf-8")
    assert inv.sample_content(root).fingerprint != before


def case_edited_content_changes_the_fingerprint() -> None:
    root = _tree({"a.txt": "one\n"})
    before = inv.sample_content(root).fingerprint
    (root / "a.txt").write_text("one changed\n", encoding="utf-8")
    assert inv.sample_content(root).fingerprint != before


def case_a_deleted_file_changes_the_fingerprint() -> None:
    root = _tree({"a.txt": "one\n", "b.txt": "two\n"})
    before = inv.sample_content(root).fingerprint
    (root / "b.txt").unlink()
    assert inv.sample_content(root).fingerprint != before


def case_git_internals_do_not_move_the_content_fingerprint() -> None:
    """`project_plans` is itself a git repo, and no triage run can write a git
    internal. 5045 of its 6136 files are under `.git/` — 82% of the guarded
    surface, moving for a neighbour's commit."""
    root = _git_tree()
    before = inv.sample_content(root).fingerprint
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-q", "--allow-empty", "-m", "noise"],
                   cwd=root, check=True, capture_output=True)
    assert inv.sample_content(root).fingerprint == before


def case_a_working_file_beside_git_still_moves_the_fingerprint() -> None:
    """The paired case. Excluding `.git/` must not excuse a plan file."""
    root = _git_tree()
    before = inv.sample_content(root).fingerprint
    (root / "planted.md").write_text("a run wrote here\n", encoding="utf-8")
    assert inv.sample_content(root).fingerprint != before


def case_a_dolt_lock_under_a_content_tree_moves_the_fingerprint() -> None:
    """`skills-kld.4`. The lock exclusion was measured on `git status
    --porcelain` in demo, where the file is git-tracked and a settling Dolt
    server moved the hash with no bead write. Content hashing of it was never
    the measured problem, and `project_plans` and `~/.claude/plans` are guarded
    by content: a lock appearing under either is a real write."""
    root = _tree({"todo/plan.md": "one\n"})
    before = inv.sample_content(root).fingerprint
    (root / ".beads").mkdir()
    (root / ".beads" / "dolt.gate.lock").write_text("1\n", encoding="utf-8")
    assert inv.sample_content(root).fingerprint != before


def case_bytecode_under_a_content_tree_is_still_excused() -> None:
    """The paired case for the two exclusions the content half keeps."""
    root = _tree({"todo/plan.md": "one\n"})
    before = inv.sample_content(root).fingerprint
    (root / "__pycache__").mkdir()
    (root / "__pycache__" / "x.cpython-311.pyc").write_bytes(b"\x00")
    (root / "lib").mkdir()
    (root / "lib" / "y.pyc").write_bytes(b"\x00")
    assert inv.sample_content(root).fingerprint == before


def case_a_file_the_walk_cannot_read_is_marked_not_dropped() -> None:
    """The other half of `skills-kld.5`'s rule, which never moved.

    `content_map` enumerates with `rglob` and then reads each path, so a file
    deleted between the two used to raise `FileNotFoundError` out of the
    sampler. Both content-guarded trees are live directories — `~/.claude
    /plans` and `project_plans` — and an atomic save creates and deletes files
    inside the walk. The post-run sample runs after the testbed teardown, so
    the traceback replaced the whole sweep verdict; the sweep must never
    raise. The file is recorded rather than dropped, so the guard still sees
    it, and the tree's other files keep their own hashes.
    """
    root = _tree({"a.md": "one", "b.md": "two"})
    clean = inv.sample_content(root)
    real = Path.read_bytes

    def vanish(self):
        if self.name == "b.md":
            raise FileNotFoundError(2, "No such file or directory", str(self))
        return real(self)

    with mock.patch.object(Path, "read_bytes", vanish):
        taken = inv.sample_content(root)
    assert taken.detail["b.md"].startswith(f"{inv.UNREADABLE}:"), taken.detail
    assert taken.detail["a.md"] == clean.detail["a.md"], taken.detail
    assert taken.fingerprint not in (inv.ABSENT, clean.fingerprint), taken


def case_a_write_beside_an_unreadable_file_is_still_reported() -> None:
    """The review's own repro, and the reason the marker is per path.

    Answering `ABSENT` for the whole tree looked safe — the driver has an
    unreadable branch — but a permission error persists, so both samples came
    back `ABSENT`, the comparison read them as equal, and a real write beside
    the unreadable file went unreported while the run printed PASS. Measured
    before the fix with exactly this tree.
    """
    root = _tree({"plan.md": "one", "locked.md": "two"})
    locked = root / "locked.md"
    locked.chmod(0o000)
    try:
        before = inv.sample_content(root)
        (root / "LEAK.md").write_text("planted", encoding="utf-8")
        after = inv.sample_content(root)
    finally:
        locked.chmod(0o644)
    assert before.detail["locked.md"].startswith(inv.UNREADABLE), before.detail
    assert before.fingerprint != inv.ABSENT, before.fingerprint
    assert after.fingerprint != before.fingerprint, "the planted write was invisible"
    assert inv.delta_lines("plans", before.detail, after.detail) == [
        "plans: 1 file(s) moved — ['LEAK.md']"]
    assert before.detail["locked.md"].count(":") == 2, "the marker lost stat's answer"


def case_a_fifo_is_recorded_but_never_read() -> None:
    """Two answers, both wrong before this. `read_bytes` on a FIFO blocks
    until a writer appears and nothing in the sampler has a timeout, so a pipe
    in a guarded tree wedged the sweep with no verdict at all — measured,
    killed at twelve seconds. Skipping it instead dropped the key, so a pipe,
    a socket or a symlink to a directory planted in a guarded tree moved no
    fingerprint. `stat` blocks on none of them, so the entry is recorded and
    never opened. Driven in a subprocess so a regression fails this case
    instead of hanging the suite."""
    probe = f"""
import os, sys, tempfile, pathlib
sys.path.insert(0, {str(Path(__file__).resolve().parent)!r})
import suite_invariant as inv
root = pathlib.Path(tempfile.mkdtemp())
(root / "plan.md").write_text("one")
os.mkfifo(root / "pipe")
(root / "link_to_dir").symlink_to(tempfile.mkdtemp(), target_is_directory=True)
mapping = inv.content_map(root)
print(sorted(mapping), mapping["pipe"].startswith(inv.UNREADABLE),
      mapping["link_to_dir"].startswith(inv.UNREADABLE))
"""
    done = subprocess.run([sys.executable, "-c", probe], capture_output=True,
                          text=True, timeout=20)
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == (
        "['link_to_dir', 'pipe', 'plan.md'] True True"), done.stdout


def case_an_unreadable_noise_directory_is_still_excused() -> None:
    """`blocked` writes into the same map the file loop does, so it needs the
    same filter. Without it an unreadable `.git/objects` or `__pycache__` is
    recorded with an mtime that git and bytecode churn move — the churn the
    exclusion was measured to suppress, on a tree that is 82% git internals.
    Judged with a trailing slash, because the pattern's anchor expects a
    directory path and a cache at a tree root otherwise reads as a name."""
    root = _tree({"plan.md": "one", ".git/objects/ff/abc": "obj",
                  "__pycache__/x.cpython-311.pyc": "byte",
                  "secret/inner.md": "two"})
    blocked = [root / ".git" / "objects", root / "__pycache__", root / "secret"]
    for path in blocked:
        path.chmod(0o000)
    try:
        mapping = inv.content_map(root)
    finally:
        for path in blocked:
            path.chmod(0o755)
    assert sorted(mapping) == ["plan.md", "secret"], sorted(mapping)


def case_a_missing_tree_fingerprints_as_absent_not_as_empty() -> None:
    """`absent` and `an empty directory` must not hash alike.

    Otherwise deleting a guarded tree entirely reads as "unchanged" against a
    run that started with nothing there.
    """
    root = _tree({})
    gone = root / "nope"
    assert inv.sample_content(gone).fingerprint == inv.ABSENT
    assert inv.sample_content(root).fingerprint != inv.ABSENT
# --- content_map --------------------------------------------------------------


def case_content_map_names_a_planted_file_by_relative_path() -> None:
    root = _tree({"a.md": "one", "runs/r1/b.md": "two"})
    assert set(inv.content_map(root)) == {"a.md", "runs/r1/b.md"}


def case_content_map_is_stable_across_calls() -> None:
    root = _tree({"a.md": "one"})
    assert inv.content_map(root) == inv.content_map(root)


def case_content_map_notices_an_edit_not_just_a_new_file() -> None:
    """Content hashes, not a file list: a worker that rewrites an existing
    plan in place adds no path at all."""
    root = _tree({"a.md": "one"})
    before = inv.content_map(root)
    (root / "a.md").write_text("one changed", encoding="utf-8")
    assert inv.content_map(root) != before


def case_content_map_omits_git_internals() -> None:
    """The map has to filter on the same predicate the hash does, or a fired
    guard would name 5045 git internals `sample_content`'s hash never counts."""
    root = _tree({"a.txt": "one", ".git/objects/ab/cdef": "x"})
    mapping = inv.content_map(root)
    assert "a.txt" in mapping, mapping
    assert not [name for name in mapping if ".git" in name], mapping


def case_the_content_hash_is_built_from_the_map() -> None:
    """The property that makes the map safe to use *instead of* the hash at run
    scope: an empty delta and a moved fingerprint cannot both be true."""
    root = _git_tree({"a.txt": "one\n"})
    before_hash = inv.sample_content(root).fingerprint
    before_map = inv.content_map(root)
    (root / "planted.md").write_text("a run wrote here\n", encoding="utf-8")
    assert inv.sample_content(root).fingerprint != before_hash
    assert set(inv.content_map(root)) - set(before_map) == {"planted.md"}


# --- the failures the walk has to survive ------------------------------------


def case_a_non_executable_directory_does_not_raise_out_of_the_sweep() -> None:
    """`rglob` enumerated children it could not stat, and `is_file()` raises
    `PermissionError` for a path inside a directory at mode 0o444 — read
    permission lists the entries, execute permission is what stats them. That
    exception left `sample_content` for `run_e2e.main`, where the post-run
    sample sits after the teardown, so the traceback replaced the whole
    verdict. `os.walk` classifies without stat'ing, and the read is guarded."""
    root = _tree({"plan.md": "one", "noexec/inner.md": "two"})
    (root / "noexec").chmod(0o444)
    try:
        taken = inv.sample_content(root)
    finally:
        (root / "noexec").chmod(0o755)
    assert taken.fingerprint != inv.ABSENT, taken.fingerprint
    assert taken.detail["noexec/inner.md"].startswith(inv.UNREADABLE), taken.detail
    assert taken.detail["plan.md"] != inv.UNREADABLE, taken.detail


def case_a_directory_the_walk_cannot_enter_is_recorded_not_dropped() -> None:
    """`rglob` yielded nothing for such a subtree, so a file planted inside it
    was invisible and the run still printed PASS. `os.walk`'s `onerror` is the
    only way to hear about it, and the directory's own mtime is what makes the
    planted write move the hash."""
    root = _tree({"plan.md": "one", "secret/inner.md": "two"})
    secret = root / "secret"
    secret.chmod(0o300)  # writable and enterable, not listable
    try:
        before = inv.sample_content(root)
        (secret / "LEAK.md").write_text("planted", encoding="utf-8")
        after = inv.sample_content(root)
    finally:
        secret.chmod(0o755)
    assert before.detail["secret"].startswith(f"{inv.UNREADABLE}:"), before.detail
    assert after.fingerprint != before.fingerprint, "the planted write was invisible"


def case_an_unreadable_root_does_not_hash_as_an_empty_tree() -> None:
    """It passed `exists()`, walked to nothing, and hashed as an empty
    directory — so a tree nothing could guard was indistinguishable from a
    tree with nothing in it, and never reached the driver's unreadable
    branch."""
    root = _tree({"plan.md": "one"})
    root.chmod(0o000)
    try:
        blind = inv.sample_content(root)
    finally:
        root.chmod(0o755)
    empty = inv.sample_content(Path(tempfile.mkdtemp(prefix="inv-empty-")))
    assert blind.fingerprint != empty.fingerprint, blind.fingerprint
    assert blind.detail["."].startswith(f"{inv.UNREADABLE}:"), blind.detail


def case_an_edit_of_a_file_unreadable_in_both_samples_moves_the_hash() -> None:
    """A fixed marker contributes the same bytes to both samples, so an
    in-place edit of a file neither sample could read would not move the hash.
    `st_size` and `st_mtime_ns` are what close that, and neither is hex, so no
    marker can be mistaken for a digest."""
    root = _tree({"locked.md": "two"})
    locked = root / "locked.md"
    locked.chmod(0o000)
    try:
        before = inv.sample_content(root)
        locked.chmod(0o644)
        locked.write_text("two and a half", encoding="utf-8")
        locked.chmod(0o000)
        after = inv.sample_content(root)
    finally:
        locked.chmod(0o644)
    assert before.detail["locked.md"].startswith(f"{inv.UNREADABLE}:"), before.detail
    assert after.fingerprint != before.fingerprint, "an edit went unrecorded"


CASES = [v for k, v in sorted(globals().items()) if k.startswith("case_")]


def main() -> int:
    failed = 0
    for case in CASES:
        try:
            case()
            print(f"PASS  {case.__name__}")
        except AssertionError as err:
            failed += 1
            print(f"FAIL  {case.__name__}: {err}")
        except Exception as err:  # a stub, or a case reaching unwritten code
            failed += 1
            print(f"ERROR {case.__name__}: {type(err).__name__}: {err}")
    print(f"\n{len(CASES) - failed}/{len(CASES)} cases passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
