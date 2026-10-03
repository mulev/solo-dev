#!/usr/bin/env python3
"""Assert the shape of a live worker's answer, never the judgment inside it.

Every function here holds across models. A partition is a partition regardless
of which beads land in which group; a flagged bead needs exactly one coverage
line regardless of which way it was ruled; a park needs a real question
regardless of what the question is; a written path either sits inside the run
directory or it does not.

That restraint is the whole design. An oracle that demanded a specific
judgment — "this pair must be ruled `duplicate`", even though the fixture was
built to be a duplicate — would go red the day a model change produced a
different but equally defensible answer, and a test that cannot separate "the
code broke" from "the model had an off day" is not a test. It is a mood ring
that happens to be green today.

Pure functions over plain data. The only I/O any of them performs is path
arithmetic, which is what lets `test_oracles.py` mutation-check both sides of
every one without a testbed, an agent or a temp directory.
"""

from __future__ import annotations

from pathlib import Path

# The public surface, in the order the waves consume it. `test_oracles.py`
# asserts that every name here has a recorded mutation and a rejecting case, so
# a sixth oracle cannot arrive untested.
ORACLES = (
    "partition_covers_every_member",
    "coverage_line_per_flagged_bead",
    "park_carries_a_question",
    "report_echoes_contract_token",
    "artifact_is_inside",
)


def partition_covers_every_member(members: list, groups: list) -> bool:
    """True iff every member appears in exactly one group's `members` list.

    Shape only — it never reads a group's verdict. A ruling that drops a bead
    or double-counts one fails this even when every verdict it did make is
    defensible, and that is the right trade: a dropped bead leaves the backlog
    silently, and nobody reconstructs it.
    """
    if not groups:
        return False
    seen = [bead for group in groups for bead in group.get("members") or []]
    return sorted(seen) == sorted(members) and len(seen) == len(set(seen))


def coverage_line_per_flagged_bead(flagged: list, rulings: list) -> bool:
    """True iff every flagged bead id carries exactly one ruling.

    Never checks the verdict. `covered` and `not-covered` are both complete
    answers; the failure this catches is the third case, where a bead the
    mechanical stage flagged for review is answered by nobody and is then
    investigated from scratch while an existing plan already covers it.
    """
    ruled = [ruling.get("id") for ruling in rulings]
    return sorted(ruled) == sorted(flagged) and len(ruled) == len(set(ruled))


# The fewest words that can still be a question a human can answer. Not a
# quality bar and not a judgment about *which* question: it is what separates a
# question from a punctuation mark. Non-emptiness alone was the original test,
# and the first live park in development passed it on the two-word fragment
# ". Report" that a sloppy reader pulled out of the report's opening line — a
# green oracle over an answer nobody could act on.
MIN_QUESTION_WORDS = 4


def park_carries_a_question(report: dict) -> bool:
    """True iff a PARK report names a question a human could actually answer.

    A park is a finished outcome, not a failure — but a park with no question
    is a dropped bead wearing an outcome's name, and nobody reconstructs the
    question later.

    Shape, not content: what the question *asks* is never checked, only that
    there is one. See `MIN_QUESTION_WORDS`.
    """
    if report.get("outcome") != "PARK":
        return False
    return len((report.get("question") or "").split()) >= MIN_QUESTION_WORDS


def report_echoes_contract_token(report: dict, token: str) -> bool:
    """True iff the worker's `contract` field carries the exact version token.

    A report without it means the worker never opened `autonomous-mode.md`, so
    every other claim it makes is unverified against the rules it was given.
    None of the brief generators prints the token, deliberately: a token handed
    to a worker proves it can copy a brief, not that it read the contract.

    Markdown dressing is stripped before the comparison, and the test is
    containment rather than equality. The contract file writes the token as
    `**SW-...**` and a worker that copies the line as it reads it has proved
    exactly what is being checked — failing that on formatting would be the
    mood-ring failure in miniature. A stale token still fails, because the
    version string it is looking for is simply not in there.
    """
    field = (report.get("contract") or "").strip(" \t\n`*_\"'")
    return token.strip() in field


def artifact_is_inside(run_dir, path) -> bool:
    """True iff `path` resolves under `run_dir` — never a sibling, never a parent.

    Path arithmetic rather than a string prefix, because the staging root holds
    sibling run directories whose names share a prefix (`..._abc` and
    `..._abcdef`), and `resolve()` is what collapses a `../..` traversal back
    out of the run into the parent it actually names.
    """
    return Path(path).resolve().is_relative_to(Path(run_dir).resolve())
