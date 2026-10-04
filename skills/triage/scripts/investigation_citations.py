#!/usr/bin/env python3
"""Verify that an artifact's `file:line` citations point at what it claims.

Fabricated evidence is the number one failure mode of autonomous
investigation, and it is the one failure mode a machine can settle: the file
either exists at that line and carries the quoted text, or it does not. This
module reads the cited files and nothing else — no writes, no model.

`lint_investigation.py` is the caller; `Finding` lives here because this is
the lower module, so the CLI imports downward and nothing imports back.
"""

from __future__ import annotations

import collections
import os
import re
from pathlib import Path

Finding = collections.namedtuple("Finding", "severity code artifact line detail")

WINDOW = 3            # citation quote tolerance, in lines
MIN_QUOTE_CHARS = 8   # shorter quotes match anything and prove nothing
SKIP_DIRS = {".git", "build", ".dart_tool", "node_modules", "Pods", ".beads"}

# The dotted extension before the colon is what keeps log timestamps
# (21:41:27), version strings (^0.17.0) and symbol references
# (EpubPage.ts:getLocatorFragments) out of the citation set.
#
# The extension must **start with a letter**, which is what keeps a decimal
# ratio out of it. `4.5:1` and `18.88:1` otherwise parse as `path.ext:line`
# and report the fraction as a file that does not exist — measured on a live
# triage run, where an investigation into theme contrast quoted WCAG ratios
# throughout and every one came back `citation-file-missing`. Worse than the
# noise: a ratio earlier on the line consumed the text a real citation beside
# it needed, so the genuine one failed too. No source extension begins with a
# digit; every decimal fraction does.
CITATION = re.compile(
    r"(?P<path>[A-Za-z0-9_./-]+\.[A-Za-z][A-Za-z0-9]{0,5})"
    r":(?P<start>\d+)(?:-(?P<end>\d+))?")

INLINE_CODE = re.compile(r"`([^`]+)`")

# The gap between a citation and the text that follows it is what decides
# whether that text is a quote. A closed vocabulary is the structure;
# adjacency is not — backticked prose beside a citation is commentary.
QUOTE_LEAD = re.compile(
    r"^[\s`*_~()\[\]:;,.—–-]*"
    r"(?:the\s+|that\s+|which\s+)?(?:line\s+|text\s+|code\s+)?"
    r"(?:quotes?|quoted|quoting|reads|read|says|verbatim)"
    r"[\s`*_~()\[\]:;,.—–-]*$", re.IGNORECASE)

# A nested package is real structure, not proximity: it declares itself with a
# manifest. "One level down" alone would turn resolution into "search anywhere".
PACKAGE_MARKERS = ("pubspec.yaml", "package.json", "pyproject.toml", "setup.py",
                   "Cargo.toml", "go.mod", "build.gradle", "build.gradle.kts",
                   "Package.swift", "Gemfile", "composer.json")


def candidate_roots(repo_root: Path) -> list[Path]:
    """`repo_root`, then every first-level directory that declares itself a package."""
    roots = [repo_root]
    try:
        children = sorted(p for p in repo_root.iterdir() if p.is_dir())
    except OSError:
        return roots
    for child in children:
        if child.name in SKIP_DIRS or child.name.startswith("."):
            continue
        if any((child / marker).is_file() for marker in PACKAGE_MARKERS):
            roots.append(child)
    return roots


def searched(roots: list[Path]) -> str:
    """Where a cited path was looked for, said in one phrase."""
    nested = len(roots) - 1
    if not nested:
        return str(roots[0])
    return f"{roots[0]} and {nested} nested package root{'' if nested == 1 else 's'}"


def basename_index(root: Path, cache: dict) -> dict[str, list[Path]]:
    """Filename -> paths under `root`, walked once per root and memoised."""
    if root not in cache:
        index = collections.defaultdict(list)
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for name in filenames:
                index[name].append(Path(dirpath) / name)
        cache[root] = index
    return cache[root]


def quote_for(line: str, cite_end: int) -> str | None:
    """The quote an artifact explicitly binds to a citation on the same line."""
    # Only the first span past the citation can be its quote; a later one is
    # already separated from the citation by that span's own prose.
    after = (m for m in INLINE_CODE.finditer(line) if m.start(1) >= cite_end)
    span = next(after, None)
    if span is None:
        return None
    if not QUOTE_LEAD.match(line[cite_end:span.start(0)]):
        return None                    # commentary, not a quote — stay silent
    text = span.group(1).strip()
    if CITATION.fullmatch(text):
        return None                    # a second citation is never a quote
    return text if len(text) >= MIN_QUOTE_CHARS else None


def fenced_quote(lines: list[str], n: int, fences: dict[int, list[str]]) -> str | None:
    """First substantial line of a fenced block bound to the citation on line `n`."""
    for nxt in range(n + 1, min(n + 4, len(lines) + 1)):
        if nxt in fences:
            bodies = (" ".join(body.split()) for body in fences[nxt])
            return next((t for t in bodies if len(t) >= MIN_QUOTE_CHARS), None)
        if lines[nxt - 1].strip():     # prose intervened — nothing is bound
            return None
    return None


def source_lines(target: Path) -> list[str]:
    try:
        return target.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []


def resolve(rel: str, repo_root: Path, roots: list[Path],
            cache: dict) -> tuple[Path | None, int]:
    """(file, candidate count) for one cited path. 0 is missing, >1 ambiguous."""
    if "/" in rel:
        # dict.fromkeys dedupes: an absolute `rel` swallows every root,
        # so a plain list would count the same file once per root.
        hits = list(dict.fromkeys(
            root / rel for root in roots if (root / rel).is_file()))
    else:
        hits = basename_index(repo_root, cache).get(rel, [])
    return (hits[0] if len(hits) == 1 else None, len(hits))


def check_citations(path: Path, lines: list[str], repo_root: Path, cache: dict,
                    fences: dict[int, list[str]] | None = None) -> list[Finding]:
    """Findings for every citation in `lines`, which must already be fence-stripped."""
    out, roots = [], candidate_roots(repo_root)
    fences = fences or {}
    for n, line in enumerate(lines, 1):
        for m in CITATION.finditer(line):
            rel = m.group("path")
            target, matches = resolve(rel, repo_root, roots, cache)
            if matches > 1:
                out.append(Finding("warning", "citation-ambiguous", path, n,
                                   f"{rel} — {matches} files match under {repo_root}"))
                continue
            if target is None:
                out.append(Finding("error", "citation-file-missing", path, n,
                                   f"{rel} — not found under {searched(roots)}"))
                continue
            if "/" not in rel:
                # It resolves today, and to a *different* file the day a second
                # file of that name lands. Say so, then check it anyway: the
                # citation did resolve, so the quote below is still worth reading.
                out.append(Finding("warning", "citation-bare-filename", path, n,
                                   f"{rel} — cite the repo-relative path "
                                   f"({target.relative_to(repo_root)})"))
            src = source_lines(target)
            start = int(m.group("start"))
            end = int(m.group("end") or start)
            if start < 1 or end > len(src):
                out.append(Finding("error", "citation-line-out-of-range", path, n,
                                   f"{rel}:{start} — file has {len(src)} lines"))
                continue
            quote = quote_for(line, m.end())
            if quote is None and QUOTE_LEAD.match(line[m.end():]):
                quote = fenced_quote(lines, n, fences)
            if quote is None:
                continue
            want = " ".join(quote.split())
            lo, hi = max(1, start - WINDOW), min(len(src), end + WINDOW)
            hits = [i for i in range(lo, hi + 1) if want in " ".join(src[i - 1].split())]
            if not hits:
                out.append(Finding("error", "citation-quote-absent", path, n,
                                   f"{rel}:{start} — quote absent from lines {lo}-{hi}"))
            elif not any(start <= i <= end for i in hits):
                out.append(Finding("warning", "citation-quote-offset", path, n,
                                   f"{rel}:{start} — quote found at line {hits[0]}"))
    return out
