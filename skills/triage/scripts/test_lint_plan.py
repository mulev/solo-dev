#!/usr/bin/env python3
"""Tests for lint_plan.py — one fixture plan tree per check.

Run with `python3 test_lint_plan.py` (no pytest dependency).

**LOC waiver:** a fixture-per-check case list, read one case at a time — the
same shape as `execute/scripts/test_run_arch_gate.py` and
`test_lint_investigation.py`. Alternatives considered are recorded in the
phase slice's Files Created section. It is a few lines over 300: splitting the
case list would hand both halves the same fixture builders and move no
behaviour — the metric-laundering split `_shared/architecture-principles.md`
fails on sight.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "lint_plan.py"

CHECK_IDS = ["shape", "headers", "thresholds", "step-order", "components",
             "dependencies", "verification", "tracker", "localization",
             "background"]

MASTER = """# Skills Epic: Demo thing

**Status:** 🔄 IN PROGRESS
**System plan file:** /Users/demo/.claude/plans/skills_epic_demo_thing.md

A demo master plan used by the linter's own fixtures.
{background}
## Dependency Table

| Phase | Scope | Depends on | Slice |
|-------|-------|------------|-------|
{rows}

## Progress

{progress}

## Objective

Demonstrate a clean plan artifact.
{tracker}
## Success Criteria

- [ ] The linter reports nothing.
"""

DEP_ROW = ("| **{n}: Demo slice** | scope {n} | {deps} | "
           "[phase_{n}_demo_slice.md](phase_{n}_demo_slice.md) |")

PROGRESS_ROW = "- [ ] [Phase {n}: Demo slice](phase_{n}_demo_slice.md) — `skills-demo.{n}`"

SLICE = """# Phase {n}: Demo slice — does one demo thing

{parent}**Beads task:** `skills-demo.{n}`
**Status:** 🔄 IN PROGRESS

## Prerequisites

None — this phase has no dependencies.

## Component Decomposition

| Component | Responsibility (one sentence, no "and") | Public API | \
Callers (≥2 OR single-caller + own test) | Foreign modules touched | \
Projected LOC | Test approach |
|---|---|---|---|---|---|---|
| `demo/thing_{n}.py` | {responsibility} | `main(argv)` | `runner.py`, its own \
test | none | {loc} | pure function over text |
{waiver}
## Implementation Progress

{steps}

## Implementation

{files}
## Testing

### Unit Tests

**New file:** `demo/test_thing_{n}.py`

### Integration Tests

- Scenario: the demo flow end to end.

## Documentation

- Update `docs/demo.md`.

{verification}
## Files Created

## Files Modified
"""

STEPS = """- [ ] Read `demo/thing_{n}.py` — understand the flow. Done when you can describe it.
- [ ] Create `demo/test_thing_{n}.py` — a test for parsing. Done when it **fails**.
- [ ] Implement parsing in `demo/thing_{n}.py`. Done when the suite is green.
- [ ] Add an integration test for the demo flow in `demo/test_thing_{n}.py`. Done when it compiles.
- [ ] Update `docs/demo.md` — add a section on parsing. Done when saved.
- [ ] Run the formatter, then the polish pass. Done when clean."""

VERIFICATION = """## Verification

- TDD inner loop: `python3 demo/test_thing_{n}.py`.
- Phase exit, from the repo root: `./validate run phase-exit` — every row PASS.
"""

FILES = "### File: `demo/thing_{n}.py`\n\nWhat changes and why.\n"


def slice_text(n: int, **over) -> str:
    return SLICE.format(
        n=n,
        parent=over.get("parent", "**Parent plan:** [plan.md](plan.md)\n"),
        responsibility=over.get("responsibility", "Parses the demo file"),
        loc=over.get("loc", "90"),
        waiver=over.get("waiver", ""),
        steps=over.get("steps", STEPS.format(n=n)),
        files=over.get("files", FILES.format(n=n)),
        verification=over.get("verification", VERIFICATION.format(n=n)),
    )


def plan_tree(tmp: Path, numbers=(1, 2), deps=None, slices=None, **over) -> Path:
    """Write a clean plan folder, then apply the named overrides."""
    root = tmp / "skills_epic_demo_thing"
    root.mkdir()
    deps = deps or {}
    rows = "\n".join(DEP_ROW.format(n=n, deps=deps.get(n, "—")) for n in numbers)
    progress = "\n".join(PROGRESS_ROW.format(n=n) for n in numbers)
    (root / "plan.md").write_text(
        over.get("master", MASTER).format(
            rows=rows, progress=progress,
            background=over.get("background", ""),
            tracker=over.get("tracker", "")),
        encoding="utf-8")
    for n in numbers:
        body = (slices or {}).get(n) or slice_text(n)
        (root / f"phase_{n}_demo_slice.md").write_text(body, encoding="utf-8")
    return root


def run(*args) -> tuple[int, str]:
    proc = subprocess.run([sys.executable, str(SCRIPT), *[str(a) for a in args]],
                          capture_output=True, text=True)
    return proc.returncode, proc.stdout + proc.stderr


def errors_for(out: str, check: str) -> list[str]:
    return [l for l in out.splitlines()
            if l.startswith("ERROR") and f" {check} " in l]


# --------------------------------------------------------------------------
# cases
# --------------------------------------------------------------------------

def case_clean_two_phase_folder_passes(tmp: Path) -> None:
    code, out = run(plan_tree(tmp))
    assert code == 0, out
    assert not [l for l in out.splitlines() if l.startswith("ERROR")], out


def case_single_phase_written_as_folder_fails(tmp: Path) -> None:
    code, out = run(plan_tree(tmp, numbers=(1,)))
    assert code == 1, out
    assert errors_for(out, "shape"), out


def case_phase_number_gap_fails(tmp: Path) -> None:
    code, out = run(plan_tree(tmp, numbers=(1, 3)))
    assert code == 1, out
    hits = errors_for(out, "shape")
    assert any("1, 3" in h for h in hits), out


def case_missing_parent_plan_field_fails(tmp: Path) -> None:
    root = plan_tree(tmp, slices={1: slice_text(1, parent="")})
    code, out = run(root)
    assert code == 1, out
    assert any("Parent plan" in h for h in errors_for(out, "headers")), out


def case_nine_implementation_steps_fail(tmp: Path) -> None:
    """The padding must be implementation, which is what the limit counts.

    It used to read "Run the formatter once more" — `polish`, not
    implementation, which passed only while the counter counted every checkbox
    regardless of category. `STEPS` contributes one implementation step, so
    eight more reach the limit and trip it.
    """
    extra = "".join(f"\n- [ ] Implement step {i} in `demo/thing_1.py`. Done when green."
                    for i in range(8))
    root = plan_tree(tmp, slices={1: slice_text(1, steps=STEPS.format(n=1) + extra)})
    code, out = run(root)
    assert code == 1, out
    assert any("9" in h for h in errors_for(out, "thresholds")), out


GATE_STEP_LINE = ("\n- [ ] **Gate artifact.** Run the architecture gate on every "
                  "changed file, and write the `## Architecture Gate Results` block.")


def case_gate_checkbox_does_not_count_toward_the_step_limit(tmp: Path) -> None:
    extra = ("\n- [ ] Run the linter over the fixture. Done when clean."
             "\n- [ ] Update `docs/demo.md` — add a second section. Done when saved.")
    steps = STEPS.format(n=1) + extra + GATE_STEP_LINE
    root = plan_tree(tmp, slices={1: slice_text(1, steps=steps)})
    code, out = run(root)
    assert code == 0, out
    assert not errors_for(out, "thresholds"), out


def case_docs_only_slice_passes(tmp: Path) -> None:
    steps = ("- [ ] Read `docs/demo.md` — understand the structure. Done when described.\n"
             "- [ ] Update `docs/demo.md` — add a section on parsing. Done when saved.\n"
             "- [ ] Update `README.md` — link the new section. Done when saved.\n"
             "- [ ] Run `./validate run phase-exit`. Done when every row is PASS.")
    root = plan_tree(tmp, slices={1: slice_text(1, steps=steps)})
    code, out = run(root)
    assert code == 0, out
    assert not errors_for(out, "step-order"), out


def case_description_naming_a_skill_doc_passes(tmp: Path) -> None:
    tracker = ('\n## Tracker\n\n```sh\nbd create "Phase 1" -t task '
               '--description "Read investigate SKILL.md Steps 2/4/5" '
               '--notes "Slice: /abs/phase_1_demo_slice.md"\n```\n')
    code, out = run(plan_tree(tmp, tracker=tracker))
    assert code == 0, out
    assert not errors_for(out, "tracker"), out


def case_six_unrelated_files_warn(tmp: Path) -> None:
    """A warning: the rule counts *unrelated* files, which no count can decide."""
    files = "".join(f"### File: `demo/mod_{i}.py`\n\nWhat changes.\n\n" for i in range(6))
    root = plan_tree(tmp, slices={1: slice_text(1, files=files)})
    code, out = run(root)
    assert code == 0, out
    warns = [l for l in out.splitlines() if l.startswith("WARN") and " thresholds " in l]
    assert any("demo/mod_5.py" in w for w in warns), out


def case_implementation_before_tests_fails(tmp: Path) -> None:
    steps = ("- [ ] Implement parsing in `demo/thing_1.py`. Done when it works.\n"
             "- [ ] Create `demo/test_thing_1.py` — a test for parsing. Done when it **fails**.")
    root = plan_tree(tmp, slices={1: slice_text(1, steps=steps)})
    code, out = run(root)
    assert code == 1, out
    assert errors_for(out, "step-order"), out


def case_step_order_missing_category_warns(tmp: Path) -> None:
    steps = ("- [ ] Read `demo/thing_1.py` — understand the flow. Done when described.\n"
             "- [ ] Create `demo/test_thing_1.py` — a test. Done when it **fails**.\n"
             "- [ ] Implement parsing in `demo/thing_1.py`. Done when green.")
    root = plan_tree(tmp, slices={1: slice_text(1, steps=steps)})
    code, out = run(root)
    assert code == 0, out
    warns = [l for l in out.splitlines() if l.startswith("WARN") and " step-order " in l]
    assert any("documentation" in w for w in warns), out


def case_responsibility_with_and_fails(tmp: Path) -> None:
    root = plan_tree(tmp, slices={1: slice_text(1, responsibility="Parses X and writes Y")})
    code, out = run(root)
    assert code == 1, out
    assert any("and" in h for h in errors_for(out, "components")), out


def case_400_loc_without_waiver_fails(tmp: Path) -> None:
    root = plan_tree(tmp, slices={1: slice_text(1, loc="400")})
    code, out = run(root)
    assert code == 1, out
    assert any("400" in h for h in errors_for(out, "components")), out


def case_400_loc_with_waiver_passes(tmp: Path) -> None:
    waiver = ("\n**LOC waiver:** `demo/thing_1.py` — projected 400 LOC. Reason: cohesive "
              "state machine. Alternatives considered: a split by stage, rejected.\n")
    root = plan_tree(tmp, slices={1: slice_text(1, loc="400", waiver=waiver)})
    code, out = run(root)
    assert code == 0, out


def case_cyclic_dependency_table_fails(tmp: Path) -> None:
    code, out = run(plan_tree(tmp, deps={1: "Phase 2", 2: "Phase 1"}))
    assert code == 1, out
    assert any("1 -> 2 -> 1" in h for h in errors_for(out, "dependencies")), out


def case_invented_verification_command_fails(tmp: Path) -> None:
    bogus = "## Verification\n\n- Phase exit: run `make phase-gate` and read the report.\n"
    root = plan_tree(tmp, slices={1: slice_text(1, verification=bogus)})
    code, out = run(root)
    assert code == 1, out
    assert any("make phase-gate" in h for h in errors_for(out, "verification")), out


def case_notes_with_relative_path_fails(tmp: Path) -> None:
    tracker = ('\n## Tracker\n\n```sh\nbd create "Phase 1" -t task '
               '--notes "Slice: phase_1_demo_slice.md"\n```\n')
    code, out = run(plan_tree(tmp, tracker=tracker))
    assert code == 1, out
    assert any("phase_1_demo_slice.md" in h for h in errors_for(out, "tracker")), out


def case_a_slice_quoting_an_example_create_is_not_an_intent(tmp: Path) -> None:
    """A slice documenting a bad `bd create` fixture is not issuing one."""
    bad = ('\n## Testing\n\n```sh\nbd create "Phase 1" -t task '
           '--notes "Slice: phase_1_demo_slice.md"\n```\n')
    root = plan_tree(tmp, slices={1: slice_text(1) + bad})
    code, out = run(root)
    assert code == 0, out
    assert not errors_for(out, "tracker"), out


def case_notes_merged_into_description_fails(tmp: Path) -> None:
    tracker = ('\n## Tracker\n\n```sh\nbd create "Phase 1" -t task '
               '--description "Do the work. Slice: /abs/phase_1.md"\n```\n')
    code, out = run(plan_tree(tmp, tracker=tracker))
    assert code == 1, out
    assert len(errors_for(out, "tracker")) == 2, out


def _background(tmp: Path) -> tuple[Path, str]:
    invest = tmp / "demo_invest_thing.md"
    invest.write_text("# Investigation\n\nRoot cause found.\n", encoding="utf-8")
    section = (f"\n## Background\n\n**Investigation:** {invest}\n"
               "**Root cause (1 sentence):** The counter reset.\n")
    return invest, section


def case_background_hash_mismatch_fails(tmp: Path) -> None:
    invest, section = _background(tmp)
    root = plan_tree(tmp, background=section)
    code, out = run(root, "--investigation-hash", "0" * 64)
    assert code == 1, out
    real = hashlib.sha256(invest.read_bytes()).hexdigest()
    hits = errors_for(out, "background")
    assert any(real in h and "0" * 64 in h for h in hits), out


def case_background_without_expectation_reports_skip(tmp: Path) -> None:
    _, section = _background(tmp)
    code, out = run(plan_tree(tmp, background=section))
    assert code == 0, out
    assert [l for l in out.splitlines()
            if l.startswith("SKIP") and " background " in l], out


def case_a_hash_file_turns_the_background_skip_into_a_comparison(tmp: Path) -> None:
    """`--investigation-hash-file` in the order `shasum -a 256` prints it:
    hash first, absolute path second. Reversed, every line is ignored and the
    check silently falls back to the SKIP it was added to remove."""
    invest, section = _background(tmp)
    root = plan_tree(tmp, background=section)
    digest = hashlib.sha256(invest.read_bytes()).hexdigest()
    hashes = tmp / "hashes.txt"
    hashes.write_text(f"{digest}  {invest}\n", encoding="utf-8")
    code, out = run(root, "--investigation-hash-file", str(hashes))
    assert code == 0, out
    assert not [l for l in out.splitlines()
                if l.startswith("SKIP") and " background " in l], out


def case_a_missing_hash_file_stays_a_skip(tmp: Path) -> None:
    """`SKILL.md` Wave 5 passes `--investigation-hash-file {run}/hashes.txt`
    unconditionally, so the flag arrives for runs that never wrote the file:
    a Wave 4 that predates it, or one that dispatched no investigation at all.
    `references/ledger.md` says such a run "has nothing to compare and is not
    thereby defective" - a missing hash stays a SKIP, never an error. It exited
    2 instead, which turns the orchestrator's own hot path into a hard failure.
    """
    _, section = _background(tmp)
    root = plan_tree(tmp, background=section)
    code, out = run(root, "--investigation-hash-file", str(tmp / "absent.txt"))
    assert code == 0, out
    assert [l for l in out.splitlines()
            if l.startswith("SKIP") and " background " in l], out


def case_localization_missing_locales_warn(tmp: Path) -> None:
    code_root = tmp / "demoapp" / "demoapp"
    (code_root / "lib" / "l10n").mkdir(parents=True)
    for locale in ("en", "fr"):
        (code_root / "lib" / "l10n" / f"app_{locale}.arb").write_text("{}", encoding="utf-8")
    master = MASTER.replace("Demonstrate a clean plan artifact.",
                            "Move a user-facing string into `lib/l10n/app_en.arb`.")
    root = plan_tree(tmp, master=master)
    code, out = run(root, "--project-root", tmp / "demoapp")
    assert code == 0, out
    warns = [l for l in out.splitlines() if l.startswith("WARN") and " localization " in l]
    assert any("fr" in w for w in warns), out


def case_no_locale_files_reports_skip(tmp: Path) -> None:
    empty = tmp / "noloc"
    empty.mkdir()
    code, out = run(plan_tree(tmp), "--project-root", empty)
    assert code == 0, out
    assert [l for l in out.splitlines()
            if l.startswith("SKIP") and " localization " in l], out


def case_help_lists_every_check(tmp: Path) -> None:
    code, out = run("--help")
    assert code == 0, out
    missing = [c for c in CHECK_IDS if c not in out]
    assert not missing, missing


def case_missing_path_returns_2(tmp: Path) -> None:
    code, out = run(tmp / "nope")
    assert code == 2, out
    assert out.startswith("lint_plan:"), out


def case_directory_without_plan_md_warns(tmp: Path) -> None:
    empty = tmp / "not_a_plan"
    empty.mkdir()
    code, out = run(empty)
    assert code == 0, out
    warns = [l for l in out.splitlines() if l.startswith("WARN")]
    assert len(warns) == 1 and "plan.md" in warns[0], out


def case_json_output_reports_counts(tmp: Path) -> None:
    code, out = run(plan_tree(tmp, numbers=(1,)), "--json")
    assert code == 1, out
    data = json.loads(out)
    assert data["errors"] == len([f for f in data["findings"]
                                  if f["severity"] == "error"]), data
    assert data["errors"] >= 1, data
    assert {"findings", "errors", "warnings", "skipped"} <= set(data), data


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
