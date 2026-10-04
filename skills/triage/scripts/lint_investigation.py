#!/usr/bin/env python3
"""Fail an investigation artifact that cannot be trusted, without an LLM.

Tier 1 of the triage skill's quality control. The script reads artifact text,
the source files that artifact cites, and one read-only `git status
--porcelain`. It never calls a model and never writes anything.

Citation resolution — the check worth the most — lives in
`investigation_citations.py`; everything here reads artifact text.

**Why this is one module:** 300 code lines by `run_arch_gate.py`'s count, plus
26 of doc prose — at the 300 signal, not over it, so no waiver is owed. Every
check here
reads the same artifact text through the same two helpers (`header_values`,
`section_bounds`), which is what makes the file cohesive rather than merely
long. Two candidate splits were considered and both fail the Meaningfulness
Test: an `investigation_header` module would have to carry `check_filename` and
`check_versions` too, which are not header checks — a grouping by leftover, not
by responsibility — and splitting those three apart instead produces exactly
the single-caller satellites the principles reject. The one genuinely separable
responsibility, citation resolution with its repo indexing and file I/O, is
already `investigation_citations.py`.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from investigation_citations import Finding, check_citations

BASE_SECTIONS = ["Problem", "Execution Chain", "Root Cause",
                 "Supporting Evidence", "Ruled Out"]
SECTIONS = BASE_SECTIONS + ["Approved Fix"]
PARK_SECTIONS = BASE_SECTIONS + ["Open Question"]
FIX_SUBSECTIONS = ["Summary:", "What changes:",
                   "Why this fix is correct:", "Side effects checked:"]
HEADER_FIELDS = ["Status:", "Date:", "Project:", "Beads task:"]

# An investigation has four legal outcomes, and the Status field is what says
# which one this artifact is. The first two carry a fix and differ only in who
# has approved it; the last two are parks.
#
# The parks exist because a park is a **success** outcome —
# `triage/references/qc-gates.md` §7 — and with one legal status the linter
# could not say so. A correctly parked artifact failed on its status and on
# four absent fix subsections; Wave 5 gates the reviewer on tier 1, so it could
# never reach one. The only way through was to claim FIX APPROVED, an approval
# `_shared/autonomous-mode.md` §A forbids a worker to grant itself. That made
# self-approval the cheapest path out of an honest park, which is the opposite
# of what tier 1 is for.
#
# FIX PROPOSED closes the same hole one step further along. An interactive
# `investigate` writes its artifact after the user answers Gate 2, so FIX
# APPROVED is true when written; a delegated run has that gate answered by a
# verdict *on the artifact*, so the artifact comes first and the outcome every
# non-parking worker reaches had no status it was allowed to write. Neither park
# fits — both say the fix is undetermined, and it is determined and merely
# unapproved. Measured on the first full run: it blocked all nine beads.
STATUS_VALUE = "ROOT CAUSE CONFIRMED — FIX APPROVED"
STATUS_FIX_PROPOSED = "ROOT CAUSE CONFIRMED — FIX PROPOSED"
STATUS_FIX_PARKED = "ROOT CAUSE CONFIRMED — FIX PARKED"
STATUS_CAUSE_UNPROVEN = "ROOT CAUSE UNPROVEN — PARKED"
# The section set follows the split, not the individual status: both fix
# statuses require `## Approved Fix` and its four subsections, because that
# section IS the `<fix-format>` Gate 2 payload the verdict rules on. Naming the
# section for the approval state instead would fork it in two and break every
# reader of it, `plan` Step 2's investigation shortcut first.
FIX_STATUSES = (STATUS_VALUE, STATUS_FIX_PROPOSED)
PARK_STATUSES = (STATUS_FIX_PARKED, STATUS_CAUSE_UNPROVEN)
STATUS_VALUES = (*FIX_STATUSES, *PARK_STATUSES)

PLACEHOLDERS = {"none", "n/a", "na", "nothing", "tbd", "not applicable"}

ASSUMPTION = re.compile(
    r"\b(probably|likely|presumably|seems|appears to|might be|"
    r"should be|i think|i believe|my guess)\b", re.IGNORECASE)

HEADER_FIELD = re.compile(r"^\*\*([^*]+:)\*\*\s*(.*)$")

FENCE = re.compile(r"^\s*(`{3,}|~{3,})")

FILENAME = re.compile(
    r"^(?P<project>[a-z0-9-]+)_invest_"
    r"(?P<short>[a-z0-9]+(?:-[a-z0-9]+)*"
    r"(?:_(?!v[2-9]\d*(?:\.md)?$)[a-z0-9]+(?:-[a-z0-9]+)*){2,4})"
    r"(?:_v(?P<version>[2-9]\d*))?\.md$")

EPILOG = """\
finding codes (error fails the run, warning reports it):
  error    section-missing, fix-subsection-missing, park-question-missing,
           ruled-out-empty, citation-file-missing, citation-line-out-of-range,
           citation-quote-absent, assumption-language, header-field-missing,
           header-status-wrong, header-date-malformed, filename-convention,
           filename-location, prior-version-missing, source-tree-dirty,
           source-tree-unverified

an artifact has four legal Status values. "ROOT CAUSE CONFIRMED — FIX APPROVED"
and "ROOT CAUSE CONFIRMED — FIX PROPOSED" both require the four Approved Fix
subsections and differ only in whether the fix has been approved yet — a
delegated worker writes the second, since its Gate 2 is answered by a verdict on
the artifact. "ROOT CAUSE CONFIRMED — FIX PARKED" and "ROOT CAUSE UNPROVEN —
PARKED" require an ## Open Question section carrying a real question instead; a
park is a success outcome, not a failed investigation.
  warning  citation-quote-offset, citation-ambiguous, citation-bare-filename,
           filename-project-mismatch, prior-version-touched,
           source-tree-unchecked

a citation quote is checked only where the artifact marks one: a quote/reads/says
lead-in between the citation and a backticked span on its own line, or a lead-in
ending the line and a fenced block right below. Backticked prose beside a citation
is commentary and is not checked. Cited paths resolve against the repo root and
against every first-level directory that carries a package manifest. A bare
filename still resolves, through a repo-wide index, but it is reported: it will
silently resolve to a different file the day a second file of that name lands.

exit codes:
  0  no error-severity findings (warnings alone do not fail)
  1  at least one error-severity finding
  2  usage or unreadable input only — never a bad artifact
"""


class Usage(Exception):
    """Raised for input the run cannot even read. Always exit 2."""


def strip_fences(text: str) -> tuple[list[str], dict[int, list[str]]]:
    """Blank out fenced blocks, keeping line numbers; return the bodies by opening line."""
    out, fences, fence, start = [], {}, None, 0
    for i, raw in enumerate(text.splitlines(), 1):
        marker = FENCE.match(raw)
        char = marker.group(1)[0] if marker else None
        if fence is None:
            if char is None:
                out.append(raw)
                continue
            fence, start = char, i     # only this char can close the block
            fences[i] = []
        elif char == fence:
            fence = None
        else:
            fences[start].append(raw)
        out.append("")                 # markers and bodies alike blank out
    return out, fences


def header_values(text: str) -> dict[str, tuple[int, str]]:
    """Bold `**Field:** value` pairs above the first `---`, by field name."""
    lines = text.splitlines()
    end = next((i for i, l in enumerate(lines) if l.strip() == "---"), len(lines))
    values = {}
    for i, line in enumerate(lines[:end]):
        m = HEADER_FIELD.match(line.strip())
        if m:
            values[m.group(1).strip()] = (i + 1, m.group(2).strip())
    return values


def section_bounds(lines: list[str], name: str) -> tuple[int, int] | None:
    """(heading index, first index past the body) for a `## name` section."""
    pat = re.compile(r"^##\s+" + re.escape(name) + r"\b", re.IGNORECASE)
    for i, line in enumerate(lines):
        if pat.match(line):
            for j in range(i + 1, len(lines)):
                if re.match(r"^#{1,6}\s", lines[j]):
                    return i, j
            return i, len(lines)
    return None


def status_of(text: str) -> str:
    """The artifact's Status value, whitespace-normalised. `""` when absent."""
    n, value = header_values(text).get("Status:", (0, ""))
    return " ".join(value.split())


def check_sections(path: Path, text: str) -> list[Finding]:
    lines = text.splitlines()
    out, bounds = [], {}
    parked = status_of(text) in PARK_STATUSES
    for name in (PARK_SECTIONS if parked else SECTIONS):
        found = section_bounds(lines, name)
        if found is None:
            out.append(Finding("error", "section-missing", path, 0, f"## {name}"))
        else:
            bounds[name] = found
    if parked and "Open Question" in bounds:
        # A question, not a summary of the defect. qc-gates §7 draws the line:
        # "the root cause is unproven" sends a human back to re-read the
        # artifact, while a real question can be answered from where they
        # stand. A question mark is the cheapest honest test of that.
        i, j = bounds["Open Question"]
        if "?" not in "\n".join(lines[i + 1:j]):
            out.append(Finding("error", "park-question-missing", path, i + 1,
                               "a park states the question a human must answer"))
    if "Approved Fix" in bounds:
        i, j = bounds["Approved Fix"]
        blob = "\n".join(lines[i:j])
        for sub in FIX_SUBSECTIONS:
            if f"**{sub}**" not in blob:
                out.append(Finding("error", "fix-subsection-missing", path,
                                   i + 1, f"**{sub}**"))
    if "Ruled Out" in bounds:
        i, j = bounds["Ruled Out"]
        words = re.sub(r"[^a-z0-9/ ]+", " ", " ".join(lines[i + 1:j]).lower()).split()
        if not words or " ".join(words) in PLACEHOLDERS:
            out.append(Finding("error", "ruled-out-empty", path, i + 1,
                               "no competing hypothesis was eliminated"))
    return out


def check_language(path: Path, lines: list[str]) -> list[Finding]:
    """Findings for `lines`, which must already be fence-stripped."""
    out = []
    for n, line in enumerate(lines, 1):
        for m in ASSUMPTION.finditer(line):
            out.append(Finding("error", "assumption-language", path, n,
                               f'"{m.group(1)}"'))
    return out


def check_header(path: Path, text: str) -> list[Finding]:
    out, values = [], header_values(text)
    for field in HEADER_FIELDS:
        if field not in values:
            out.append(Finding("error", "header-field-missing", path, 0, f"**{field}**"))
        elif not values[field][1]:
            out.append(Finding("error", "header-field-missing", path,
                               values[field][0], f"**{field}** has no value"))
    if "Status:" in values:
        n, value = values["Status:"]
        if " ".join(value.split()) not in STATUS_VALUES:
            out.append(Finding("error", "header-status-wrong", path, n, f'"{value}"'))
    if "Date:" in values:
        n, value = values["Date:"]
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            out.append(Finding("error", "header-date-malformed", path, n, f'"{value}"'))
    return out


def check_filename(path: Path, root: Path | None, text: str) -> list[Finding]:
    out = []
    named = FILENAME.match(path.name)
    if not named:
        out.append(Finding("error", "filename-convention", path, 0,
                           f"{path.name} — expected {{project}}_invest_"
                           "{3-5_words}[_vN].md"))
    if root:
        expected = root.resolve()
        misplaced = path.parent != expected
    else:
        expected = "a directory named investigations"
        misplaced = path.parent.name != "investigations"
    if misplaced:
        out.append(Finding("error", "filename-location", path, 0,
                           f"{path.parent} — expected {expected}"))
    if named:
        stated = header_values(text).get("Project:", (0, ""))[1].split()
        first = stated[0].lower() if stated else ""
        if first and first != named.group("project"):
            out.append(Finding("warning", "filename-project-mismatch", path, 0,
                               f"filename says {named.group('project')}, "
                               f"header says {first}"))
    return out


def check_versions(path: Path) -> list[Finding]:
    named = FILENAME.match(path.name)
    if not named or not named.group("version"):
        return []
    version = int(named.group("version"))
    stem = path.name[: -len(f"_v{version}.md")]
    out = []
    for prior_n in range(1, version):
        prior = path.parent / (f"{stem}.md" if prior_n == 1 else f"{stem}_v{prior_n}.md")
        if not prior.is_file():
            out.append(Finding("error", "prior-version-missing", path, 0,
                               f"{prior.name} — prior investigations are evidence"))
        elif prior.stat().st_mtime > path.stat().st_mtime:
            out.append(Finding("warning", "prior-version-touched", path, 0,
                               f"{prior.name} is newer than {path.name}"))
    return out


def check_source_tree(repo_root: Path) -> list[Finding]:
    try:
        proc = subprocess.run(["git", "-C", str(repo_root), "status", "--porcelain"],
                              capture_output=True, text=True)
    except OSError as exc:
        return [Finding("error", "source-tree-unverified", repo_root, 0, str(exc))]
    if proc.returncode != 0:
        detail = proc.stderr.strip().splitlines()
        return [Finding("error", "source-tree-unverified", repo_root, 0,
                        detail[0] if detail else f"git exited {proc.returncode}")]
    out = []
    for line in proc.stdout.splitlines():
        rel = line[3:].split(" -> ")[-1].strip().strip('"')
        if line.startswith("??") or rel.startswith(("project_plans/", ".beads/")):
            continue
        out.append(Finding("error", "source-tree-dirty", repo_root, 0, rel))
    return out


def expand(paths: list[str]) -> list[Path]:
    found = []
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            found += sorted(p.glob("*.md"))
        elif p.is_file():
            found.append(p)
        else:
            raise Usage(f"{raw}: not a readable file or directory")
    return sorted({p.resolve() for p in found})


def derive_repo(artifact: Path) -> Path | None:
    """`{plans}/{project}/investigations/x.md` -> the sibling `{project}` repo."""
    parents = artifact.parents
    if len(parents) < 4:
        return None
    return parents[3] / parents[1].name


def plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def report(findings: list[Finding], count: int, as_json: bool) -> int:
    errors = [f for f in findings if f.severity == "error"]
    warnings = [f for f in findings if f.severity == "warning"]
    if as_json:
        print(json.dumps({
            "artifacts": count, "errors": len(errors), "warnings": len(warnings),
            "findings": [{"severity": f.severity, "code": f.code,
                          "artifact": str(f.artifact), "line": f.line,
                          "detail": f.detail} for f in findings],
        }, ensure_ascii=False))
    else:
        print(f"lint_investigation: {plural(count, 'artifact')}, "
              f"{plural(len(errors), 'error')}, {plural(len(warnings), 'warning')}")
        for f in sorted(findings, key=lambda f: (str(f.artifact), f.line, f.code)):
            where = f"{f.artifact.name}:{f.line}" if f.line else f.artifact.name
            level = "ERROR" if f.severity == "error" else "WARN"
            print(f"{level:<5}  {where:<34}  {f.code:<28}  {f.detail}")
    return 1 if errors else 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="lint_investigation.py", epilog=EPILOG,
        description="Lint investigation artifacts mechanically — no LLM, no writes.",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("paths", nargs="+", metavar="PATH",
                        help="an artifact, or a directory whose *.md files are all linted")
    parser.add_argument("--root", type=Path,
                        help="directory artifacts must live in (default: a parent "
                             "named investigations)")
    parser.add_argument("--repo", type=Path,
                        help="project repo root for citation and source-tree checks "
                             "(default: derived from the artifact's own location)")
    parser.add_argument("--no-tree-check", action="store_true",
                        help="skip the source-tree check and report source-tree-unchecked")
    parser.add_argument("--json", action="store_true", dest="as_json",
                        help="emit one JSON object instead of the human table")
    args = parser.parse_args(argv)

    findings: list[Finding] = []
    cache: dict = {}
    roots: list[Path] = []
    try:
        artifacts = expand(args.paths)
        for artifact in artifacts:
            try:
                text = artifact.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                raise Usage(f"{artifact}: {exc}") from exc
            repo = args.repo.resolve() if args.repo else derive_repo(artifact)
            if repo is None or not repo.is_dir():
                raise Usage(f"{artifact}: repo root {repo} does not exist")
            if repo not in roots:
                roots.append(repo)
            prose, fences = strip_fences(text)
            findings += check_sections(artifact, text)
            findings += check_language(artifact, prose)
            findings += check_citations(artifact, prose, repo, cache, fences)
            findings += check_header(artifact, text)
            findings += check_filename(artifact, args.root, text)
            findings += check_versions(artifact)
    except Usage as exc:
        print(f"lint_investigation: {exc}", file=sys.stderr)
        return 2

    for repo in roots:
        if args.no_tree_check:
            findings.append(Finding("warning", "source-tree-unchecked", repo, 0,
                                    f"{repo} — skipped by request"))
        else:
            findings += check_source_tree(repo)
    return report(findings, len(artifacts), args.as_json)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
