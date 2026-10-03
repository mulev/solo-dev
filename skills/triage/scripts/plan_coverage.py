#!/usr/bin/env python3
"""Find which plan files already cite a bead, and how strongly they claim it.

Pure filesystem reads over one project's plan corpus. No tracker, no network,
no subprocess — which is what lets the citation grammar be tested on a fixture
tree in a temp directory.

The doctrine this file executes is documented in ../references/deduplication.md
(section 3, "Citation strength").
"""

from __future__ import annotations

import re
from pathlib import Path

STRONG_CITATIONS = ("beads-task",)
# The field itself, plus the markdown dressing between it and the ID it names.
BEADS_TASK_RE = re.compile(r"beads\s+task\s*:[\s*`\"'\[(]*", re.IGNORECASE)
LINE_CLIP = 200


def _owns(line: str, bead_id: str) -> bool:
    """True when `bead_id` is the ID the `Beads task:` field itself names.

    The field is an ownership declaration about exactly one bead. Everything
    after that bead — `supersedes demo-def`, `blocked on demo-x` — is prose,
    and prose is never an ownership claim, however strong the line it sits on.
    """
    field = BEADS_TASK_RE.search(line)
    if not field:
        return False
    tail = line[field.end():]
    return _id_pattern(bead_id).match(tail) is not None


def citation_form(line: str, bead_id: str) -> str:
    """How strongly this line claims to own `bead_id` in particular.

    Strength is a property of the (line, bead) pair, never of the line alone.
    A `Beads task:` line yields `beads-task` for the one bead its field names
    and `bare-id` — or `beads-table`, on a table row — for every other ID on
    it. That downgrade is deliberate: those beads go to the judge brief
    instead of leaving the run on a coincidental string match.
    """
    if _owns(line, bead_id):
        return "beads-task"
    stripped = line.strip()
    if stripped.startswith("|") and stripped.endswith("|"):
        return "beads-table"
    return "bare-id"


def coverage_action(citations: list) -> str:
    """Only a plan claiming the bead outright drops it; the rest go to a judge.

    `**Beads task:**` is the plan skill's ownership field, so it is the one
    form that can retire a bead unattended. A Beads *table* row is not: those
    tables list de-scoped and discovered work beside owned work, and the
    column separating them is free prose — `| Not this epic |`,
    `| Discovered (de-scoped) |`, `| Known residue (planning) |`. Measured on
    the live demo corpus, trusting table rows dropped 7 of 9 real beads.
    """
    cite = deciding_citation(citations)
    return "drop" if cite and cite["how"] in STRONG_CITATIONS else "review"


def deciding_citation(citations: list) -> dict:
    """The one citation the action rests on — the strong one where there is one.

    Reports name this, never `citations[0]`. Citations arrive in filesystem
    order, so the first is whichever file sorted earliest, and a bead dropped
    on a `Beads task:` field in `done/b/plan.md` was being reported against a
    table row in `todo/a/more.md`. Deriving both the action and the reason
    from this function is what stops them disagreeing again.

    `None` for an empty list, which is what `any()` used to give the caller
    for free — no live caller passes one, and none should acquire the habit.
    """
    strong = [c for c in citations if c["how"] in STRONG_CITATIONS]
    return strong[0] if strong else (citations[0] if citations else None)


# --- the judge's ruling on coverage ------------------------------------------


COVERAGE_VERDICTS = ("covered", "not-covered")


def validate_coverage(bead_ids: list, rulings: list) -> list[str]:
    """Findings against the judge's coverage rulings. Empty list means complete.

    `coverage_action` returns `review` for every weak citation, and `review`
    means a human-grade look — so a bead flagged and never ruled on is a bead
    that gets a fresh investigation while an existing plan already covers it.
    The first live demo run flagged nine and answered none of them.
    """
    known, seen, out = set(bead_ids), [], []
    for index, ruling in enumerate(rulings):
        where = f"rulings[{index}]"
        bead = ruling.get("id")
        seen.append(bead)
        # The key is `id`, and naming the missing key is the whole finding. A
        # live run keyed nine rulings `bead`: every one reported as the bead
        # `None` not being flagged, and then the duplicate check below raised
        # `TypeError` sorting a set of `None`s — so the validator written to
        # reject a malformed ruling was the thing that crashed on one.
        if bead is None:
            out.append(f"{where}: ruling carries no id")
        elif bead not in known:
            out.append(f"{where}: {bead} was not flagged for review")
        verdict = ruling.get("verdict")
        if verdict not in COVERAGE_VERDICTS:
            out.append(f"{where}: unknown verdict {verdict!r}")
        elif verdict == "covered" and not ruling.get("plan"):
            out.append(f"{where}: covered names no plan")
    twice = sorted({b for b in seen if b is not None and seen.count(b) > 1})
    if twice:
        out.append(f"ruled more than once: {', '.join(twice)}")
    missing = [b for b in bead_ids if b not in seen]
    if missing:
        out.append(f"not ruled on: {', '.join(missing)}")
    return out


def skipped(rulings: list) -> list:
    """The beads an existing plan already covers — the only ones Wave 1 drops.

    `not-covered` means the citation was a mention, not ownership, and the
    bead is dispatched exactly as if it had never been flagged.
    """
    return sorted(r["id"] for r in rulings if r.get("verdict") == "covered")


def _id_pattern(bead_id: str) -> re.Pattern:
    """Exact-ID match with the three boundaries the real corpus demands.

    `demo-lproj-2026` is not `demo-lproj`; `d-g65.3` is not its parent
    `d-g65`; and `/project_plans/demo-app/x.md` is not a bead called
    `demo-app`, because a path segment is never an ownership claim.
    """
    return re.compile(
        r"(?<![0-9A-Za-z_/-])" + re.escape(bead_id) + r"(?![0-9A-Za-z_-])(?!\.\d)"
    )


def scan_plan_coverage(plans_dir, project: str, ids: list) -> dict:
    """Walk todo/ and done/ for citations of each given bead ID.

    Shipped work counts, so done/ is scanned exactly like todo/: a bead
    covered by work that landed last month is as covered as one queued today.
    The root is an exact path join, so scanning `demo` never descends into
    a sibling project tree such as `demo-app`.
    """
    patterns = {bid: _id_pattern(bid) for bid in ids}
    coverage: dict = {}
    for state in ("todo", "done"):
        root = Path(plans_dir) / project / state
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.md")):
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for line in text.splitlines():
                for bid, pattern in patterns.items():
                    if pattern.search(line):
                        coverage.setdefault(bid, []).append(
                            {
                                "path": str(path),
                                "how": citation_form(line, bid),
                                "line": line.strip()[:LINE_CLIP],
                            }
                        )
    return coverage
