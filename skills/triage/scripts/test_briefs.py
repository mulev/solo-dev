"""Tests for the three worker brief generators — brief_invest.sh,
brief_plan.sh and brief_qc.sh.

Every case copies the scripts into a temp skills tree and runs them from
there, because each script derives its skills root from `$0` rather than
from the caller's cwd. That is the whole seam: writing a contract file
with, without, or with a malformed `Contract version:` line is then a
one-line change per case, and no test-only environment override had to be
invented to get at it.

The load-bearing assertion is `case_no_generator_prints_the_contract_token`.
A brief that hands the worker the token turns a proof of reading into a
copy-paste, so the omission is a contract, not an oversight.

**LOC waiver:** a case-per-assertion list over four generators, read one case
at a time — the same shape and the same reasoning as
`test_lint_investigation.py`. Splitting it by generator would put the shared
temp-tree scaffolding behind an import and buy a smaller number in four files
nobody reads end to end; splitting it by assertion kind would cut across the
generators each case is about.

Run with `python3 test_briefs.py` (no pytest dependency).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

import intent_records
import staged_run
# The token, its declaration prefix and its shape all come from the production
# reader: this file must not hold a second grammar for the line, and
# `test_contract.py` fails any file that re-literalises the value.
from contract import DECL_PREFIX, TOKEN_RE, token as declared_token

HERE = Path(__file__).resolve().parent
SCRIPTS = ("brief_invest.sh", "brief_plan.sh", "brief_qc.sh", "brief_judge.sh")

JSON_FENCE = re.compile(r"```json\n(.*?)\n```", re.DOTALL)

TOKEN = declared_token()

GOOD_CONTRACT = f"# Autonomous mode\n\n{DECL_PREFIX} **{TOKEN}** — echo it.\n"
NO_VERSION = "# Autonomous mode\n\nNo version line anywhere in this file.\n"
MALFORMED = f"# Autonomous mode\n\n{DECL_PREFIX} **SW-v1** — malformed.\n"


def expect(got, want) -> None:
    assert got == want, f"got {got!r}, want {want!r}"


def tree(tmp: Path, contract: str | None = GOOD_CONTRACT) -> Path:
    """Build a temp skills root holding copies of all three generators."""
    root = tmp / "skills"
    (root / "triage" / "scripts").mkdir(parents=True)
    for name in SCRIPTS:
        shutil.copy(HERE / name, root / "triage" / "scripts" / name)
    (root / "_shared").mkdir()
    if contract is not None:
        (root / "_shared" / "autonomous-mode.md").write_text(contract)
    for skill in ("investigate", "plan"):
        (root / skill).mkdir()
        (root / skill / "SKILL.md").write_text("# stub\n")
    (root / "AGENTS.md").write_text("workspace\n")
    (root / "repo").mkdir()
    (root / "repo" / "AGENTS.md").write_text("repo\n")
    (root / "stage").mkdir()
    return root


def happy_args(root: Path, script: str) -> list[str]:
    repo, stage = str(root / "repo"), str(root / "stage")
    art = f"{stage}/investigations/b-1.md"
    return {
        "brief_invest.sh": ["b-1", art, stage, repo],
        "brief_plan.sh": ["b-1,b-2", f"{art},{stage}/investigations/b-2.md", stage, repo],
        "brief_qc.sh": [art, "investigation", "1", repo],
        "brief_judge.sh": [f"{stage}/judge_brief.md", repo],
    }[script]


def run(root: Path, script: str, *args: str) -> tuple[int, str, str]:
    proc = subprocess.run(
        ["sh", str(root / "triage" / "scripts" / script), *args],
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout, proc.stderr


def brief(tmp: Path, script: str) -> str:
    root = tree(tmp)
    code, out, err = run(root, script, *happy_args(root, script))
    expect(code, 0)
    assert out.strip(), f"{script} printed nothing: {err}"
    return out


# --- usage and configuration errors, applied to all three --------------------


def case_wrong_argument_counts_exit_two_with_a_usage_line(tmp: Path) -> None:
    for script in SCRIPTS:
        root = tree(tmp / script)
        for args in ([], ["one"], ["a", "b", "c", "d", "e"]):
            code, _, err = run(root, script, *args)
            expect(code, 2)
            assert "usage:" in err, (script, args, err)
            assert script in err, (script, args, err)


def case_missing_contract_file_exits_two(tmp: Path) -> None:
    for script in SCRIPTS:
        root = tree(tmp / script, contract=None)
        code, _, err = run(root, script, *happy_args(root, script))
        expect(code, 2)
        assert "autonomous-mode.md" in err, (script, err)


def case_contract_without_a_version_line_exits_two(tmp: Path) -> None:
    for script in SCRIPTS:
        root = tree(tmp / script, contract=NO_VERSION)
        code, _, err = run(root, script, *happy_args(root, script))
        expect(code, 2)
        assert str(root / "_shared" / "autonomous-mode.md") in err, (script, err)


def case_contract_with_a_malformed_token_exits_two(tmp: Path) -> None:
    for script in SCRIPTS:
        root = tree(tmp / script, contract=MALFORMED)
        code, _, err = run(root, script, *happy_args(root, script))
        expect(code, 2)
        assert "contract version" in err.lower(), (script, err)


def case_a_repo_root_that_does_not_exist_exits_two(tmp: Path) -> None:
    for script in SCRIPTS:
        root = tree(tmp / script)
        args = happy_args(root, script)
        args = [str(root / "ghost") if a == str(root / "repo") else a for a in args]
        code, _, _ = run(root, script, *args)
        expect(code, 2)


def case_every_generator_takes_repo_root_last(tmp: Path) -> None:
    """Every generator ends its signature with <repo-root>.

    brief_invest.sh and brief_qc.sh both took it third at first — a divergence
    the single caller that builds every invocation would have paid for. Parse
    the usage line and read its final token, so rewording the text around the
    signature cannot quietly retire this check. Arity is deliberately not
    asserted: the generators take two to four arguments and the convention is
    about the last one.
    """
    root = tree(tmp)
    for script in SCRIPTS:
        code, _, err = run(root, script)
        expect(code, 2)
        usage = [ln for ln in err.splitlines() if ln.startswith("usage:")]
        expect(len(usage), 1)
        _, name, *params = usage[0].split()
        expect(name, script)
        assert len(params) >= 2, (script, params)
        expect(params[-1], "<repo-root>")


# --- the section contract, applied to all three ------------------------------


def case_every_brief_carries_the_five_section_headings(tmp: Path) -> None:
    for script in SCRIPTS:
        out = brief(tmp / script, script)
        for heading in (
            "# Read first (in this order, before any other tool call)",
            "# Constraints (decided by the main session — do NOT re-decide)",
            "# Escalation",
            "# PARK — recognise your own exit",
            "# Report (at most 15 lines, no diffs, no logs)",
        ):
            assert heading in out, (script, heading)


def case_every_brief_names_the_contract_and_both_agents_files(tmp: Path) -> None:
    for script in SCRIPTS:
        root = tree(tmp / script)
        code, out, _ = run(root, script, *happy_args(root, script))
        expect(code, 0)
        for path in (
            root / "_shared" / "autonomous-mode.md",
            root / "AGENTS.md",
            root / "repo" / "AGENTS.md",
        ):
            assert str(path) in out, (script, str(path))


def case_every_report_opens_with_the_contract_field(tmp: Path) -> None:
    for script in SCRIPTS:
        out = brief(tmp / script, script)
        assert "contract: the version token" in out, script


def case_no_generator_prints_the_contract_token(tmp: Path) -> None:
    """The worker looks the token up; a printed token proves only copying."""
    for script in SCRIPTS:
        out = brief(tmp / script, script)
        assert TOKEN not in out, script
        leaked = TOKEN_RE.search(out)
        assert leaked is None, (script, leaked.group(0))


def case_this_file_never_pins_the_contract_token(tmp: Path) -> None:
    """Regression: the fixture token is read off the contract, not written here.

    A literal pinned in this file passes every case above and still fails the
    repository-wide scan in test_contract.py, which is how the first version
    of this file broke the phase-exit stage.
    """
    source = Path(__file__).read_text(encoding="utf-8")
    assert TOKEN not in source, f"{Path(__file__).name} pins {TOKEN}"


def case_every_brief_forbids_commits_and_pushes(tmp: Path) -> None:
    for script in SCRIPTS:
        out = brief(tmp / script, script)
        assert "No commits, no pushes" in out, script


def case_both_worker_briefs_keep_the_orchestrator_lint_authoritative(tmp: Path) -> None:
    """A worker told to pass a linter will pass it — including by contorting
    the artifact around a finding that is wrong. The brief has to say which
    run is the gate, and what to do with a finding the worker disputes."""
    for script in ("brief_invest.sh", "brief_plan.sh"):
        out = brief(tmp / script, script)
        assert "This is a pre-flight, never a substitute." in out, script
        assert "runs the same linter authoritatively" in out, script
        assert "never contort the artifact to silence a finding you believe is wrong" in out, script


# --- brief_invest.sh only ----------------------------------------------------


def case_invest_brief_names_its_bead_artifact_and_skill(tmp: Path) -> None:
    root = tree(tmp)
    code, out, _ = run(root, "brief_invest.sh", *happy_args(root, "brief_invest.sh"))
    expect(code, 0)
    assert "b-1" in out, out
    assert f"{root}/stage/investigations/b-1.md" in out, out
    assert f"{root}/investigate/SKILL.md" in out, out
    assert str(root / "stage") in out, out


def case_invest_brief_names_the_park_statuses_the_linter_accepts(tmp: Path) -> None:
    """A worker told to park must be told what a parked artifact looks like.

    Measured: two live workers parked correctly and invented two different
    Status strings between them, because the brief named the exit and not the
    artifact. Both then failed tier 1 on `header-status-wrong`.

    Read off `lint_investigation` rather than spelled out here — the brief and
    the linter are the two ends of the same contract, and a test that restated
    the strings would let them drift while staying green.
    """
    sys.path.insert(0, str(HERE))
    from lint_investigation import PARK_STATUSES

    out = brief(tmp, "brief_invest.sh")
    for status in PARK_STATUSES:
        assert status in out, f"brief never names {status}: {out}"
    assert "## Open Question" in out, out


def case_invest_brief_names_the_gate_stop_status(tmp: Path) -> None:
    """A worker stopped at Gate 2 must be told what its artifact's header says.

    Measured on the first full run: the brief ordered the artifact written and
    the gate left unanswered, named the two park statuses and banned
    `FIX APPROVED` — and named nothing for the outcome every non-parking worker
    reaches. The worker invented a status, tier 1 rejected it, and the run
    stalled on all nine beads.

    Read off `lint_investigation` for the same reason the park case is: the
    brief and the linter are two ends of one contract, and a restated string
    lets them drift while staying green.
    """
    sys.path.insert(0, str(HERE))
    from lint_investigation import STATUS_FIX_PROPOSED

    out = brief(tmp, "brief_invest.sh")
    assert STATUS_FIX_PROPOSED in out, f"brief never names {STATUS_FIX_PROPOSED}: {out}"


def case_invest_brief_demands_a_footprint_block(tmp: Path) -> None:
    out = brief(tmp, "brief_invest.sh")
    assert "footprint:" in out, out
    for field in ("files:", "modules:", "symbols:"):
        assert field in out, field


def case_a_brief_names_exactly_two_output_paths(tmp: Path) -> None:
    """The one-output-file rule is two paths wide now, and no wider.

    The second path is the report the worker returns. A return that lives only
    on the harness job leg is retained five minutes past settlement, and every
    verdict this system has produced arrived later than that — so a `REVISE`
    had nothing to route back to. Both paths sit inside the staging root, which
    is § B of the contract unchanged; the loosening is exactly one path wide,
    asserted by reading the one sentence that names them.
    """
    root = tree(tmp)
    stage = root / "stage"
    code, out, _ = run(root, "brief_invest.sh", *happy_args(root, "brief_invest.sh"))
    expect(code, 0)
    named = [ln for ln in out.splitlines() if ln.startswith("Your two output files:")]
    expect(len(named), 1)
    for path in (f"{stage}/investigations/b-1.md", f"{stage}/reports/b-1_r1.md"):
        assert path in named[0], (path, named[0])
    assert "and nothing else, anywhere." in named[0], named[0]


def case_the_invest_brief_prints_a_report_path_inside_the_run(tmp: Path) -> None:
    """Derived from the staging root and the bead id the generator already
    takes — never a fifth positional argument, because five arguments is a
    pinned usage error and `<repo-root>` is pinned last."""
    root = tree(tmp)
    code, out, _ = run(root, "brief_invest.sh", *happy_args(root, "brief_invest.sh"))
    expect(code, 0)
    assert f"{root}/stage/reports/b-1_r1.md" in out, out


def case_the_plan_brief_prints_a_report_path_inside_the_run(tmp: Path) -> None:
    """A planning worker covers a whole collision group, so its report is keyed
    by the group's first bead — the same id Wave 4 keys the group's brief by."""
    root = tree(tmp)
    code, out, _ = run(root, "brief_plan.sh", *happy_args(root, "brief_plan.sh"))
    expect(code, 0)
    assert f"{root}/stage/reports/b-1_plan_r1.md" in out, out


def case_invest_brief_permits_read_only_research_agents(tmp: Path) -> None:
    out = brief(tmp, "brief_invest.sh")
    assert "Parallel read-only research agents are permitted" in out, out


def case_invest_brief_never_offers_the_plan_handoff(tmp: Path) -> None:
    out = brief(tmp, "brief_invest.sh")
    assert "Gate 3 (handoff to implementation) never fires here." in out, out


def case_the_invest_brief_grants_exactly_one_record_kind(tmp: Path) -> None:
    """A parked bead never reaches a planner, so without this grant a title the
    investigation disproved has no writer at all. The grant is exactly one kind
    wide, and the rest of the brief's read-only tracker rule still stands.
    """
    out = brief(tmp, "brief_invest.sh")
    named = {kind for kind in intent_records.KINDS if f"`{kind}`" in out}
    expect(named, {"retitle"})
    assert "Tracker: read-only." in out, out
    assert "No `bd update`" in out, out


def case_invest_brief_orders_a_pre_return_lint(tmp: Path) -> None:
    """A worker that never lints returns work tier 1 rejects on sight.

    Three of three plans in one live run bounced tier 1 on findings the
    producing worker could have read off its own linter in seconds — each
    bounce an orchestrator round trip plus a worker re-wake.
    """
    root = tree(tmp)
    code, out, _ = run(root, "brief_invest.sh", *happy_args(root, "brief_invest.sh"))
    expect(code, 0)
    art = f"{root}/stage/investigations/b-1.md"
    assert f"lint_investigation.py {art} --repo {root}/repo" in out, out
    assert "before you report" in out, out


# --- brief_plan.sh only ------------------------------------------------------


def case_plan_brief_swaps_the_output_root_and_kills_the_mirror(tmp: Path) -> None:
    root = tree(tmp)
    stage = str(root / "stage")
    code, out, _ = run(root, "brief_plan.sh", *happy_args(root, "brief_plan.sh"))
    expect(code, 0)
    swap = [ln for ln in out.splitlines() if "Output root swap" in ln]
    expect(len(swap), 1)
    block = out.split("**Output root swap")[1].split("\n\n")[0]
    assert f"{stage}/todo" in block, block
    assert "~/.claude/plans" in block, block
    assert "mirror is OFF" in block, block


def case_plan_brief_writes_where_promote_reads(tmp: Path) -> None:
    """The brief's output root must be the directory `staged_plans` reads.

    Measured on a live orchestrator run: the brief sent plans to
    `<run>/plans/<project>/todo/` while `staged_run.staged_plans()` reads
    `<run>/todo/` and SKILL.md's staging layout documents the same. A plan
    written where the brief said would have been invisible to promote — staged
    correctly by every other measure, and silently dropped.

    Derived from `staged_plans` rather than spelled out here, so the brief and
    the reader cannot drift apart again without this failing.
    """
    root = tree(tmp)
    stage = root / "stage"
    code, out, _ = run(root, "brief_plan.sh", *happy_args(root, "brief_plan.sh"))
    expect(code, 0)

    (stage / "todo" / "proj_fix_a_thing").mkdir(parents=True, exist_ok=True)
    read_from = staged_run.staged_plans(stage)[0].parent

    block = out.split("**Output root swap")[1].split("\n\n")[0]
    assert f"{read_from}/" in block, f"brief does not name {read_from}: {block}"
    assert f"{stage}/plans" not in block, block


def case_plan_brief_names_every_bead_and_every_investigation(tmp: Path) -> None:
    root = tree(tmp)
    code, out, _ = run(root, "brief_plan.sh", *happy_args(root, "brief_plan.sh"))
    expect(code, 0)
    for bead in ("b-1", "b-2"):
        assert bead in out, bead
    for path in ("investigations/b-1.md", "investigations/b-2.md"):
        assert f"{root}/stage/{path}" in out, path
    assert f"{root}/plan/SKILL.md" in out, out


def plan_brief_example(tmp: Path) -> list:
    """The worked example the plan brief prints, parsed.

    The brief interpolates `$STAGING`, so the example carries real absolute
    paths and can be fed straight to the store's own validator.
    """
    blocks = JSON_FENCE.findall(brief(tmp, "brief_plan.sh"))
    expect(len(blocks), 1)
    return json.loads(blocks[0])


def case_plan_brief_names_the_intent_record_schema(tmp: Path) -> None:
    root = tree(tmp)
    code, out, _ = run(root, "brief_plan.sh", *happy_args(root, "brief_plan.sh"))
    expect(code, 0)
    assert f"{root}/triage/scripts/intent_records.py" in out, out
    assert f"{root}/stage/intents/" in out, out


def case_plan_brief_example_uses_only_worker_kinds(tmp: Path) -> None:
    """Read the kinds off the store: a list restated here would let the brief
    and the schema drift apart while this stays green."""
    kinds = {record["kind"] for record in plan_brief_example(tmp)}
    expect(kinds, set(intent_records.WORKER_KINDS))


def case_plan_brief_example_validates_under_intent_records(tmp: Path) -> None:
    """The brief teaches a shape the store accepts — the whole point of the
    example being real records rather than a prose sketch."""
    findings = [f for record in plan_brief_example(tmp)
                for f in intent_records.validate(record)]
    expect(findings, [])


def case_plan_brief_replaces_every_tracker_call_with_an_intent_block(tmp: Path) -> None:
    """`source-bead:` was the prose shape; that intent is derived now, so the
    brief names the worker's kinds in prose and forbids the derived ones.

    The prose half is asserted above the example deliberately: a kind that
    appears only inside the JSON block is a shape the worker can copy and not
    a rule it was taught.
    """
    out = brief(tmp, "brief_plan.sh")
    assert "you never run" in out, out
    prose, _ = out.split("\n```json\n", 1)
    for kind in intent_records.WORKER_KINDS:
        assert kind in prose, kind
    never = out.split("Never write")[1]
    for kind in intent_records.DERIVED_KINDS:
        assert kind in never, kind


def case_plan_brief_makes_the_worker_write_its_own_slices(tmp: Path) -> None:
    out = brief(tmp, "brief_plan.sh")
    assert "Write the slice files yourself, sequentially." in out, out


def case_plan_brief_orders_a_pre_return_lint(tmp: Path) -> None:
    """The plan worker's linter is the one that caught every live bounce."""
    root = tree(tmp)
    code, out, _ = run(root, "brief_plan.sh", *happy_args(root, "brief_plan.sh"))
    expect(code, 0)
    assert "lint_plan.py" in out, out
    assert f"--project-root {root}/repo" in out, out
    assert f"{root}/stage/todo/" in out, out
    assert "before you report" in out, out


# --- brief_qc.sh only --------------------------------------------------------


def case_qc_brief_echoes_the_round_it_was_given(tmp: Path) -> None:
    root = tree(tmp)
    args = happy_args(root, "brief_qc.sh")
    code, out, _ = run(root, "brief_qc.sh", args[0], args[1], "3", args[3])
    expect(code, 0)
    assert "# Round 3" in out, out
    assert "round 3" in out, out
    assert "round 1" not in out, out


def case_qc_brief_output_differs_by_kind(tmp: Path) -> None:
    root = tree(tmp)
    args = happy_args(root, "brief_qc.sh")
    _, investigation, _ = run(root, "brief_qc.sh", args[0], "investigation", *args[2:])
    _, plan, _ = run(root, "brief_qc.sh", args[0], "plan", *args[2:])
    assert "kind=investigation" in investigation, investigation
    assert "kind=plan" in plan, plan
    assert investigation != plan


def case_qc_brief_names_the_gates_reference_without_requiring_it(tmp: Path) -> None:
    root = tree(tmp)
    gates = root / "triage" / "references" / "qc-gates.md"
    assert not gates.exists(), "the fixture must not ship qc-gates.md"
    code, out, _ = run(root, "brief_qc.sh", *happy_args(root, "brief_qc.sh"))
    expect(code, 0)
    assert str(gates) in out, out


def case_qc_brief_withholds_the_transcript_and_demands_refutation(tmp: Path) -> None:
    out = brief(tmp, "brief_qc.sh")
    assert "You do NOT receive the producing worker's transcript" in out, out
    assert "Your job is to refute, not to agree." in out, out
    assert "Write nothing." in out, out


def case_qc_rejects_an_unknown_kind(tmp: Path) -> None:
    root = tree(tmp)
    args = happy_args(root, "brief_qc.sh")
    for kind in ("slice", "Investigation", ""):
        code, _, err = run(root, "brief_qc.sh", args[0], kind, *args[2:])
        expect(code, 2)
        assert "kind must be" in err, (kind, err)


def case_qc_rejects_a_round_that_is_not_a_positive_integer(tmp: Path) -> None:
    root = tree(tmp)
    args = happy_args(root, "brief_qc.sh")
    for round_ in ("0", "-1", "x", "", "1.5"):
        code, _, err = run(root, "brief_qc.sh", args[0], args[1], round_, args[3])
        expect(code, 2)
        assert "round must be a positive integer" in err, (round_, err)


# --- the Wave 1 judge --------------------------------------------------------


def case_judge_brief_names_the_brief_it_rules_on(tmp: Path) -> None:
    root = tree(tmp)
    code, out, _ = run(root, "brief_judge.sh", *happy_args(root, "brief_judge.sh"))
    expect(code, 0)
    assert f"{root}/stage/judge_brief.md" in out, out


def case_judge_brief_is_read_only(tmp: Path) -> None:
    out = brief(tmp, "brief_judge.sh")
    for rule in ("read-only", "Do not write", "any `bd` command that mutates"):
        assert rule in out, rule


def case_judge_brief_refuses_to_let_similarity_decide(tmp: Path) -> None:
    """The score groups candidates; it never rules. Shared vocabulary reads as
    shared work exactly where a cluster is worth ruling on."""
    out = brief(tmp, "brief_judge.sh")
    assert "an input, not an answer" in out, out


def case_judge_brief_sends_the_judge_to_the_source(tmp: Path) -> None:
    out = brief(tmp, "brief_judge.sh")
    assert "Read the code before ruling" in out, out


def case_judge_brief_makes_unsure_the_safe_verdict(tmp: Path) -> None:
    """A wrong `duplicate` silently deletes real work; a wrong
    `related-not-duplicate` costs one extra plan."""
    out = brief(tmp, "brief_judge.sh")
    assert "related-not-duplicate" in out and "unsure" in out, out
    assert "silently" in out, out


def case_judge_brief_demands_a_partition_per_cluster(tmp: Path) -> None:
    out = brief(tmp, "brief_judge.sh")
    assert "exactly one group" in out, out
    for verdict in ("duplicate", "distinct", "related-not-duplicate"):
        assert verdict in out, verdict
    assert "representative" in out, out


def case_judge_brief_demands_a_coverage_line_per_flagged_bead(tmp: Path) -> None:
    out = brief(tmp, "brief_judge.sh")
    assert "not-covered" in out, out
    assert "every bead" in out.lower(), out


def case_every_generator_is_committed_executable(tmp: Path) -> None:
    """A bare-path invocation is what `triage/SKILL.md` documents for all four
    generators, and exit 126 leaves a zero-byte brief the run then dispatches.
    Every automated caller launches them through `sh`, which needs no bit —
    so without this case the mode can regress with every suite green.

    The git root is asked for rather than assumed. In the public bundle this
    directory sits one level deeper, under `skills/`, so a hard-coded
    `parents[1]` found no tracked files there and the case passed on an empty
    set — green while checking nothing.
    """
    here = HERE.resolve()
    root = Path(subprocess.run(["git", "rev-parse", "--show-toplevel"],
                               cwd=str(here), capture_output=True, text=True,
                               check=True).stdout.strip())
    prefix = here.relative_to(root)
    out = subprocess.run(["git", "ls-files", "-s", "--", f"{prefix}/brief_*.sh"],
                         cwd=str(root), capture_output=True, text=True, check=True)
    entries = dict((line.split("\t")[1], line.split()[0])
                   for line in out.stdout.splitlines() if line.strip())
    assert entries, f"no tracked generators under {prefix} — the glob found nothing"
    expect(sorted(Path(p).name for p in entries), sorted(SCRIPTS))
    for path, mode in sorted(entries.items()):
        expect((path, mode), (path, "100755"))
        assert os.access(root / path, os.X_OK), f"{path} is not executable in the worktree"


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
