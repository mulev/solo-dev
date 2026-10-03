#!/usr/bin/env python3
"""The delegated-worker contract's declared version token, read off its line.

Every consumer needs the live value and none may hold a copy: `test_contract.py`
fails any file in the repository that re-literalises it, and a pinned copy goes
stale the moment the contract is versioned up. The four brief generators do this
read in shell with a `grep`; this is the same read for the Python callers.

It exists because there was no production reader at all, so
`triage/e2e/suite_live.py` imported a test module to get at the value — the
import inversion this repository documents against.
"""

from __future__ import annotations

import re
from pathlib import Path

CONTRACT = Path(__file__).resolve().parents[2] / "_shared" / "autonomous-mode.md"
# The declaration line every consumer greps for, and the token's own shape.
DECL_PREFIX = "Contract version:"
TOKEN_RE = re.compile(r"SW-[0-9]{4}-[0-9]{2}-v[0-9]+")


def token(path: Path | str | None = None) -> str:
    """The token declared by `path`, defaulting to this repository's contract.

    Raises `ValueError` when the line is absent or its value malformed. It
    raises rather than returning `""` because the value's only job is to be
    compared against what a worker echoed, and an empty token would make that
    comparison pass on a worker that read nothing.
    """
    source = Path(path) if path else CONTRACT
    for line in source.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith(DECL_PREFIX):
            found = TOKEN_RE.search(line)
            if found:
                return found.group(0)
    raise ValueError(f"no '{DECL_PREFIX}' token in {source}")
