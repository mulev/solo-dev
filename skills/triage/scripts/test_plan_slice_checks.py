#!/usr/bin/env python3
"""Tests for plan_slice_checks.py — direct calls, no CLI in the way.

Run with `python3 test_plan_slice_checks.py` (no pytest dependency).
"""

from __future__ import annotations

import sys
import traceback

from plan_slice_checks import (check_components, check_phase_thresholds,
                               check_slice_headers, check_step_order,
                               check_verification, classify)

HEADERS = """# Phase 2: Demo slice — does one demo thing

**Parent plan:** [plan.md](plan.md)
**Beads task:** `skills-demo.2`
**Status:** 🔄 IN PROGRESS

## Prerequisites

None — this phase has no dependencies.
"""

STEPS = """## Implementation Progress

- [ ] Read `a.py` — understand the flow.
- [ ] Create `test_a.py` — a test. Done when it **fails**.
- [ ] Implement parsing in `a.py`.
"""

COMPONENTS = """## Component Decomposition

| Component | Responsibility | Public API | Callers | Foreign modules touched \
| Projected LOC | Test approach |
|---|---|---|---|---|---|---|
| `a.py` | {resp} | `main` | `x`, `y` | {foreign} | {loc} | direct |
{waiver}
"""

VERIFICATION = """## Verification

- Phase exit: `./validate run phase-exit` — every row PASS.
"""


def severities(findings, check):
    return [f.severity for f in findings if f.check == check]


def case_clean_headers_report_nothing() -> None:
    assert check_slice_headers(HEADERS, "s.md", 2) == []


def case_header_number_must_match_the_filename() -> None:
    found = check_slice_headers(HEADERS, "s.md", 3)
    assert severities(found, "headers") == ["error"], found
    assert "filename says 3" in found[0].reason, found


def case_missing_field_is_an_error_and_a_missing_tail_is_a_warning() -> None:
    text = HEADERS.replace("**Beads task:** `skills-demo.2`\n", "")
    text = text.replace(" — does one demo thing", "")
    found = check_slice_headers(text, "s.md", 2)
    assert sorted(severities(found, "headers")) == ["error", "warn"], found


def case_single_phase_plan_uses_the_other_template() -> None:
    """`n=None` must not demand a slice H1 the single-phase template never has."""
    text = "# Demo Fix: A thing\n\n**Status:** 🔄 IN PROGRESS\n"
    assert check_slice_headers(text, "p.md", None) == []


def build(n: int) -> str:
    """`n` implementation checkboxes — steps `classify` puts in that category.

    The padding used to be `Run the formatter.`, which `classify` calls
    `polish`. That was invisible while the counter counted every checkbox, and
    it is what made these cases agree with a counter measuring the wrong thing.
    """
    return "".join(f"- [ ] Implement step {i} in `a.py`.\n" for i in range(n))


def case_nine_steps_fail_a_slice_and_only_warn_a_single_phase_plan() -> None:
    text = STEPS + build(8)
    assert severities(check_phase_thresholds(text, "s.md", True), "thresholds") == ["error"]
    assert severities(check_phase_thresholds(text, "p.md", False), "thresholds") == ["warn"]


def case_files_created_outranks_the_implementation_headings() -> None:
    text = (STEPS + "\n## Implementation\n\n### File: `a.py`\n\n## Files Created\n\n"
            + "".join(f"- `m{i}.py` (10 lines) — x\n" for i in range(6)))
    found = check_phase_thresholds(text, "s.md", True)
    assert severities(found, "thresholds") == ["warn"], found
    assert "m5.py" in found[0].reason and "a.py" not in found[0].reason, found


def case_tdd_order_is_an_error_and_categories_are_warnings() -> None:
    swapped = STEPS.replace(
        "- [ ] Read `a.py` — understand the flow.\n", "").replace(
        "- [ ] Create `test_a.py` — a test. Done when it **fails**.\n"
        "- [ ] Implement parsing in `a.py`.",
        "- [ ] Implement parsing in `a.py`.\n"
        "- [ ] Create `test_a.py` — a test. Done when it **fails**.")
    found = check_step_order(swapped, "s.md")
    assert "error" in severities(found, "step-order"), found
    assert severities(check_step_order(STEPS, "s.md"), "step-order").count("error") == 0


def case_a_verb_inside_prose_is_not_a_mutating_step() -> None:
    """"does not split into two parts", inside a Read step, is not an edit."""
    text = ("## Implementation Progress\n\n"
            "- [ ] Read `lib/mediatype.dart` — `_create` throws only when the "
            "component does not split into exactly two parts.\n"
            "- [ ] Run the suite.\n")
    assert severities(check_step_order(text, "s.md"), "step-order").count("error") == 0


def case_camelcase_and_kotlin_test_paths_count_as_tests() -> None:
    """A Swift or Kotlin test file is a test file; `latest.dart` is not."""
    for path in ("example/ios/RunnerTests/CarTemplateRendererTests.swift",
                 "android/src/test/kotlin/FooTest.kt",
                 "integration_test/all_tests.dart"):
        text = ("## Implementation Progress\n\n"
                f"- [ ] Add a test to `{path}`. Done when it **fails**.\n"
                "- [ ] Implement it in `lib/a.dart`. Done when it passes.\n")
        assert severities(check_step_order(text, "s.md"), "step-order").count("error") == 0, path
    swapped = ("## Implementation Progress\n\n"
               "- [ ] Implement it in `lib/latest.dart`. Done when green.\n"
               "- [ ] Add a test to `test/a_test.dart`. Done when it **fails**.\n")
    assert severities(check_step_order(swapped, "s.md"), "step-order").count("error") == 1


def case_classify_reads_the_six_categories() -> None:
    assert classify("Read `a.py` — understand it.") == "exploration"
    assert classify("Create `test_a.py` — a test.") == "tests"
    assert classify("Implement parsing in `a.py`. Done when the test passes.") == "implementation"
    assert classify("Add an integration test for the flow.") == "integration"
    assert classify("Update `docs/demo.md`.") == "documentation"
    assert classify("Run the formatter.") == "polish"


def case_a_path_named_e2e_does_not_make_a_step_an_integration_step() -> None:
    """`skills-dgl`: a path fragment is weaker evidence of intent than a verb.

    Every step of a plan whose files live under a directory called `e2e` used
    to classify as integration, so `check_step_order` reported "no tests step
    was classified" on a slice full of them. A plan then gets reworded to
    please the classifier, and the contortion outlives the bug.
    """
    assert classify("Write `triage/e2e/test_suite.py` — unit tests.") == "tests"
    assert classify("Document `triage/e2e/README.md`.") == "documentation"
    assert classify("Implement `triage/e2e/harness.py`.") == "implementation"
    assert classify("Read `triage/e2e/run.py` — understand it.") == "exploration"


def case_the_phrase_e2e_testbed_is_not_an_integration_step() -> None:
    """`testbed` starts with `test`, so an unanchored alternation matched it.

    "the e2e testbed" is this repo's own vocabulary — it appears throughout
    `harness.py`, `run_e2e.py`, `SKILL.md` and the README — so a plan step
    saying "Build the e2e testbed" was still forced to `integration`,
    reproducing the exact bug the alternation was written to fix.
    """
    assert classify("Build the `triage/e2e/` testbed fixtures.") == "implementation"
    assert classify("Build the e2e testbed before running suites.") == "implementation"
    assert classify("Run the e2e-testbed script.") == "implementation"


def case_a_step_that_really_is_end_to_end_still_classifies_as_integration() -> None:
    assert classify("Add an e2e test for the promote flow.") == "integration"
    assert classify("Run the e2e suite against the testbed.") == "integration"
    assert classify("Add an end-to-end check.") == "integration"
    assert classify("Write e2e cases for the promote paths.") == "integration"


def case_responsibility_with_and_is_an_error() -> None:
    text = COMPONENTS.format(resp="Parses X and writes Y", loc="90",
                             foreign="none", waiver="")
    found = check_components(text, "s.md", 300)
    assert severities(found, "components") == ["error"], found


def case_a_compound_object_is_one_responsibility() -> None:
    """One verb with two objects, and two nouns inside one object, are one."""
    for resp in ("Points a delegated worker at the contract and at the "
                 "bead-routing rubric",
                 "Defines how investigate and plan behave with no human at the gate"):
        text = COMPONENTS.format(resp=resp, loc="90", foreign="none", waiver="")
        assert severities(check_components(text, "s.md", 300), "components") == [], resp


def case_a_compound_predicate_is_one_responsibility() -> None:
    """Two verbs sharing one object state one responsibility, not two."""
    text = COMPONENTS.format(resp="Discovers and runs every triage script test file",
                             loc="90", foreign="none", waiver="")
    assert severities(check_components(text, "s.md", 300), "components") == []


def case_two_verb_phrases_are_still_an_error() -> None:
    for resp in ("Parses X and writes Y", "Loads the manifest and validates its rows"):
        text = COMPONENTS.format(resp=resp, loc="90", foreign="none", waiver="")
        assert severities(check_components(text, "s.md", 300), "components") == ["error"], resp


def case_a_row_declaring_no_component_is_skipped() -> None:
    """A placeholder row has no component, so no per-row rule can apply to it."""
    head = ("## Component Decomposition\n\n"
            "| Component | Responsibility | Public API | Callers | Foreign modules "
            "touched | Projected LOC | Test approach |\n|---|---|---|---|---|---|---|\n")
    bare = head + "| — (none) | — | — | — | — | 0 | — |\n"
    assert check_components(bare, "s.md", 300) == []
    prose = head + ("| — (none) | This phase introduces no code component and "
                    "writes no module | — | — | — | 0 | — |\n")
    assert check_components(prose, "s.md", 300) == []


GATE_CHECKBOX = ("- [ ] **Gate artifact.** Run the architecture gate on every "
                 "changed file, and write the `## Architecture Gate Results` "
                 "block into this file.\n")


def case_the_gate_checkbox_is_not_an_implementation_step() -> None:
    """The template's gate checkbox is boilerplate, not work the phase chose."""
    text = STEPS + build(7) + GATE_CHECKBOX
    assert check_phase_thresholds(text, "s.md", True) == []


def case_nine_real_steps_still_fail() -> None:
    text = STEPS + build(8) + GATE_CHECKBOX
    found = check_phase_thresholds(text, "s.md", True)
    assert severities(found, "thresholds") == ["error"], found
    assert "9 implementation steps" in found[0].reason, found


def case_only_implementation_checkboxes_count_towards_the_limit() -> None:
    """The limit is `plan` Step 5.2's re-slice trigger, and that trigger counts
    implementation steps — not every checkbox the slice template mandates.

    The template requires exploration, a failing test, integration, docs, the
    formatter and the gate, so a phase starts at six or seven boilerplate
    checkboxes before it does any work of its own. Counting all of them made
    the limit unreachable: measured on eight freshly written slices, every one
    reported 9 to 19 "implementation steps" while holding two or three. A live
    triage run hit the same thing from the other side — the planning worker
    reported "8 implementation steps (limit 8)", the linter said 26, and the
    orchestrator relayed "recount" to the worker as a real finding.

    `classify` already sorts each checkbox into its category, twenty lines
    below the counter that ignored it.
    """
    noise = ("- [ ] Read `b.py` — understand the seam.\n"
             "- [ ] Add unit tests in `test_b.py`.\n"
             "- [ ] Add an integration test for the flow.\n"
             "- [ ] Update `docs/overview.md` — add a section.\n"
             "- [ ] Run the formatter.\n"
             "- [ ] Run `./validate run phase-exit`.\n")
    text = STEPS + noise * 3 + build(5) + GATE_CHECKBOX
    assert check_phase_thresholds(text, "s.md", True) == []


DOCS_STEPS = ("## Implementation Progress\n\n"
              "- [ ] Read `docs/overview.md` — understand the structure.\n"
              "- [ ] Update `docs/architecture/overview.md` — add a section.\n"
              "- [ ] Update `README.md` — link the new section.\n"
              "- [ ] Run `./validate run phase-exit`.\n")


def case_a_documentation_only_phase_needs_no_test() -> None:
    """A phase whose product is prose has no source to test-drive."""
    found = check_step_order(DOCS_STEPS, "s.md")
    assert severities(found, "step-order") == ["skip"], found


def case_a_prose_titled_code_phase_is_not_documentation_only() -> None:
    """Regression: a real slice titles its steps `**Implementation.** …`, so no
    step's *first* word is a mutating verb and nothing sets first_impl. Reading
    that as documentation-only switched the whole check off for `.py` phases."""
    text = ("## Implementation Progress\n\n"
            "- [ ] **Tests (red).** Add the cases to `test_a.py`.\n"
            "- [ ] **Implementation.** The parser in `a.py` gains a branch.\n"
            "- [ ] **Documentation.** The module docstring records it.\n")
    found = check_step_order(text, "s.md")
    assert "skip" not in severities(found, "step-order"), found
    assert "no exploration step was classified" in " ".join(f.reason for f in found), found


def case_a_code_phase_still_fails_tdd_order() -> None:
    """The escape reads a document as a document — it does not excuse `a.py`."""
    text = ("## Implementation Progress\n\n"
            "- [ ] Update `docs/overview.md` — add a section.\n"
            "- [ ] Implement parsing in `a.py`.\n"
            "- [ ] Create `test_a.py` — a test. Done when it **fails**.\n")
    found = [f for f in check_step_order(text, "s.md") if f.severity == "error"]
    assert len(found) == 1, found
    assert "step 2 changes source before step 3" in found[0].reason, found


def case_over_limit_loc_is_an_error_only_without_a_waiver() -> None:
    over = COMPONENTS.format(resp="Parses X", loc="400", foreign="none", waiver="")
    assert severities(check_components(over, "s.md", 300), "components") == ["error"]
    waived = COMPONENTS.format(resp="Parses X", loc="400", foreign="none",
                               waiver="\n**LOC waiver:** `a.py` — projected 400 LOC.")
    assert check_components(waived, "s.md", 300) == []


def case_a_prose_component_is_outside_the_code_loc_signal() -> None:
    """The 300 threshold is `run_arch_gate.py`'s, and that gate reads code.

    A phase that edits a long reference document is not carrying a 300-LOC
    violation, and a `**LOC waiver:**` asserting otherwise would be a false
    statement written to silence a check. Measured: a slice editing
    `triage/SKILL.md` — prose with its own separate 420-line hot-path budget,
    enforced by `test_skill_structure.py` — was reported as 419 LOC over a 300
    limit, and the only way through was that false waiver.
    """
    text = COMPONENTS.format(resp="Parses X", loc="419", foreign="none", waiver="")
    for doc in ("triage/SKILL.md", "references/ledger.md", "notes.txt", "README.rst"):
        prose = text.replace("`a.py`", f"`{doc}`")
        assert check_components(prose, "s.md", 300) == [], (doc, prose)


def case_a_code_component_is_still_measured() -> None:
    """The skip is by file kind, never a blanket amnesty."""
    for code in ("a.py", "run.sh", "lib/reader.dart", "Main.kt"):
        text = COMPONENTS.format(resp="Parses X", loc="400",
                                 foreign="none", waiver="").replace("`a.py`", f"`{code}`")
        assert severities(check_components(text, "s.md", 300), "components") == ["error"], code


def case_missing_loc_cell_is_only_a_warning() -> None:
    text = COMPONENTS.format(resp="Parses X", loc="tbd", foreign="none", waiver="")
    assert severities(check_components(text, "s.md", 300), "components") == ["warn"]


def case_six_foreign_modules_are_an_error() -> None:
    text = COMPONENTS.format(resp="Parses X", loc="90",
                             foreign="a, b, c, d, e, f", waiver="")
    found = check_components(text, "s.md", 300)
    assert severities(found, "components") == ["error"], found
    assert "6 foreign" in found[0].reason, found


def case_missing_component_table_is_an_error() -> None:
    found = check_components("# Phase 1\n", "s.md", 300)
    assert severities(found, "components") == ["error"], found


def case_a_phase_that_declares_no_components_is_clean() -> None:
    """A delivery phase edits configuration only and creates no component."""
    text = ("## Component Decomposition\n\nNo components. This phase changes "
            "dependency configuration only.\n\n## Implementation Progress\n")
    assert check_components(text, "s.md", 300) == []


def case_a_symbol_or_a_version_is_not_a_file() -> None:
    text = (STEPS + "\n## Files Created\n\n- `0.18.0`\n- `^0.17.2`\n"
            "- `Locations.tocFragment`\n- `package:collection`\n- `toc=`\n"
            "- `findTocIndexByPage`\n- `lib/a.dart` (10 lines)\n")
    assert check_phase_thresholds(text, "s.md", True) == []


def case_a_phase_that_writes_no_source_needs_no_test_step() -> None:
    """A version bump has nothing to test-drive; only implementation demands a test."""
    text = ("## Implementation Progress\n\n"
            "- [ ] Bump the constraint in `pubspec.yaml`. Done when resolved.\n"
            "- [ ] Run the formatter.\n")
    assert severities(check_step_order(text, "s.md"), "step-order").count("error") == 0


def case_invented_gate_command_is_an_error() -> None:
    text = "## Verification\n\n- Phase exit: run `make phase-gate`.\n"
    found = check_verification(text, "s.md")
    assert severities(found, "verification") == ["error", "error"], found
    assert check_verification(VERIFICATION, "s.md") == []


def case_a_non_gate_command_is_left_alone() -> None:
    text = VERIFICATION + "- TDD inner loop: `flutter test test/a_test.dart`.\n"
    assert check_verification(text, "s.md") == []


def case_a_heading_name_or_a_stage_name_is_not_a_command() -> None:
    """`## Architecture Gate Results` and a bare `phase-exit` are prose."""
    text = (VERIFICATION
            + "- Paste the ledger into `## Architecture Gate Results`.\n"
            + "- The stage is `phase-exit`.\n"
            + "- Run `python3 execute/scripts/run_arch_gate.py lib/a.dart`.\n")
    assert check_verification(text, "s.md") == []


def case_a_cd_prefixed_validate_call_is_allowed() -> None:
    text = ("## Verification\n\n- Run `cd /repo && ./validate run phase-exit` "
            "— every row PASS.\n")
    assert check_verification(text, "s.md") == []


CASES = [v for k, v in sorted(globals().items()) if k.startswith("case_")]


def main() -> int:
    failed = 0
    for case in CASES:
        try:
            case()
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
