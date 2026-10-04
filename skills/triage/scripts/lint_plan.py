#!/usr/bin/env python3
"""Fail a plan artifact that breaks the plan skill's own structural rules.

Tier 1 quality control for planning artifacts: an exit code, no LLM, no
writes. The script reads markdown, reads the filesystem for the things a plan
claims exist — slice files, locale files, the investigation it was built from
— and emits findings.

Severity carries the whole contract. `error` is the only severity that changes
the exit code, so a rule precise enough to fail a plan on is an `error` and a
heuristic over free prose is a `warn`; a linter that cries wolf gets switched
off. `skip` says a check did not apply and names why, because a check that
silently passes reads as evidence it never earned.

The rules live in `plan_artifact_checks.py` (whole-artifact) and
`plan_slice_checks.py` (per-slice); this module resolves the artifact on disk,
routes each half at it, and reports.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from plan_artifact_checks import (PHASE_FILE, check_background,
                                  check_dependencies, check_localization,
                                  check_shape, check_tracker_intents)
from plan_markdown import ERROR, SKIP, WARN, Finding
from plan_slice_checks import check_slice

EPILOG = """\
checks (error fails the run; warn and skip only report):
  shape          file layout, plan and phase file names, dependency-table links
  headers        slice H1, Parent plan / Beads task / Status, Prerequisites
  thresholds     <=8 implementation steps, the template's gate checkbox
                 excluded (error); <=5 files touched (warn)
  step-order     tests before implementation (error); skipped for a
                 documentation-only phase; step categories (warn)
  components     Component Decomposition table, responsibility (two verb
                 phrases, not any "and"), LOC, coupling
  dependencies   the dependency table parses, resolves, and is acyclic
  verification   names ./validate run phase-exit and invents no other gate
  tracker        bd create carries --notes, holding absolute paths, and no
                 plan path sits in --description
  localization   every locale found on disk is named when strings move (warn:
                 whether strings move is read out of prose, and prose negates)
  background     the investigation link exists and hashes as recorded

exit codes:
  0  no error-severity findings (warnings and skips alone do not fail)
  1  at least one error-severity finding
  2  usage or unreadable input only — never a bad artifact
"""


class Usage(Exception):
    """Raised for input the run cannot even read. Always exit 2."""


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise Usage(f"{path}: {exc}") from exc


def load_artifact(path: Path) -> tuple[str, list]:
    """(master text, [(phase number, path, text)]), the slices in phase order.

    A plain `.md` file is a single-phase plan: it is its own sole slice, and
    its phase number is None so the slice checks relax to that template.
    """
    if path.is_file():
        text = read(path)
        return text, [(None, path, text)]
    slices = []
    for p in path.glob("*.md"):
        m = PHASE_FILE.match(p.name)
        if m:
            slices.append((int(m.group(1)), p, read(p)))
    slices.sort()
    return read(path / "plan.md"), slices


def derive_code_root(path: Path) -> Path | None:
    """`{plans}/{project}/todo/x` -> the sibling `{project}` code repository."""
    parts = path.resolve().parts
    if "project_plans" not in parts:
        return None
    i = parts.index("project_plans")
    return Path(*parts[:i], parts[i + 1]) if i + 1 < len(parts) else None


def lint_one(path: Path, args, expected: dict) -> list[Finding]:
    if not path.exists():
        raise Usage(f"{path}: not a readable file or directory")
    if path.is_dir() and not (path / "plan.md").is_file():
        return [Finding("shape", WARN, path.name,
                        "no plan.md — not a plan artifact, skipped")]
    master_text, slices = load_artifact(path)
    loc = "plan.md" if path.is_dir() else path.name
    out = check_shape(path, master_text, slices)
    # Tracker intents are the master plan's business: `plan/SKILL.md` Step 8
    # creates the tasks from it, and a slice is told not to duplicate tracker
    # specifics. Scanning slices too reads a documented example `bd create` —
    # a test fixture quoted in prose — as an intent the plan is issuing.
    out += check_tracker_intents(master_text, loc)
    if path.is_dir():
        out += check_dependencies(master_text, loc)
    blob = master_text
    for n, p, text in slices:
        out += check_slice(text, p.name, n, args.max_loc)
        if p != path:              # a single-phase plan is its own sole slice
            blob += "\n" + text
    out += check_localization(master_text, blob,
                              args.project_root or derive_code_root(path), loc)
    out += check_background(master_text, loc, expected)
    if not path.is_dir():
        return out
    # A sweep over the whole corpus reports many files called `plan.md`, so a
    # finding has to name the artifact it belongs to.
    return [f._replace(location=f"{path.name}/{f.location}") for f in out]


def report(findings: list[Finding], as_json: bool) -> int:
    errors = [f for f in findings if f.severity == ERROR]
    warns = [f for f in findings if f.severity == WARN]
    skips = [f for f in findings if f.severity == SKIP]
    if as_json:
        print(json.dumps({"findings": [f._asdict() for f in findings],
                          "errors": len(errors), "warnings": len(warns),
                          "skipped": len(skips)}, ensure_ascii=False))
    else:
        for f in sorted(findings, key=lambda f: (f.location, f.check)):
            print(f"{f.severity.upper():<5}  {f.check:<13}  {f.location:<34}  {f.reason}")
        print(f"\n{len(errors)} error(s), {len(warns)} warning(s), {len(skips)} skipped")
    return 1 if errors else 0


def expectations(args) -> dict:
    """Recorded investigation hashes, by absolute path; `*` applies to any.

    An absent hash file yields none. `SKILL.md` Wave 5 passes
    `--investigation-hash-file` unconditionally, so the flag arrives for runs
    that never wrote one - a Wave 4 predating the file, or one that dispatched
    no investigation - and `references/ledger.md` holds that such a run has
    nothing to compare and is not thereby defective. A file that exists and
    will not read is still a `Usage` fault: that is an environment problem,
    not a plan with nothing recorded against it.
    """
    out = {"*": args.investigation_hash} if args.investigation_hash else {}
    path = Path(args.investigation_hash_file) if args.investigation_hash_file else None
    if path and path.exists():
        for line in read(path).splitlines():
            bits = line.split()
            if len(bits) >= 2:
                out[str(Path(bits[1]).resolve())] = bits[0]
    return out


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="lint_plan.py", epilog=EPILOG,
        description="Lint plan artifacts against the plan skill's structural rules.",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("paths", nargs="+", metavar="PATH",
                        help="a plan folder, or a single-phase plan .md file")
    parser.add_argument("--max-loc", type=int, default=300,
                        help="projected-LOC limit for a component (default: 300)")
    parser.add_argument("--project-root", type=Path,
                        help="code repository whose locale files define the locale "
                             "set (default: derived from the plan's own location)")
    parser.add_argument("--investigation-hash",
                        help="sha256 every linked investigation must hash to")
    parser.add_argument("--investigation-hash-file", type=Path,
                        help="file of `<sha256>  <absolute path>` lines")
    parser.add_argument("--json", action="store_true", dest="as_json",
                        help="emit one JSON object instead of the human table")
    args = parser.parse_args(argv)

    findings: list[Finding] = []
    try:
        expected = expectations(args)
        for raw in args.paths:
            findings += lint_one(Path(raw), args, expected)
    except Usage as exc:
        print(f"lint_plan: {exc}", file=sys.stderr)
        return 2
    return report(findings, args.as_json)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
