#!/usr/bin/env python3
"""Tests for the ledger's documented row contract.

`references/ledger.md` is the only definition of what a ledger row means, and
after a compaction the ledger *is* the run state — so a column whose meaning is
undefined for a row kind is a hole in the run's memory, not a formatting
detail. `check(root)` takes a root so the fixture cases can drive it against a
temp tree.

Run with `python3 test_ledger_doc.py` (no pytest dependency).
"""

from __future__ import annotations

import re
import sys
import tempfile
import traceback
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LEDGER_REL = "triage/references/ledger.md"

COLUMNS = ["bead", "wave", "worker", "dispatched", "returned", "artifact",
           "tier-1", "verdict", "round", "final"]
HEADER = "| " + " | ".join(COLUMNS) + " |"
KINDS = ("artifact row", "quality-control row", "decision record",
         "cluster row", "wave row")
# A rule stated with a negation is the rule, not a violation of it: "never as
# `final: failed`" must not read as offering `failed`.
NEGATION = re.compile(r"\b(not|never|rather than)\b")
DEAD = ("dead worker", "worker that died", "dispatch that died",
        "process that died")
UNPLANNED = ("nobody planned", "no planner", "not planned")


def check(root: Path) -> list[str]:
    """Findings against the ledger reference. Empty list means clean."""
    path = Path(root) / LEDGER_REL
    if not path.is_file():
        return [f"missing {LEDGER_REL}"]
    text = path.read_text(encoding="utf-8")
    out = []

    lines = text.splitlines()
    # A definition lives in a two-cell row, so the ten-cell example header
    # cannot stand in for one — that substring match is what let an undeleted
    # header hide a missing definition.
    defined = {l.strip("|").split("|")[0].strip() for l in lines
               if l.startswith("| ") and len(l.strip("|").split("|")) == 2}
    for column in COLUMNS:
        if column not in defined:
            out.append(f"column not defined: {column}")
    if HEADER not in text:
        out.append("no example table carries the canonical ten-column header")

    # A kind must be the subject of a definition row, never only a mention in
    # prose — the ledger's readings of `verdict` are what a resumed run needs.
    subjects = {l.strip("|").split("|")[0].strip().lower().removeprefix("the ")
                for l in lines if l.startswith("| ")}
    for kind in KINDS:
        if kind not in subjects:
            out.append(f"row kind not documented: {kind}")

    # The bug this file exists for: Wave 1's ruling had nowhere to live, so the
    # reference must say what a cluster row puts in `verdict`.
    if "related-not-duplicate" not in text:
        out.append("the dedup ruling vocabulary is not stated for the cluster row")

    # `skills-j4q`, then `skills-w7z`: the resume rule tested `final` for
    # completeness while the row-kind table says a cluster row leaves it empty.
    # Read literally that marks Wave 1 incomplete on any ledger holding a
    # cluster row, so a resumed run can never pass it. This is a contradiction
    # check, not a prose match: it fires only when the doc says both things at
    # once.
    empty_final_kind = any(
        l.startswith("| ") and l.rstrip().endswith("empty |")
        for l in lines)
    # `final` records an outcome when it is known — a Wave 2 investigation's is
    # not knowable until Wave 4 or 5 settles the bead — so a resume rule that
    # tests it sends a healthy Wave 5 run back to Wave 2. Sentence-scoped, not a
    # substring match on one phrasing: the previous version keyed on wording
    # this file itself then rewrote, which would have left a check that can
    # never fire.
    resume = _section(lines, "## Resume protocol")
    # Phrasing-independent, because two earlier versions of this check were
    # not. The first keyed on "empty `final`" plus "incomplete" and missed the
    # live bullet reading "has no `final` resumes at its Wave 5"; widening it
    # to two spellings and two verbs still let "carries a blank `final`",
    # "`final` unset" and "without a `final`" through. So: any sentence that
    # mentions `final` and makes a completeness claim is a finding unless it
    # is negated — and every legitimate sentence here is ("`final` is **not** a
    # completeness signal", "**never** an empty `final`"), which is the same
    # NEGATION trick the dead-worker scan above already relies on.
    # "owes" is deliberately absent: this section legitimately says "which row
    # kind owns `final` is a separate question from which rows a resume owes
    # work", which is unnegated and correct. The claims below all assert that
    # a particular row is unfinished, which is the thing `final` may not decide.
    claims = ("incomplete", "resumes", "outstanding", "returns to")
    unscoped = any("`final`" in s and any(c in s for c in claims)
                   and not NEGATION.search(s)
                   for s in resume.split(". "))
    if empty_final_kind and unscoped:
        out.append("the resume rule tests `final` on row kinds documented to "
                   "leave it empty")

    # `final` is one artifact's outcome, recorded once. A live run wrote it on
    # the Wave 5 row as well, so one bead carried two finals — and where the
    # two disagreed, nothing in the table said which one was the bead's.
    qc = kind_row(lines, "quality-control row")
    if qc is not None and qc[-1] != "empty":
        out.append("the quality-control row does not leave `final` empty")

    # A reviewer process that exits without a verdict never gave the bead an
    # outcome. Every paragraph mentioning a death is scanned, not the first:
    # the resume protocol already says a worker that died mid-write leaves a
    # file behind, and a first-match check would read that paragraph and
    # report green with the rule absent altogether.
    dead = [p for p in paragraphs(text) if any(d in p for d in DEAD)]
    if not any("`returned`" in p and "re-dispatch" in p for p in dead):
        out.append("the reference does not say a dead worker is recorded by "
                   "leaving `returned` empty until the re-dispatch returns")
    for para in dead:
        for sentence in para.split(". "):
            if "`failed`" in sentence and not NEGATION.search(sentence):
                out.append("a dead worker is offered `failed` as its record: "
                           + sentence[:60])
                break

    # A group nobody planned still owes a Wave 4 row. "We wrote something
    # about it" is the half-answer this check exists to reject, so the rule
    # has to name every cell a reader needs. `artifact` `—` and the stamps are
    # in the list because both are load-bearing, and `skills-way.8`'s Bug
    # Round 1 is what proved it: a decision row carrying a real artifact path
    # reads as an ungated artifact and pins the resume at Wave 5, and one with
    # an empty `returned` pins it at Wave 4. Prose that drops either cell
    # invites a run to write the row that broke three readers.
    needles = ("Wave 4", "`worker` `—`", "`artifact` `—`", "both stamps",
               "`parked`", "`duplicate`")
    groups = [p for p in paragraphs(text) if any(u in p for u in UNPLANNED)]
    if not groups:
        out.append("the reference does not say how a group nobody planned "
                   "is recorded")
    elif not any(all(n in p for n in needles) for p in groups):
        missing = [n for n in needles if not any(n in p for p in groups)]
        out.append("the unplanned-group rule does not name: "
                   + ", ".join(missing))

    # A re-dispatch row's `returned` had no event to record: the verdict that
    # ordered it lands long after the producing worker settled, so nothing
    # observable happened at the moment the row is closed. Run
    # `2026-09-02_3f7d` row 9 reached for the artifact's mtime instead, which
    # breaks both stamp rules at once — a value nobody observed, saying when a
    # file was written rather than when the result was taken. The event exists
    # now, so the reference has to name it: the orchestrator reading the
    # report file.
    stamping = [p for p in paragraphs(text)
                if "re-dispatch" in p and "`returned`" in p and "report" in p]
    if not any("`date -u`" in p and "mtime" in p for p in stamping):
        out.append("the reference does not say `returned` on a re-dispatch row "
                   "is measured with `date -u` when the report is read, and "
                   "never from an artifact's mtime")

    return out


def _section(lines: list[str], heading: str) -> str:
    """The named `##` section's text, newlines flattened, or "" if absent."""
    out, seen = [], False
    for line in lines:
        if line.strip() == heading:
            seen = True
        elif seen:
            if line.startswith("## "):
                break
            out.append(line)
    return " ".join(out)


def paragraphs(text: str) -> list[str]:
    """Blank-line-separated blocks, wrapping removed so a needle that spans a
    line break still matches. Every rule below is one paragraph in the file."""
    return [" ".join(p.split()) for p in text.split("\n\n") if p.strip()]


def kind_row(lines: list[str], subject: str) -> list[str] | None:
    """The row-kind table row whose subject is `subject`, cells stripped."""
    for line in lines:
        if not line.startswith("| "):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if cells[0].lower().removeprefix("the ") == subject:
            return cells
    return None


def expect(got, want) -> None:
    assert got == want, f"got {got!r}, want {want!r}"


def fixture(tmp: Path, text: str) -> Path:
    path = tmp / LEDGER_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return tmp


def kind_cells(kind: str) -> str:
    """A row-kind definition row. `final` reads `empty` for the three kinds
    that leave it so, which is the half of the contradiction the doc must
    keep. The decision record is the exception that is not an artifact row:
    it carries an outcome without ever having produced an artifact."""
    if kind == "artifact row":
        final = "the bead's outcome"
    elif kind == "decision record":
        final = "why no plan exists: `parked` or `duplicate`"
    else:
        final = "empty"
    return f"| the {kind} | wave | bead | verdict | {final} |"


DEAD_RULE = ("A dispatch that died is recorded by leaving `returned` empty "
             "until the re-dispatch returns, never as `final: failed`.\n")
GROUP_RULE = ("A group nobody planned gets a Wave 4 row with `worker` `—`, "
              "`artifact` `—`, both stamps measured when the decision is "
              "taken, and `final` naming why: `parked` or `duplicate`.\n")
STAMP_RULE = ("`returned` on a re-dispatch row is the output of `date -u` at "
              "the moment the orchestrator reads the worker's report file; an "
              "artifact's mtime is never its source.\n")


def good() -> str:
    example = "| " + " | ".join(f"{c}-val" for c in COLUMNS) + " |"
    kinds = "\n".join(kind_cells(k) for k in KINDS)
    cols = "\n".join(f"| {c} | what it holds |" for c in COLUMNS)
    return (f"# The run ledger\n\n{cols}\n\n{HEADER}\n{example}\n\n{kinds}\n"
            "A cluster row's verdict is duplicate / distinct / "
            f"related-not-duplicate.\n\n{DEAD_RULE}\n{GROUP_RULE}\n{STAMP_RULE}\n"
            "## Resume protocol\n\nA wave is incomplete when any row belonging "
            "to it has an empty `returned`.\n")


# --- cases -------------------------------------------------------------------


def case_real_ledger_reference_is_clean(tmp: Path) -> None:
    expect(check(REPO), [])


def case_a_final_based_resume_rule_is_a_finding(tmp: Path) -> None:
    """`skills-w7z`. A resume rule that tests `final` for completeness is the
    defect this check exists to catch, in whatever words it is written."""
    text = good().replace(
        "has an empty `returned`.",
        "has an empty `returned` or an empty `final`.")
    assert any("row kinds documented to leave it empty" in f
               for f in check(fixture(tmp, text)))


def case_a_resumes_phrasing_of_the_final_rule_is_a_finding(tmp: Path) -> None:
    """`skills-way.8` Bug Round 3. The first version of this check keyed on
    "empty `final`" plus "incomplete" and missed the live bullet reading "has
    no `final` resumes at its Wave 5 quality control" — the same defect one
    phrasing over, which is how it outlived the rewrite that took `final` out
    of the paragraphs above it. The sibling case above covers the wording the
    original check caught; this one covers the wording it did not, so weakening
    the check back to a single spelling turns this case red.
    """
    text = good().replace(
        "has an empty `returned`.",
        "has an empty `returned`. A Wave 2 row that returned but has no "
        "`final` resumes at its Wave 5 quality control.")
    assert any("row kinds documented to leave it empty" in f
               for f in check(fixture(tmp, text)))


def case_fixture_is_clean(tmp: Path) -> None:
    expect(check(fixture(tmp, good())), [])


def case_missing_file_is_a_finding(tmp: Path) -> None:
    expect(check(tmp), [f"missing {LEDGER_REL}"])


def case_undefined_column_is_a_finding(tmp: Path) -> None:
    text = good().replace("| verdict | what it holds |\n", "")
    assert "column not defined: verdict" in check(fixture(tmp, text))


def case_missing_row_kind_is_a_finding(tmp: Path) -> None:
    text = good().replace(kind_cells("cluster row") + "\n", "")
    assert "row kind not documented: cluster row" in check(fixture(tmp, text))


def case_missing_dedup_vocabulary_is_a_finding(tmp: Path) -> None:
    text = good().replace("related-not-duplicate", "something else")
    assert any("dedup ruling vocabulary" in f for f in check(fixture(tmp, text)))


def case_example_without_the_canonical_header_is_a_finding(tmp: Path) -> None:
    text = good().replace(HEADER, "| bead | wave |")
    assert any("canonical ten-column header" in f for f in check(fixture(tmp, text)))


def case_a_wave_5_row_carrying_a_final_is_a_finding(tmp: Path) -> None:
    """One artifact, one `final`. A live run wrote it on the Wave 2 row and on
    a Wave 5 row of the same bead, the two disagreed, and nothing said which
    one the bead ended on."""
    text = good().replace(kind_cells("quality-control row"),
                          "| the quality-control row | wave | bead | verdict "
                          "| the bead's outcome |")
    assert any("quality-control row does not leave `final` empty" in f
               for f in check(fixture(tmp, text)))


def case_a_reference_silent_on_a_dead_worker_is_a_finding(tmp: Path) -> None:
    text = good().replace(DEAD_RULE, "")
    assert any("leaving `returned` empty until the re-dispatch returns" in f
               for f in check(fixture(tmp, text)))


def case_offering_failed_for_a_dead_worker_is_a_finding(tmp: Path) -> None:
    """`final` is the bead's outcome, never a report on a subprocess — and a
    reference that offers `failed` for a death is how a live run came to
    record one."""
    text = good() + "\nA dead worker is recorded as `failed`.\n"
    assert any("offered `failed` as its record" in f
               for f in check(fixture(tmp, text)))


def case_a_reference_silent_on_an_unplanned_group_is_a_finding(
        tmp: Path) -> None:
    text = good().replace(GROUP_RULE, "")
    assert any("how a group nobody planned is recorded" in f
               for f in check(fixture(tmp, text)))


def case_a_half_stated_unplanned_group_rule_is_a_finding(tmp: Path) -> None:
    """The one that matters: "we wrote something about it" is the half-answer
    this check rejects. Without the `worker` cell a reader cannot write the
    row, and the group is recorded as a loss again."""
    text = good().replace("with `worker` `—`, ", "with ")
    assert any("unplanned-group rule does not name: `worker` `—`" in f
               for f in check(fixture(tmp, text)))


def case_a_blank_final_resume_rule_is_a_finding(tmp: Path) -> None:
    """The generalised check, pinned. Three spellings escaped the version that
    matched "empty `final`" and "no `final`" literally — this is one of them,
    and it is a finding now because the check asks whether a sentence mentions
    `final` while claiming a row is unfinished, not how it spells it.

    Known escape, recorded rather than papered over: a defect carrying its own
    negation ("whose `final` has not been written is incomplete") still passes,
    because `NEGATION` cannot tell which clause the "not" belongs to. Closing
    that needs a parser, not a longer word list.
    """
    text = good().replace(
        "has an empty `returned`.",
        "has an empty `returned`. A Wave 2 row that returned but carries a "
        "blank `final` resumes at its Wave 5 quality control.")
    assert any("row kinds documented to leave it empty" in f
               for f in check(fixture(tmp, text)))


def case_an_unplanned_group_rule_missing_the_artifact_cell_is_a_finding(
        tmp: Path) -> None:
    """`artifact` `—` is the cell `skills-way.8` Bug Round 1 turned on: a
    decision record carrying a real path reads as an ungated artifact row,
    which pins the resume at Wave 5 and hands `promote` a path to move. Prose
    that stops naming the cell invites exactly that row."""
    text = good().replace("`artifact` `—`, ", "")
    assert any("does not name: `artifact` `—`" in f
               for f in check(fixture(tmp, text)))


def case_an_unplanned_group_rule_missing_the_stamps_is_a_finding(
        tmp: Path) -> None:
    """The stamps are load-bearing the other way: a decision record with an
    empty `returned` makes its own wave incomplete under rule 1, so a group
    nobody planned would pin the resume at Wave 4 forever."""
    text = good().replace("both stamps measured when the decision is taken, ", "")
    assert any("does not name: both stamps" in f
               for f in check(fixture(tmp, text)))


def case_a_reference_silent_on_the_re_dispatch_stamp_is_a_finding(
        tmp: Path) -> None:
    """Run `2026-09-02_3f7d` row 9. A `REVISE` reaches a worker whose job leg
    settled ten minutes earlier, so the row's `returned` had no observable
    event and the orchestrator took the artifact's mtime — a stamp nobody
    measured, of when a file was written rather than when the result was
    taken. The event exists now, and the reference has to name it."""
    text = good().replace(STAMP_RULE, "")
    assert any("measured with `date -u` when the report is read" in f
               for f in check(fixture(tmp, text)))


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
