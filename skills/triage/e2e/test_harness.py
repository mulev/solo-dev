#!/usr/bin/env python3
"""Unit cases for the harness's lock, reuse and database-guard contract.

`reuse` is the path that continues an interrupted run, and the lock is what
keeps two drivers off one testbed. `build`'s success path cannot be tested
here: it shells out to the generator and creates three real `bd` databases,
which is the `e2e` stage's job. Its failure path can, and is — a build that
dies must not leave the lock behind. `reuse` can be tested whole, because it
does the opposite of building — it refuses to create anything and only adopts
trees that are already there. That refusal is the whole safety property, so it
is the part worth testing without a testbed.

Marked directories are enough: `reuse` looks for the `.triage-testbed` marker
and never runs `bd` or git, which is itself one of the assertions below.

Run with `python3 test_harness.py` (no pytest dependency).
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import traceback
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import harness  # noqa: E402
from test_suite_invariant_facts import _fake_bd  # noqa: E402


def marked(root: Path) -> Path:
    """The three generated trees, each carrying the marker and nothing else."""
    for name in (harness.PROJECT, harness.CLEAN_PROJECT, harness.CORPUS):
        tree = root / name
        tree.mkdir(parents=True)
        (tree / harness.MARKER).write_text("", encoding="utf-8")
    return root


def lock_of(root: Path) -> Path:
    return root / ".triage-testbed.lock"


def case_assert_db_inside_asks_bd_which_database_it_opened(tmp: Path) -> None:
    """A tree carrying an empty `.beads/` and no database must be refused.

    The guard this replaced answered from a Python replica of bd's upward walk,
    so it accepted any tree with a `.beads` directory in it — including a
    testbed whose database was a clone of the real skills tracker, which is the
    defect that produced this case. Only `bd` can say which database `bd`
    opened, so the guard has to ask it.
    """
    root = tmp.resolve()
    for name in (harness.PROJECT, harness.CLEAN_PROJECT):
        (root / name / ".beads").mkdir(parents=True)
    try:
        harness.assert_db_inside(harness._assemble(root))
    except AssertionError as err:
        assert "outside the testbed" in str(err) or "no database" in str(err), err
        return
    raise AssertionError(
        "the guard accepted a tree with no database in it — a path check "
        "cannot see which database bd opens")


def _rostered(rows: list, tmp: Path, code: int = 0):
    """`assert_fixture_roster` over marked trees, with `bd` answering `rows`."""
    bed = harness._assemble(marked(Path(tmp).resolve()))
    path = f"{_fake_bd(json.dumps(rows), code)}{os.pathsep}{os.environ['PATH']}"
    with mock.patch.dict(os.environ, {"PATH": path}):
        harness.assert_fixture_roster(bed)


def case_a_database_holding_a_bead_the_fixture_never_declared_is_refused(
        tmp: Path) -> None:
    """`skills-d96`'s second half. `bd init` copies an enclosing workspace's
    `.beads/config.yaml` and clones the remote it names, so a generated
    database came up holding real skills beads at the testbed's own path —
    where every path check passes it. This is the only question that can see
    that, and it has to be asked at run start, because `--reuse` adopts trees
    an older generator built."""
    try:
        _rostered([{"id": "skills-rjb"}, {"id": "tb-inv1"}], tmp)
    except AssertionError as err:
        assert "skills-rjb" in str(err), err
        assert "tb-inv1" not in str(err), f"a declared bead was reported: {err}"
        return
    raise AssertionError("a database holding a real skills bead was adopted")


def case_a_roster_with_nothing_foreign_in_it_is_adopted(tmp: Path) -> None:
    """Extra ids only, so a guard that raised here would fail every run.

    Empty rather than a declared id, because one fake `bd` answers both trees
    and the two fixtures share no bead: `beads.json` declares the twenty
    `tb-*` and `beads_clean.json` declares only `tb-clean1`. The subset
    tolerance is proven by the case above, which asserts a declared bead is
    not named among the leaks it reports.
    """
    _rostered([], tmp)


def case_a_database_bd_cannot_read_is_refused_not_passed(tmp: Path) -> None:
    """An unreadable roster is not an empty one. Reading a failure as "no
    foreign beads" is the fail-open shape this whole guard exists to close."""
    try:
        _rostered([], tmp, code=1)
    except AssertionError as err:
        assert "cannot read" in str(err), err
        return
    raise AssertionError("a bd failure was read as an empty roster")


def case_reuse_adopts_marked_trees_without_running_the_generator(tmp: Path) -> None:
    """No subprocess, no bd, no git — the trees are taken as found."""
    # Resolved, because `reuse` resolves: on macOS the temp root is a symlink
    # into /private, and comparing against the unresolved path would fail on
    # the platform rather than on the behaviour.
    root = marked(tmp).resolve()
    testbed = harness.reuse(root)
    try:
        assert testbed.root == root, testbed.root
        assert testbed.path == root / harness.PROJECT, testbed.path
        assert testbed.corpus == root / harness.CORPUS, testbed.corpus
        assert testbed.scratch.is_dir(), testbed.scratch
        assert testbed.bead_ids, "the fixture matrix was not read"
    finally:
        harness.release(root)


def case_reuse_refuses_a_directory_it_did_not_generate(tmp: Path) -> None:
    """The marker check, and the reason `--reuse` cannot adopt a stray tree.

    Same rule `teardown` and `make_testbed.sh` apply before they delete
    anything: a directory without the marker is somebody else's.
    """
    (tmp / harness.PROJECT).mkdir(parents=True)
    try:
        harness.reuse(tmp)
    except harness.Missing as err:
        assert harness.MARKER in str(err), err
    else:
        harness.release(tmp)
        raise AssertionError("reuse adopted a tree carrying no marker")


def case_reuse_refuses_an_empty_root(tmp: Path) -> None:
    try:
        harness.reuse(tmp)
    except harness.Missing:
        pass
    else:
        harness.release(tmp)
        raise AssertionError("reuse adopted a root with no trees at all")


def case_a_refused_reuse_leaves_no_lock_behind(tmp: Path) -> None:
    """The leak class that cost a day: a failure that keeps the lock wedges
    every later run, and the only recovery was deleting the file by hand."""
    try:
        harness.reuse(tmp)
    except harness.Missing:
        pass
    assert not lock_of(tmp).exists(), f"{lock_of(tmp)} survived a refused reuse"


def case_reuse_refuses_while_another_run_holds_the_lock(tmp: Path) -> None:
    """Reuse takes the same lock a build does: two drivers on one testbed
    corrupt it, and adopting trees somebody else is mid-way through is worse
    than rebuilding them."""
    root = marked(tmp)
    lock_of(root).write_text(str(harness.os.getpid()), encoding="utf-8")
    try:
        harness.reuse(root)
    except harness.Busy as err:
        assert str(harness.os.getpid()) in str(err), err
    else:
        raise AssertionError("reuse ran while the lock was held")
    finally:
        lock_of(root).unlink(missing_ok=True)


def case_a_second_build_is_refused_while_one_holds_the_lock(tmp: Path) -> None:
    """Two drivers rebuilding the same testbed corrupt it.

    The generator wipes while the other process has the Dolt database open,
    and the second run dies with a missing-manifest fatal error that reads like
    a fixture bug rather than a collision. Measured, not theorised.
    """
    harness._lock(tmp)
    try:
        harness._lock(tmp)
    except harness.Busy as err:
        assert "another e2e run holds" in str(err), err
    else:
        raise AssertionError("a second build was allowed to start")
    harness.release(tmp)
    harness._lock(tmp)          # released, so it may be taken again
    harness.release(tmp)


def case_release_is_safe_when_no_lock_is_held(tmp: Path) -> None:
    harness.release(tmp)


def case_a_failed_build_releases_the_lock(tmp: Path) -> None:
    """A lock nobody holds turns a transient failure into a permanent one.

    `build()` takes the lock and then runs the generator. When the generator
    died the lock stayed on disk with a dead pid, and every later run refused
    to start until somebody deleted the file by hand. Measured twice in one
    session before this was fixed.
    """
    original = harness.MAKE_TESTBED
    harness.MAKE_TESTBED = tmp / "no-such-generator.sh"
    try:
        harness.build(tmp)
    except RuntimeError:
        pass
    else:
        raise AssertionError("a missing generator should have raised")
    finally:
        harness.MAKE_TESTBED = original
    assert not lock_of(tmp).exists(), "the lock survived a failed build"
    harness._lock(tmp)          # provably retakeable
    harness.release(tmp)


def case_a_lock_whose_owner_is_gone_is_reclaimed(tmp: Path) -> None:
    """No `rm -f` should ever be the recovery.

    A lock left by a killed process used to refuse every later run until a
    human deleted the file, and reaching for that delete is what stopped the
    leak being read as a bug.
    """
    lock_of(tmp).write_text("999999", encoding="utf-8")
    harness._lock(tmp)          # reclaimed, no exception
    assert lock_of(tmp).read_text().strip() == str(harness.os.getpid())
    harness.release(tmp)


def case_a_lock_held_by_a_live_process_is_still_refused(tmp: Path) -> None:
    """Reclaiming must not become "always take it": this pid is running.

    `case_reuse_refuses_while_another_run_holds_the_lock` asserts the same
    intent through `reuse`; this one goes at `_lock` directly, which is the
    entry point `build` uses.
    """
    lock_of(tmp).write_text(str(harness.os.getpid()), encoding="utf-8")
    try:
        harness._lock(tmp)
    except harness.Busy:
        return
    raise AssertionError("a live owner's lock was stolen")


def case_an_unreadable_pid_is_treated_as_alive(tmp: Path) -> None:
    """Refusing is recoverable; stealing a held lock is not."""
    lock_of(tmp).write_text("not-a-pid", encoding="utf-8")
    try:
        harness._lock(tmp)
    except harness.Busy:
        return
    raise AssertionError("a lock with an unparseable owner was stolen")


CASES = [v for k, v in sorted(globals().items()) if k.startswith("case_")]


def main() -> int:
    failed = 0
    for case in CASES:
        with tempfile.TemporaryDirectory() as raw:
            try:
                case(Path(raw))
                print(f"PASS  {case.__name__}")
            except AssertionError as err:
                failed += 1
                print(f"FAIL  {case.__name__}: {err}")
            except Exception:
                failed += 1
                print(f"ERROR {case.__name__}")
                traceback.print_exc()
    print(f"\n{len(CASES) - failed}/{len(CASES)} cases passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
