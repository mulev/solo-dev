#!/usr/bin/env python3
"""Architecture gate runner — automated checks only.

Counts one file's code lines — non-blank, non-comment, and for Python not
docstring prose — and detects the re-export shim anti-pattern (file body is
overwhelmingly `export` / barrel statements, created to launder a parent
file's import count). The LOC field carries a `+{n}doc` suffix when the file
spends lines on doc prose, so a 300-line module and a 100-line module with a
200-line explanation do not report the same number.

Coupling (DEPS), SRP, DRY, and testability are model/human judgments and
are emitted as MANUAL in the banner — the executor records the foreign-
module enumeration and reasoning in the working file's `## Architecture
Gate Results` block.

Usage:
    python run_arch_gate.py <file> [--max-loc N] [--shim-ratio R]

Exit:
    0  all automated checks PASS
    1  any automated check FAIL (LOC over limit or re-export shim detected)
    2  file not found / unreadable
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

LINE_COMMENT_PREFIXES = {
    ".py": ("#",),
    ".rb": ("#",),
    ".sh": ("#",),
    ".dart": ("//", "///"),
    ".kt": ("//", "///"),
    ".kts": ("//", "///"),
    ".swift": ("//", "///"),
    ".ts": ("//",),
    ".tsx": ("//",),
    ".js": ("//",),
    ".jsx": ("//",),
    ".go": ("//",),
    ".rs": ("//",),
    ".java": ("//",),
    ".c": ("//",),
    ".cc": ("//",),
    ".cpp": ("//",),
    ".h": ("//",),
    ".hpp": ("//",),
    ".m": ("//",),
    ".mm": ("//",),
}

# Languages whose comments are line-only. Scanning one of them for `/* */`
# reads a string literal as a comment: a `/*` inside a Python blob or docstring
# opens a block nothing closes, and the rest of the file vanishes from the
# count. Unknown suffixes keep the scanner — the fallback prefixes include
# `//`, so a C-family file is the safer assumption.
LINE_COMMENTS_ONLY = frozenset({".py", ".rb", ".sh"})

RE_EXPORT_PATTERNS = {
    ".dart": re.compile(r"^\s*export\s+['\"]"),
    ".ts": re.compile(r"^\s*export\s+(\*|\{|type\s+\{)"),
    ".tsx": re.compile(r"^\s*export\s+(\*|\{|type\s+\{)"),
    ".js": re.compile(r"^\s*export\s+(\*|\{)"),
    ".jsx": re.compile(r"^\s*export\s+(\*|\{)"),
    ".py": re.compile(r"^\s*from\s+\S+\s+import\s+\*"),
}


def read_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


def prose_lines(path: Path) -> frozenset[int]:
    """Line numbers this Python file spends on docstring prose.

    A docstring is a string literal standing as the first statement of a
    module, class, or function (PEP 257) — neither a comment nor `/*`
    delimited, so `iter_code_lines` cannot recognise one and charges every
    line of it to code. Only the lines that filter would otherwise have
    counted are returned, so `len()` is the figure the banner prints.

    Anything this cannot read returns an empty set — a non-Python suffix, a
    py2 or half-edited file, a file carrying null bytes. Those count exactly
    as they did before this existed, because a gate that crashes on a
    malformed file is worse than one that overcounts it.
    """
    if path.suffix != ".py":
        return frozenset()
    lines = read_lines(path)
    try:
        tree = ast.parse("\n".join(lines))
    except (SyntaxError, ValueError):
        return frozenset()
    out: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                 ast.AsyncFunctionDef)):
            continue
        if ast.get_docstring(node, clean=False) is None:
            continue
        doc = node.body[0]
        for lineno in range(doc.lineno, doc.end_lineno + 1):
            text = lines[lineno - 1].strip()
            if text and not text.startswith("#"):
                out.add(lineno)
    return frozenset(out)


def iter_code_lines(path: Path, skip: frozenset[int]):
    """Yield each non-blank, non-comment, non-prose line (stripped)."""
    prefixes = LINE_COMMENT_PREFIXES.get(path.suffix, ("#", "//"))
    blocks = path.suffix not in LINE_COMMENTS_ONLY
    in_block = False
    for lineno, raw in enumerate(read_lines(path), 1):
        if lineno in skip:
            continue
        line = raw.strip()
        if not line:
            continue
        if blocks and in_block:
            if "*/" in line:
                in_block = False
            continue
        if blocks and line.startswith("/*"):
            if "*/" not in line:
                in_block = True
            continue
        if any(line.startswith(p) for p in prefixes):
            continue
        yield line


def count_code_lines(path: Path, skip: frozenset[int]) -> int:
    return sum(1 for _ in iter_code_lines(path, skip))


def shim_ratio(path: Path, skip: frozenset[int]) -> tuple[float, int, int]:
    """Return (ratio, code_lines, export_lines).

    Languages without an export pattern return (-1, code, 0) — the caller
    treats negative as MANUAL.
    """
    pattern = RE_EXPORT_PATTERNS.get(path.suffix)
    if not pattern:
        return -1.0, count_code_lines(path, skip), 0
    code = 0
    exp = 0
    for line in iter_code_lines(path, skip):
        code += 1
        if pattern.match(line):
            exp += 1
    if code == 0:
        return 0.0, 0, 0
    return exp / code, code, exp


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run automated architecture-gate checks on one file."
    )
    parser.add_argument("file", type=Path)
    parser.add_argument("--max-loc", type=int, default=300)
    parser.add_argument(
        "--shim-ratio",
        type=float,
        default=0.8,
        help="Re-export ratio at or above which the file is flagged as a shim.",
    )
    args = parser.parse_args()

    if not args.file.exists() or not args.file.is_file():
        print(f"[arch-gate] file={args.file} ERROR=file_not_found")
        return 2

    prose = prose_lines(args.file)
    loc = count_code_lines(args.file, prose)
    ratio, code_lines, exp_lines = shim_ratio(args.file, prose)

    # Appended only when prose was found, so every non-Python banner and every
    # docstring-free Python banner renders exactly as it did before.
    doc = f"+{len(prose)}doc" if prose else ""
    loc_pass = loc <= args.max_loc
    loc_str = f"PASS({loc}{doc})" if loc_pass else f"FAIL({loc}{doc}>{args.max_loc})"

    if ratio < 0:
        shim_str = "MANUAL"
        shim_pass = True
    elif code_lines == 0:
        shim_str = "PASS"
        shim_pass = True
    elif ratio >= args.shim_ratio:
        shim_str = f"FAIL(reexport={exp_lines}/{code_lines})"
        shim_pass = False
    else:
        shim_str = f"PASS({exp_lines}/{code_lines})"
        shim_pass = True

    print(
        f"[arch-gate] file={args.file} "
        f"LOC={loc_str} SHIM={shim_str} DEPS=MANUAL "
        f"SRP=MANUAL DRY=MANUAL TEST=MANUAL"
    )

    return 0 if (loc_pass and shim_pass) else 1


if __name__ == "__main__":
    sys.exit(main())
