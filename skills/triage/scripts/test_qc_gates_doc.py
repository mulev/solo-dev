#!/usr/bin/env python3
"""Tests for the tier-2 dispatch contract in `references/qc-gates.md`.

§ 1 is the only definition of *which* reviewer tier 2 dispatches. `SKILL.md`
Wave 5 points here for the branch detail, so a § 1 that names one branch
leaves the orchestrator with the unresolvable instruction this file exists to
prevent — and the briefed branch loses restrictions only frontmatter enforces.

Run with `python3 test_qc_gates_doc.py` (no pytest dependency).
"""

from __future__ import annotations

import sys
import tempfile
import traceback
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GATES_REL = "triage/references/qc-gates.md"
SECTION = "## 1. Two-tier order"
# The registry branch, the briefed branch, and what the briefed one inherits
# from a frontmatter nothing loads for it.
#
# **Every phrase here is absent from § 1 today** — checked against the file
# before it was written, because a phrase the section already carries is a
# check that passes before the edit and can never go red. Three drafts of
# this tuple failed that test: bare `"nothing"` (§ 1 already reads "teaches
# the reviewer nothing" and "nothing to overwrite"), bare `"worker"` (§ 1
# already reads "producing worker"), and bare `"opus"`, which any `"octopus"`
# in § 1 would satisfy. All three are pinned to the longer string the fix
# actually adds.
REQUIRED = (
    ("registry branch", ("registered `triage-qc` agent", "roster")),
    ("briefed branch", ("a worker briefed", "brief_qc.sh")),
    ("tool restriction", ("`Read`", "`Grep`", "`Glob`")),
    ("model restriction", ("model `opus`",)),
    ("write restriction", ("nothing written anywhere",)),
    ("wave 6 report", ("wave 6",)),
    # The restrictions are worth nothing stated passively: the model and the
    # tool set are fixed when the worker is spawned, so § 1 has to name who
    # applies them. Without this row the section could revert to "the briefed
    # branch is held to ..." and every other phrase here would still be found.
    ("spawn actor", ("orchestrator holds", "spawns that worker")),
)


def check(root: Path) -> list[str]:
    """Findings against § 1 of the gates reference. Empty list means clean."""
    path = Path(root) / GATES_REL
    if not path.is_file():
        return [f"missing {GATES_REL}"]
    lines = path.read_text(encoding="utf-8").splitlines()
    start = next((i for i, l in enumerate(lines) if l.strip() == SECTION), -1)
    if start < 0:
        return [f"section not found: {SECTION}"]
    end = next((j for j in range(start + 1, len(lines))
                if lines[j].startswith("## ")), len(lines))
    low = " ".join(" ".join(lines[start:end]).split()).lower()
    out = [f"{name}: § 1 does not state {phrase!r}"
           for name, phrases in REQUIRED for phrase in phrases
           if phrase.lower() not in low]
    # Two tier-2 rows, not one sentence mentioning both: the table is what a
    # dispatching orchestrator reads, and a branch with no row has no tier.
    tier_two = [l for l in lines[start:end]
                if l.startswith("| 2 ") or l.startswith("|2 ")]
    if len(tier_two) < 2:
        out.append(f"tier table carries {len(tier_two)} tier-2 row(s), "
                   "one per branch is two")
    return out


REGISTRY_ROW = ("| 2 | the registered `triage-qc` agent "
                "(`../agents/triage-qc.md`) | an artifact that passed tier 1, "
                "on a harness whose roster carries that agent |")
BRIEFED_ROW = ("| 2 | a worker briefed by `../scripts/brief_qc.sh`, first read "
               "`../agents/triage-qc.md` | the same artifact, on a harness "
               "whose roster does not |")
RESTRICTIONS = ("**The orchestrator holds the briefed branch to the "
                "definition's own restrictions**: it spawns that worker on "
                "model `opus`, with tools `Read`, `Grep` and `Glob`, and "
                "nothing written anywhere. The orchestrator names the branch "
                "it took in its Wave 6 close-out.")


def good() -> str:
    return (f"# QC gates\n\n{SECTION}\n\n| Tier | What runs | On what |\n"
            "|---|---|---|\n"
            "| 1 | `../scripts/lint_investigation.py` | an investigation |\n"
            f"{REGISTRY_ROW}\n{BRIEFED_ROW}\n\n"
            f"Tier 2 runs only on a tier-1 pass.\n\n{RESTRICTIONS}\n\n"
            "## 2. Verdict-to-gate mapping\n\nElsewhere.\n")


def fixture(tmp: Path, text: str) -> Path:
    path = tmp / GATES_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return tmp


# --- cases -------------------------------------------------------------------


def case_the_real_reference_is_clean(tmp: Path) -> None:
    findings = check(REPO)
    assert findings == [], f"real {GATES_REL}: {findings}"


def case_the_fixture_is_clean(tmp: Path) -> None:
    """Every red case below mutates this text, so it must start green."""
    findings = check(fixture(tmp, good()))
    assert findings == [], findings


def case_a_missing_file_is_a_finding(tmp: Path) -> None:
    findings = check(tmp)
    assert findings == [f"missing {GATES_REL}"], findings


def case_a_reference_without_the_section_is_a_finding(tmp: Path) -> None:
    text = good().replace(SECTION, "## 1. Tiers")
    assert check(fixture(tmp, text)) == [f"section not found: {SECTION}"]


def case_a_single_tier_two_row_is_a_finding(tmp: Path) -> None:
    """One row is the unfixed state: the briefed branch has no tier."""
    text = good().replace(BRIEFED_ROW + "\n", "")
    assert any("one per branch is two" in f for f in check(fixture(tmp, text)))


def case_an_untyped_registry_branch_is_a_finding(tmp: Path) -> None:
    """The unfixed wording: an agent name with no statement that the harness
    must actually carry it."""
    text = good().replace("the registered `triage-qc` agent",
                          "the `triage-qc` agent")
    assert any("registry branch" in f for f in check(fixture(tmp, text)))


def case_a_briefed_branch_without_its_brief_is_a_finding(tmp: Path) -> None:
    text = good().replace("a worker briefed by", "a reviewer given")
    assert any("briefed branch" in f for f in check(fixture(tmp, text)))


def case_a_briefed_branch_without_its_tool_restriction_is_a_finding(
        tmp: Path) -> None:
    """`tools: Read, Grep, Glob` is enforced by frontmatter a registry loads.
    On the briefed branch nothing loads it, so § 1 stating it is the only
    thing holding the reviewer to it."""
    text = good().replace("`Read`, `Grep` and `Glob`", "the usual tools")
    assert any("tool restriction" in f for f in check(fixture(tmp, text)))


def case_a_briefed_branch_without_its_model_restriction_is_a_finding(
        tmp: Path) -> None:
    text = good().replace("model `opus`", "a capable model")
    assert any("model restriction" in f for f in check(fixture(tmp, text)))


def case_a_write_restriction_stated_loosely_is_a_finding(tmp: Path) -> None:
    """Pinned to the phrase the fix adds, not to the word `nothing`: § 1
    already reads "teaches the reviewer nothing" and "nothing to overwrite",
    so the bare word passes before the edit and the fixture cannot go red."""
    text = good().replace("nothing written anywhere", "no writes")
    assert any("write restriction" in f for f in check(fixture(tmp, text)))


def case_a_section_silent_on_the_close_out_is_a_finding(tmp: Path) -> None:
    """Which branch reviewed which artifact is only knowable from the
    close-out; § 1 is where that obligation is stated."""
    text = good().replace("in its Wave 6 close-out", "in its close-out")
    assert any("wave 6 report" in f for f in check(fixture(tmp, text)))


def case_restrictions_stated_without_an_actor_is_a_finding(tmp: Path) -> None:
    """The wording § 1 shipped with first. It lists the same restrictions and
    every other phrase here still matches, so this is the one revert the rest
    of the tuple cannot see: a model and a tool set are chosen at spawn, and
    the worker the passive voice leaves them to cannot apply either."""
    text = good().replace("**The orchestrator holds the briefed branch to the "
                          "definition's own restrictions**: it spawns that "
                          "worker on",
                          "**The briefed branch is held to the definition's "
                          "own restrictions**:")
    assert any("spawn actor" in f for f in check(fixture(tmp, text)))


CASES = [v for k, v in sorted(globals().items()) if k.startswith("case_")]


def main() -> int:
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
