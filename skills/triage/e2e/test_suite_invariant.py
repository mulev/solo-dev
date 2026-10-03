#!/usr/bin/env python3
"""Unit cases for the invariant sweep's own machinery.

The sweep is the one check that would catch a testbed run writing into a real
project, so its red path has to be proven rather than assumed: a sweep that has
never reported a mismatch is indistinguishable from one that cannot.

Every case here mutates a scratch copy under `tempfile.mkdtemp()`. Nothing in
this file touches a tree the sweep actually guards — mutating one to test the
guard would be the same mistake the guard exists to prevent.
"""

from __future__ import annotations

import importlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import suite_invariant as inv  # noqa: E402


def _tree(files: dict) -> Path:
    root = Path(tempfile.mkdtemp(prefix="inv-case-"))
    for name, text in files.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return root


def _git_tree(files: dict | None = None) -> Path:
    root = _tree(files or {"a.txt": "one\n"})
    for cmd in (["git", "init", "-q"],
                ["git", "add", "-A"],
                ["git", "-c", "user.email=t@t", "-c", "user.name=t",
                 "commit", "-qm", "seed"]):
        subprocess.run(cmd, cwd=root, check=True, capture_output=True)
    return root


# --- compare ------------------------------------------------------------------


def case_compare_is_silent_when_nothing_moved() -> None:
    before = {"demo": "aaa", "plans": "bbb"}
    assert inv.compare(before, dict(before)) == []


def case_compare_names_the_tree_and_both_sides() -> None:
    before = {"demo": "aaa", "plans": "bbb"}
    after = {"demo": "aaa", "plans": "ccc"}
    findings = inv.compare(before, after)
    assert len(findings) == 1, findings
    only = findings[0]
    assert "plans" in only, only
    assert "bbb" in only and "ccc" in only, only
    assert "demo" not in only, only


def case_compare_reports_every_changed_tree_not_just_the_first() -> None:
    before = {"a": "1", "b": "2", "c": "3"}
    after = {"a": "9", "b": "2", "c": "9"}
    assert len(inv.compare(before, after)) == 2


def case_compare_flags_a_tree_that_vanished_between_captures() -> None:
    findings = inv.compare({"a": "1", "b": "2"}, {"a": "1"})
    assert len(findings) == 1 and "b" in findings[0], findings


def case_compare_flags_a_tree_that_appeared_between_captures() -> None:
    findings = inv.compare({"a": "1"}, {"a": "1", "b": "2"})
    assert len(findings) == 1 and "b" in findings[0], findings


def case_compare_says_when_the_fingerprint_moved() -> None:
    """The wording is the caller's answer to *when* a fingerprint moved, and
    with `phrase` gone it is the only wording — still exactly right for a
    bracket taken inside a run."""
    only = inv.compare({"a": "1"}, {"a": "2"})[0]
    assert "fingerprint changed during the run" in only, only


# --- the red path, kept permanently -------------------------------------------


def case_a_mutated_copy_is_caught_end_to_end() -> None:
    """The sweep's whole job, on a scratch copy of a real guarded tree.

    This is the case that keeps the red path proven. It copies
    `triage/e2e/fixtures` — small, committed, and not itself guarded — mutates
    the copy, and asserts the sweep reports it **by path**. "Something fired"
    is not the deliverable: a fingerprint pair the reader cannot act on is the
    failure this sweep was rewritten to stop producing.
    """
    source = Path(__file__).resolve().parent / "fixtures"
    assert source.is_dir(), source
    scratch = Path(tempfile.mkdtemp(prefix="inv-e2e-")) / "copy"
    shutil.copytree(source, scratch)

    before = {"scratch": inv.sample_content(scratch).fingerprint}
    before_map = inv.content_map(scratch)
    (scratch / "planted.txt").write_text("a run wrote here\n", encoding="utf-8")
    # A lock file too: `skills-kld.4` took that exclusion out of the content
    # half, and this is the whole content path proving it by path.
    (scratch / ".beads").mkdir()
    (scratch / ".beads" / "dolt.gate.lock").write_text("1\n", encoding="utf-8")
    after = {"scratch": inv.sample_content(scratch).fingerprint}

    findings = inv.compare(before, after)
    assert findings, "the sweep did not notice a file planted in a guarded tree"
    assert "scratch" in findings[0], findings
    moved = set(inv.content_map(scratch)) ^ set(before_map)
    assert moved == {"planted.txt", ".beads/dolt.gate.lock"}, moved


# --- tracker fingerprints -----------------------------------------------------


def case_tracker_fingerprint_includes_the_worktree_state() -> None:
    root = _git_tree()
    before = inv.sample_tracker(root).fingerprint
    (root / "dirty.txt").write_text("untracked\n", encoding="utf-8")
    assert inv.sample_tracker(root).fingerprint != before


def case_tracker_fingerprint_is_stable_across_calls() -> None:
    root = _git_tree()
    assert (inv.sample_tracker(root).fingerprint
            == inv.sample_tracker(root).fingerprint)


def case_a_missing_tracker_tree_is_absent() -> None:
    assert inv.sample_tracker(Path("/nope/not/here")).fingerprint == inv.ABSENT


def case_the_tracked_dolt_lock_does_not_move_the_tracker_fingerprint() -> None:
    """`git ls-files .beads/` in demo lists `dolt.gate.lock`, which is how a
    settling Dolt server oscillated `sample_tracker(demo).fingerprint`
    843728 -> ab490c -> 843728 across 60s with no work happening."""
    root = _git_tree({"a.txt": "one\n", ".beads/dolt.gate.lock": "1\n"})
    before = inv.sample_tracker(root).fingerprint
    (root / ".beads" / "dolt.gate.lock").write_text("2\n", encoding="utf-8")
    assert inv.sample_tracker(root).fingerprint == before


def case_a_cache_at_a_repo_root_is_excused_after_the_exit_code_split() -> None:
    """Two things at once. The tracker half still excuses a cache at a repo
    root, which is the regression the old `(?:^|[\\s/])` anchor existed for and
    which `porcelain_noise` now earns by extracting the path. And the filter
    only ever sees real porcelain lines: `_run` hands back the exit code as its
    own field, `sample_tracker` hashes it as its own part, so dropping a line
    as noise cannot drop the exit status with it."""
    root = _git_tree()
    before = inv.sample_tracker(root).fingerprint
    (root / "__pycache__").mkdir()
    (root / "__pycache__" / "x.pyc").write_bytes(b"\x00")
    assert inv.sample_tracker(root).fingerprint == before


# --- the external-repo contract -----------------------------------------------


def case_an_absent_external_repo_is_not_a_failure() -> None:
    """A repo that is not on this machine cannot be leaked into.

    This is the portability rule. `skills` travels between machines; the repos
    beside it do not. Demanding a checkout that is simply not here made the
    sweep red by default on any machine but the one it was written on, and a
    red-by-default guard is one nobody reads.

    `--skip-external` keeps its other meaning in `watched_trees`: it drops
    those repos from sampling even when they are present.
    """
    specs = [inv.Tree("ghost", Path("/nope/not/here"), inv.sample_content,
                      external=True)]
    assert inv.missing(specs) == []


def case_a_missing_internal_tree_is_always_a_failure() -> None:
    """An absent internal tree is always a problem: it means the run's own
    sandbox or plan tree is not where it should be, and no flag excuses it."""
    specs = [inv.Tree("ghost", Path("/nope/not/here"), inv.sample_content,
                      external=False)]
    assert inv.missing(specs), "internal tree was excused"


def case_every_guarded_tree_is_declared() -> None:
    """The three internal trees, and no silent omission.

    External repos are configuration — this repo is not pinned to a machine
    and cannot name the repos that happen to sit beside it — so the default
    roster is these three and nothing else.
    """
    names = {t.name for t in inv.guarded_trees(external=())}
    assert names == {"testbed", "home-plans", "project-plans"}, names
    assert not [t for t in inv.guarded_trees(external=()) if t.external]


def case_configured_external_repos_join_the_roster() -> None:
    """A name in TRIAGE_GUARDED_EXTERNAL becomes a guarded tree under the
    workspace root, marked external so an absent one is skipped."""
    with mock.patch.dict(os.environ, {inv.EXTERNAL_ENV: " alpha , beta ,"}):
        assert inv.external_names() == ("alpha", "beta")
        trees = {t.name: t for t in inv.guarded_trees()}
    assert set(trees) == {"testbed", "home-plans", "project-plans",
                          "alpha", "beta"}, trees
    assert trees["alpha"].path == inv.PROJECTS / "alpha", trees["alpha"].path
    assert trees["alpha"].external and trees["beta"].external
    with mock.patch.dict(os.environ, {inv.EXTERNAL_ENV: ""}):
        assert inv.external_names() == ()


def case_watched_trees_excludes_an_excused_external_tree() -> None:
    """The filter, stated once. A call site that restated it could watch an
    excused external tree in one place and skip it in the other."""
    excused = {t.name for t in inv.watched_trees(skip_external=True,
                                                external=("alpha",))}
    assert excused == {"testbed", "home-plans", "project-plans"}, excused
    every = {t.name for t in inv.watched_trees(external=("alpha",))}
    assert every == {"testbed", "home-plans", "project-plans",
                     "alpha"}, every


def case_watched_trees_is_every_guarded_tree() -> None:
    """One window, so the filter answers with the whole roster — and the
    testbed's path follows `--root` through the filter as well as through
    `guarded_trees` itself."""
    root = Path(tempfile.mkdtemp(prefix="watched-"))
    watched = inv.watched_trees(root=root, external=("alpha", "beta"))
    assert {t.name for t in watched} == {"testbed", "home-plans",
                                         "project-plans", "alpha",
                                         "beta"}, watched
    testbed = next(t for t in watched if t.name == "testbed")
    assert testbed.path == root / "triage-testbed", testbed.path


def case_fingerprints_projects_the_hash_and_drops_the_detail() -> None:
    """The bracket compares nothing but hashes, so the projection keeps
    `compare` out of the details a sample also carries."""
    samples = {"a": inv.Sample("aaa", {"x": "1"}),
               "b": inv.Sample(inv.ABSENT, None)}
    assert inv.fingerprints(samples) == {"a": "aaa", "b": inv.ABSENT}


def case_missing_names_an_absent_testbed() -> None:
    """The inverse of the property this replaces. `missing` no longer excuses
    a tree by scope, and the driver's order is what makes that right: it
    builds or reuses the sandbox and only then asks, so an absent testbed is a
    build that did not build rather than one torn down at the end of a run."""
    specs = [inv.Tree("testbed", Path("/nope/not/here"), inv.sample_tracker,
                      external=False)]
    problems = inv.missing(specs)
    assert problems and "/nope/not/here" in problems[0], problems


def case_the_testbed_tree_follows_the_run_root() -> None:
    """`skills-yc7`: `--root DIR` builds the testbed under DIR.

    A hard-coded path fingerprints a directory the run never touched, so both
    samples read ABSENT and the comparison passes while guarding nothing. The
    green output still reads as proof, which is what makes it worse than no
    guard at all.
    """
    root = Path(tempfile.mkdtemp(prefix="root-"))
    tree = next(t for t in inv.guarded_trees(root) if t.name == "testbed")
    assert tree.path == root / "triage-testbed", tree.path
    default = next(t for t in inv.guarded_trees() if t.name == "testbed")
    assert default.path == inv.SKILLS / "triage-testbed", default.path


def case_the_sampled_testbed_is_the_fingerprint_of_that_exact_path() -> None:
    """Compared against the fingerprint of that exact path, not merely
    "not ABSENT" — a leftover testbed at the default location makes the weaker
    assertion pass even when `root` is ignored entirely."""
    root = Path(tempfile.mkdtemp(prefix="root-"))
    (root / "triage-testbed").mkdir()
    with mock.patch.object(inv, "PROJECTS", root), mock.patch.object(
            inv, "sample_content", lambda path: inv.Sample("static", {})):
        got = inv.sample(root=root)
    assert got["testbed"].fingerprint == inv.sample_tracker(
        root / "triage-testbed").fingerprint, got["testbed"]
    assert got["testbed"].fingerprint != inv.sample_tracker(
        inv.SKILLS / "triage-testbed").fingerprint, "sample read the default root"


def case_only_the_testbed_moves_with_the_run_root() -> None:
    """Only the testbed is built by a run; the other four are fixed locations
    on this machine, so `--root` must leave them exactly where they are."""
    root = Path(tempfile.mkdtemp(prefix="root-"))
    moved = {t.name: t.path for t in inv.guarded_trees(root)
             if t.name != "testbed"}
    fixed = {t.name: t.path for t in inv.guarded_trees()
             if t.name != "testbed"}
    assert moved == fixed, (moved, fixed)


def case_the_roster_has_one_scope() -> None:
    """One list, one window. With no `scope` field there is no argument left
    that could widen a sample back to the whole run, and the roster answers
    with all five trees rather than a scope-filtered subset of them."""
    assert "scope" not in inv.Tree._fields, inv.Tree._fields
    root = Path(tempfile.mkdtemp(prefix="roster-"))
    trees = inv.guarded_trees(root, external=("alpha", "beta"))
    assert {t.name for t in trees} == {"testbed", "home-plans",
                                       "project-plans", "alpha",
                                       "beta"}, trees
    testbed = next(t for t in trees if t.name == "testbed")
    assert testbed.path == root / "triage-testbed", testbed.path


# --- the workspace root ---


def case_the_workspace_root_is_derived_from_this_file() -> None:
    """No machine's path is written down anywhere.

    This module lives at `<workspace>/skills/triage/e2e/`, so the workspace is
    three directories up and the suite is correct on any machine with nothing
    to configure. The previous version defaulted to the author's home
    directory, which is wrong everywhere else and wrong silently.
    """
    try:
        with mock.patch.dict(os.environ):
            os.environ.pop("PROJECTS_ROOT", None)
            importlib.reload(inv)
            expected = Path(inv.__file__).resolve().parents[3]
            assert inv.PROJECTS == expected, inv.PROJECTS
            assert inv.SKILLS == expected / "skills", inv.SKILLS
            assert inv.SKILLS.is_dir(), inv.SKILLS
            # The equality above passes on the machine the old literal named,
            # so it proves nothing on its own. This is the assertion with
            # teeth: no home directory is written into the module at all.
            src = Path(inv.__file__).read_text(encoding="utf-8")
            for bad in ("/Users/", "/home/"):
                assert bad not in src, f"{bad} is hard-coded in {inv.__file__}"
    finally:
        importlib.reload(inv)


def case_PROJECTS_ROOT_still_overrides_the_derived_root() -> None:
    """Pointing the suite somewhere else on purpose still works.

    The root never has to exist — reloading builds `Path` objects and reads no
    disk — so the case names one instead of creating a directory it would then
    have to clean up.

    The reload is in a `finally` because `main()` catches a failed assertion
    and runs the remaining cases, so a case that reloads this module owes the
    restore to every case after it, including when it is the one that failed.
    """
    root = Path("/elsewhere/workspace")
    try:
        with mock.patch.dict(os.environ, {"PROJECTS_ROOT": str(root)}):
            importlib.reload(inv)
            assert inv.PROJECTS == root, inv.PROJECTS
            assert inv.SKILLS == root / "skills", inv.SKILLS
    finally:
        importlib.reload(inv)


def case_one_sample_covers_every_guarded_tree() -> None:
    """The collapse itself: one sample is every guarded tree, testbed included.

    `PROJECTS` is rerouted and `sample_content` is patched to a constant, so
    the case reads neither of the operator's real content trees nor either
    external repo — the mistake the guard exists to prevent.
    """
    root = Path(tempfile.mkdtemp(prefix="sampled-"))
    (root / "triage-testbed").mkdir()
    with mock.patch.object(inv, "PROJECTS", root), mock.patch.object(
            inv, "sample_content", lambda path: inv.Sample("static", {})):
        got = inv.sample(root=root, external=("alpha", "beta"))
    assert set(got) == {"testbed", "home-plans", "project-plans",
                        "alpha", "beta"}, got


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
