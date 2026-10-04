#!/usr/bin/env python3
"""Tests for lint_investigation.py — one fixture artifact per check.

Run with `python3 test_lint_investigation.py` (no pytest dependency).

**LOC waiver:** a fixture-per-check case list, read one case at a time — the
same shape as `execute/scripts/test_run_arch_gate.py`. Alternatives considered
are recorded in the phase slice's Component Decomposition.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path

from lint_investigation import strip_fences

SCRIPT = Path(__file__).resolve().parent / "lint_investigation.py"

REPO_FILE = "import 'x';\nfinal int pageCount;\nvoid go() {}\n"
EVIDENCE = "1. Step one — *evidence: `lib/reader.dart:2`* quote `final int pageCount;`"
OFFSET_EVIDENCE = "1. Step one — *evidence: `lib/reader.dart:1`* quote `void go() {}`"

ASSUMPTION_WORDS = [
    "probably", "likely", "presumably", "seems", "appears to",
    "might be", "should be", "I think", "I believe", "my guess",
]

VALID = """# Proj Investigation: Thing goes wrong

**Status:** ROOT CAUSE CONFIRMED — FIX APPROVED
**Date:** 2026-08-28
**Project:** proj
**Beads task:** none

---

## Problem

The thing goes wrong on open.

## Execution Chain

{evidence}

## Root Cause

The counter reads an empty fragment and returns null.

## Supporting Evidence

- The stored value stayed at 1 for the whole run.

## Ruled Out

- Alternative A: disproved by the log timestamps.

---

## Approved Fix

**Summary:** Resolve the index through the table of contents.

**What changes:**
1. Change the resolver so it reads the index.

**Why this fix is correct:**
- The reader already resolves the index that way.

**Side effects checked:**
- No other caller reads the fragment.

**Not addressed (separate issues):** none

---

## Handoff Instructions

Pass this file path to the planning skill as background context.
"""

RULED_OUT_BODY = "- Alternative A: disproved by the log timestamps."
SIDE_EFFECTS_BLOCK = "**Side effects checked:**\n- No other caller reads the fragment.\n\n"


def body(evidence: str = EVIDENCE) -> str:
    return VALID.replace("{evidence}", evidence)


def git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)


def scaffold(
    tmp: Path,
    *,
    text: str | None = None,
    name: str = "proj_invest_thing_goes_wrong.md",
    subdir: str = "investigations",
    git_init: bool = True,
    extra: dict | None = None,
) -> Path:
    repo = tmp / "proj"
    (repo / "lib").mkdir(parents=True)
    (repo / "lib" / "reader.dart").write_text(REPO_FILE, encoding="utf-8")
    for rel, content in (extra or {}).items():
        target = repo / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    if git_init:
        git(repo, "init", "-q")
        git(repo, "add", "-A")
        git(repo, "-c", "user.email=t@e.test", "-c", "user.name=T",
            "commit", "-q", "-m", "init")
    holder = tmp / "plans" / "proj" / subdir
    holder.mkdir(parents=True)
    artifact = holder / name
    artifact.write_text(text if text is not None else body(), encoding="utf-8")
    return artifact


def dirty(tmp: Path) -> None:
    (tmp / "proj" / "lib" / "reader.dart").write_text(
        REPO_FILE + "// touched\n", encoding="utf-8")


def run(*args: str) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True
    )
    return proc.returncode, proc.stdout.strip()


# --- check 1: sections and fix subsections -----------------------------------

def case_clean_artifact_exits_0(tmp: Path) -> None:
    code, out = run(str(scaffold(tmp)))
    assert code == 0, (code, out)
    assert "0 errors, 0 warnings" in out, out


def case_missing_section_fails(tmp: Path) -> None:
    text = body().replace("## Ruled Out\n\n" + RULED_OUT_BODY + "\n\n", "")
    code, out = run(str(scaffold(tmp, text=text)))
    assert "section-missing" in out, out
    assert code == 1, (code, out)


def case_missing_fix_subsection_fails(tmp: Path) -> None:
    text = body().replace(SIDE_EFFECTS_BLOCK, "")
    code, out = run(str(scaffold(tmp, text=text)))
    assert "fix-subsection-missing" in out, out
    assert code == 1, (code, out)


# --- check 2: ruled out is not a placeholder ---------------------------------

def case_empty_ruled_out_fails(tmp: Path) -> None:
    text = body().replace(RULED_OUT_BODY, "none")
    code, out = run(str(scaffold(tmp, text=text)))
    assert "ruled-out-empty" in out, out
    assert code == 1, (code, out)


# --- check 3: citations are wired into the CLI ------------------------------
# Citation behaviour is proven directly in test_investigation_citations.py;
# this case proves only that the linter routes an error out, and
# case_assumption_word_in_fenced_block_passes does the same for a warning.

def case_citation_to_missing_file_fails(tmp: Path) -> None:
    ev = "1. Step one — *evidence: `lib/gone.dart:4`* quote `final int pageCount;`"
    code, out = run(str(scaffold(tmp, text=body(ev))))
    assert "citation-file-missing" in out, out
    assert code == 1, (code, out)


# --- check 4: assumption language --------------------------------------------

def case_each_assumption_word_fails(tmp: Path) -> None:
    art = scaffold(tmp)
    for word in ASSUMPTION_WORDS:
        art.write_text(
            body().replace("The counter reads", f"The counter {word} reads"),
            encoding="utf-8",
        )
        code, out = run(str(art))
        assert "assumption-language" in out, (word, out)
        assert code == 1, (word, code, out)


def case_assumption_word_in_fenced_block_passes(tmp: Path) -> None:
    text = body(OFFSET_EVIDENCE).replace(
        "The thing goes wrong on open.",
        "The thing goes wrong on open.\n\n```\nprobably not counted\n```",
    )
    code, out = run(str(scaffold(tmp, text=text)), "--json")
    assert code == 0, (code, out)
    data = json.loads(out)
    assert data["errors"] == 0, data
    want = next(n for n, line in enumerate(text.splitlines(), 1)
                if "lib/reader.dart:1" in line)
    offsets = [f for f in data["findings"] if f["code"] == "citation-quote-offset"]
    assert len(offsets) == 1, data
    assert offsets[0]["line"] == want, (offsets, want)


# --- check 5: header fields ---------------------------------------------------

def case_missing_header_field_fails(tmp: Path) -> None:
    text = body().replace("**Beads task:** none\n", "")
    code, out = run(str(scaffold(tmp, text=text)))
    assert "header-field-missing" in out, out
    assert code == 1, (code, out)


def case_wrong_status_value_fails(tmp: Path) -> None:
    text = body().replace("ROOT CAUSE CONFIRMED — FIX APPROVED", "UNRESOLVED")
    code, out = run(str(scaffold(tmp, text=text)))
    assert "header-status-wrong" in out, out
    assert code == 1, (code, out)


# --- check 5b: the two parked outcomes ---------------------------------------
# A park is a success outcome (`triage/references/qc-gates.md` §7): the bead
# keeps its status, the artifact is retained, and a human answers a question.
# With one legal status the linter could not express that, so a correctly
# parked artifact failed tier 1 on the status and on four absent fix
# subsections — and since Wave 5 gates tier 2 on tier 1, it could never reach a
# reviewer. Worse, the only way to pass was to claim `FIX APPROVED`, which
# `_shared/autonomous-mode.md` §B forbids a worker to grant itself. The linter
# rewarded self-approval and punished honesty. Measured on a live run.


def parked(status: str, question: str = "## Open Question\n\n"
           "Does the retry budget belong to the client or the caller?\n") -> str:
    """The valid artifact re-cut as a park: no approved fix, one open question."""
    text = body().replace("ROOT CAUSE CONFIRMED — FIX APPROVED", status)
    head, _, _ = text.partition("## Approved Fix")
    return head + question + "\n---\n\n## Handoff Instructions\n\nA human answers the question.\n"


def case_a_fix_parked_artifact_is_clean(tmp: Path) -> None:
    """Cause proven, fix undetermined — the honest outcome for an underspecified bead."""
    code, out = run(str(scaffold(tmp, text=parked("ROOT CAUSE CONFIRMED — FIX PARKED"))))
    assert code == 0, (code, out)
    assert "0 errors" in out, out


def case_a_cause_unproven_artifact_is_clean(tmp: Path) -> None:
    """Evidence exhausted without a cause — `investigate` forbids inventing one."""
    code, out = run(str(scaffold(tmp, text=parked("ROOT CAUSE UNPROVEN — PARKED"))))
    assert code == 0, (code, out)
    assert "0 errors" in out, out


def case_a_parked_artifact_needs_no_approved_fix(tmp: Path) -> None:
    """The heart of it: no `## Approved Fix`, and that is not a finding."""
    code, out = run(str(scaffold(tmp, text=parked("ROOT CAUSE UNPROVEN — PARKED"))))
    assert "fix-subsection-missing" not in out, out
    assert "section-missing" not in out, out


def case_a_park_without_the_question_section_fails(tmp: Path) -> None:
    """qc-gates §7: a park with no question is a bead nobody can answer.

    An absent section reports `section-missing`, the same code every other
    absent section reports; `park-question-missing` is for a section that is
    present and says nothing answerable. Two distinct defects, two codes.
    """
    text = parked("ROOT CAUSE UNPROVEN — PARKED", question="")
    code, out = run(str(scaffold(tmp, text=text)))
    assert "section-missing" in out and "Open Question" in out, out
    assert code == 1, (code, out)


def case_a_park_question_must_be_a_question(tmp: Path) -> None:
    """"The root cause is unproven" is a summary of the defect, not the question.

    The distinction is qc-gates' own: the first makes a human re-read the
    artifact, the second can be answered from where they stand.
    """
    text = parked("ROOT CAUSE UNPROVEN — PARKED",
                  question="## Open Question\n\nThe root cause is unproven.\n")
    code, out = run(str(scaffold(tmp, text=text)))
    assert "park-question-missing" in out, out
    assert code == 1, (code, out)


def case_an_approved_artifact_still_needs_its_fix(tmp: Path) -> None:
    """The park path must not become a way out of the approved path's rules."""
    text = body().replace(SIDE_EFFECTS_BLOCK, "")
    code, out = run(str(scaffold(tmp, text=text)))
    assert "fix-subsection-missing" in out, out
    assert code == 1, (code, out)


# --- check 5c: the gate-pending outcome --------------------------------------
# The normal Wave 2 outcome for a delegated worker: cause proven, fix chosen on
# evidence, Gate 2 unanswered because `_shared/autonomous-mode.md` §A routes it
# to an independent verdict the artifact must exist to receive. With three
# statuses that outcome was unrepresentable — `FIX APPROVED` is a claim
# `investigate/SKILL.md` forbids a worker to make, and both parks say the fix
# is undetermined when it is determined and merely unapproved. A live run hit
# it on the first artifact of the first full sweep and it blocked all nine
# beads: every delegated investigation lands here, so the linter rejected the
# one shape it exists to pass.


def case_a_proposed_fix_artifact_is_clean(tmp: Path) -> None:
    """Cause proven, fix evidenced, gate unanswered — the delegated outcome."""
    text = body().replace("ROOT CAUSE CONFIRMED — FIX APPROVED",
                          "ROOT CAUSE CONFIRMED — FIX PROPOSED")
    code, out = run(str(scaffold(tmp, text=text)))
    assert code == 0, (code, out)
    assert "0 errors" in out, out


def case_a_proposed_fix_artifact_still_needs_its_fix(tmp: Path) -> None:
    """It is not a park: the four subsections are the Gate 2 payload itself.

    The status and the section set are coupled, so a fourth status that did not
    carry the coupling would trade `header-status-wrong` for
    `fix-subsection-missing` and block the same artifact at the same gate.
    """
    text = body().replace("ROOT CAUSE CONFIRMED — FIX APPROVED",
                          "ROOT CAUSE CONFIRMED — FIX PROPOSED")
    code, out = run(str(scaffold(tmp, text=text.replace(SIDE_EFFECTS_BLOCK, ""))))
    assert "fix-subsection-missing" in out, out
    assert "header-status-wrong" not in out, out
    assert code == 1, (code, out)


def case_a_proposed_fix_artifact_may_not_park_instead(tmp: Path) -> None:
    """`## Open Question` in place of the fix is a park, and this is not one."""
    code, out = run(str(scaffold(tmp, text=parked("ROOT CAUSE CONFIRMED — FIX PROPOSED"))))
    assert "section-missing" in out and "Approved Fix" in out, out
    assert "header-status-wrong" not in out, out
    assert code == 1, (code, out)


def case_malformed_date_fails(tmp: Path) -> None:
    text = body().replace("**Date:** 2026-08-28", "**Date:** 29 June 2026")
    code, out = run(str(scaffold(tmp, text=text)))
    assert "header-date-malformed" in out, out
    assert code == 1, (code, out)


# --- check 6: filename and location ------------------------------------------

def case_bad_filename_fails(tmp: Path) -> None:
    code, out = run(str(scaffold(tmp, name="notes.md")))
    assert "filename-convention" in out, out
    assert code == 1, (code, out)


def case_two_word_short_name_fails(tmp: Path) -> None:
    code, out = run(str(scaffold(tmp, name="proj_invest_help_hang.md")))
    assert "filename-convention" in out, out
    assert code == 1, (code, out)


def case_wrong_directory_fails(tmp: Path) -> None:
    code, out = run(str(scaffold(tmp, subdir="notes")))
    assert "filename-location" in out, out
    assert code == 1, (code, out)


def case_project_mismatch_warns(tmp: Path) -> None:
    text = body().replace("**Project:** proj", "**Project:** other")
    code, out = run(str(scaffold(tmp, text=text)))
    assert "filename-project-mismatch" in out, out
    assert code == 0, (code, out)


# --- check 7: the _vN chain ---------------------------------------------------

def case_v2_without_v1_fails(tmp: Path) -> None:
    code, out = run(str(scaffold(tmp, name="proj_invest_thing_goes_wrong_v2.md")))
    assert "prior-version-missing" in out, out
    assert code == 1, (code, out)


def case_prior_version_touched_warns(tmp: Path) -> None:
    art = scaffold(tmp, name="proj_invest_thing_goes_wrong_v2.md")
    prior = art.parent / "proj_invest_thing_goes_wrong.md"
    prior.write_text(body(), encoding="utf-8")
    later = time.time() + 120
    os.utime(prior, (later, later))
    code, out = run(str(art))
    assert "prior-version-touched" in out, out
    assert code == 0, (code, out)


# --- check 8: the source tree -------------------------------------------------

def case_dirty_git_tree_fails(tmp: Path) -> None:
    art = scaffold(tmp)
    dirty(tmp)
    code, out = run(str(art))
    assert "source-tree-dirty" in out, out
    assert code == 1, (code, out)


def case_clean_git_tree_passes(tmp: Path) -> None:
    code, out = run(str(scaffold(tmp)))
    assert "source-tree" not in out, out
    assert code == 0, (code, out)


def case_untracked_file_is_ignored(tmp: Path) -> None:
    art = scaffold(tmp)
    (tmp / "proj" / "scratch.txt").write_text("x\n", encoding="utf-8")
    code, out = run(str(art))
    assert "source-tree-dirty" not in out, out
    assert code == 0, (code, out)


def case_no_tree_check_warns_not_fails(tmp: Path) -> None:
    art = scaffold(tmp)
    dirty(tmp)
    code, out = run(str(art), "--no-tree-check")
    assert "source-tree-unchecked" in out, out
    assert code == 0, (code, out)


def case_source_tree_unverified_fails(tmp: Path) -> None:
    code, out = run(str(scaffold(tmp, git_init=False)))
    assert "source-tree-unverified" in out, out
    assert code == 1, (code, out)


# --- CLI contract -------------------------------------------------------------

def case_missing_path_argument_exits_2(tmp: Path) -> None:
    code, out = run()
    assert code == 2, (code, out)


def case_unreadable_artifact_exits_2(tmp: Path) -> None:
    code, out = run(str(tmp / "nope.md"))
    assert code == 2, (code, out)


def case_directory_input_lints_all(tmp: Path) -> None:
    art = scaffold(tmp)
    (art.parent / "proj_invest_second_thing_here.md").write_text(body(), encoding="utf-8")
    code, out = run(str(art.parent))
    assert "2 artifacts" in out, out
    assert code == 0, (code, out)


def case_json_mode_emits_findings(tmp: Path) -> None:
    text = body().replace(RULED_OUT_BODY, "none")
    code, out = run(str(scaffold(tmp, text=text)), "--json")
    assert code == 1, (code, out)
    data = json.loads(out)
    assert data["artifacts"] == 1, data
    errors = [f for f in data["findings"] if f["severity"] == "error"]
    assert data["errors"] == len(errors), data
    assert data["errors"] >= 1, data


# --- check 9: nested package roots and fenced quotes -------------------------

NESTED = {"pkg/pubspec.yaml": "name: pkg\n", "pkg/lib/nested.dart": REPO_FILE}


def case_nested_package_citation_passes_through_the_cli(tmp: Path) -> None:
    ev = "1. Step one — *evidence: `lib/nested.dart:2`* quote `final int pageCount;`"
    art = scaffold(tmp, text=body(ev), extra=NESTED)
    code, out = run(str(art))
    assert "citation-file-missing" not in out, out
    assert code == 0, (code, out)


def case_fenced_quote_is_read_through_the_cli(tmp: Path) -> None:
    ev = ("1. Step one — *evidence: `lib/reader.dart:2`* reads:\n\n"
          "```\nnowhere in the file at all\n```")
    code, out = run(str(scaffold(tmp, text=body(ev))))
    assert "citation-quote-absent" in out, out
    assert code == 1, (code, out)


def case_strip_fences_keeps_a_nested_marker_inside_the_block(tmp: Path) -> None:
    prose, fences = strip_fences("a\n```\n~~~\nbody\n```\nb\n")
    assert prose == ["a", "", "", "", "", "b"], prose
    assert fences == {2: ["~~~", "body"]}, fences


def case_strip_fences_captures_an_unterminated_block(tmp: Path) -> None:
    prose, fences = strip_fences("a\n```\nbody\n")
    assert prose == ["a", "", ""], prose
    assert fences == {2: ["body"]}, fences


# --- check 10: a bare filename warns, it does not fail the run ---------------
# 1211 historical citations are bare and must keep resolving, so the severity
# is what this pins down, not just the code.


def case_bare_filename_citation_warns_without_failing(tmp: Path) -> None:
    ev = "1. Step one — *evidence: `reader.dart:2`* quote `final int pageCount;`"
    code, out = run(str(scaffold(tmp, text=body(ev))), "--json")
    assert code == 0, (code, out)
    data = json.loads(out)
    assert data["errors"] == 0, data
    bare = [f for f in data["findings"] if f["code"] == "citation-bare-filename"]
    assert len(bare) == 1 and bare[0]["severity"] == "warning", data


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
