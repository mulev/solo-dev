#!/usr/bin/env python3
"""Check the rules that apply to one slice file.

A slice file and a master plan are two different documents with two different
templates in `plan/references/plan-templates.md`, so they carry two different
rule sets. This module holds the slice-file half: headers, the two re-slice
thresholds, TDD step order, the Component Decomposition table, and the
verification section. `plan_artifact_checks.py` holds the other half.

A single-phase plan is its own sole slice, so these run against it too — with
`n=None`, which relaxes the header rule to that template's own shape and turns
the step threshold into a `warn`, because the single-phase template ships
eleven checkboxes across six sub-steps and failing it on its own template
would be a check that fires on correct work.

Two rules read structure where an earlier draft read a token: a responsibility
splits only when its ` and ` joins two verb phrases, and TDD order is skipped
for a documentation-only phase the way `NO_COMPONENTS` skips a phase that
builds nothing. Each keeps its measured evidence at the constant it shaped.
"""

from __future__ import annotations

import re

from plan_markdown import (ERROR, SKIP, WARN, Finding, body, cell, checkboxes,
                           column, section, table, waived)

MAX_STEPS = 8       # plan/SKILL.md re-slice trigger
MAX_FILES = 5       # plan/SKILL.md re-slice trigger
MAX_FOREIGN = 5     # _shared/architecture-principles.md coupling threshold

H1 = re.compile(r"^#\s+Phase\s+(\d+):\s*(.+)$")
FILE_HEADING = re.compile(r"^###\s+File:\s*`([^`]+)`")
SOURCE_PATH = re.compile(r"`([^`]+\.(?:py|dart|sh|kt|swift|ts|js|md))`")
# Test paths across the stacks this workspace plans for: `test_x.py`,
# `x_test.dart`, `test/…`, and the CamelCase `RunnerTests/XTests.swift` /
# `FooTest.kt` shapes. The CamelCase arm stays case-sensitive on purpose —
# case-folding it makes `latest.dart` a test file.
IS_TEST = re.compile(
    r"(?:^|/)(?i:tests?)/|(?:^|/)test_[A-Za-z0-9_]+\.|_(?i:tests?)\."
    r"|[a-z0-9]Tests?\.[A-Za-z]+$")
# A plan step is an imperative, so the verb that decides whether it mutates
# anything is the step's *first* word. Matching the verb anywhere reads prose
# as structure — "does not split into exactly two parts", in a Read step,
# turned an exploration step into an implementation step in the corpus.
MUTATING_VERB = re.compile(
    r"(?i)^[*_\s]*(create|write|add|implement|rewrite|extend|delete|split"
    r"|update|replace)\b")
# A file path, not a symbol or a version: the extension has to start with a
# letter, which is what keeps `0.18.0`, `^0.17.2` and `Locations.tocFragment`
# out of a phase's file count.
FILE_PATH = re.compile(r"^[A-Za-z0-9_./~-]+\.[A-Za-z][A-Za-z0-9]{0,5}$")
GATE_WORD = re.compile(r"(?i)phase[- ]?exit|phase[- ]?gate")
VALIDATE_OK = re.compile(r"(?i)\./validate\s+(run|verify|list)\b")
NO_COMPONENTS = re.compile(r"(?i)^(none|no components)\b")
# The template's gate checkbox produces the mandatory `## Architecture Gate
# Results` artifact. Every slice carries it, so counting it against the
# re-slice trigger reports an 8-step phase as 9.
# `GATE_STEP` lived here to subtract the template's gate checkbox from the step
# count. Counting only implementation steps retires it: `classify` already puts
# "architecture gate" in `polish`, so the exception and the rule are one rule.
# Prose, not code: the LOC signal below does not apply to it. Deliberately a
# suffix list rather than "not a known code suffix" — a component whose kind
# this file cannot recognise should be measured and argued about, not skipped.
PROSE_SUFFIX = re.compile(r"(?i)\.(md|markdown|rst|txt|arb)$")
# Three corpus shapes carry an ` and ` and still state one responsibility, so
# `two_verb_phrases` must not fire on them:
#   compound object     Points a worker at the contract and at the rubric
#   compound predicate  Discovers and runs every triage script test file
#   nouns in one object Defines how investigate and plan behave at the gate
# Case-sensitive on purpose: it keeps the symbol in `skipToNext and
# skipToPrevious` from reading as a verb.
VERBISH = re.compile(r"^[a-z][a-z-]{2,}s$")
# Plural nouns that turn up after an ` and ` inside a compound object.
# `locators`, `preferences`, `paths` and `tests` are measured in the corpus;
# the rest are the vocabulary these plans are written in. A word listed here is
# never read as a verb, so a genuine `and files the report` is missed — that is
# the cost of a stop list, and this list is the only place to fix either side.
PLURAL_NOUNS = {"plans", "notes", "files", "tests", "steps", "paths", "rows",
                "beads", "phases", "citations", "components", "findings",
                "warnings", "errors", "checks", "cases", "locales", "slices",
                "locators", "preferences"}

COLUMNS = ("component", "responsib", "public api", "caller", "foreign", "loc",
           "test approach")
CATEGORIES = (
    ("exploration", re.compile(r"(?i)^(read|explore|review|inspect|study)\b|understand")),
    # `\be2e\b` alone matched any path under a directory called e2e, and a
    # path says where work lands, not what it is — so every step of such a
    # plan read as integration and the tests/documentation categories went
    # unfilled. The noun after it is what carries the intent.
    ("integration", re.compile(
        r"(?i)integration test|end-to-end|\be2e[ -](test|suite|run|case)s?\b")),
    ("polish", re.compile(r"(?i)\bformat|\blint\b|\bpolish\b|architecture gate|\./validate")),
    ("documentation", re.compile(r"(?i)\bdocs?/|\bdocument|readme")),
    ("tests", re.compile(r"(?i)\b(unit|regression|widget) tests?\b")),
)
ORDER = ("exploration", "tests", "implementation", "integration",
         "documentation", "polish")


def check_slice_headers(text: str, loc: str, n: int | None) -> list[Finding]:
    out, lines = [], text.splitlines()
    h1 = next((l for l in lines if l.startswith("# ")), "")
    if n is None:                       # single-phase plan: a different template
        if not h1:
            out.append(Finding("headers", ERROR, loc, "no H1 title"))
        if "**Status:**" not in text:
            out.append(Finding("headers", ERROR, loc, "**Status:** is missing"))
        return out
    m = H1.match(h1)
    if not m:
        out.append(Finding("headers", ERROR, loc,
                           f"H1 is not `# Phase {{N}}: {{name}}` — {h1[:60]!r}"))
    else:
        if int(m.group(1)) != n:
            out.append(Finding("headers", ERROR, loc,
                               f"H1 says phase {m.group(1)}, the filename says {n}"))
        if " — " not in m.group(2):
            out.append(Finding("headers", WARN, loc, "H1 carries no ` — description` tail"))
    for field in ("**Parent plan:**", "**Beads task:**", "**Status:**"):
        if field not in text:
            out.append(Finding("headers", ERROR, loc, f"{field} is missing"))
    if section(lines, "Prerequisites") is None:
        out.append(Finding("headers", ERROR, loc, "## Prerequisites is missing"))
    return out


def check_phase_thresholds(text: str, loc: str, strict: bool) -> list[Finding]:
    out, lines = [], text.splitlines()
    if section(lines, "Implementation Progress") is None:
        out.append(Finding("thresholds", ERROR, loc,
                           "## Implementation Progress is missing"))
    else:
        steps = checkboxes(lines, "Implementation Progress")
        # `plan` Step 5.2's trigger counts **implementation** steps, and
        # `classify` below already sorts every checkbox into its category. This
        # used to count them all, minus one gate step — but the slice template
        # mandates exploration, a failing test, integration, docs, the
        # formatter and the gate, so a phase began at six or seven boilerplate
        # checkboxes before choosing any work of its own, and the limit was
        # unreachable. Measured on eight freshly written slices: every one
        # reported 9 to 19 steps while holding two or three. A live triage run
        # met it from the other side — the planning worker counted 8 against a
        # limit of 8, the linter said 26, and the orchestrator relayed
        # "recount" to the worker as a real finding. The worker was right.
        count = sum(1 for step in steps if classify(step) == "implementation")
        if count > MAX_STEPS:
            out.append(Finding("thresholds", ERROR if strict else WARN, loc,
                               f"{count} implementation steps — "
                               f"the limit is {MAX_STEPS}"))
    paths = [p for name in ("Files Created", "Files Modified")
             for p in re.findall(r"`([^`]+)`", "\n".join(body(lines, name)))
             if FILE_PATH.match(p)]
    if not paths:
        for line in body(lines, "Implementation"):
            m = FILE_HEADING.match(line)
            if m:
                paths.append(m.group(1))
    uniq = sorted(set(paths))
    if len(uniq) > MAX_FILES:
        # A warning, not an error: the rule counts *unrelated* files, and a
        # phase that legitimately edits its source, its test and its doc has
        # no mechanical way to say so. Failing it would fire on correct work.
        out.append(Finding("thresholds", WARN, loc,
                           f"{len(uniq)} files touched — the limit is {MAX_FILES} "
                           "unrelated files: " + ", ".join(uniq)))
    return out


def classify(step: str) -> str:
    """The six-step category a checkbox falls in. First match wins."""
    for name, pat in CATEGORIES:
        if pat.search(step):
            return name
    if any(IS_TEST.search(p) for p in SOURCE_PATH.findall(step)):
        return "tests"
    return "implementation"


def two_verb_phrases(responsibility: str) -> bool:
    """True when an ` and ` joins two verb phrases that each own an object —
    the only shape in which a responsibility states two responsibilities."""
    for m in re.finditer(r"\band\b", responsibility):
        before = responsibility[:m.start()].split()
        after = responsibility[m.end():].split()
        if len(before) < 2 or len(after) < 2:
            continue        # nothing owned before the `and`, or nothing after
        word = after[0].strip("`*_,.")
        if VERBISH.match(word) and word not in PLURAL_NOUNS:
            return True
    return False


def check_step_order(text: str, loc: str) -> list[Finding]:
    """TDD order is an `error`; category coverage is a `warn`, and the split is
    the point — keyword classification of free prose is not reliable enough to
    fail a plan on, while "a test path is created before a source path is" is."""
    out, steps = [], checkboxes(text.splitlines(), "Implementation Progress")
    if not steps:
        return out
    kinds = [classify(s) for s in steps]
    first_test = first_impl = None
    for k, step in enumerate(steps):
        paths = SOURCE_PATH.findall(step)
        if kinds[k] == "documentation":
            # A `.md` path in a documentation step is a document, not source.
            paths = [p for p in paths if not p.endswith(".md")]
        if not paths or not MUTATING_VERB.match(step):
            continue
        if any(IS_TEST.search(p) for p in paths):
            if first_test is None:
                first_test = k
        elif first_impl is None:
            first_impl = k
    if (first_impl is None and first_test is None and "documentation" in kinds
            and not {"implementation", "tests"}.intersection(kinds)):
        # The counterpart of `check_components`'s NO_COMPONENTS escape: a
        # documentation-only phase has no source to test-drive, so demanding a
        # test step — and warning that no implementation step exists — is the
        # check firing on correct work. The category test is what keeps the
        # escape narrow: a real slice titles its steps `**Implementation.** …`,
        # so no first word is a mutating verb and nothing sets `first_impl` —
        # resting on that alone switched the check off for every `.py` phase.
        return [Finding("step-order", SKIP, loc,
                        "documentation-only phase — TDD order does not apply")]
    if first_impl is not None:
        if first_test is None:
            out.append(Finding("step-order", ERROR, loc,
                               f"step {first_impl + 1} changes source and no step writes "
                               "a test — TDD order cannot be read"))
        elif first_impl < first_test:
            out.append(Finding("step-order", ERROR, loc,
                               f"step {first_impl + 1} changes source before step "
                               f"{first_test + 1} writes a test"))
    seen: dict[str, int] = {}
    for k, kind in enumerate(kinds):
        seen.setdefault(kind, k)
    for name in ORDER:
        if name not in seen:
            out.append(Finding("step-order", WARN, loc,
                               f"no {name} step was classified"))
    ranked = [seen[n] for n in ORDER if n in seen]
    if ranked != sorted(ranked):
        out.append(Finding("step-order", WARN, loc, "step categories run out of order: "
                           + " -> ".join(n for n in ORDER if n in seen)))
    return out


def check_components(text: str, loc: str, max_loc: int) -> list[Finding]:
    lines = text.splitlines()
    found = section(lines, "Component Decomposition")
    if found is None:
        return [Finding("components", ERROR, loc,
                        "## Component Decomposition is missing")]
    lo, hi = found
    grid = table(lines, lo, hi, ("component", "responsib"))
    if grid is None:
        prose = next((l.strip() for l in body(lines, "Component Decomposition")
                      if l.strip()), "")
        if NO_COMPONENTS.match(prose):
            return []       # a delivery or config phase creates no component
        return [Finding("components", ERROR, loc,
                        "## Component Decomposition holds no component table")]
    head, rows = grid
    out = []
    missing = [k for k in COLUMNS if column(head, k) < 0]
    if missing:
        out.append(Finding("components", ERROR, loc,
                           "component table has no " + ", ".join(missing) + " column"))
    loc_waived = waived(text, "LOC waiver")
    coupling_waived = waived(text, "coupling waiver")
    for j, cells in rows:
        component = cell(head, cells, "component")
        responsibility = cell(head, cells, "responsib")
        first = re.search(r"`([^`]+)`", component)
        name = first.group(1) if first else component
        bare = name.strip("—-– ()*`")
        if not bare or NO_COMPONENTS.match(bare):
            continue        # a placeholder row: this phase creates no component
        where = f"{loc}:{j + 1}"
        if two_verb_phrases(responsibility):
            out.append(Finding("components", ERROR, where,
                               f'{name}: responsibility states two — '
                               f'"{responsibility}"'))
        digits = re.search(r"\d+", cell(head, cells, "loc"))
        if PROSE_SUFFIX.search(bare):
            # The threshold is `run_arch_gate.py`'s, and that gate reads code.
            # A phase editing a long reference document carries no 300-LOC
            # violation, and the only way past this check was a
            # `**LOC waiver:**` asserting a code rule applies to prose — a
            # false statement written to silence a check. Measured: a slice
            # editing `triage/SKILL.md`, which has its own 420-line hot-path
            # budget enforced by `test_skill_structure.py`, was reported as
            # 419 LOC over a 300 limit.
            continue
        if not digits:
            out.append(Finding("components", WARN, where, f"{name} projects no LOC"))
        elif int(digits.group()) > max_loc and name not in loc_waived:
            out.append(Finding("components", ERROR, where,
                               f"{name} projects {digits.group()} LOC over the "
                               f"{max_loc} limit with no **LOC waiver:**"))
        foreign = [f for f in cell(head, cells, "foreign").split(",")
                   if f.strip() and f.strip().lower() not in ("none", "—", "-", "n/a")]
        if len(foreign) > MAX_FOREIGN and name not in coupling_waived:
            out.append(Finding("components", ERROR, where,
                               f"{name} touches {len(foreign)} foreign modules over "
                               f"the {MAX_FOREIGN} limit with no **coupling waiver:**"))
    return out


def check_verification(text: str, loc: str) -> list[Finding]:
    """`_shared/validators.md` fixes the rows and forbids the plan writing the
    config, so a gate command that is not `./validate` was invented here."""
    lines = text.splitlines()
    found = section(lines, "Verification")
    if found is None:
        return [Finding("verification", ERROR, loc, "## Verification is missing")]
    lo, hi = found
    out = []
    if "./validate run phase-exit" not in "\n".join(lines[lo:hi]):
        out.append(Finding("verification", ERROR, loc,
                           "## Verification never names `./validate run phase-exit`"))
    for i in range(lo, hi):
        for m in re.finditer(r"`([^`]+)`", lines[i]):
            cmd = m.group(1).strip()
            # A backticked span is only a command when it has an argument and
            # is not a heading name: `## Architecture Gate Results` and a bare
            # `phase-exit` are prose the earlier draft read as invocations.
            if cmd.startswith("#") or " " not in cmd:
                continue
            if not GATE_WORD.search(cmd) or VALIDATE_OK.search(cmd):
                continue
            out.append(Finding("verification", ERROR, f"{loc}:{i + 1}",
                               f"invented verification command: `{cmd}` — the gate is "
                               "`./validate` with run, verify or list"))
    return out


def check_slice(text: str, loc: str, n: int | None, max_loc: int) -> list[Finding]:
    """Every slice-file check, in reading order."""
    return (check_slice_headers(text, loc, n)
            + check_phase_thresholds(text, loc, n is not None)
            + check_step_order(text, loc)
            + check_components(text, loc, max_loc)
            + check_verification(text, loc))
