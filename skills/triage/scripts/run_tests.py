#!/usr/bin/env python3
"""Run every triage unit test file. Exit 1 if any of them failed.

Two directories, both one level deep and relative to this file, so
`validators.conf` can call it from the repo root and neither `fixtures/` nor a
generated testbed is ever walked.

`../e2e` is here because its helper modules — the oracles, the worker-report
reader, the dispatch bracket, the invariant sweep — are pure functions with
ordinary unit tests, and they were running under no stage at all: this file
used to glob only its own directory, and the `e2e` stage runs the *suites*,
not their tests. Roughly a hundred cases were therefore green only when
somebody remembered to run them by hand. They cost under three seconds
together, so they belong in `phase-exit` with everything else fast.

What does NOT belong here is `run_e2e.py` itself: it builds three real `bd`
databases and takes minutes. That is the `e2e` stage's job, and keeping the
split is what stops `phase-exit` becoming the slow one.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    here = Path(__file__).resolve().parent
    tests = sorted(here.glob("test_*.py"))
    tests += sorted((here.parent / "e2e").glob("test_*.py"))
    failed = 0
    for test in tests:
        # Each file runs in its own directory: both suites put their imports
        # on `sys.path` relative to themselves.
        proc = subprocess.run([sys.executable, str(test)], cwd=str(test.parent))
        passed = proc.returncode == 0
        # Only the second directory is prefixed. A bare name is unambiguous
        # for this directory, and the fixtures in `test_run_tests.py` live in
        # temp directories whose names would make the label unstable.
        label = (test.name if test.parent == here
                 else f"{test.parent.name}/{test.name}")
        print(f"{'PASS' if passed else 'FAIL'}  {label}")
        if not passed:
            failed += 1
    print(f"\n{len(tests) - failed}/{len(tests)} test files passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
