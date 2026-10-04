#!/usr/bin/env python3
"""Tests for plan_artifact_checks.py — direct calls, no CLI in the way.

Run with `python3 test_plan_artifact_checks.py` (no pytest dependency).
"""

from __future__ import annotations

import hashlib
import sys
import tempfile
import traceback
from pathlib import Path

from plan_artifact_checks import (check_background, check_dependencies,
                                  check_localization, check_shape,
                                  check_tracker_intents, cycle_path,
                                  locales_on_disk, parse_deps)

DEPS = """## Dependency Table

| Phase | Repo | Scope | Depends on | Slice |
|---|---|---|---|---|
| **1: One** | r | a | — | [phase_1_one.md](phase_1_one.md) |
| **2: Two** | r | b | {two} | [phase_2_two.md](phase_2_two.md) |
"""


def severities(findings, check):
    return [f.severity for f in findings if f.check == check]


def write_plan(tmp: Path, name="skills_epic_demo_thing", phases=(1, 2), master=None):
    root = tmp / name
    root.mkdir()
    rows = "\n".join(
        f"| **{n}: P{n}** | s | — | [phase_{n}_demo_slice.md](phase_{n}_demo_slice.md) |"
        for n in phases)
    (root / "plan.md").write_text(master or (
        "# T\n\n## Dependency Table\n\n| Phase | Scope | Depends on | Slice |\n"
        "|---|---|---|---|\n" + rows + "\n"), encoding="utf-8")
    slices = []
    for n in phases:
        p = root / f"phase_{n}_demo_slice.md"
        p.write_text("# x\n", encoding="utf-8")
        slices.append((n, p, "# x\n"))
    return root, slices


def case_clean_folder_shape_reports_nothing(tmp: Path) -> None:
    root, slices = write_plan(tmp)
    assert check_shape(root, (root / "plan.md").read_text(), slices) == []


def case_folder_name_off_convention_is_an_error(tmp: Path) -> None:
    root, slices = write_plan(tmp, name="skills_thing_demo")
    found = check_shape(root, (root / "plan.md").read_text(), slices)
    assert severities(found, "shape") == ["error"], found


def case_a_dead_slice_link_is_an_error(tmp: Path) -> None:
    root, slices = write_plan(tmp)
    (root / "phase_2_demo_slice.md").unlink()
    found = check_shape(root, (root / "plan.md").read_text(), slices[:1])
    reasons = " ".join(f.reason for f in found)
    assert "phase_2_demo_slice.md does not exist" in reasons, found


def case_deps_are_read_only_after_the_word_phase(tmp: Path) -> None:
    """A version number in the cell must not become a dependency."""
    assert parse_deps("—") == set()
    assert parse_deps("Phase 1") == {1}
    assert parse_deps("Phases 1,2,5") == {1, 2, 5}
    assert parse_deps("Phases 1–3 **and** plugin 0.18.0 published") == {1, 2, 3}


def case_a_dependency_on_an_undefined_phase_is_an_error(tmp: Path) -> None:
    found = check_dependencies(DEPS.format(two="Phase 9"), "plan.md")
    assert severities(found, "dependencies") == ["error"], found
    assert "phase 9" in found[0].reason, found


def case_a_self_dependency_is_an_error(tmp: Path) -> None:
    found = check_dependencies(DEPS.format(two="Phase 2"), "plan.md")
    assert "depends on itself" in found[0].reason, found


def case_a_clean_table_with_an_extra_column_parses(tmp: Path) -> None:
    assert check_dependencies(DEPS.format(two="Phase 1"), "plan.md") == []


def case_cycle_path_names_the_cycle(tmp: Path) -> None:
    assert cycle_path({1: {2}, 2: {3}, 3: {1}}) == [1, 2, 3, 1]
    assert cycle_path({1: set(), 2: {1}}) is None


def case_create_without_notes_is_an_error(tmp: Path) -> None:
    found = check_tracker_intents('bd create "T" -t task\n', "plan.md")
    assert severities(found, "tracker") == ["error"], found


def case_a_relative_notes_path_is_an_error(tmp: Path) -> None:
    text = 'bd create "T" -t task --notes "Slice: phase_1_a.md\nMaster: /abs/plan.md"\n'
    found = check_tracker_intents(text, "plan.md")
    assert severities(found, "tracker") == ["error"], found
    assert "phase_1_a.md" in found[0].reason, found


def case_absolute_notes_across_lines_are_clean(tmp: Path) -> None:
    text = ('bd create "T" -t task --notes "Slice: /abs/phase_1_a.md\n'
            'Master: /abs/plan.md\nFull detail in the slice."\n')
    assert check_tracker_intents(text, "plan.md") == []


def case_a_file_reference_in_description_is_an_error(tmp: Path) -> None:
    text = 'bd create "T" --description "Do it. Slice: /abs/p.md" --notes "Plan: /abs/plan.md"\n'
    found = check_tracker_intents(text, "plan.md")
    assert severities(found, "tracker") == ["error"], found
    assert "--description" in found[0].reason, found


def case_a_document_named_in_a_description_is_not_a_path(tmp: Path) -> None:
    """The real `skills-g57.2` description names a skill doc inside a prose step."""
    text = ('bd create "T" --description "1. Explore investigate SKILL.md Steps '
            '2/4/5; read two real investigation files" --notes "Plan: /abs/plan.md"\n')
    assert check_tracker_intents(text, "plan.md") == []


def case_a_labelled_path_in_a_description_is_still_an_error(tmp: Path) -> None:
    """A label introducing a path, and a bare absolute path, both still fail."""
    for desc in ("Do it. Investigation: notes/x.md", "Do it. See /abs/x.md"):
        text = (f'bd create "T" --description "{desc}" '
                '--notes "Plan: /abs/plan.md"\n')
        found = check_tracker_intents(text, "plan.md")
        assert severities(found, "tracker") == ["error"], (desc, found)
        assert "--description" in found[0].reason, found


def case_a_bare_plan_filename_in_a_description_is_an_error(tmp: Path) -> None:
    text = ('bd create "T" --description "See phase_2_plan_lint_checks.md" '
            '--notes "Plan: /abs/plan.md"\n')
    found = check_tracker_intents(text, "plan.md")
    assert severities(found, "tracker") == ["error"], found


def case_locales_are_read_from_a_nested_package_root(tmp: Path) -> None:
    """A plan's project directory is routinely the outer of two package roots."""
    nested = tmp / "repo" / "pkg" / "lib" / "l10n"
    nested.mkdir(parents=True)
    for locale in ("en", "pt_BR"):
        (nested / f"app_{locale}.arb").write_text("{}", encoding="utf-8")
    ios = tmp / "repo" / "ios" / "de.lproj"
    ios.mkdir(parents=True)
    (ios / "Localizable.strings").write_text("", encoding="utf-8")
    assert locales_on_disk(tmp / "repo") == {"en", "pt_BR", "de"}


def case_localization_skips_when_no_locale_files_exist(tmp: Path) -> None:
    found = check_localization("# T\n", "touches `app_en.arb`", tmp, "plan.md")
    assert severities(found, "localization") == ["skip"], found


def case_missing_locales_are_listed_once(tmp: Path) -> None:
    l10n = tmp / "lib" / "l10n"
    l10n.mkdir(parents=True)
    for locale in ("en", "fr", "de"):
        (l10n / f"app_{locale}.arb").write_text("{}", encoding="utf-8")
    master = "# T\n\n## Localization\n\n| Locale | File |\n|---|---|\n| en | x |\n"
    found = check_localization(master, "adds a key to `app_en.arb`", tmp, "plan.md")
    assert severities(found, "localization") == ["warn"], found
    assert "de, fr" in found[0].reason, found


def case_a_plan_that_moves_no_strings_is_clean(tmp: Path) -> None:
    l10n = tmp / "lib" / "l10n"
    l10n.mkdir(parents=True)
    (l10n / "app_en.arb").write_text("{}", encoding="utf-8")
    assert check_localization("# T\n", "no strings move here", tmp, "plan.md") == []


def case_a_mention_of_the_l10n_directory_alone_does_not_trigger(tmp: Path) -> None:
    """The trigger must not fire on a plan that only names the l10n folder."""
    l10n = tmp / "lib" / "l10n"
    l10n.mkdir(parents=True)
    (l10n / "app_en.arb").write_text("{}", encoding="utf-8")
    assert check_localization("# T\n", "reads `lib/l10n/` for context", tmp, "plan.md") == []


def case_a_backticked_investigation_path_is_still_absolute(tmp: Path) -> None:
    invest = tmp / "i.md"
    invest.write_text("evidence\n", encoding="utf-8")
    master = f"# T\n\n## Background\n\n**Investigation:** `{invest}`\n"
    assert severities(check_background(master, "plan.md", {}), "background") == ["skip"]


def case_a_backticked_notes_path_is_still_absolute(tmp: Path) -> None:
    text = 'bd create "T" --notes "Slice: `/abs/phase_1_a.md`"\n'
    assert check_tracker_intents(text, "plan.md") == []


def case_background_without_a_recorded_hash_reports_skip(tmp: Path) -> None:
    invest = tmp / "i.md"
    invest.write_text("evidence\n", encoding="utf-8")
    master = f"# T\n\n## Background\n\n**Investigation:** {invest}\n"
    found = check_background(master, "plan.md", {})
    assert severities(found, "background") == ["skip"], found
    assert "skipped, not passed" in found[0].reason, found


def case_background_hash_mismatch_quotes_both(tmp: Path) -> None:
    invest = tmp / "i.md"
    invest.write_text("evidence\n", encoding="utf-8")
    master = f"# T\n\n## Background\n\n**Investigation:** {invest}\n"
    real = hashlib.sha256(invest.read_bytes()).hexdigest()
    found = check_background(master, "plan.md", {"*": "0" * 64})
    assert severities(found, "background") == ["error"], found
    assert real in found[0].reason and "0" * 64 in found[0].reason, found
    assert check_background(master, "plan.md", {str(invest.resolve()): real}) == []


def case_a_missing_investigation_file_is_an_error(tmp: Path) -> None:
    master = f"# T\n\n## Background\n\n**Investigation:** {tmp / 'gone.md'}\n"
    found = check_background(master, "plan.md", {})
    assert severities(found, "background") == ["error"], found


def case_a_background_about_something_else_only_warns(tmp: Path) -> None:
    master = "# T\n\n## Background\n\n**Design spec:** `design/spec.html`\n"
    assert severities(check_background(master, "plan.md", {}), "background") == ["warn"]


def case_no_background_section_means_no_findings(tmp: Path) -> None:
    assert check_background("# T\n\n## Objective\n\nx\n", "plan.md", {}) == []


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
