#!/usr/bin/env python3
"""Tests for the autonomous-mode contract token — one fixture tree per check.

`check(root)` is the whole assertion: the contract declares its version once,
both pointer skills name the contract file, `plan` additionally names the
routing rubric, and no other file in the repository re-literalises the token.
It takes a root so the fixture cases can drive it against a temp tree.

Run with `python3 test_contract.py` (no pytest dependency).

Exit codes: 0 clean, 1 findings, 2 broken invocation.
"""

from __future__ import annotations

import re
import sys
import tempfile
import traceback
from pathlib import Path

import contract

REPO = Path(__file__).resolve().parents[2]
TOKEN = "SW-2026-08-v4"
CONTRACT_REL = "_shared/autonomous-mode.md"
CLASSIFICATION_REL = "triage/references/classification.md"
POINTERS = ("investigate/SKILL.md", "plan/SKILL.md")

# The declaration line prefix every consumer greps for. Brief generators must
# match this prefix and read the value off it — never hard-code the value.
DECL_PREFIX = "Contract version:"
DECL_VALUE = re.compile(r"\*\*([A-Za-z0-9._-]+)\*\*")

SCAN_SUFFIXES = (".md", ".py", ".sh")
# The generated e2e trees are gitignored and disposable, never repository
# content — and they fill up with artifacts real workers wrote, which quote the
# contract token because a worker echoing it is exactly what the contract asks
# for. They are absent on a clean checkout and present after any `--keep` run or
# any failing one, so scanning them makes this suite pass or fail on whether
# somebody ran the e2e driver recently. Measured: a kept run turned this row red
# with a finding about a live investigation artifact.
SCAN_SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv",
                  "triage-testbed", "triage-testbed-clean", "triage-testbed-plans"}
# This file owns the token value; it is the one place a literal is correct.
SCAN_SKIP_FILES = {CONTRACT_REL, "triage/scripts/test_contract.py"}


# --------------------------------------------------------------------------
# the check
# --------------------------------------------------------------------------

def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _check_declaration(root: Path) -> list[str]:
    """The contract declares the token once, in bold, on the `DECL_PREFIX` line."""
    contract = root / CONTRACT_REL
    if not contract.is_file():
        return [f"{CONTRACT_REL}: missing — the contract file does not exist"]

    text = _read(contract)
    decls = [line.strip() for line in text.splitlines()
             if line.strip().startswith(DECL_PREFIX)]
    if len(decls) != 1:
        return [f"{CONTRACT_REL}: expected exactly one '{DECL_PREFIX}' line, "
                f"found {len(decls)}"]

    findings: list[str] = []
    match = DECL_VALUE.search(decls[0])
    declared = match.group(1) if match else None
    if declared != TOKEN:
        findings.append(
            f"{CONTRACT_REL}: declares {declared!r}, expected {TOKEN!r} in bold on the "
            f"'{DECL_PREFIX}' line")

    occurrences = text.count(TOKEN)
    if declared == TOKEN and occurrences != 1:
        findings.append(
            f"{CONTRACT_REL}: token appears {occurrences} times; the declaration line "
            "must be its only occurrence")
    return findings


def _check_pointers(root: Path) -> list[str]:
    """Both pointer skills name the contract; only `plan` also names the rubric."""
    findings: list[str] = []
    for rel in POINTERS:
        path = root / rel
        if not path.is_file():
            findings.append(f"{rel}: missing — cannot carry the contract pointer")
            continue
        text = _read(path)
        if CONTRACT_REL not in text:
            findings.append(f"{rel}: no pointer block naming {CONTRACT_REL}")
        if rel == "plan/SKILL.md" and CLASSIFICATION_REL not in text:
            findings.append(f"{rel}: pointer does not name {CLASSIFICATION_REL}")
    return findings


def _check_no_reliteralisation(root: Path) -> list[str]:
    """No scannable file outside the skip list repeats the token value."""
    findings: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix not in SCAN_SUFFIXES:
            continue
        rel = path.relative_to(root)
        if set(rel.parts) & SCAN_SKIP_DIRS or rel.as_posix() in SCAN_SKIP_FILES:
            continue
        if TOKEN in _read(path):
            findings.append(
                f"{rel.as_posix()}: re-literalises {TOKEN}; grep the "
                f"'{DECL_PREFIX}' line in {CONTRACT_REL} instead")
    return findings


def check(root: Path) -> list[str]:
    """Return a list of findings; empty means the contract is consistent."""
    return [
        *_check_declaration(root),
        *_check_pointers(root),
        *_check_no_reliteralisation(root),
    ]


# --------------------------------------------------------------------------
# fixtures
# --------------------------------------------------------------------------

CONTRACT_BODY = """# Autonomous mode

{decl}

Body text the worker obeys.
"""

INVESTIGATE_POINTER = """# Investigate

**Delegated triage runs only.** If your brief names `../{contract}`, read it
before Gate 1. Echo its contract token in your report.
"""

PLAN_POINTER = """# Plan

**Delegated triage runs only.** If your brief names `../{contract}`, read it
before Step 2. `../{classification}` is the single definition of bead routing.
"""


def _write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def contract_tree(tmp: Path, *, declared: str = TOKEN, decl_lines: int = 1,
                  investigate_names_contract: bool = True,
                  plan_names_contract: bool = True,
                  plan_names_classification: bool = True,
                  extra: dict[str, str] | None = None) -> Path:
    """Write a clean repository skeleton, then apply the named overrides."""
    root = tmp / "skills"
    decl_line = f"{DECL_PREFIX} **{declared}** — echo this token in your report."
    _write(root / CONTRACT_REL,
           CONTRACT_BODY.format(decl="\n".join([decl_line] * decl_lines)))

    investigate = INVESTIGATE_POINTER.format(contract=CONTRACT_REL)
    if not investigate_names_contract:
        investigate = investigate.replace(CONTRACT_REL, "somewhere-else.md")
    _write(root / "investigate/SKILL.md", investigate)

    plan = PLAN_POINTER.format(contract=CONTRACT_REL, classification=CLASSIFICATION_REL)
    if not plan_names_contract:
        plan = plan.replace(CONTRACT_REL, "somewhere-else.md")
    if not plan_names_classification:
        plan = plan.replace(CLASSIFICATION_REL, "some/other/rubric.md")
    _write(root / "plan/SKILL.md", plan)

    for rel, body in (extra or {}).items():
        _write(root / rel, body)
    return root


# --------------------------------------------------------------------------
# cases
# --------------------------------------------------------------------------

def case_repository_contract_is_consistent(tmp: Path) -> None:
    findings = check(REPO)
    assert not findings, "\n".join(findings)


def case_clean_fixture_tree_passes(tmp: Path) -> None:
    assert check(contract_tree(tmp)) == []


def case_token_declared_once(tmp: Path) -> None:
    findings = check(contract_tree(tmp, decl_lines=2))
    assert any("found 2" in f for f in findings), findings


def case_pointer_blocks_exist(tmp: Path) -> None:
    """Each pointer is broken in its own tree, so neither finding masks the other."""
    findings = check(contract_tree(tmp / "investigate_broken",
                                   investigate_names_contract=False))
    assert any(f.startswith("investigate/SKILL.md: no pointer") for f in findings), findings
    findings = check(contract_tree(tmp / "plan_broken", plan_names_contract=False))
    assert any(f.startswith("plan/SKILL.md: no pointer") for f in findings), findings


def case_plan_pointer_names_classification(tmp: Path) -> None:
    findings = check(contract_tree(tmp, plan_names_classification=False))
    assert any(CLASSIFICATION_REL in f and f.startswith("plan/") for f in findings), findings


def case_investigate_pointer_need_not_name_classification(tmp: Path) -> None:
    """Only `plan` routes beads, so only `plan`'s pointer carries the rubric."""
    assert check(contract_tree(tmp)) == []


def case_token_not_reliteralised(tmp: Path) -> None:
    root = contract_tree(tmp, extra={"triage/scripts/brief_plan.sh":
                                     f'echo "contract {TOKEN}"\n'})
    findings = check(root)
    assert any("re-literalises" in f and "brief_plan.sh" in f for f in findings), findings


def case_mismatched_fixture_fails(tmp: Path) -> None:
    """Contract declares v0 while a pointer hard-codes v1 — the drift this test exists for."""
    root = contract_tree(tmp, declared="SW-2026-08-v0",
                         extra={"execute/SKILL.md": f"echo the token {TOKEN}\n"})
    findings = check(root)
    assert findings, "a disagreeing tree must produce findings"
    assert any("declares 'SW-2026-08-v0'" in f for f in findings), findings
    assert any("re-literalises" in f for f in findings), findings


def case_missing_contract_file_is_a_finding(tmp: Path) -> None:
    empty = tmp / "empty"
    empty.mkdir()
    findings = check(empty)
    assert any("missing" in f and CONTRACT_REL in f for f in findings), findings
    assert len(findings) == 3, findings


def case_the_reader_returns_the_token_this_file_pins(tmp: Path) -> None:
    """`contract.token()` is the production read of the declaration line.

    This file owns the only legal literal, so the two must agree: a reader
    that drifted from the pin would hand workers a token no check rejects.
    """
    assert contract.token() == TOKEN


def case_the_reader_reads_the_contract_it_is_given(tmp: Path) -> None:
    root = contract_tree(tmp, declared="SW-2026-08-v0")
    assert contract.token(root / CONTRACT_REL) == "SW-2026-08-v0"


def case_a_contract_with_no_declaration_is_an_error(tmp: Path) -> None:
    """Absent or malformed both raise: a caller must never get a silent empty
    token, which would make every worker's echo trivially match."""
    for name, body in (("none.md", "# Autonomous mode\n\nNo version line.\n"),
                       ("bad.md", f"# Autonomous mode\n\n{DECL_PREFIX} **SW-v1**\n")):
        path = tmp / name
        path.write_text(body, encoding="utf-8")
        try:
            contract.token(path)
        except ValueError:
            continue
        raise AssertionError(f"{name}: no ValueError for a token-less contract")


CASES = [v for k, v in sorted(globals().items()) if k.startswith("case_")]


def main() -> int:
    if not REPO.is_dir():
        print(f"test_contract: {REPO} is not a directory", file=sys.stderr)
        return 2
    failed = 0
    for case in CASES:
        with tempfile.TemporaryDirectory() as td:
            try:
                case(Path(td))
                print(f"PASS  {case.__name__}")
            except AssertionError as e:
                failed += 1
                print(f"FAIL  {case.__name__}: {e}")
            except Exception:
                failed += 1
                print(f"ERROR {case.__name__}")
                traceback.print_exc()
    print(f"\n{len(CASES) - failed}/{len(CASES)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
