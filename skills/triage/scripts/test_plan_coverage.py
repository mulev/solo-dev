"""Tests for plan_coverage.py — the citation grammar, its boundaries, and
which forms are strong enough to retire a bead unattended.

Run with `python3 test_plan_coverage.py` (no pytest dependency).
"""

from __future__ import annotations

import sys
import tempfile
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import plan_coverage  # noqa: E402


def expect(got, want) -> None:
    assert got == want, f"got {got!r}, want {want!r}"


def plan_tree(tmp: Path, files: dict) -> Path:
    """files maps 'todo/foo/plan.md' -> body. Returns the plans-dir root."""
    plans = tmp / "plans"
    for rel, body in files.items():
        path = plans / "demo" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    for state in ("todo", "done"):
        (plans / "demo" / state).mkdir(parents=True, exist_ok=True)
    return plans


# --- which forms are found, and where ---------------------------------------


def case_beads_task_field_is_found_in_a_todo_plan(tmp: Path) -> None:
    plans = plan_tree(tmp, {"todo/x/plan.md": "**Beads task:** `d-1`\n"})
    cov = plan_coverage.scan_plan_coverage(plans, "demo", ["d-1", "d-2"])
    expect(sorted(cov), ["d-1"])
    expect(cov["d-1"][0]["how"], "beads-task")


def case_done_plans_are_scanned_exactly_like_todo(tmp: Path) -> None:
    plans = plan_tree(tmp, {"done/x/plan.md": "**Beads task:** `d-7`\n"})
    cov = plan_coverage.scan_plan_coverage(plans, "demo", ["d-7"])
    assert cov["d-7"][0]["path"].endswith("done/x/plan.md"), cov["d-7"]
    expect(plan_coverage.coverage_action(cov["d-7"]), "drop")


def case_table_row_is_found_as_beads_table(tmp: Path) -> None:
    plans = plan_tree(tmp, {"todo/x/plan.md": "| Task | d-7 | Phase 1 |\n"})
    cov = plan_coverage.scan_plan_coverage(plans, "demo", ["d-7"])
    expect(cov["d-7"][0]["how"], "beads-table")


def case_bare_mention_is_found_as_bare_id(tmp: Path) -> None:
    body = "The retry path was reworked while chasing d-5 last month.\n"
    plans = plan_tree(tmp, {"todo/x/notes.md": body})
    cov = plan_coverage.scan_plan_coverage(plans, "demo", ["d-5"])
    expect(cov["d-5"][0]["how"], "bare-id")


def case_bead_cited_nowhere_is_absent(tmp: Path) -> None:
    plans = plan_tree(tmp, {"todo/x/plan.md": "**Beads task:** `d-1`\n"})
    expect(plan_coverage.scan_plan_coverage(plans, "demo", ["d-2"]), {})


def case_missing_plan_tree_is_not_an_error(tmp: Path) -> None:
    expect(plan_coverage.scan_plan_coverage(tmp / "nowhere", "demo", ["d-1"]), {})


def case_citation_line_is_recorded_and_clipped(tmp: Path) -> None:
    body = "**Beads task:** `d-1` " + ("x" * 400) + "\n"
    plans = plan_tree(tmp, {"todo/x/plan.md": body})
    cov = plan_coverage.scan_plan_coverage(plans, "demo", ["d-1"])
    expect(len(cov["d-1"][0]["line"]), plan_coverage.LINE_CLIP)


# --- ID boundaries: the three near-misses seen in the real corpus ------------


def case_longer_hyphenated_token_is_not_a_citation(tmp: Path) -> None:
    body = 'DEFAULT_SEED = "demo-lproj-2026"\n'
    plans = plan_tree(tmp, {"todo/x/plan.md": body})
    expect(plan_coverage.scan_plan_coverage(plans, "demo", ["demo-lproj"]), {})


def case_path_segment_is_not_a_citation(tmp: Path) -> None:
    body = "See /Users/x/project_plans/demo-app/todo/x.md for the sibling work.\n"
    plans = plan_tree(tmp, {"todo/x/plan.md": body})
    expect(plan_coverage.scan_plan_coverage(plans, "demo", ["demo-app"]), {})


def case_child_bead_citation_does_not_cover_its_parent(tmp: Path) -> None:
    plans = plan_tree(tmp, {"todo/x/plan.md": "**Beads task:** `d-g65.3`\n"})
    cov = plan_coverage.scan_plan_coverage(plans, "demo", ["d-g65", "d-g65.3"])
    expect(sorted(cov), ["d-g65.3"])


def case_sibling_project_plan_tree_is_not_scanned(tmp: Path) -> None:
    plans = plan_tree(tmp, {"todo/x/plan.md": "nothing here\n"})
    sibling = plans / "demo-app" / "todo"
    sibling.mkdir(parents=True, exist_ok=True)
    (sibling / "plan.md").write_text("**Beads task:** `d-1`\n", encoding="utf-8")
    expect(plan_coverage.scan_plan_coverage(plans, "demo", ["d-1"]), {})


# --- citation strength -------------------------------------------------------


def case_only_the_beads_task_field_is_a_strong_citation(tmp: Path) -> None:
    expect(plan_coverage.STRONG_CITATIONS, ("beads-task",))


def case_a_beads_table_row_alone_never_drops_a_bead(tmp: Path) -> None:
    """Regression from the live demo run.

    A plan's Beads table lists de-scoped and discovered work as often as work
    it owns, and the status column that tells them apart is free prose.
    Reading any such row as ownership dropped 7 of 9 real demo beads.
    """
    rows = "\n".join(
        [
            "| Not this epic | `d-1` | separate feature, unrelated to this epic |",
            "| Discovered (de-scoped) | `d-2` | give HttpService an override seam |",
            "| Known residue (planning) | `d-3` | navigateToEntry drops collaborators |",
        ]
    )
    plans = plan_tree(tmp, {"todo/x/plan.md": rows + "\n"})
    cov = plan_coverage.scan_plan_coverage(plans, "demo", ["d-1", "d-2", "d-3"])
    expect(sorted(cov), ["d-1", "d-2", "d-3"])
    for bid in ("d-1", "d-2", "d-3"):
        expect(cov[bid][0]["how"], "beads-table")
        expect(plan_coverage.coverage_action(cov[bid]), "review")


def case_bare_mention_alone_never_drops_a_bead(tmp: Path) -> None:
    citations = [{"path": "/p.md", "how": "bare-id", "line": "saw d-2 once"}]
    expect(plan_coverage.coverage_action(citations), "review")


def case_one_strong_citation_outranks_any_number_of_weak_ones(tmp: Path) -> None:
    plans = plan_tree(
        tmp,
        {
            "todo/a/notes.md": "mentions d-5 in passing\n",
            "todo/a/more.md": "| Not this epic | `d-5` | later |\n",
            "done/b/plan.md": "**Beads task:** d-5\n",
        },
    )
    cov = plan_coverage.scan_plan_coverage(plans, "demo", ["d-5"])
    expect(len(cov["d-5"]), 3)
    expect(plan_coverage.coverage_action(cov["d-5"]), "drop")


def case_a_superseded_id_on_a_beads_task_line_is_not_ownership(tmp: Path) -> None:
    """Regression: a second ID on a `Beads task:` line used to inherit its strength.

    The field is an ownership declaration about exactly one bead. Reading the
    whole line dropped `d-def` — a real, unplanned bead — with no report line.
    """
    body = "**Beads task:** d-abc (epic) — supersedes d-def, which this plan replaces\n"
    plans = plan_tree(tmp, {"todo/x/plan.md": body})
    cov = plan_coverage.scan_plan_coverage(plans, "demo", ["d-abc", "d-def"])
    expect(cov["d-abc"][0]["how"], "beads-task")
    expect(plan_coverage.coverage_action(cov["d-abc"]), "drop")
    expect(cov["d-def"][0]["how"], "bare-id")
    expect(plan_coverage.coverage_action(cov["d-def"]), "review")


def case_a_beads_task_line_naming_a_blocker_still_drops_only_its_own_bead(
    tmp: Path,
) -> None:
    """Calibration in both directions: the owned bead still drops, the other reviews."""
    body = "**Beads task:** `d-1` — blocked on d-2 landing first\n"
    plans = plan_tree(tmp, {"todo/x/plan.md": body})
    cov = plan_coverage.scan_plan_coverage(plans, "demo", ["d-1", "d-2"])
    expect(cov["d-1"][0]["how"], "beads-task")
    expect(plan_coverage.coverage_action(cov["d-1"]), "drop")
    expect(cov["d-2"][0]["how"], "bare-id")
    expect(plan_coverage.coverage_action(cov["d-2"]), "review")


def case_citation_form_reads_a_line_without_touching_disk(tmp: Path) -> None:
    expect(plan_coverage.citation_form("**Beads Task:** d-1", "d-1"), "beads-task")
    expect(plan_coverage.citation_form("| a | d-1 | b |", "d-1"), "beads-table")
    expect(plan_coverage.citation_form("filed d-1 yesterday", "d-1"), "bare-id")
    expect(
        plan_coverage.citation_form("**Beads task:** d-1 supersedes d-2", "d-2"),
        "bare-id",
    )


# --- defect skills-dm0: the report must name the citation that decided ------


def case_the_deciding_citation_is_the_strong_one_not_the_first(tmp: Path) -> None:
    """Regression: the report used to name whichever file sorted first.

    `coverage_action` scans the whole list, so a bead can be dropped on a
    strong citation while an alphabetically earlier weak one sits at index 0.
    Reporting that weak file as the reason defeats the only check a reader of
    the judge brief has.
    """
    plans = plan_tree(
        tmp,
        {
            "todo/a/more.md": "| Not this epic | `d-5` | later |\n",
            "done/b/plan.md": "**Beads task:** d-5\n",
        },
    )
    cov = plan_coverage.scan_plan_coverage(plans, "demo", ["d-5"])
    expect(cov["d-5"][0]["how"], "beads-table")
    cite = plan_coverage.deciding_citation(cov["d-5"])
    expect(cite["how"], "beads-task")
    assert cite["path"].endswith("done/b/plan.md"), cite


def case_with_no_strong_citation_the_first_one_decides(tmp: Path) -> None:
    plans = plan_tree(tmp, {"todo/a/more.md": "| listed | `d-5` | later |\n",
                            "todo/b/notes.md": "mentions d-5 in passing\n"})
    cov = plan_coverage.scan_plan_coverage(plans, "demo", ["d-5"])
    cite = plan_coverage.deciding_citation(cov["d-5"])
    expect(cite, cov["d-5"][0])
    expect(plan_coverage.coverage_action(cov["d-5"]), "review")


def case_no_citations_at_all_reviews_rather_than_raising(tmp: Path) -> None:
    """`any()` over an empty list used to give this for free; the rewrite must
    not quietly turn a caller's empty list into an IndexError."""
    expect(plan_coverage.deciding_citation([]), None)
    expect(plan_coverage.coverage_action([]), "review")


# --- defect skills-y33: the judge must rule on coverage, and it must be acted on


def ruling(bead, verdict, plan=None) -> dict:
    out = {"id": bead, "verdict": verdict}
    if plan:
        out["plan"] = plan
    return out


def case_a_complete_coverage_ruling_is_valid(tmp: Path) -> None:
    got = plan_coverage.validate_coverage(
        ["d-1", "d-2"],
        [ruling("d-1", "covered", "/plans/demo/todo/x/plan.md"),
         ruling("d-2", "not-covered")])
    expect(got, [])


def case_covered_beads_are_the_ones_skipped(tmp: Path) -> None:
    rulings = [ruling("d-1", "covered", "/plans/demo/todo/x/plan.md"),
               ruling("d-2", "not-covered")]
    expect(plan_coverage.skipped(rulings), ["d-1"])


def case_an_unruled_bead_is_a_finding(tmp: Path) -> None:
    """The whole defect: a review result nobody answers is a bead nobody routes."""
    got = plan_coverage.validate_coverage(["d-1", "d-2"],
                                          [ruling("d-1", "not-covered")])
    assert any("d-2" in f for f in got), got


def case_a_bead_ruled_twice_is_a_finding(tmp: Path) -> None:
    got = plan_coverage.validate_coverage(
        ["d-1"], [ruling("d-1", "not-covered"), ruling("d-1", "covered", "/p.md")])
    assert any("d-1" in f for f in got), got


def case_a_foreign_bead_is_a_finding(tmp: Path) -> None:
    got = plan_coverage.validate_coverage(["d-1"], [ruling("d-1", "not-covered"),
                                                    ruling("d-9", "not-covered")])
    assert any("d-9" in f for f in got), got


def case_an_unknown_verdict_is_a_finding(tmp: Path) -> None:
    got = plan_coverage.validate_coverage(["d-1"], [ruling("d-1", "maybe")])
    assert any("maybe" in f for f in got), got


def case_covered_without_naming_the_plan_is_a_finding(tmp: Path) -> None:
    """A skip whose reason cannot be checked is a bead deleted on an opinion."""
    got = plan_coverage.validate_coverage(["d-1"], [ruling("d-1", "covered")])
    assert any("plan" in f for f in got), got


def case_a_ruling_with_no_id_is_a_finding(tmp: Path) -> None:
    """The key is `id`, and a ruling missing it must be reported, not raised on."""
    got = plan_coverage.validate_coverage(["d-1"], [{"verdict": "not-covered"}])
    assert any("id" in f for f in got), got


def case_every_ruling_missing_its_id_still_returns_findings(tmp: Path) -> None:
    """A live run keyed nine rulings `bead` and got a TypeError out of the
    duplicate check instead of nine findings. A validator that raises on the
    malformed input it exists to reject tells the caller nothing about it."""
    rulings = [{"bead": f"d-{n}", "verdict": "not-covered"} for n in range(1, 4)]
    got = plan_coverage.validate_coverage(["d-1", "d-2", "d-3"], rulings)
    assert len(got) >= 3, got
    assert all("d-" in f for f in got if "not ruled on" in f), got


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
