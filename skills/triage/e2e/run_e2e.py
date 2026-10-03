#!/usr/bin/env python3
"""Run the triage end-to-end suites against a freshly built testbed.

One build per invocation, the database guard immediately after it, then one
PASS/FAIL line per case and a single exit code — the same reporting shape
`triage/scripts/run_tests.py` uses, so a red e2e run reads like a red unit run.

Suites are imported lazily so `--only routing` never loads a suite it is not
going to run, and a suite that fails to import is reported as that suite's
failure rather than taking the driver down with it.
"""

from __future__ import annotations

import argparse
import importlib
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import harness  # noqa: E402
import suite_invariant  # noqa: E402

# Insertion order is run order, and it is load-bearing rather than cosmetic:
# `suite_promote` and `suite_lifecycle` create real beads in the testbed's
# tracker, and `suite_routing` asserts that every bead the manifest routes is
# one the fixture declares. Read-only suites therefore run first. `--only NAME`
# is unaffected, and the driver rebuilds the testbed every invocation, so no
# ordering can leak across runs.
SUITES = {
    "routing": "suite_routing",
    "exit-codes": "suite_exit_codes",
    "qc": "suite_qc",
    "lifecycle": "suite_lifecycle",
    "promote": "suite_promote",
}


# Suites B and C, behind `--live` and off by default. They dispatch real agents
# — eight of them, minutes and dollars each — so adding them to the `e2e` stage
# would spend that on every invocation of a stage whose whole point is being
# cheap enough to run after any change under triage/scripts/.
# `orchestrator` last: it drives the whole skill and is the slowest
# single thing here, so a cheaper live failure surfaces first.
LIVE_SUITES = {"live": "suite_live", "orchestrator": "suite_orchestrator"}


def suites(live: bool) -> dict:
    """The suite name→module map for this run. `--live` is purely additive."""
    return {**SUITES, **LIVE_SUITES} if live else dict(SUITES)


def run_suite(name: str, module_name: str, testbed: harness.Testbed) -> int:
    """Failing case count for one suite. An unimportable suite counts as one."""
    try:
        module = importlib.import_module(module_name)
    except Exception:
        print(f"FAIL  {name}: suite did not import")
        traceback.print_exc()
        return 1
    failed = 0
    for case in module.CASES:
        try:
            case(testbed)
            print(f"PASS  {name}.{case.__name__}")
        except AssertionError as err:
            failed += 1
            print(f"FAIL  {name}.{case.__name__}: {err}")
        except Exception:
            failed += 1
            print(f"ERROR {name}.{case.__name__}")
            traceback.print_exc()
    return failed


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="run_e2e.py",
        description="Run the triage e2e suites against a generated testbed.")
    parser.add_argument("--only", choices=sorted(suites(live=True)),
                        help="run one suite instead of all of them")
    parser.add_argument("--live", action="store_true",
                        help="also run the live suites B and C (~8 real agents, "
                             "minutes and dollars each) — off by default")
    parser.add_argument("--keep", action="store_true",
                        help="leave the generated trees on disk even when the "
                             "run passes (a failing run always keeps them)")
    parser.add_argument("--reuse", action="store_true",
                        help="adopt the trees a previous run left instead of "
                             "rebuilding — what continues a live run that was "
                             "cut off, since a rebuild would destroy it")
    parser.add_argument("--root", type=Path,
                        help="where to build the testbed (default: the skills repo)")
    parser.add_argument("--skip-external", action="store_true",
                        help="drop demo and plugin from the invariant "
                             "sweep even when they are checked out here "
                             "(absent ones are skipped either way)")
    args = parser.parse_args(argv)
    chosen = suites(args.live)
    if args.only and args.only not in chosen:
        parser.error(f"--only {args.only} needs --live: it spends real agents")

    try:
        testbed = harness.reuse(args.root) if args.reuse else harness.build(args.root)
    except harness.Busy as err:
        print(f"FAIL  e2e.busy: {err}")
        return 2
    except harness.Missing as err:
        print(f"FAIL  e2e.nothing-to-reuse: {err}")
        return 2
    # Never a warning. Every suite below shells out to bd through a triage
    # script, and a database that resolves outside the testbed is a write into
    # a real tracker. Releasing on the way out matters as much as raising: an
    # assertion here used to leave the lock held, so one bad database wedged
    # every later run.
    #
    # Two questions, and the second is not implied by the first: where the
    # database is, and what is in it. An inherited clone of a real tracker sits
    # at exactly the path the first question expects — which is how it went
    # unseen for months — and `--reuse` can adopt trees an older generator
    # built before the seed that prevents it existed.
    try:
        harness.assert_db_inside(testbed)
        harness.assert_fixture_roster(testbed)
    except BaseException:
        harness.release(args.root)
        raise

    # The roster, and nothing sampled from it. An absent *internal* tree is a
    # failure, never a silent skip: `_shared/validators.md` is explicit that a
    # row which did not run is a failed row. An absent external repo is not a
    # failure — this repo travels between machines and the repos beside it do
    # not, and one that is not here cannot be written into.
    #
    # Asked after the build, which is what makes the testbed answerable here
    # too: nothing on disk at this point is a sandbox that did not build. The
    # before/after comparison this used to wrap the whole run in has moved to
    # the per-worker bracket in `live_dispatch`, because a window minutes wide
    # over trees the operator writes to cannot say who wrote in it.
    trees = suite_invariant.guarded_trees(args.root)
    absent = suite_invariant.missing(trees)
    if absent:
        for line in absent:
            print(f"FAIL  invariant.missing-tree: {line}")
        harness.teardown(testbed)
        harness.release(args.root)
        print(f"\nFAIL — {len(absent)} guarded tree(s) not found")
        return 1
    # Say out loud which guarded trees are not being watched. A guard that
    # silently stops guarding is worse than no guard, because the green output
    # still reads as proof.
    for tree in trees:
        if not tree.external:
            continue
        if args.skip_external:
            print(f"SKIP  invariant.{tree.name} (--skip-external)")
        elif not tree.path.exists():
            print(f"SKIP  invariant.{tree.name} (not on this machine)")

    selected = [args.only] if args.only else list(chosen)
    failed = 0
    crashed = False
    try:
        for name in selected:
            failed += run_suite(name, chosen[name], testbed)
    except BaseException:
        # `run_suite` catches per case, so reaching here means the driver
        # itself came apart — still a failure, and still evidence worth keeping.
        crashed = True
        raise
    finally:
        # A failing run keeps its trees. `--keep` existed already, but it had to
        # be asked for *before* the run, which is exactly when you do not yet
        # know you will need it — so the failures that most want the evidence
        # were the ones that destroyed it. A live suite spends real agents over
        # minutes, and the run directory it leaves behind is the only record of
        # what the agent actually did; a teardown on failure means the only way
        # to diagnose is to spend the run again. Measured: an orchestrator run
        # died on a usage limit mid-sweep and took its whole run directory with
        # it. Passing runs still clean up, so the trees are not left to rot.
        if args.keep or failed or crashed:
            print(f"KEPT  {testbed.root} — generated trees left for inspection")
        else:
            harness.teardown(testbed)
        # Released even when a case raised, or the next run inherits a lock
        # nobody holds and reports a busy testbed that is actually free.
        harness.release(args.root)

    print(f"\n{'FAIL' if failed else 'PASS'} — {failed} failing case(s)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
