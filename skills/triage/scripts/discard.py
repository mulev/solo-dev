#!/usr/bin/env python3
"""Delete exactly one staged triage run, and refuse anything else.

`promote` — the reversible half of the pair — is an eight-step fail-closed
script. `discard`, the half that actually deletes, was a paragraph in
`triage/SKILL.md` that an orchestrator had to remember. That asymmetry is what
this file removes: the command that destroys is now the one with the guards.

Two refusals, each for a loss that no rerun undoes:

* a `--run-id` matching zero or many runs — resolving it is not a guess;
* a path that is a symlink, so a link planted in the staging directory cannot
  redirect the delete somewhere real — reported as a symlink, not as "outside
  the runs directory", because the two need different fixes.

**Everything else is refused one level down, by `resolve_run`,** and this file
deliberately does not re-check it. `resolve_run` returns a directory that is a
direct child of the runs directory and is not `promoted/`, so guards here for
"the runs directory itself", "not directly inside", and "already promoted" were
all unreachable. Each was removed rather than kept: an unreachable guard cannot
fail, so it reads as protection while providing none, and a reader who trusts
it stops looking for the check that actually holds. A promoted run therefore
exits 2 as "matches 0 runs", which is the honest message — promotion is past
the point where deleting is an undo.

The symlink check stays because it is the one case `resolve_run` lets through:
`is_dir()` follows a link, so a link planted in staging resolves as a run.

Exit 0 discarded, 1 refused, 2 usage or environment error.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import staged_run

EPILOG = """\
discard is a complete undo only because promote has not run: a staged run has
written nothing outside its own directory. A run under promoted/ is past that
point and is not a discard candidate.
"""


def _refuse(reason: str) -> tuple:
    return 1, f"discard: refused — {reason}"


def plan(runs_dir, run_id: str) -> tuple:
    """Resolve the target and decide. Returns `(code, message, path)`.

    Pure apart from the filesystem reads: nothing is deleted here, so the
    decision can be tested and printed before anything is destroyed.
    """
    root = Path(runs_dir)
    try:
        run = staged_run.resolve_run(root, run_id)
    except staged_run.Usage as exc:
        return 2, f"discard: {exc}", None

    if run.is_symlink():
        return (*_refuse(f"{run} is a symlink"), None)
    return 0, f"discard: {run}", run


def main(argv: list) -> int:
    parser = argparse.ArgumentParser(
        prog="discard.py", epilog=EPILOG,
        description="Delete exactly one staged triage run.",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run-id", required=True,
                        help="run directory name, or its short random suffix")
    parser.add_argument("--runs-dir", default=".",
                        help="the project's staging folder")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the absolute path and delete nothing")
    args = parser.parse_args(argv)

    code, message, run = plan(args.runs_dir, args.run_id)
    print(message, file=sys.stderr if code else sys.stdout)
    if code or run is None:
        return code
    if args.dry_run:
        print("discard: --dry-run, nothing deleted")
        return 0
    shutil.rmtree(run)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
