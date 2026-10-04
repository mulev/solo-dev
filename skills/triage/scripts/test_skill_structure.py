"""Structural assertions over triage/SKILL.md.

The orchestrator skill is prose, so nothing compiles it and no linter reads
it. These checks are the only thing standing between a wording change and a
skill that silently stops printing its banner, loses a wave, or names a
config shorthand nobody defined.

Every assertion here is calibrated to fail on a structural defect and on
nothing else: each one has a red fixture below proving it fires, and
`case_real_skill_is_clean` proving it does not fire on the real file. A check
that cannot do both is a check that will be waived the first time it is
inconvenient.

**LOC waiver:** a check paired with its red fixture, one pair at a time — the
same shape and reasoning as `test_lint_investigation.py`. The pairing is the
point: separating the checks from the fixtures that prove they fire would put
the two halves of every assertion in different files, which is the one split
that would make this suite harder to trust rather than easier.

Run with `python3 test_skill_structure.py` (no pytest dependency).
Exit 0 = every case passed, 1 = findings, 2 = broken invocation.
"""

from __future__ import annotations

import contextlib
import io
import re
import sys
import tempfile
import traceback
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]  # .../skills
SKILL = REPO / "triage" / "SKILL.md"
# The shipped template, not the live `skill.config.md`: `**/skill.config.md`
# is gitignored, so on a fresh clone the live file does not exist and this
# suite — a phase-exit validator row — would fail for having been checked out.
# The template is also the stronger subject: it is what a new install reads.
CONFIG = REPO / "triage" / "skill.config.example.md"
BANNER = "[triage] Triaging..."
# Raised from 400 by an explicit call, not by nudging it to fit an edit. The
# budget's job is to keep the hot path readable, not to hold a number: what it
# actually forbids is detail that belongs in `references/`, and the Wave 6
# dry-run rule that pushed past 400 is a rule the orchestrator applies inline.
# Move detail out before raising this again.
#
# Raised from 420 to 430 by a second explicit call: every workflow skill in the
# bundle gained a `## Conduct` section pointing at `_shared/agent-conduct.md`,
# which is bundle-wide required reading rather than detail belonging in
# `references/`. Wave 1 was checked first and holds no reference-grade detail —
# it is all instruction the orchestrator applies inline — so there was nothing
# to move out instead.
MAX_LINES = 430

REQUIRED_SECTIONS = (
    "## Invocation",
    "## Asking the user",
    "## Invoking companion skills",
    "## Configuration",
    "## Wave 0 — Inventory",
    "## Wave 1 — Dedup",
    "## Wave 2 — Investigation",
    "## Wave 3 — Collision",
    "## Wave 4 — Planning",
    "## Wave 5 — Quality control",
    "## Wave 6 — Report",
    "## Constraints",
)

# Phrases each wave's own body must state; `_ledger_row_findings` carries the
# rationale. Matching is whitespace- and case-insensitive, so a rewrap is safe.
LEDGER_ROW_WAVES = (
    ("## Wave 0 — Inventory", ("ledger row", "`all`")),
    ("## Wave 1 — Dedup", ("ledger row", "`all`", "one row per group")),
    ("## Wave 3 — Collision", ("ledger row", "`all`", "one row per group")),
)

# Phrases Wave 5's tier-2 step must state, so the dispatch resolves on a
# harness whose roster carries no `triage-qc`. Each one is absent from the
# unfixed file: a phrase the section already carries proves nothing.
TIER_TWO_PHRASES = ("registered `triage-qc` agent", "roster carries",
                    "else a worker", "agents/triage-qc.md")

# Braced names that stand for a value the run computes, not a config field.
# The set is closed and small on purpose: without it the shorthand cross-check
# would demand a config field for `{project}`, and a check that fires on
# correct prose gets switched off rather than obeyed.
RUNTIME_PLACEHOLDERS = frozenset({"project", "run", "runid", "projects_root"})

TOKEN_RE = re.compile(r"\{([a-z][a-z0-9_]*)\}")
ROW_RE = re.compile(r"^\|\s*`\{([a-z][a-z0-9_]*)\}`\s*\|([^|]*)\|")


# --- reading the file ---------------------------------------------------------


def _heading_index(lines: list[str], heading: str) -> int:
    """Index of `heading` as a real H2 line, or -1.

    Anchored on the whole line: the same string routinely appears inside a
    bullet or a table cell, and matching those finds the wrong place.
    """
    for i, line in enumerate(lines):
        if line.rstrip() == heading:
            return i
    return -1


def _next_h2(lines: list[str], start: int) -> int:
    for i in range(start + 1, len(lines)):
        if lines[i].startswith("## "):
            return i
    return len(lines)


def _outside_fences(lines: list[str]) -> list[int]:
    """Indices of lines that are not inside a fenced code block."""
    outside, fenced = [], False
    for i, line in enumerate(lines):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if not fenced:
            outside.append(i)
    return outside


# --- the six assertions -------------------------------------------------------


def _frontmatter_findings(lines: list[str]) -> list[str]:
    if not lines or lines[0].rstrip() != "---":
        return ["frontmatter: file does not open with `---`"]
    close = next((i for i in range(1, len(lines)) if lines[i].rstrip() == "---"), -1)
    if close < 0:
        return ["frontmatter: no closing `---`"]
    block = lines[1:close]
    findings = []
    name = next((ln.split(":", 1)[1].strip() for ln in block
                 if ln.startswith("name:")), None)
    if name is None:
        findings.append("frontmatter: no `name:` key")
    elif name != "triage":
        findings.append(f"frontmatter: name is {name!r}, must be 'triage'")
    if not any(ln.startswith("description:") for ln in block):
        findings.append("frontmatter: no `description:` key")
    return findings


def _banner_findings(lines: list[str]) -> list[str]:
    where = next((i for i, ln in enumerate(lines) if BANNER in ln), -1)
    if where < 0:
        return [f"banner: {BANNER!r} appears nowhere in the file"]
    start = _heading_index(lines, "## Invocation")
    if start < 0:
        return []  # the missing section is reported by the section check
    if not (start < where < _next_h2(lines, start)):
        return [f"banner: {BANNER!r} sits outside the `## Invocation` section"]
    return []


def _section_findings(lines: list[str]) -> list[str]:
    return [f"section: {name!r} is missing"
            for name in REQUIRED_SECTIONS if _heading_index(lines, name) < 0]


def _ledger_row_findings(lines: list[str]) -> list[str]:
    """A wave that owes a ledger row and does not say so in its own body.

    Waves 0, 1 and 3 run in the main session: each records the script it ran,
    keyed `all`, plus — for 1 and 3 — every group that output was ruled into.
    That obligation lived only in `references/ledger.md`, whose read
    instruction fires at resume or report time, after the clocks these rows
    need are gone. Two live runs dropped Wave 1's row and one dropped Wave 3's.
    """
    findings = []
    for heading, phrases in LEDGER_ROW_WAVES:
        start = _heading_index(lines, heading)
        if start < 0:
            continue  # the missing section is reported by the section check
        body = " ".join(" ".join(lines[start:_next_h2(lines, start)]).split()).lower()
        findings += [f"ledger row: {heading!r} does not state {phrase!r}"
                     for phrase in phrases if phrase not in body]
    return findings


def _tier_two_findings(lines: list[str]) -> list[str]:
    """Wave 5 naming one dispatch the harness may not resolve.

    The typed name is the only one in the file; `triage/agents/triage-qc.md`
    is a definition no skill installs, so a tier-2 step that names it and
    nothing else is an instruction the orchestrator has to improvise past.
    """
    start = _heading_index(lines, "## Wave 5 — Quality control")
    if start < 0:
        return []  # the missing section is reported by the section check
    body = " ".join(" ".join(lines[start:_next_h2(lines, start)]).split()).lower()
    return [f"tier 2: Wave 5 does not state {phrase!r}"
            for phrase in TIER_TWO_PHRASES if phrase.lower() not in body]


def _defined_shorthands(lines: list[str]) -> tuple[dict[str, str], set[int]]:
    """Shorthand rows of the Configuration table: name -> config-field cell."""
    start = _heading_index(lines, "## Configuration")
    if start < 0:
        return {}, set()
    defined, rows = {}, set()
    for i in range(start, _next_h2(lines, start)):
        match = ROW_RE.match(lines[i])
        if match:
            defined[match.group(1)] = match.group(2).strip()
            rows.add(i)
    return defined, rows


def _shorthand_findings(lines: list[str], config_path) -> list[str]:
    defined, rows = _defined_shorthands(lines)
    used: set[str] = set()
    for i in _outside_fences(lines):
        if i not in rows:
            used.update(TOKEN_RE.findall(lines[i]))
    used -= RUNTIME_PLACEHOLDERS

    findings = [f"shorthand: {{{name}}} is used but the Configuration table "
                "does not define it" for name in sorted(used - set(defined))]
    findings += [f"shorthand: {{{name}}} is defined but the body never uses it"
                 for name in sorted(set(defined) - used)]

    config = Path(config_path)
    if not config.is_file():
        return findings + [f"config: no config file at {config}"]
    text = config.read_text(encoding="utf-8")
    for name in sorted(defined):
        key = defined[name].split("→")[-1].strip().strip("`")
        if not re.search(rf"(?m)^{re.escape(key)}:", text):
            findings.append(f"shorthand: {{{name}}} names config field "
                            f"{key!r}, which {config.name} does not carry")
    return findings


def check(skill_path, config_path) -> list[str]:
    """Return a list of findings; empty means the skill file is well-formed."""
    skill = Path(skill_path)
    if not skill.is_file():
        return [f"skill: no SKILL.md at {skill}"]
    lines = skill.read_text(encoding="utf-8").splitlines()
    findings = _frontmatter_findings(lines)
    findings += _banner_findings(lines)
    findings += _section_findings(lines)
    findings += _ledger_row_findings(lines)
    findings += _tier_two_findings(lines)
    findings += _shorthand_findings(lines, config_path)
    if len(lines) > MAX_LINES:
        findings.append(f"budget: SKILL.md is {len(lines)} lines, "
                        f"over the {MAX_LINES}-line hot-path budget")
    return findings


# --- fixtures -----------------------------------------------------------------

FIXTURE_SKILL = """---
name: triage
description: Fixture skill used by the structure checker's red cases.
---

# Triage

## Invocation

```
[triage] Triaging...
```

## Asking the user

Use the host's structured-question tool.

## Invoking companion skills

Invoke `investigate` and `plan` through the harness mechanism.

## Configuration

| Shorthand | Config field | Default |
|-----------|-------------|---------|
| `{plans_dir}` | Plans Directory → plans_dir | `project_plans` |

Every run stages under `{plans_dir}`.

## Wave 0 — Inventory

Inventory. Ledger row: `all` for the script it ran.

## Wave 1 — Dedup

Dedup. Ledger rows: `all` for the script, then one row per group.

## Wave 2 — Investigation

Investigation.

## Wave 3 — Collision

Collision. Ledger rows: one row per group, alongside the `all` row.

## Wave 4 — Planning

Planning.

## Wave 5 — Quality control

Quality control. Dispatch the registered `triage-qc` agent when this harness's
roster carries that name, else a worker whose first read is
`agents/triage-qc.md`.

## Wave 6 — Report

Report.

## Constraints

None.
"""

FIXTURE_CONFIG = "plans_dir: project_plans\n"

# The sole Configuration row of FIXTURE_SKILL; `sub` fails loudly if they drift.
FIXTURE_ROW = "| `{plans_dir}` | Plans Directory → plans_dir | `project_plans` |\n"

# FIXTURE_SKILL's tier-2 step, carrying every `TIER_TWO_PHRASES` entry; the red
# case replaces it with the one-branch form, and `sub` fails loudly on drift.
TIER_TWO_FIXTURE_STEP = (
    "Dispatch the registered `triage-qc` agent when this harness's\n"
    "roster carries that name, else a worker whose first read is\n"
    "`agents/triage-qc.md`.")


def sub(text: str, old: str, new: str) -> str:
    """Replace `old` once, refusing an ambiguous match."""
    assert text.count(old) == 1, f"{old!r} occurs {text.count(old)} times"
    return text.replace(old, new)


def drop_line(text: str, prefix: str) -> str:
    """Delete the one line starting with `prefix`, refusing an ambiguous match."""
    matches = [ln for ln in text.splitlines(keepends=True) if ln.startswith(prefix)]
    assert len(matches) == 1, f"{prefix!r} starts {len(matches)} lines"
    return sub(text, matches[0], "")


def write(tmp: Path, skill: str, config: str = FIXTURE_CONFIG) -> tuple[Path, Path]:
    skill_path, config_path = tmp / "SKILL.md", tmp / "skill.config.md"
    skill_path.write_text(skill, encoding="utf-8")
    config_path.write_text(config, encoding="utf-8")
    return skill_path, config_path


def expect_clean(tmp: Path, skill: str, config: str = FIXTURE_CONFIG) -> None:
    findings = check(*write(tmp, skill, config))
    assert findings == [], f"expected no findings, got {findings}"


def expect_finding(tmp: Path, skill: str, needle: str,
                   config: str = FIXTURE_CONFIG) -> None:
    findings = check(*write(tmp, skill, config))
    assert any(needle in f for f in findings), f"no {needle!r} in {findings}"


# --- cases --------------------------------------------------------------------


def case_real_skill_is_clean(tmp: Path) -> None:
    findings = check(SKILL, CONFIG)
    assert findings == [], f"real SKILL.md: {findings}"


def case_the_assigned_artifact_name_is_one_the_linter_accepts(tmp: Path) -> None:
    """Wave 2's naming rule and `lint_investigation.FILENAME` must agree.

    The orchestrator assigns every investigation's filename, so a convention
    the linter does not accept is unrepairable by the worker that receives it:
    the artifact fails `filename-convention` in Wave 5, tier 2 is gated on tier
    1, and the whole wave dies without ever reaching a reviewer. Measured on a
    live run whose orchestrator assigned `{bead}_{slug}.md`.

    The example in the prose is checked against the real regex rather than
    described, because a documented convention nothing executes is the one that
    drifts.
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from lint_investigation import FILENAME

    text = SKILL.read_text(encoding="utf-8")
    examples = re.findall(r"`([a-z0-9-]+_invest_[a-z0-9_-]+\.md)`", text)
    assert examples, "Wave 2 shows no example investigation filename"
    for name in examples:
        assert FILENAME.match(name), f"SKILL.md shows {name}, the linter rejects it"


def case_fixture_is_clean(tmp: Path) -> None:
    """Every red case below mutates this text, so it must start green."""
    expect_clean(tmp, FIXTURE_SKILL)


def case_missing_skill_is_a_finding(tmp: Path) -> None:
    findings = check(tmp / "absent.md", tmp / "absent.config.md")
    assert findings and "no SKILL.md" in findings[0], findings


def case_frontmatter_missing_name(tmp: Path) -> None:
    expect_finding(tmp, drop_line(FIXTURE_SKILL, "name:"), "no `name:` key")


def case_frontmatter_wrong_name(tmp: Path) -> None:
    expect_finding(tmp, sub(FIXTURE_SKILL, "name: triage", "name: sweep"),
                   "must be 'triage'")


def case_frontmatter_missing_description(tmp: Path) -> None:
    expect_finding(tmp, drop_line(FIXTURE_SKILL, "description:"),
                   "no `description:` key")


def case_frontmatter_absent(tmp: Path) -> None:
    expect_finding(tmp, "# Triage\n", "does not open with `---`")


def case_frontmatter_unterminated(tmp: Path) -> None:
    expect_finding(tmp, "---\nname: triage\n", "no closing `---`")


def case_banner_missing(tmp: Path) -> None:
    expect_finding(tmp, sub(FIXTURE_SKILL, BANNER, "Starting."), "appears nowhere")


def case_banner_outside_invocation(tmp: Path) -> None:
    """Presence is not placement: a banner under a later heading never prints first."""
    moved = sub(FIXTURE_SKILL, f"```\n{BANNER}\n```\n\n", "")
    expect_finding(tmp, sub(moved, "None.\n", f"```\n{BANNER}\n```\n"),
                   "outside the `## Invocation` section")


def case_banner_unverifiable_without_invocation_section(tmp: Path) -> None:
    text = sub(FIXTURE_SKILL, "## Invocation\n", "## Preamble\n")
    expect_finding(tmp, text, "'## Invocation' is missing")


def case_missing_wave_section(tmp: Path) -> None:
    text = sub(FIXTURE_SKILL, "## Wave 3 — Collision\n", "## Wave 3 — Overlap\n")
    expect_finding(tmp, text, "'## Wave 3 — Collision' is missing")


def case_a_wave_section_without_its_ledger_row_is_a_finding(tmp: Path) -> None:
    """The obligation lives in `references/ledger.md`, read too late to help."""
    body = "Dedup. Ledger rows: `all` for the script, then one row per group.\n"
    expect_finding(tmp, sub(FIXTURE_SKILL, body, "Dedup.\n"),
                   "'## Wave 1 — Dedup' does not state")


def case_a_wave_five_naming_only_the_agent_is_a_finding(tmp: Path) -> None:
    """The defect this phase fixes, pinned. A tier-2 step that names the typed
    agent and offers no branch is unresolvable on a harness without it, and
    every review of the first four runs improvised onto a generic worker."""
    expect_finding(tmp, sub(FIXTURE_SKILL, TIER_TWO_FIXTURE_STEP,
                            "Dispatch the `triage-qc` agent."),
                   "does not state 'roster carries'")


def case_shorthand_used_but_undefined(tmp: Path) -> None:
    expect_finding(tmp, FIXTURE_SKILL + "\nPromote into {promote_dir}.\n",
                   "{promote_dir} is used but")


def case_shorthand_defined_but_unused(tmp: Path) -> None:
    extra_row = "| `{max_beads}` | Dispatch → max_beads | `0` |\n"
    expect_finding(tmp, sub(FIXTURE_SKILL, FIXTURE_ROW, FIXTURE_ROW + extra_row),
                   "{max_beads} is defined but",
                   FIXTURE_CONFIG + "max_beads: 0\n")


def case_shorthand_inside_fence_ignored(tmp: Path) -> None:
    """Otherwise every example snippet would demand a config field."""
    expect_clean(tmp, FIXTURE_SKILL + "\n```\npromote {promote_dir}\n```\n")


def case_shorthand_field_missing_from_config(tmp: Path) -> None:
    text = sub(FIXTURE_SKILL, "Plans Directory → plans_dir", "Plans Directory → absent")
    expect_finding(tmp, text, "which skill.config.md does not carry")


def case_missing_config_file_is_a_finding(tmp: Path) -> None:
    skill_path, config_path = write(tmp, FIXTURE_SKILL)
    config_path.unlink()
    findings = check(skill_path, config_path)
    assert any("no config file" in f for f in findings), findings


def case_checked_config_is_committed_not_gitignored(tmp: Path) -> None:
    """Regression: `**/skill.config.md` is gitignored, so a fresh clone has
    only the template. Checking the live file made this suite fail on any
    machine that had not run the skill's setup once."""
    assert CONFIG.name == "skill.config.example.md", CONFIG
    assert CONFIG.is_file(), CONFIG


def case_over_line_budget(tmp: Path) -> None:
    at_budget = FIXTURE_SKILL.splitlines()
    at_budget += ["Filler."] * (MAX_LINES - len(at_budget))
    expect_clean(tmp, "\n".join(at_budget) + "\n")
    expect_finding(tmp, "\n".join(at_budget + ["Filler."]) + "\n",
                   f"over the {MAX_LINES}-line")


def case_repo_status_reports_a_broken_invocation(tmp: Path) -> None:
    assert repo_status(REPO) == 0, REPO
    assert repo_status(tmp / "absent") == 2


def case_run_cases_reports_both_exit_paths(tmp: Path) -> None:
    def case_green(_: Path) -> None:
        return None

    def case_red(_: Path) -> None:
        raise AssertionError("deliberate")

    with contextlib.redirect_stdout(io.StringIO()):
        green, red = run_cases([case_green]), run_cases([case_red])
    assert (green, red) == (0, 1), (green, red)


# --- runner -------------------------------------------------------------------


def repo_status(root) -> int:
    """0 when the repo root is usable, 2 when the invocation is broken."""
    return 0 if Path(root).is_dir() else 2


def run_cases(cases: list) -> int:
    failed = 0
    for case in cases:
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
    print(f"\n{len(cases) - failed}/{len(cases)} passed")
    return 1 if failed else 0


CASES = [v for k, v in sorted(globals().items()) if k.startswith("case_")]


def main() -> int:
    broken = repo_status(REPO)
    if broken:
        print(f"test_skill_structure.py: {REPO} is not a directory", file=sys.stderr)
        return broken
    return run_cases(CASES)


if __name__ == "__main__":
    sys.exit(main())
