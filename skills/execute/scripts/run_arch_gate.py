#!/usr/bin/env python3
"""Architecture gate runner — automated checks only.

Counts non-blank, non-comment LOC for one file, and detects the re-export
shim anti-pattern (file body is overwhelmingly `export` / barrel statements,
created to launder a parent file's import count).

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


def iter_code_lines(path: Path):
    """Yield each non-blank, non-comment line (stripped)."""
    prefixes = LINE_COMMENT_PREFIXES.get(path.suffix, ("#", "//"))
    in_block = False
    for raw in read_lines(path):
        line = raw.strip()
        if not line:
            continue
        if in_block:
            if "*/" in line:
                in_block = False
            continue
        if line.startswith("/*"):
            if "*/" not in line:
                in_block = True
            continue
        if any(line.startswith(p) for p in prefixes):
            continue
        yield line


def count_code_lines(path: Path) -> int:
    return sum(1 for _ in iter_code_lines(path))


def shim_ratio(path: Path) -> tuple[float, int, int]:
    """Return (ratio, code_lines, export_lines).

    Languages without an export pattern return (-1, code, 0) — the caller
    treats negative as MANUAL.
    """
    pattern = RE_EXPORT_PATTERNS.get(path.suffix)
    if not pattern:
        return -1.0, count_code_lines(path), 0
    code = 0
    exp = 0
    for line in iter_code_lines(path):
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

    loc = count_code_lines(args.file)
    ratio, code_lines, exp_lines = shim_ratio(args.file)

    loc_pass = loc <= args.max_loc
    loc_str = f"PASS({loc})" if loc_pass else f"FAIL({loc}>{args.max_loc})"

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
