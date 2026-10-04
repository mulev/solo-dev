#!/usr/bin/env python3
"""Unit cases for the adjudicators that explain a fired fingerprint.

`test_suite_invariant.py` answers "did anything move" — content and tracker
fingerprints, `compare`, and the tree roster. This file answers the other
half: *what* moved. A guard that reports sixteen hex characters and stops has
told the reader nothing they can act on, so the adjudicators are a deliverable
in their own right and their red paths are proven here rather than assumed.

Every case works on scratch data — `tempfile.mkdtemp()` directories, a real
git tree, and plain dicts. Nothing touches a tree the sweep actually guards;
mutating one to test the guard would be the same mistake the guard exists to
prevent.
"""

from __future__ import annotations

import os
import stat
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import suite_invariant as inv  # noqa: E402
from test_suite_invariant import _git_tree, _tree  # noqa: E402


def case_delta_lines_names_an_unreadable_tree_rather_than_raising() -> None:
    """A `None` detail is what the samplers return for a tree they could not
    read, and it used to fall through to `fact_delta`, which subscripts it.
    Both directions, because a tree can vanish or appear inside one bracket,
    and the answer must never be `[]` — an empty list is the caller's cue to
    print `NOISE`, which would be a lie about a tree nobody could read."""
    facts = ((), (("tb-1", "open", "t0"),))
    for was, now in ((facts, None), (None, facts), (None, None)):
        lines = inv.delta_lines("testbed", was, now)
        assert lines, f"was={was is None} now={now is None} returned nothing"
        assert "tree unreadable" in lines[0], lines


def _state(worktree: tuple, beads: tuple) -> dict:
    return {"testbed": (worktree, beads), "skills-repo": ((), ())}


def _fake_bd(output: str, code: int = 0) -> Path:
    """A `bd` on PATH that prints `output` and exits `code`, in a directory of
    its own.

    Its own `tempfile.mkdtemp()` rather than the git tree under test: a script
    written inside that tree would show up in the very worktree half it exists
    to leave alone.

    Single-quoted so a JSON payload survives: `test_harness.py` imports this
    to answer `bd list --json`, and double quotes would be eaten by the shell.
    """
    home = Path(tempfile.mkdtemp(prefix="fake-bd-"))
    script = home / "bd"
    script.write_text(f"#!/bin/sh\nprintf %s '{output}'\nexit {code}\n",
                      encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return home


# --- the tracker detail ------------------------------------------------------


def case_tracker_facts_names_an_untracked_file() -> None:
    """`sample_tracker`'s fingerprint moves for this too — it just cannot say
    which file. The beads half degrades to the sentinel in a scratch tree with
    no database above it, which is not what this case is about."""
    root = _git_tree()
    (root / "dirty.txt").write_text("untracked\n", encoding="utf-8")
    worktree, _beads = inv.sample_tracker(root).detail
    assert "?? dirty.txt" in worktree, worktree


def case_tracker_facts_survives_an_unreadable_listing() -> None:
    """A `bd` that cannot answer is a fact about the tracker, not a reason to
    raise inside a guard: the sweep still has to report what it does know."""
    root = _git_tree()
    saved = os.environ["PATH"]
    os.environ["PATH"] = f"{_fake_bd('not json at all')}{os.pathsep}{saved}"
    try:
        _worktree, beads = inv.sample_tracker(root).detail
    finally:
        os.environ["PATH"] = saved
    assert len(beads) == 1, beads
    assert beads[0][0] == "unreadable", beads


# --- the samplers ------------------------------------------------------------


def case_sample_content_agrees_with_the_map_it_hashed() -> None:
    """The property that makes one read enough: the hash is `_hash` over the
    map's sorted items, so an empty delta and a moved fingerprint cannot both
    be true. `case_the_content_hash_is_built_from_the_map` asserts the same
    thing end to end, by planting a file; this one pins the arithmetic.
    """
    root = _tree({"a.md": "one", "runs/r1/b.md": "two"})
    taken = inv.sample_content(root)
    assert taken.detail == inv.content_map(root), taken.detail
    parts = [part for name in sorted(taken.detail)
             for part in (name, taken.detail[name])]
    assert taken.fingerprint == inv._hash(parts), taken.fingerprint


def case_sample_content_reports_an_absent_tree_without_a_map() -> None:
    """`None` and not `{}`: the driver's unreadable branch reads the detail,
    and `{}` is what an empty tree legitimately maps to."""
    assert inv.sample_content(Path("/nope/not/here")) == inv.Sample(
        inv.ABSENT, None)


def case_sample_tracker_agrees_with_the_hash_and_the_facts() -> None:
    """One read, two answers, and a second read of an unchanged tree agrees.

    An agreement case rather than a re-derivation: re-deriving the hash here
    would re-run the two commands and re-implement the sampler. What the two
    projections this absorbed promised — a hash that carries no per-call
    state, and a detail taken from the same bytes that names the file it saw
    — is asserted against a second read instead.
    """
    root = _git_tree()
    (root / "dirty.txt").write_text("untracked\n", encoding="utf-8")
    taken = inv.sample_tracker(root)
    again = inv.sample_tracker(root)
    assert taken.fingerprint == again.fingerprint, taken.fingerprint
    assert taken.detail == again.detail, taken.detail
    assert "?? dirty.txt" in taken.detail[0], taken.detail


def case_sample_tracker_reports_an_absent_tree_without_facts() -> None:
    """What makes `run_e2e._detail_of`'s deletion safe. The two-pass version
    checked existence in one function and shelled out with `cwd=root` in the
    other, so a tree that vanished between them raised `FileNotFoundError`
    after the testbed had been torn down — costing the sweep its output."""
    assert inv.sample_tracker(Path("/nope/not/here")) == inv.Sample(
        inv.ABSENT, None)


def case_sample_tracker_survives_an_unreadable_listing() -> None:
    """One read serves both derivations even when one of them degrades: the
    beads half falls back to its sentinel and the hash is still a hash."""
    root = _git_tree()
    saved = os.environ["PATH"]
    os.environ["PATH"] = f"{_fake_bd('not json at all')}{os.pathsep}{saved}"
    try:
        taken = inv.sample_tracker(root)
    finally:
        os.environ["PATH"] = saved
    _worktree, beads = taken.detail
    assert len(beads) == 1 and beads[0][0] == "unreadable", beads
    assert len(taken.fingerprint) == 64, taken.fingerprint


def case_every_run_tree_names_exactly_one_sampler() -> None:
    """One sampler per tree, so a fingerprint and a detail cannot arrive from
    different reads — and a content tree cannot be routed into `fact_delta`,
    which used to fail with a `TypeError` fifteen minutes into a run.

    Configured external repos are trackers, so the case states one and checks
    it is sampled as such: the roster builds them from a name alone, and a
    name is not enough to tell you how a tree should be read.
    """
    samplers = {"home-plans": inv.sample_content,
                "project-plans": inv.sample_content,
                "testbed": inv.sample_tracker,
                "alpha": inv.sample_tracker}
    trees = inv.guarded_trees(external=("alpha",))
    assert {t.name for t in trees} == set(samplers), trees
    for tree in trees:
        assert tree.sample is samplers[tree.name], tree.name


# --- fact_delta ---------------------------------------------------------------


def case_fact_delta_is_silent_when_nothing_moved() -> None:
    state = _state((" M a.py",), (("tb-1", "open", "t0"),))
    same = _state((" M a.py",), (("tb-1", "open", "t0"),))
    assert inv.fact_delta(state, same) == []


def case_fact_delta_names_a_file_that_appeared() -> None:
    before = _state((), ())
    after = _state(("?? leaked.md",), ())
    lines = inv.fact_delta(before, after)
    assert len(lines) == 1 and "leaked.md" in lines[0], lines
    assert "worktree" in lines[0], lines


def case_fact_delta_names_a_bead_that_appeared() -> None:
    """A `bd create` run without `-C` walks up into the real tracker, and this
    is the half of the bracket that sees it."""
    before = _state((), (("tb-1", "open", "t0"),))
    after = _state((), (("tb-1", "open", "t0"), ("skills-999", "open", "t1")))
    lines = inv.fact_delta(before, after)
    assert len(lines) == 1 and "skills-999" in lines[0], lines
    assert "tracker" in lines[0], lines


def case_fact_delta_names_a_bead_whose_status_moved() -> None:
    """A claim or a close is a tracker write too, and it adds no row."""
    before = _state((), (("tb-1", "open", "t0"),))
    after = _state((), (("tb-1", "closed", "t1"),))
    assert inv.fact_delta(before, after), "a status change was not reported"


def case_fact_delta_reports_both_repos_not_just_the_first() -> None:
    before = {"testbed": ((), ()), "skills-repo": ((), ())}
    after = {"testbed": (("?? a",), ()), "skills-repo": (("?? b",), ())}
    assert len(inv.fact_delta(before, after)) == 2


def case_fact_delta_ignores_row_order_in_the_tracker_listing() -> None:
    """The reason this adjudicator exists. The tracker fingerprint hashes raw
    `bd list --json` bytes, so anything that varies its output moves the
    tripwire; sorted tuples answer the question that was actually asked."""
    beads = (("tb-1", "open", "t0"), ("tb-2", "open", "t0"))
    assert inv.fact_delta(_state((), beads),
                          _state((), tuple(reversed(beads)))) == []


# --- delta_lines --------------------------------------------------------------


def case_delta_lines_names_the_files_a_content_tree_moved() -> None:
    """Asserted whole, because the fire path produced this string before the
    function existed and the README quotes its shape."""
    lines = inv.delta_lines("project-plans", {"plan.md": "1"},
                            {"plan.md": "1", "leaked.md": "2"})
    assert lines == ["project-plans: 1 file(s) moved — ['leaked.md']"], lines


def case_delta_lines_counts_an_edited_file_not_only_a_new_one() -> None:
    """Same path, different hash. Compared by value rather than by key set, or
    a worker rewriting a plan in place would add no path at all."""
    lines = inv.delta_lines("home-plans", {"plan.md": "1"}, {"plan.md": "2"})
    assert lines == ["home-plans: 1 file(s) moved — ['plan.md']"], lines


def case_delta_lines_delegates_a_tracker_pair_to_fact_delta() -> None:
    """Dispatched by shape, and it delegates rather than re-deriving: a second
    tracker delta here is a second thing to keep in step with `fact_delta`."""
    was = ((), (("tb-1", "open", "t0"),))
    now = ((), (("tb-1", "open", "t0"), ("demo-999", "open", "t1")))
    lines = inv.delta_lines("demo", was, now)
    assert lines == inv.fact_delta({"demo": was}, {"demo": now}), lines
    assert lines and "demo-999" in lines[0], lines


def case_delta_lines_is_empty_when_the_detail_cannot_say() -> None:
    """What keeps `NOISE` reachable for its real meaning: a fire the detail
    cannot explain is forgiven as a diagnosis, never as a verdict."""
    same = {"plan.md": "1"}
    assert inv.delta_lines("project-plans", same, dict(same)) == []
    facts = ((), (("tb-1", "open", "t0"),))
    assert inv.delta_lines("demo", facts, facts) == []


# --- the two noise predicates ------------------------------------------------


def case_content_map_names_a_planted_dolt_lock_by_path() -> None:
    """A fired guard has to answer "what moved" with a path. The lock was
    excused by the shared predicate, so `content_map` did not list it and the
    fire path had nothing to name."""
    root = _tree({"todo/plan.md": "one\n"})
    before = set(inv.content_map(root))
    (root / ".beads").mkdir()
    (root / ".beads" / "dolt.gate.lock").write_text("1\n", encoding="utf-8")
    assert set(inv.content_map(root)) - before == {".beads/dolt.gate.lock"}


def case_the_tracked_dolt_lock_is_still_excused_in_a_porcelain_line() -> None:
    """The paired forgiveness case: the oscillation `skills-kld` was filed for
    stays forgiven on the half where it was measured."""
    assert inv.porcelain_noise(" M .beads/dolt.gate.lock")
    assert inv.porcelain_noise("?? .beads/dolt.gate.lock")


def case_a_rename_into_a_cache_path_is_not_noise() -> None:
    """A rename names two paths, and the old predicate searched the whole line,
    so `\\.pyc$` at the end excused the tracked file at the start. Both
    orderings, because either half of the pair could be the noisy one."""
    assert not inv.porcelain_noise("R  a.py -> lib/__pycache__/b.pyc")
    assert not inv.porcelain_noise("R  lib/__pycache__/b.pyc -> a.py")
    assert not inv.porcelain_noise("C  a.py -> lib/__pycache__/b.pyc")


def case_a_rename_between_two_cache_paths_is_still_noise() -> None:
    """The paired case for the rule: every path noise means the line is noise,
    so a genuinely irrelevant rename is still excused."""
    assert inv.porcelain_noise("R  old/__pycache__/a.pyc -> new/b.pyc")


def case_a_bare_pycache_at_a_repo_root_is_still_noise() -> None:
    """The regressions the anchor comment exists for, in both halves. Found
    live: a planning worker imported the fixture module it was planning
    against and left `lib/__pycache__/` in the testbed. The path taken out of
    `?? __pycache__/` has no status prefix in front of it, which is why the
    tight `(?:^|/)` anchor is now enough."""
    for line in ("?? __pycache__/", "?? lib/__pycache__/",
                 "?? lib/app_startup.cpython-311.pyc", "?? .git/index",
                 " M .git/config"):
        assert inv.porcelain_noise(line), line
    for name in ("__pycache__/x.pyc", "lib/__pycache__/x.pyc", ".git/index",
                 "lib/y.pyc"):
        assert inv.CONTENT_NOISE_RE.search(name), name


def case_a_quoted_porcelain_path_is_read_out_of_the_line() -> None:
    """git wraps a path with special characters in double quotes
    (`core.quotePath`), and the predicate has to see the path, not the
    wrapping — excusing a quoted cache, firing on a quoted plan file. Every
    line the bare-root case excuses is excused in its quoted form too, or the
    anchor would depend on how git chose to print the path."""
    assert inv.porcelain_paths('?? "lib/a b.py"') == ["lib/a b.py"]
    assert inv.porcelain_noise('?? "lib/__pycache__/a b.pyc"')
    assert not inv.porcelain_noise('?? "todo/a b.md"')
    assert inv.porcelain_paths('R  "old name.py" -> "new/__pycache__/x.pyc"') \
        == ["old name.py", "new/__pycache__/x.pyc"]
    for line in ('?? "__pycache__/"', '?? "lib/__pycache__/x.pyc"',
                 '?? ".git/index"'):
        assert inv.porcelain_noise(line), line


def case_a_working_path_is_noise_in_neither_half() -> None:
    """Both exclusions are narrow: a run's leak is always a working file, and
    the lock exclusion must not spread by substring. `.beads/dolt.gate.lock`
    is deliberately absent — it is excused in the tracker half only, and the
    two cases above cover it on both sides."""
    for name in ("skills/todo/plan.md", "demo/todo/plan.md",
                 "lib/app_startup.py", "lib/pycache_notes.md", ".gitignore",
                 "docs/dolt.gate.lock.md"):
        assert not inv.CONTENT_NOISE_RE.search(name), name
        assert not inv.TRACKER_NOISE_RE.search(name), name
    for line in (" M lib/app_startup.py", "?? lib/pycache_notes.md",
                 "?? .gitignore", "?? docs/dolt.gate.lock.md",
                 "?? .beads/dolt.gate.lock.bak"):
        assert not inv.porcelain_noise(line), line


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
        except Exception as err:
            failed += 1
            print(f"ERROR {case.__name__}: {type(err).__name__}: {err}")
    print(f"\n{len(CASES) - failed}/{len(CASES)} cases passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
