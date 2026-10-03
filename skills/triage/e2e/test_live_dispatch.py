#!/usr/bin/env python3
"""Unit cases for the per-worker bracket itself — `live_dispatch.dispatch`.

The bracket is the only thing standing between a worker with write tools and
the user's real backlog, so its red path has to be proven rather than assumed:
a guard that has never reported a leak is indistinguishable from one that
cannot.

Every case here works on scratch data — `tempfile.mkdtemp()` directories and
plain dicts — with `inv.PROJECTS` rerouted into that scratch tree. Nothing
dispatches an agent, and nothing reads a tree the bracket actually guards;
mutating one to test the guard would be the mistake the guard exists to
prevent.

`dispatch()` is unit-tested here for one reason: the defect this file's
bracket cases pin was never in a function `dispatch` calls, it was in the
**order** it called them in, and that ordering is invisible from outside
`dispatch`. So the spawn, the tracker commands and the corpus map are stubbed;
everything that decides — the samples, the comparison, the assert, the ledger
row — is real. A live `--live` run still exercises the spawn itself.

`strayed` is a pure function with no need of any of this machinery, so its
cases live in `test_strayed.py`. No fixture is shared across that seam.
"""

from __future__ import annotations

import collections
import contextlib
import json
import os
import shutil
import sys
import tempfile
import types
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import live_dispatch as ld  # noqa: E402
import suite_invariant as inv  # noqa: E402


# --- the noise predicate the bracket shares -----------------------------------


def case_bytecode_is_not_a_worktree_fact() -> None:
    """Regression, found live: a planning worker imported the fixture module it
    was planning against and left `lib/__pycache__/` in the testbed. Every real
    repo here gitignores that, so the same import in the skills repo is
    invisible — the guard was comparing unlike with unlike and failing a worker
    for reading code.

    Asserted against the predicate `sample_guarded_trees` actually uses,
    `suite_invariant.porcelain_noise`. The tracker half has two readers — the
    tripwire's hashed lines and this adjudicator's worktree tuple — and both
    call that one function, so they cannot drift apart over what counts as
    noise. The content half has its own predicate for its own reason; see
    `CONTENT_NOISE_RE`."""
    assert inv.porcelain_noise("?? lib/__pycache__/")
    assert inv.porcelain_noise("?? lib/app_startup.cpython-311.pyc")


def case_a_real_source_change_is_still_a_worktree_fact() -> None:
    """The exclusion is narrow: anything that is not bytecode still counts."""
    assert not inv.porcelain_noise(" M lib/app_startup.py")
    assert not inv.porcelain_noise("?? lib/pycache_notes.md")


# --- the dispatch bracket -----------------------------------------------------

_Dispatched = collections.namedtuple("_Dispatched", "outcome ledger reads argv")


def _tracker_state() -> dict:
    """Every fake tracker a bracket reads: porcelain lines, and `bd list
    --json` rows.

    Four rather than two, because the roster the bracket samples carries two
    configured external repos. The case names its own — `alpha` and `beta`,
    with `inv.PROJECTS` rerouted to its own tmp directory — so nothing here
    can read a real repository, which is the mistake the guard exists to
    prevent.
    """
    return {"testbed": {"worktree": [],
                        "beads": [{"id": "tb-1", "status": "open",
                                   "updated_at": "t0", "title": "first"}]},
            "skills-repo": {"worktree": [], "beads": []},
            "alpha": {"worktree": [], "beads": []},
            "beta": {"worktree": [], "beads": []}}


def _shell(state: dict, worker_write, roots: dict, reads: list):
    """Every subprocess the bracket takes, answered from `state`.

    One stub for all three commands: `live_dispatch.subprocess` and
    `suite_invariant.subprocess` are the same module object, so a single patch
    covers the spawn and both halves of every tracker read — the hash and the
    facts, from one sampled read.

    Keyed on the working directory for **every** tracker root the roster
    carries, rather than the testbed-or-skills-repo pair it used to be, and an
    unmapped root raises: a tracker added to the roster later cannot answer
    silently with another tree's state. It raises a `RuntimeError` and not an
    assertion, because `_dispatched` catches `AssertionError` as the bracket's
    own verdict — a mis-mapped stub would read as a fire.

    Each answered command is recorded, which is what makes the read count
    measurable instead of asserted.

    `claude` is the worker. Its argv lands in `state["argv"]` — the permission
    blob is passed on the command line, so the argv is the only place a unit
    case can read it back — and then `worker_write` is applied to `state` and
    the stub returns a payload shaped like `--output-format json`.
    """
    def run(cmd, cwd=None, capture_output=True, text=True, timeout=None):
        if cmd[0] == "claude":
            state["argv"] = list(cmd)
            worker_write(state)
            return types.SimpleNamespace(
                returncode=0, stderr="",
                stdout=json.dumps({"result": "done", "total_cost_usd": 0.0,
                                   "num_turns": 1}))
        key = roots.get(Path(cwd))
        if key is None:
            raise RuntimeError(f"a tracker was read from an unmapped root: {cwd}")
        reads.append((key, cmd[0]))
        stdout = ("".join(f"{line}\n" for line in state[key]["worktree"])
                  if cmd[0] == "git" else json.dumps(state[key]["beads"]))
        return types.SimpleNamespace(returncode=0, stdout=stdout, stderr="")
    return run


def _window(state: dict, window_write, corpus: Path, reads: list):
    """`content_map` of the corpus, with `window_write` applied on its first
    call.

    That call is where the defect lived: `dispatch` maps the corpus between
    its two sample points, so this stages the write exactly in the gap.
    Anchored on the corpus path rather than on call order, because the roster's
    two content trees are sampled through `sample_content` and which stub runs
    first is not a property this file may depend on. The map is empty because
    these cases are about the trackers — `strayed` has its own cases above, on
    real scratch corpora.
    """
    staged = []

    def content_map(path):
        reads.append((str(path), "map"))
        if Path(path) == corpus and not staged:
            staged.append(path)
            window_write(state)
        return {}
    return content_map


def _content_sampler(reads: list):
    """`sample_content` as one constant answer, counted.

    Both content trees on the roster resolve outside any tmp directory —
    `~/.claude/plans` through `Path.home()`, which the `PROJECTS` patch cannot
    reroute — so a unit case must not walk them. A constant keeps the file
    hermetic and inside the "under three seconds together" budget
    `run_tests.py` claims for it.
    """
    def sample_content(path):
        reads.append((str(path), "content"))
        return inv.Sample("static", {})
    return sample_content


def _new_bead(bead_id: str, tree: str = "testbed"):
    """A `bd` write into one of the guarded trackers."""
    def write(state):
        state[tree]["beads"].append(
            {"id": bead_id, "status": "open", "updated_at": "t1",
             "title": bead_id})
    return write


def _quiet(state) -> None:
    """Nothing written."""


def _dispatched(worker_write=_quiet, window_write=_quiet) -> _Dispatched:
    """One real `dispatch` over fake trackers and a fake worker.

    `outcome` is the report it returned, or the `AssertionError` the bracket
    raised. `ledger` is the staged run's `ledger.md`, which is where a forgiven
    fire leaves its `noise/` row. `reads` is one entry per answered read, in
    order, which is what the read-count case measures. `argv` is the command
    the spawn was called with, which is where the permission cases read the
    settings blob back out.

    `inv.PROJECTS` is rerouted to this case's tmp directory, two external
    repos are created under it, and `TRIAGE_GUARDED_EXTERNAL` names them, so
    the roster's external rows resolve inside the sandbox. The patch takes
    only because the roster is built per call: as a module-level tuple those
    paths were frozen at import, and `sample_tracker` answers `ABSENT` for a
    directory that is not there — so without this a case would pass or fail
    depending on what happens to be checked out on the machine running it.
    """
    tmp = Path(tempfile.mkdtemp(prefix="ld-bracket-"))
    for leaf in ("triage-testbed", "corpus", "alpha", "beta"):
        (tmp / leaf).mkdir()
    testbed = types.SimpleNamespace(root=tmp, path=tmp / "triage-testbed",
                                    corpus=tmp / "corpus")
    run = ld.staged_run.create_run(tmp / "runs", "w1")
    state = _tracker_state()
    # The tree's own path, so a write can make it unreadable rather than only
    # changing what a `bd` call would have said about it.
    state["testbed"]["root"] = testbed.path
    roots = {testbed.path: "testbed", ld.harness.SKILLS_ROOT: "skills-repo",
             tmp / "alpha": "alpha", tmp / "beta": "beta"}
    reads: list = []
    fakes = {"subprocess.run": _shell(state, worker_write, roots, reads),
             "suite_invariant.content_map": _window(state, window_write,
                                                    testbed.corpus, reads)}
    with contextlib.ExitStack() as stack:
        stack.enter_context(mock.patch.dict(
            os.environ, {inv.EXTERNAL_ENV: "alpha,beta"}))
        for target, value in fakes.items():
            stack.enter_context(mock.patch(f"live_dispatch.{target}", value))
        stack.enter_context(mock.patch.object(inv, "PROJECTS", tmp))
        stack.enter_context(mock.patch.object(inv, "sample_content",
                                              _content_sampler(reads)))
        try:
            outcome = ld.dispatch(testbed, run, "w1", "brief", "target")
        except AssertionError as err:
            outcome = err
    return _Dispatched(outcome,
                       (run / "ledger.md").read_text(encoding="utf-8"),
                       tuple(reads), state.get("argv", []))


def _vanish(state) -> None:
    """The guarded tree itself goes away mid-bracket."""
    shutil.rmtree(state["testbed"]["root"])


def case_a_tracker_tree_that_vanishes_mid_bracket_fails_the_dispatch() -> None:
    """The loudest thing the bracket can see must not arrive as a traceback.

    `sample_tracker` answers `Sample(ABSENT, None)` for a root that is gone,
    and `dispatch` hands both details to `delta_lines` once the tripwire
    fires. A `None` detail used to reach `fact_delta` and raise `TypeError`
    there — after the worker had returned, so the bracket's own assert never
    ran, no `noise/` row was written and the corpus check never happened. Run
    scope has said `tree unreadable` since `skills-kld.5`; worker scope has to
    say it too.
    """
    got = _dispatched(worker_write=_vanish)
    assert isinstance(got.outcome, AssertionError), got.outcome
    assert "tree unreadable" in str(got.outcome), got.outcome


def case_a_write_in_the_sampling_window_fails_the_dispatch() -> None:
    """The defect this phase closes. A `bd` write landing between the
    bracket's two former sample points was in `before_facts` and missing from
    `before`, so after the worker returned the hash had moved, the facts
    agreed, `assert not delta` passed and the write was filed as `noise/`.
    One sampled bracket cannot split that write across two moments."""
    got = _dispatched(window_write=_new_bead("win-1"))
    assert isinstance(got.outcome, AssertionError), got.outcome
    assert "win-1" in str(got.outcome), got.outcome
    assert "noise/w1" not in got.ledger, got.ledger


def case_a_hash_only_move_is_still_filed_as_noise() -> None:
    """`NOISE` keeps its meaning and stays reachable. The fingerprint hashes
    `bd list --json` whole; the facts keep `(id, status, updated_at)`. So a
    title edit moves the tripwire and not the adjudicator, and the bracket
    names it in the ledger rather than failing the dispatch.

    The row names the *tree*, and the assertion pins the list `dispatch`
    actually recovered, not merely that the word appears somewhere in the
    ledger. `dispatch` builds it with `line.split(':')[0]` over `compare`'s
    output, so the `{name}: ` prefix is load-bearing, and the case that
    pinned that split died with `compare`'s `phrase` parameter in
    `skills-92s.4`.

    `"['testbed']"` and not `"testbed"`: the weaker form passes on a reworded
    `compare` that keeps the name out of the prefix — `f"tree {name}
    fingerprint changed during the run: ..."` yields the row
    `['tree testbed fingerprint changed during the run']`, which contains
    "testbed" and is exactly the garbage this case exists to catch. Verified
    both directions by mutation."""
    def retitle(state):
        state["testbed"]["beads"][0]["title"] = "rewritten"
    got = _dispatched(worker_write=retitle)
    assert got.outcome == "done", got.outcome
    assert "noise/w1" in got.ledger, got.ledger
    assert "['testbed']" in got.ledger, got.ledger


def case_a_tracker_write_by_the_worker_trips_the_assert() -> None:
    """The thing the bracket exists for: a worker writing into a guarded
    tracker fails the dispatch, and the delta names the bead."""
    got = _dispatched(worker_write=_new_bead("leak-1"))
    assert isinstance(got.outcome, AssertionError), got.outcome
    assert "leak-1" in str(got.outcome), got.outcome


def case_a_write_in_a_real_tracker_names_the_tree_and_the_worker() -> None:
    """The phase's headline behaviour. A configured external repo is inside the
    bracket, so a bead written into a real tracker fails the dispatch, and the
    message names both the tree that moved and the worker that moved it. The
    same write against a run-wide sample said only that something had happened
    somewhere in the run's minutes — a `FAIL invariant.alpha` the operator's
    own session would have earned just as easily."""
    got = _dispatched(worker_write=_new_bead("alpha-999", tree="alpha"))
    assert isinstance(got.outcome, AssertionError), got.outcome
    assert "alpha" in str(got.outcome), got.outcome
    assert "w1" in str(got.outcome), got.outcome
    assert "alpha-999" in str(got.outcome), got.outcome


def case_each_guarded_tree_is_read_once_per_sample_point() -> None:
    """`skills-rjb`, re-homed from the deleted run-scope sweep, and not
    trivially one.

    The defect it pins hashed every root in one pass and read its facts in a
    second, so a `bd` write landing between the two was in the facts and
    missing from the hash: the tripwire fired, nothing explained it, and a real
    write was filed as `noise/`. One read per tree per sample point is what
    makes that unexpressible, and a bracket is two sample points — so every
    tracker answers exactly two `git status` and two `bd list` calls, each
    content tree is sampled exactly twice, and the corpus is mapped twice.
    """
    got = _dispatched()
    counted = collections.Counter(got.reads)
    for key in ("testbed", "skills-repo", "alpha", "beta"):
        assert counted[(key, "git")] == 2, (key, counted)
        assert counted[(key, "bd")] == 2, (key, counted)
    content = collections.Counter(name for name, kind in got.reads
                                  if kind == "content")
    assert len(content) == 2 and set(content.values()) == {2}, content
    mapped = collections.Counter(name for name, kind in got.reads
                                 if kind == "map")
    assert len(mapped) == 1 and set(mapped.values()) == {2}, mapped
    assert {kind for _, kind in got.reads} == {"git", "bd", "content",
                                               "map"}, got.reads


# --- the permission floor a dispatched worker runs under ----------------------


def _deny_rules(blob: str) -> list:
    return json.loads(blob)["permissions"]["deny"]


def case_the_deny_list_names_every_tree_but_the_testbed() -> None:
    """Every guarded tree except the one the worker is meant to write in.

    `Read` and `Edit` and not `Write`: a path rule written for `Write` or
    `NotebookEdit` is accepted and never consulted, and a `Read` deny does not
    cover NotebookEdit. And `//` and not `/`: a single leading slash anchors at
    the settings source rather than the filesystem root, so that rule would
    match nothing.

    Derived from the roster rather than listed, so a tree added to
    `guarded_trees` and forgotten in `DENIED_TREES` fails here instead of
    shipping as a watched-but-reachable path. Configured external repos are
    denied even though every bracket already samples them, because a rule
    refuses a write and a bracket only reports one.
    """
    with mock.patch.dict(os.environ, {inv.EXTERNAL_ENV: "alpha,beta"}):
        trees = {tree.name: tree.path for tree in inv.guarded_trees()}
        rules = _deny_rules(ld.permission_settings())
    expected = [name for name in trees if name != "testbed"]
    assert len(expected) == 4, expected
    for name in expected:
        anchored = str(trees[name]).lstrip("/")
        assert f"Read(//{anchored}/**)" in rules, (name, rules)
        assert f"Edit(//{anchored}/**)" in rules, (name, rules)
    testbed_path = str(trees["testbed"]).lstrip("/")
    assert f"Edit(//{testbed_path}/**)" not in rules, rules


def case_an_unknown_tree_name_refuses_to_produce_an_empty_deny_list() -> None:
    """A guard that silently stops guarding is worse than none.

    A rename in `guarded_trees` has to arrive here as a failure rather than as
    a settings blob that denies nothing while the suite stays green.
    """
    try:
        ld.permission_settings(("no-such-tree",))
    except AssertionError as err:
        assert "no-such-tree" in str(err), err
        return
    raise AssertionError("a name no guarded tree carries produced a deny list")


def case_the_dispatch_carries_the_deny_rules() -> None:
    """A helper nothing calls guards nothing: the blob must reach the argv.

    Asserted on `home-plans` rather than on the whole blob, because
    `_dispatched` reroutes `inv.PROJECTS` into its own tmp tree for the
    roster's sake — so the `project-plans` rule the spawn carried names a path
    this case cannot name from outside that patch. `home-plans` resolves
    through `Path.home()`, which the reroute does not touch, and the case above
    pins the whole list anyway. `defaultMode` is checked here because a blob
    that lost it would leave the worker in Manual mode under `-p`, where every
    tool call is denied and the failure looks nothing like a permission test.
    """
    argv = _dispatched().argv
    assert "--settings" in argv, argv
    blob = argv[argv.index("--settings") + 1]
    settings = json.loads(blob)["permissions"]
    rules = settings["deny"]
    trees = {tree.name: tree.path for tree in inv.guarded_trees()}
    home = str(trees["home-plans"]).lstrip("/")
    assert f"Read(//{home}/**)" in rules, rules
    assert f"Edit(//{home}/**)" in rules, rules
    assert settings["defaultMode"] == "auto", blob


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
