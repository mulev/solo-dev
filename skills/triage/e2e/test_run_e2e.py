#!/usr/bin/env python3
"""Unit cases for the driver's suite selection and its teardown decision.
Neither is plumbing.

The live suites must stay **out** of a default run: they dispatch real agents
and the `e2e` stage invokes the driver with no flags. A **failing** run must
keep its trees — that default was the other way round once, and a live
orchestrator run that died mid-sweep on a usage limit had its run directory
deleted by the teardown, so the only way to see what the agent had done was to
spend the run again. The driver samples no guarded tree at all: the sweep it
used to run at run scope is now the per-worker bracket, and what a fire says
lives with it in `test_live_dispatch.py`.
"""

from __future__ import annotations

import collections
import contextlib
import io
import sys
import types
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import run_e2e  # noqa: E402


# Stand-in testbed. `root` is all the teardown decision reads.
_FAKE = types.SimpleNamespace(root=Path("/nowhere/testbed"))


def _no_sample(*args, **kwargs):
    """The sampler a default run must never reach.

    Every driven run installs this, so reintroducing a run-scope sample fails
    the whole file rather than one case. A window that wide cannot attribute
    what it finds: `project_plans` and `~/.claude/plans` are trees the
    operator writes to continuously, so a before/after across a run reports a
    neighbouring session in the words it would use for a leak.
    """
    raise RuntimeError("the driver sampled a guarded tree")


# Named fields rather than a bare 4-tuple: a case reads one or two of these,
# and positional unpacking made every one of them declare throwaways for the
# rest, which is noise that hides which field the case is actually about.
_Run = collections.namedtuple("_Run", "outcome torn output called")


@contextlib.contextmanager
def _stubbed(failures: int, raises: bool = False):
    """`run_e2e.main` with the build, the suites and the sweep replaced.

    Everything the decision depends on stays real — the flags, the counter, the
    `finally` — and everything below it is a stub, so a case costs nothing and
    can still assert what the driver did. `torn` is one entry per teardown.

    The roster is empty and the sampler raises, which is the driver's real
    shape now: it asks `missing` whether every guarded tree is on disk and
    takes no sample of any of them.
    """
    torn: list = []
    called: list = []

    def sweep(name, module, testbed):
        if raises:
            raise RuntimeError("driver came apart")
        return failures

    def acquire(label):
        called.append(label)
        return _FAKE

    fakes = {
        "harness.build": lambda root=None: acquire("build"),
        "harness.reuse": lambda root=None: acquire("reuse"),
        "harness.assert_db_inside": lambda testbed: acquire("db-inside"),
        "harness.assert_fixture_roster": lambda testbed: acquire("roster"),
        "harness.teardown": torn.append,
        "harness.release": lambda root=None: None,
        "suite_invariant.guarded_trees": lambda root=None: [],
        "suite_invariant.sample": _no_sample,
        "run_suite": sweep,
    }
    # `mock.patch` restores all of these on the way out, including when a case
    # raises. The hand-rolled save/restore this replaced had to name every
    # attribute twice, so it was one edit away from leaking a stub into the
    # next case.
    with contextlib.ExitStack() as stack:
        for target, value in fakes.items():
            stack.enter_context(mock.patch(f"run_e2e.{target}", value))
        yield torn, called


def _drive(failures: int, *argv: str, raises: bool = False) -> _Run:
    """One driven run. `outcome` is the exit code, or the exception raised."""
    buffer = io.StringIO()
    with _stubbed(failures, raises) as (torn, called):
        with contextlib.redirect_stdout(buffer):
            try:
                outcome = run_e2e.main(["--only", "routing", *argv])
            except RuntimeError as err:
                outcome = err
    return _Run(outcome, torn, buffer.getvalue(), called)


def case_a_default_run_is_exactly_the_deterministic_suites() -> None:
    assert run_e2e.suites(live=False) == run_e2e.SUITES
    assert set(run_e2e.suites(live=False)) == {
        "routing", "exit-codes", "qc", "lifecycle", "promote"}


def case_no_live_suite_reaches_a_default_run() -> None:
    """The one that matters: the `e2e` stage runs the driver with no flags."""
    default = run_e2e.suites(live=False)
    assert not set(default) & set(run_e2e.LIVE_SUITES), default


def case_live_is_additive_never_a_replacement() -> None:
    live = run_e2e.suites(live=True)
    assert set(live) == set(run_e2e.SUITES) | set(run_e2e.LIVE_SUITES), live
    for name, module in run_e2e.SUITES.items():
        assert live[name] == module, name


def case_the_default_suite_order_is_preserved_under_live() -> None:
    """Read-only suites run before the two that create beads in the testbed;
    the driver iterates insertion order, so `--live` must not reshuffle it."""
    assert list(run_e2e.suites(live=True))[:len(run_e2e.SUITES)] == list(run_e2e.SUITES)


def case_help_names_the_flag_and_its_cost() -> None:
    """A flag that spends agents has to say so where the user meets it.
    `--help` as the user sees it: argparse prints and exits, so both are caught."""
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer), contextlib.suppress(SystemExit):
        run_e2e.main(["--help"])
    assert "--live" in buffer.getvalue(), buffer.getvalue()
    assert "agent" in buffer.getvalue(), buffer.getvalue()


def case_only_a_live_suite_without_live_is_refused() -> None:
    """`--only live` must not become a back door around the default."""
    try:
        run_e2e.main(["--only", "live"])
    except SystemExit as err:
        assert err.code == 2, err.code
    else:
        raise AssertionError("--only live ran without --live")


def case_a_failing_run_keeps_its_trees() -> None:
    """The whole point. A red run is the run whose evidence is worth money."""
    run = _drive(1)
    assert run.outcome == 1, run.outcome
    assert run.torn == [], "a failing run tore down the trees it should have kept"
    assert "KEPT" in run.output, run.output


def case_a_passing_run_still_cleans_up() -> None:
    """Keeping on failure must not turn into never cleaning up: a green run
    leaves nothing behind, or the trees accumulate one testbed per invocation."""
    run = _drive(0)
    assert run.outcome == 0, run.outcome
    assert len(run.torn) == 1, run.torn
    assert "KEPT" not in run.output, run.output


def case_keep_overrides_a_green_run() -> None:
    """`--keep` keeps its original meaning — inspect a run that passed."""
    run = _drive(0, "--keep")
    assert run.outcome == 0, run.outcome
    assert run.torn == [], run.torn
    assert "KEPT" in run.output, run.output


def case_a_driver_crash_keeps_the_trees_too() -> None:
    """`run_suite` catches per case, so an exception reaching the driver is a
    failure the counter never saw. It is still evidence, and still kept."""
    run = _drive(0, raises=True)
    assert isinstance(run.outcome, RuntimeError), run.outcome
    assert run.torn == [], "a crashed run tore down the trees"
    assert "KEPT" in run.output, run.output


def case_a_default_run_builds_a_fresh_testbed_then_asks_both_guards() -> None:
    """Order is the assertion. Both database questions have to run after the
    trees exist and before any suite reaches `bd`, and placement is the only
    part of them a stub cannot prove: patching the names to no-ops leaves the
    suite green even with the calls deleted, which is how the roster check sat
    in the generator — build-time only — without a red case."""
    assert _drive(0).called == ["build", "db-inside", "roster"]


def case_reuse_adopts_the_trees_instead_of_rebuilding() -> None:
    """The point of the flag: a rebuild destroys the run being continued.

    `make_testbed.sh` wipes and rebuilds all three trees, so before this
    existed, starting the driver again to continue an interrupted live sweep
    deleted the sweep — the ledger a resume reads included. Keeping the trees
    on failure made the run survivable; this is what lets the harness use it.
    """
    assert _drive(0, "--reuse").called == ["reuse", "db-inside", "roster"]


def case_nothing_to_reuse_exits_2_rather_than_building_over_it() -> None:
    """A missing testbed under `--reuse` is a usage error, never a silent build.

    Falling back to a build would be the one behaviour that cannot be undone:
    the caller asked to continue something, and a rebuild answers by destroying
    whatever was there.
    """
    buffer = io.StringIO()
    with _stubbed(0):
        def absent(root=None):
            raise run_e2e.harness.Missing("no marker at /nowhere/testbed")
        run_e2e.harness.reuse = absent
        with contextlib.redirect_stdout(buffer):
            code = run_e2e.main(["--only", "routing", "--reuse"])
    assert code == 2, code
    assert "nothing-to-reuse" in buffer.getvalue(), buffer.getvalue()


def case_the_kept_path_is_printed() -> None:
    """A message that says trees were kept and not where is not a message."""
    out = _drive(1).output
    assert str(_FAKE.root) in out, out


def case_a_default_run_samples_nothing_outside_the_sandbox() -> None:
    """The phase's claim in its strongest form. `_stubbed` answers
    `suite_invariant.sample` with a raiser, so a driver that samples a guarded
    tree at all fails here — a window minutes wide over trees the operator is
    working in cannot come back by accident."""
    run = _drive(0)
    assert run.outcome == 0, run.outcome


def case_allow_busy_is_no_longer_a_flag() -> None:
    """The flag accepted an ambiguous verdict from a pre-flight over trees a
    default run can no longer write to, so there is nothing left to excuse.
    argparse refuses an unknown flag with exit 2 and says so on stderr."""
    out, err = io.StringIO(), io.StringIO()
    with _stubbed(0), contextlib.redirect_stdout(out), \
            contextlib.redirect_stderr(err):
        try:
            run_e2e.main(["--only", "routing", "--allow-busy"])
        except SystemExit as raised:
            assert raised.code == 2, raised.code
        else:
            raise AssertionError("--allow-busy still parses")
    assert "unrecognized arguments" in err.getvalue(), err.getvalue()


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
