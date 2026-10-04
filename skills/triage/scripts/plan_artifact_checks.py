#!/usr/bin/env python3
"""Check the rules that apply to a plan artifact as a whole.

The other half of the plan linter's rule set: everything that reads the folder
layout, the master plan, or the artifact's full text — file shape and naming,
the dependency graph, tracker intents, localization, and the investigation a
plan was built from. `plan_slice_checks.py` holds the per-slice half.

Four of these resolve a path or read a file, so they carry the linter's own
false-positive risk. Each one names what it could not resolve rather than
asserting the artifact is wrong, and localization reads its locale set off the
disk instead of a hardcoded list that would rot.

`--description` is checked for a plan *path* rather than for any `.md` token;
`DESC_PATH` carries the corpus case that forced the distinction.
"""

from __future__ import annotations

import hashlib
import re
import shlex
from pathlib import Path

from plan_markdown import ERROR, SKIP, WARN, Finding, body, cell, section, table

PLAN_NAME = re.compile(
    r"^[a-z0-9-]+_(feat|fix|refactor|tech|docs|epic)_[a-z0-9-]+(?:_[a-z0-9-]+)*$")
PHASE_FILE = re.compile(r"^phase_(\d+)_[a-z0-9]+(?:_[a-z0-9]+)*\.md$")
CREATE = re.compile(r"(?:\bbd|\{tracker_cli\})\s+create\b")
INVESTIGATION = re.compile(r"\*\*Investigation:\*\*\s*(\S+)")
NOTES_PATH = re.compile(
    r"(?:Plan|Slice|Master|Investigation):\s*(\S+)|(?<![\w/.-])(\S+\.md)\b")
# `--description` is a step checklist; a *plan path* must not sit in it. A
# label introducing a path, an absolute `.md` path, or a plan file name is
# that. A step that merely names a document — the real `skills-g57.2`
# description opens "Explore investigate SKILL.md Steps 2/4/5" — is not.
DESC_PATH = re.compile(
    r"(?:Plan|Slice|Master|Investigation):\s*\S*\.md\b"
    r"|(?<![\w.-])/\S+\.md\b"
    r"|(?<![\w.-])(?:plan|phase_\d+[a-z0-9_]*)\.md\b")
TOUCHES_STRINGS = re.compile(
    r"(?i)\.arb\b|Localizable\.strings|user-facing string")
TRIM = "`'\",.;:)]"
ARB_GLOBS = ("lib/l10n/app_*.arb", "*/lib/l10n/app_*.arb")
STRINGS_GLOBS = ("*.lproj/Localizable.strings", "*/*.lproj/Localizable.strings",
                 "*/*/*.lproj/Localizable.strings")


def dep_table(master_lines: list[str]):
    found = section(master_lines, "Dependency Table")
    if found is None:
        return None
    lo, hi = found
    return table(master_lines, lo, hi, ("phase", "depends", "slice"))


def check_shape(root: Path, master_text: str, slices: list) -> list[Finding]:
    out = []
    name = root.stem if root.is_file() else root.name
    if not PLAN_NAME.match(name):
        out.append(Finding("shape", ERROR, root.name, f"{name} — expected "
                           "{project}_{feat|fix|refactor|tech|docs|epic}_{short_name}"))
    if root.is_file():
        return out
    numbers = [n for n, _, _ in slices]
    if len(numbers) < 2:
        out.append(Finding("shape", ERROR, "plan.md", "single-phase plan written as "
                           f"a folder — {len(numbers)} phase file(s)"))
    if numbers and numbers != list(range(1, len(numbers) + 1)):
        out.append(Finding("shape", ERROR, "plan.md", "phase numbers are not 1..N — "
                           "observed " + ", ".join(str(n) for n in numbers)))
    for p in sorted(root.glob("*.md")):
        if p.name.startswith("phase") and not PHASE_FILE.match(p.name):
            out.append(Finding("shape", ERROR, p.name, "expected phase_{N}_{slug}.md"))
    found = dep_table(master_text.splitlines())
    if found is None:
        return out
    head, rows = found
    for j, cells in rows:
        for target in re.findall(r"\]\(([^)]+)\)", cell(head, cells, "slice")):
            if not (root / target).is_file():
                out.append(Finding("shape", ERROR, f"plan.md:{j + 1}",
                                   f"dependency-table slice link {target} does not exist"))
    if len(rows) != len(numbers):
        out.append(Finding("shape", ERROR, "plan.md#Dependency Table",
                           f"{len(rows)} dependency-table rows but "
                           f"{len(numbers)} phase files"))
    return out


def parse_deps(cell: str) -> set[int]:
    """Phase numbers a `Depends on` cell names.

    Only digits introduced by `Phase`/`Phases` count, so a real corpus cell
    reading `Phases 1–3 **and** plugin 0.18.0 published` yields {1,2,3}
    and not the version number's digits.
    """
    out: set[int] = set()
    for m in re.finditer(r"(?i)phases?\s+([0-9]+(?:\s*[,&–-]\s*[0-9]+)*)", cell):
        span = m.group(1)
        for r in re.finditer(r"(\d+)\s*[–-]\s*(\d+)", span):
            out.update(range(int(r.group(1)), int(r.group(2)) + 1))
        out.update(int(x.group(1))
                   for x in re.finditer(r"(?<![\d–-])(\d+)(?![\d–-])", span))
    return out


def cycle_path(graph: dict[int, set[int]]) -> list[int] | None:
    """The first cycle as a path, so the finding names it rather than asserting it."""
    state: dict[int, int] = {}
    stack: list[int] = []

    def walk(node: int) -> list[int] | None:
        state[node] = 1
        stack.append(node)
        for nxt in sorted(graph.get(node, ())):
            if state.get(nxt) == 1:
                return stack[stack.index(nxt):] + [nxt]
            if state.get(nxt) is None:
                hit = walk(nxt)
                if hit:
                    return hit
        stack.pop()
        state[node] = 2
        return None

    for node in sorted(graph):
        if state.get(node) is None:
            hit = walk(node)
            if hit:
                return hit
    return None


def check_dependencies(master_text: str, loc: str) -> list[Finding]:
    found = dep_table(master_text.splitlines())
    if found is None:
        return [Finding("dependencies", ERROR, loc, "## Dependency Table is missing")]
    head, rows = found
    out, graph, at = [], {}, {}
    for j, cells in rows:
        m = re.match(r"\**\s*(\d+)\s*:", cell(head, cells, "phase"))
        if not m:
            out.append(Finding("dependencies", WARN, f"{loc}:{j + 1}",
                               "phase cell is not `**N: name**`"))
            continue
        n = int(m.group(1))
        at[n] = j + 1
        graph[n] = parse_deps(cell(head, cells, "depends"))
    for n, deps in sorted(graph.items()):
        for d in sorted(deps):
            if d == n:
                out.append(Finding("dependencies", ERROR, f"{loc}:{at[n]}",
                                   f"phase {n} depends on itself"))
            elif d not in graph:
                out.append(Finding("dependencies", ERROR, f"{loc}:{at[n]}",
                                   f"phase {n} depends on phase {d}, "
                                   "which no row defines"))
    path = cycle_path(graph)
    if path:
        out.append(Finding("dependencies", ERROR, f"{loc}#Dependency Table",
                           "cycle: " + " -> ".join(str(x) for x in path)))
    return out


def invocations(text: str):
    """(line number, command) per `create` call, ending at a newline outside quotes."""
    for m in CREATE.finditer(text):
        quote, k = None, m.start()
        while k < len(text):
            ch = text[k]
            if quote:
                if ch == quote:
                    quote = None
            elif ch in "\"'":
                quote = ch
            elif ch == "\n":
                break
            k += 1
        yield text.count("\n", 0, m.start()) + 1, text[m.start():k]


def flag_value(cmd: str, flag: str) -> str | None:
    try:
        parts = shlex.split(cmd)
    except ValueError:
        return None
    for k, part in enumerate(parts):
        if part == flag and k + 1 < len(parts):
            return parts[k + 1]
        if part.startswith(flag + "="):
            return part[len(flag) + 1:]
    return None


def check_tracker_intents(text: str, loc: str) -> list[Finding]:
    """`--description` and `--notes` are separate flags with separate purposes
    (`plan/SKILL.md` <tracker-notes-requirement>); a task with no `--notes` is
    an orphan, and a relative path in `--notes` resolves to nothing later."""
    out = []
    for line, cmd in invocations(text):
        where = f"{loc}:{line}"
        notes, desc = flag_value(cmd, "--notes"), flag_value(cmd, "--description")
        if notes is None:
            out.append(Finding("tracker", ERROR, where,
                               "`create` carries no --notes — the task would be an orphan"))
        if desc and DESC_PATH.search(desc):
            out.append(Finding("tracker", ERROR, where,
                               "--description carries a file reference; plan paths "
                               "belong in --notes, which is a separate flag"))
        for m in NOTES_PATH.finditer(notes or ""):
            found = (m.group(1) or m.group(2) or "").strip(TRIM)
            if found and not found.startswith("/"):
                out.append(Finding("tracker", ERROR, where,
                                   f"--notes path is not absolute: {found}"))
    return out


def locales_on_disk(code_root: Path) -> set[str]:
    """Locale codes read off the tree, never from a list in here that would rot.

    Both a flat repo (`lib/l10n/`) and a nested package root
    (`{repo}/{package}/lib/l10n/`) are covered — a plan's project directory is
    routinely the outer of the two, and resolving only the flat case is what
    made Phase 3 report 106 live paths as missing.
    """
    found = set()
    for pat in ARB_GLOBS:
        found.update(p.stem.removeprefix("app_") for p in code_root.glob(pat))
    for pat in STRINGS_GLOBS:
        found.update(p.parent.name.removesuffix(".lproj")
                     for p in code_root.glob(pat))
    return found


def check_localization(master_text: str, blob: str, code_root: Path | None,
                       loc: str) -> list[Finding]:
    if code_root is None or not code_root.is_dir():
        return [Finding("localization", SKIP, loc,
                        f"no project code root at {code_root} — check does not apply")]
    locales = locales_on_disk(code_root)
    if not locales:
        return [Finding("localization", SKIP, loc, f"no locale files under {code_root}")]
    if not TOUCHES_STRINGS.search(blob):
        return []
    named = "\n".join(body(master_text.splitlines(), "Localization"))
    missing = [l for l in sorted(locales) if not re.search(
        r"(?<![A-Za-z0-9_-])" + re.escape(l) + r"(?![A-Za-z0-9_-])", named)]
    if missing:
        # A warning, not an error: whether a plan moves user-facing strings is
        # read out of prose, and prose negates. A measured corpus case reads
        # "No user-facing string changes, so no locale work" — the phrase that
        # proves the check does not apply is the phrase that triggers it.
        return [Finding("localization", WARN, loc,
                        f"{len(missing)} of {len(locales)} locales are not named in "
                        "## Localization: " + ", ".join(missing))]
    return []


def check_background(master_text: str, loc: str, expected: dict) -> list[Finding]:
    """A hash check that silently passes when nobody recorded an expectation is
    worse than no check, because it reads as evidence — so say it was skipped."""
    lines = master_text.splitlines()
    if section(lines, "Background") is None:
        return []
    claim = next((l.strip() for l in body(lines, "Background")
                  if "**Investigation:**" in l), "")
    m = INVESTIGATION.match(claim)
    if not m:
        # A warning: `## Background` is a natural heading, and a measured
        # corpus case uses it for a design spec. Only a section that claims an
        # investigation can be held to the investigation's own rules.
        return [Finding("background", WARN, loc,
                        "## Background carries no **Investigation:** line")]
    raw = m.group(1).strip(TRIM)
    if not raw.startswith("/"):
        return [Finding("background", ERROR, loc,
                        f"investigation path is not absolute: {raw}")]
    target = Path(raw)
    if not target.is_file():
        return [Finding("background", ERROR, loc,
                        f"investigation file does not exist: {raw}")]
    want = expected.get(str(target.resolve()), expected.get("*"))
    if want is None:
        return [Finding("background", SKIP, loc, f"no hash was recorded for "
                        f"{target.name} — the comparison was skipped, not passed")]
    got = hashlib.sha256(target.read_bytes()).hexdigest()
    if got != want:
        return [Finding("background", ERROR, loc,
                        f"{target.name} hashes {got}, recorded {want}")]
    return []
