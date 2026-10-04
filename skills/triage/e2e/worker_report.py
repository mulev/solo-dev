#!/usr/bin/env python3
"""Read a worker's prose report into the plain data the oracles take.

The return contract in `_shared/autonomous-mode.md` is prose with a fixed field
list, not JSON, because a human reads it too. So something has to do the
orchestrator's own reading of it, and that job is here rather than beside the
cases — every function is pure over a string, and every one of them can be
tested without a testbed or an agent.

That separation is not tidiness. **Both live defects this phase produced were
in this file's job**, and neither had a test while the parsing sat among the
cases. A first-occurrence reader handed `park_carries_a_question` the fragment
`". Report"` off a real report's opening line, and the oracle passed it; the
assigned-path comparison failed on a worker that wrapped its own path in
backticks. Parsing a model's prose is the part most likely to be wrong and the
cheapest part to check, which is an argument for testing it, not for hiding it.

Generous about formatting, strict about meaning. A worker that writes
`**contract:** `SW-...`` has obeyed the contract and a reader that fails it on
punctuation is measuring the wrong thing — but a reader that guesses at a
missing representative, or takes any non-empty string as a park's question,
turns a worker's incomplete answer into a green run.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import harness

sys.path.insert(0, str(harness.SCRIPTS))

import cluster_ruling  # noqa: E402

FIELD_RE = re.compile(r"^\s*[-*]?\s*\**([A-Za-z][A-Za-z0-9 _-]{0,28})\**\s*:\s*(.*)$")
# Presence of the word anywhere in the report is the whole question. What the
# park *asks* is read out of the designated fields — see `park_report`.
PARK_RE = re.compile(r"\bPARK\b")
# The fields the return contract designates for a park's question, in the order
# a reader should prefer them.
QUESTION_FIELDS = ("open questions", "blockers", "gate")
REPRESENTATIVE_RE = re.compile(r"represent\w*[^0-9A-Za-z]+`?([0-9A-Za-z._-]+)", re.I)
# The verdict a judge's line rules. Longest alternative first, and a boundary
# that excludes `-` as well as word characters: a hyphen *is* a word boundary
# to `\b`, so `\bduplicate\b` matched inside `related-not-duplicate` while
# `duplicate` sorts first in `cluster_ruling.VERDICTS` — one ruled-out member
# came back as a one-member `duplicate` group off a live judge, and
# `cluster_ruling.validate` rejected a partition that was clean (`skills-hqw`).
# The leading alternative absorbs a spelled-out negation so a judge that rules
# `distinct` and then says "not a duplicate of the pair" is read as `distinct`,
# the same way `coverage_rulings` matches `not-covered` before `covered`.
VERDICT_RE = re.compile(
    r"(?<![\w-])(?:not(?:\s+an?)?[\s-]+duplicate|"
    + "|".join(re.escape(v) for v in
               sorted(cluster_ruling.VERDICTS, key=len, reverse=True))
    + r")(?![\w-])")


# Markdown dressing a worker puts around a value. Stripped once here rather
# than at each consumer: `**contract:** x` leaves the closing `**` on the value,
# and five readers each remembering to strip it is five chances to forget.
DRESSING = " \t`*_\"'"


def fields(report: str) -> dict:
    """The worker's `key: value` report lines, first occurrence winning."""
    out: dict = {}
    for line in report.splitlines():
        found = FIELD_RE.match(line)
        if found:
            out.setdefault(found.group(1).strip().lower(),
                           found.group(2).strip(DRESSING))
    return out


def path_field(report_fields: dict, key: str) -> Path:
    """One reported path, undressed.

    Workers write `` `/abs/path` `` and `</abs/path>` as often as the bare
    form, and a comparison that fails on a backtick is measuring formatting
    rather than obedience. `fields` has already taken the rest.
    """
    return Path(report_fields.get(key, "").strip(DRESSING + "<>"))


def park_report(report: str) -> dict:
    """`{outcome, question}` in the shape `oracles.park_carries_a_question` reads.

    The question comes from the fields the contract designates and never from
    wherever the word PARK first appears. A real report opened with the line
    `PARK. Report:`, and a first-occurrence reader handed the oracle the
    fragment `". Report"` — which it then passed, because the oracle only
    required a non-empty string. Both halves of that were fixed: the reader
    looks at the designated fields, and the oracle counts words.
    """
    if not PARK_RE.search(report):
        return {"outcome": "COMPLETE", "question": ""}
    found = fields(report)
    parts = [re.sub(r"^\W*PARK\b\W*", "", found.get(key, "")).strip()
             for key in QUESTION_FIELDS]
    return {"outcome": "PARK", "question": " ".join(p for p in parts if p)}


def groups(report: str, members: list) -> list:
    """The judge's partition over one cluster, read out of its prose report.

    One group per report line that names a verdict and at least one of this
    cluster's members. A line the reader could not attribute is skipped rather
    than guessed at — the oracle's question is whether every member landed in
    exactly one group, and a bad attribution answers it wrongly by omission.

    A `duplicate` group's representative is taken from the line and never
    filled in. `cluster_ruling` requires one and requires it to be a member, and
    supplying it here would be this file inventing the answer SKILL.md says
    goes back to the judge.

    **A member joins the first group that claims it**, the same rule `fields`
    and `coverage_rulings` use. A live judge ruled `tb-dup1, tb-dup2 —
    duplicate — representative tb-dup1` and then restated both ids and the
    word `duplicate` in its reasoning, so a reader taking every qualifying line
    built two groups over the same pair and the partition oracle rejected a
    ruling that was in fact a clean partition. A judge that rules once and then
    explains itself has still ruled once.
    """
    out, assigned = [], set()
    for line in report.splitlines():
        # Left to right, negations discarded rather than read: the leftmost
        # match that *is* a verdict is the one the line rules.
        verdict = next((v for v in VERDICT_RE.findall(line)
                        if v in cluster_ruling.VERDICTS), None)
        listed = [m for m in members if m not in assigned
                  and re.search(rf"\b{re.escape(m)}\b", line)]
        if not verdict or not listed:
            continue
        assigned.update(listed)
        group = {"members": listed, "verdict": verdict}
        named = REPRESENTATIVE_RE.search(line)
        if verdict == "duplicate" and named:
            group["representative"] = named.group(1)
        out.append(group)
    return out


def coverage_rulings(report: str, flagged: list) -> list:
    """One `covered` / `not-covered` ruling per flagged bead, first line wins.

    `not-covered` is tested before `covered` because one is a substring of the
    other, and getting that order wrong turns every "not covered" line into its
    opposite — retiring a bead the judge explicitly refused to retire.

    **First mention wins**, the same rule `fields` uses, and it was a live
    judge that forced it: the report stated `tb-cov3 — not-covered` in its
    ruling list and then named `tb-cov3` again in the reasoning below, so a
    reader that took every mention emitted two rulings and
    `coverage_line_per_flagged_bead` rejected a ruling that was in fact
    complete. The oracle asks whether the judge answered for every flagged
    bead; a judge that answers once and then explains itself has. Being strict
    about repetition in free prose measures formatting, and a bead that is
    never ruled at all still fails — which is the failure that matters.
    """
    out: dict = {}
    for line in report.splitlines():
        for bead in flagged:
            if bead in out or not re.search(rf"\b{re.escape(bead)}\b", line):
                continue
            if re.search(r"\bnot[\s-]?covered\b", line, re.I):
                out[bead] = {"id": bead, "verdict": "not-covered"}
            elif re.search(r"\bcovered\b", line, re.I):
                out[bead] = {"id": bead, "verdict": "covered", "plan": line.strip()}
    return [out[bead] for bead in flagged if bead in out]
