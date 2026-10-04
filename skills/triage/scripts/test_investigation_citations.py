#!/usr/bin/env python3
"""Tests for investigation_citations.py — direct calls, no CLI, no filesystem
walk beyond a temp repo.

Run with `python3 test_investigation_citations.py` (no pytest dependency).
"""

from __future__ import annotations

import sys
import tempfile
import traceback
from pathlib import Path

from investigation_citations import candidate_roots, check_citations

ARTIFACT = Path("/plans/proj/investigations/proj_invest_thing_goes_wrong.md")
SOURCE = "import 'x';\nfinal int pageCount;\nvoid go() {}\n"


def repo_with(tmp: Path, extra: dict | None = None) -> Path:
    repo = tmp / "proj"
    (repo / "lib").mkdir(parents=True)
    (repo / "lib" / "reader.dart").write_text(SOURCE, encoding="utf-8")
    for rel, body in (extra or {}).items():
        target = repo / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
    return repo


def fenced_codes(tmp: Path, lines: list[str], fences: dict,
                 extra: dict | None = None) -> list[str]:
    """Finding codes for a whole artifact body, fenced blocks included."""
    findings = check_citations(ARTIFACT, lines, repo_with(tmp, extra), {}, fences)
    return [f.code for f in findings]


def codes(tmp: Path, line: str, extra: dict | None = None) -> list[str]:
    """Finding codes for a one-line artifact that has no fenced blocks."""
    return fenced_codes(tmp, [line], {}, extra)


def case_resolved_path_with_matching_quote_is_clean(tmp: Path) -> None:
    got = codes(tmp, "step — `lib/reader.dart:2` quote `final int pageCount;`")
    assert got == [], got


def case_missing_file_reports_missing(tmp: Path) -> None:
    got = codes(tmp, "step — `lib/gone.dart:4` quote `final int pageCount;`")
    assert got == ["citation-file-missing"], got


def case_past_eof_reports_out_of_range(tmp: Path) -> None:
    got = codes(tmp, "step — `lib/reader.dart:99` quote `final int pageCount;`")
    assert got == ["citation-line-out-of-range"], got


def case_range_past_eof_reports_out_of_range(tmp: Path) -> None:
    got = codes(tmp, "step — `lib/reader.dart:2-40` quote `final int pageCount;`")
    assert got == ["citation-line-out-of-range"], got


def case_quote_absent_from_window_is_an_error(tmp: Path) -> None:
    got = codes(tmp, "step — `lib/reader.dart:2` quote `nowhere in the file`")
    assert got == ["citation-quote-absent"], got


def case_quote_off_by_two_is_only_a_warning(tmp: Path) -> None:
    findings = check_citations(
        ARTIFACT, ["step — `lib/reader.dart:1` quote `void go() {}`"],
        repo_with(tmp), {})
    assert [f.code for f in findings] == ["citation-quote-offset"], findings
    assert findings[0].severity == "warning", findings
    assert "line 3" in findings[0].detail, findings


def case_quote_inside_a_range_is_clean(tmp: Path) -> None:
    got = codes(tmp, "step — `lib/reader.dart:1-3` quote `void go() {}`")
    assert got == [], got


def case_two_matching_basenames_are_ambiguous(tmp: Path) -> None:
    got = codes(tmp, "step — `reader.dart:2` quote `final int pageCount;`",
                {"lib/other/reader.dart": SOURCE})
    assert got == ["citation-ambiguous"], got


def case_ambiguity_stops_before_the_quote_check(tmp: Path) -> None:
    got = codes(tmp, "step — `reader.dart:99` quote `nowhere in the file`",
                {"lib/other/reader.dart": SOURCE})
    assert got == ["citation-ambiguous"], got


def case_short_quote_proves_nothing_and_is_skipped(tmp: Path) -> None:
    got = codes(tmp, "step — `lib/reader.dart:2` quote `int`")
    assert got == [], got


def case_second_citation_is_not_read_as_a_quote(tmp: Path) -> None:
    got = codes(tmp, "step — `lib/reader.dart:2` and `lib/reader.dart:3`")
    assert got == [], got


def case_log_timestamp_is_not_a_citation(tmp: Path) -> None:
    got = codes(tmp, "the reader opened at 21:41:27 and stalled")
    assert got == [], got


def case_version_string_is_not_a_citation(tmp: Path) -> None:
    got = codes(tmp, "the pin reads `sqlite3: '>=3.1.2 <5.0.0'` in the lock")
    assert got == [], got


def case_a_contrast_ratio_is_not_a_citation(tmp: Path) -> None:
    """`4.5:1` read as `file.ext:line` — measured on a live triage run.

    A worker investigating theme contrast quoted WCAG ratios throughout, and
    every one of them came back `citation-file-missing`, naming `4.5` and
    `18.88` as files it could not find. An extension is alphabetic; a decimal
    fraction is not, which is the whole difference.
    """
    got = codes(tmp, "the pair measures 18.88:1 against a required 4.5:1")
    assert got == [], got


def case_a_numeric_extension_is_still_not_a_citation(tmp: Path) -> None:
    """The general form of it — the digits after the dot are what give it away."""
    got = codes(tmp, "the sample sat at 0.75:2 through the whole window")
    assert got == [], got


def case_a_real_citation_beside_a_ratio_still_resolves(tmp: Path) -> None:
    """The narrowing must not cost a citation on the same line as a ratio."""
    got = codes(tmp, "at 4.5:1 — `lib/reader.dart:2` quote `final int pageCount;`")
    assert got == [], got


def case_skipped_directories_are_not_indexed(tmp: Path) -> None:
    got = codes(tmp, "step — `buried.dart:1` quote `final int pageCount;`",
                {"build/buried.dart": SOURCE})
    assert got == ["citation-file-missing"], got


def case_whitespace_in_the_quote_is_normalised(tmp: Path) -> None:
    got = codes(tmp, "step — `lib/reader.dart:2` quote `final    int   pageCount;`")
    assert got == [], got


def case_cache_is_reused_across_calls(tmp: Path) -> None:
    repo, cache = repo_with(tmp), {}
    line = ["step — `reader.dart:2` quote `final int pageCount;`"]
    first = check_citations(ARTIFACT, line, repo, cache)
    assert [f.code for f in first] == ["citation-bare-filename"], first
    (repo / "lib" / "later.dart").write_text(SOURCE, encoding="utf-8")
    assert check_citations(ARTIFACT, line, repo, cache) == first, first
    assert list(cache) == [repo], cache


def case_findings_carry_the_artifact_line_number(tmp: Path) -> None:
    lines = ["intro", "", "step — `lib/gone.dart:4` quote `final int pageCount;`"]
    findings = check_citations(ARTIFACT, lines, repo_with(tmp), {})
    assert [f.line for f in findings] == [3], findings
    assert findings[0].artifact == ARTIFACT, findings


# --- defect skills-1o7: citations resolve under nested package roots ---------

NESTED = {"pkg/pubspec.yaml": "name: pkg\n", "pkg/lib/nested.dart": SOURCE}


def case_nested_package_root_resolves(tmp: Path) -> None:
    got = codes(tmp, "step — `lib/nested.dart:2` quote `final int pageCount;`", NESTED)
    assert got == [], got


def case_same_path_under_two_package_roots_is_ambiguous(tmp: Path) -> None:
    extra = dict(NESTED, **{"other/pubspec.yaml": "name: other\n",
                            "other/lib/nested.dart": SOURCE})
    findings = check_citations(
        ARTIFACT, ["step — `lib/nested.dart:2` quote `final int pageCount;`"],
        repo_with(tmp, extra), {})
    assert [f.code for f in findings] == ["citation-ambiguous"], findings
    assert findings[0].severity == "warning", findings


def case_directory_without_a_manifest_is_not_a_root(tmp: Path) -> None:
    got = codes(tmp, "step — `lib/nested.dart:2` quote `final int pageCount;`",
                {"plain/lib/nested.dart": SOURCE})
    assert got == ["citation-file-missing"], got


def case_path_missing_under_every_root_still_errors(tmp: Path) -> None:
    got = codes(tmp, "step — `lib/gone.dart:4` quote `final int pageCount;`", NESTED)
    assert got == ["citation-file-missing"], got


def case_missing_detail_names_no_package_roots_when_there_are_none(tmp: Path) -> None:
    findings = check_citations(
        ARTIFACT, ["step — `lib/gone.dart:4` quote `final int pageCount;`"],
        repo_with(tmp), {})
    assert "package root" not in findings[0].detail, findings


def case_missing_detail_names_the_nested_roots_it_searched(tmp: Path) -> None:
    findings = check_citations(
        ARTIFACT, ["step — `lib/gone.dart:4` quote `final int pageCount;`"],
        repo_with(tmp, NESTED), {})
    assert "1 nested package root" in findings[0].detail, findings


def case_candidate_roots_survives_an_unreadable_repo(tmp: Path) -> None:
    missing = tmp / "nope"
    assert candidate_roots(missing) == [missing]


def case_absolute_cited_path_is_not_ambiguous_across_roots(tmp: Path) -> None:
    """`root / "/abs"` is `/abs` for every root, so a naive hit list double-counts."""
    outside = tmp / "outside.dart"
    outside.write_text(SOURCE, encoding="utf-8")
    findings = check_citations(
        ARTIFACT, [f"step — `{outside}:2` quote `final int pageCount;`"],
        repo_with(tmp, NESTED), {})
    assert [f.code for f in findings] == [], findings


# --- defect skills-02j: only a marked quote is a quote -----------------------

MARKED = "step — `lib/reader.dart:2` reads:"
UNMARKED = "step — `lib/reader.dart:2` see below"


def case_backticked_prose_after_a_citation_is_not_a_quote(tmp: Path) -> None:
    got = codes(tmp, "the resolver at `lib/reader.dart:2` returns `Locator.fromJson`")
    assert got == [], got


def case_symbol_named_before_the_citation_is_not_a_quote(tmp: Path) -> None:
    got = codes(tmp, "`Locator.fromJson` is built at `lib/reader.dart:2`")
    assert got == [], got


def case_only_the_first_span_after_a_citation_can_be_the_quote(tmp: Path) -> None:
    got = codes(tmp, "step — `lib/reader.dart:2` returns `Locator.fromJson` "
                     "quote `final int pageCount;`")
    assert got == [], got


def case_fenced_quote_absent_from_the_cited_line_still_errors(tmp: Path) -> None:
    got = fenced_codes(tmp, [MARKED, "", "", ""], {3: ["nowhere in the file at all"]})
    assert got == ["citation-quote-absent"], got


def case_fenced_quote_present_at_the_cited_line_is_clean(tmp: Path) -> None:
    got = fenced_codes(tmp, [MARKED, "", "", ""], {3: ["final int pageCount;"]})
    assert got == [], got


def case_fenced_block_without_a_marker_is_ignored(tmp: Path) -> None:
    got = fenced_codes(tmp, [UNMARKED, "", "", ""], {3: ["nowhere in the file at all"]})
    assert got == [], got


def case_fenced_block_after_prose_is_not_bound(tmp: Path) -> None:
    got = fenced_codes(tmp, [MARKED, "prose intervenes", "", ""],
                       {3: ["nowhere in the file at all"]})
    assert got == [], got


def case_short_fenced_body_proves_nothing(tmp: Path) -> None:
    got = fenced_codes(tmp, [MARKED, "", "", ""], {3: ["int"]})
    assert got == [], got


def case_marked_citation_with_no_fence_at_all_is_silent(tmp: Path) -> None:
    got = fenced_codes(tmp, [MARKED, "", "", ""], {})
    assert got == [], got


# --- defect skills-511: a bare filename warns, and still resolves ------------


def case_bare_basename_resolves_but_warns_with_the_full_path(tmp: Path) -> None:
    findings = check_citations(
        ARTIFACT, ["step — `reader.dart:2` quote `final int pageCount;`"],
        repo_with(tmp), {})
    assert [f.code for f in findings] == ["citation-bare-filename"], findings
    assert findings[0].severity == "warning", findings
    assert "lib/reader.dart" in findings[0].detail, findings


def case_bare_filename_is_still_quote_checked(tmp: Path) -> None:
    got = codes(tmp, "step — `reader.dart:2` quote `nowhere in the file`")
    assert got == ["citation-bare-filename", "citation-quote-absent"], got


def case_bare_filename_that_is_missing_is_still_an_error(tmp: Path) -> None:
    got = codes(tmp, "step — `gone.dart:4` quote `final int pageCount;`")
    assert got == ["citation-file-missing"], got


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
