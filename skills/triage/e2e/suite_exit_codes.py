"""Assert every documented exit code of every triage CLI, through the real
command line.

Each case runs a process. That is the whole point: the unit suites call these
scripts' functions, so nothing they do covers argument parsing, and the `2`
paths — the ones a wrong invocation actually hits — have never been exercised
end to end. Codes come from each script's own docstring or `EPILOG`, which is
the contract this suite holds them to.

**Coupling waiver:** this file reaches eight foreign modules. Its
responsibility is one deterministic sweep over every triage CLI, and that is
inherently one CLI per module; every reach goes through `harness.run`'s single
subprocess seam. See the phase slice's Component Decomposition.
"""

from __future__ import annotations

import re
import sys

import harness

sys.path.insert(0, str(harness.SCRIPTS))

import manifest as manifest_io  # noqa: E402

CONTRACT_TOKEN = re.compile(r"SW-[0-9]{4}-[0-9]{2}-v[0-9]+")


def _fixture(*parts: str) -> str:
    return str(harness.FIXTURES.joinpath(*parts))


def _manifest(testbed, name: str, *bead_ids: str) -> str:
    """A manifest holding exactly the beads named, all of them in the run."""
    path = harness.scratch_path(testbed, name)
    manifest_io.save(path, {
        "project": testbed.path.name,
        "generated_at": "2026-08-29T00:00:00Z",
        "beads": [{"id": bead, "title": bead, "status": "needs-plan",
                   "issue_type": "bug", "priority": 2, "route": "investigate",
                   "reason": "no investigation on record"} for bead in bead_ids],
    })
    return str(path)


def _brief_args(testbed) -> dict:
    """Correct-arity arguments for each generator, keyed by script name — the
    single source of truth for which four generators exist. Repo root is
    always last."""
    stage = str(testbed.scratch)
    artifact = f"{stage}/investigations/tb-pln1_invest_retry.md"
    repo = str(testbed.path)
    return {
        "brief_invest.sh": ("tb-pln1", artifact, stage, repo),
        "brief_plan.sh": ("tb-pln1,tb-inv1", f"{artifact},{artifact}", stage, repo),
        "brief_qc.sh": (artifact, "investigation", "1", repo),
        "brief_judge.sh": (f"{stage}/judge_brief.md", repo),
    }


# --- inventory.py ------------------------------------------------------------


def case_inventory_clean_slice_exits_zero(testbed) -> None:
    """The clean sibling project — the main testbed carries tb-drf1 by design."""
    out = harness.scratch_path(testbed, "manifest_clean.json")
    code, _, err = harness.run("inventory.py", "--project", testbed.clean.name,
                               "--json", "--out", str(out), testbed=testbed)
    assert code == 0, (code, err)


def case_inventory_drift_exits_one(testbed) -> None:
    out = harness.scratch_path(testbed, "manifest_drift.json")
    code, _, err = harness.run("inventory.py", "--project", testbed.path.name,
                               "--json", "--out", str(out), testbed=testbed)
    assert code == 1, (code, err)


def case_inventory_unknown_project_exits_two(testbed) -> None:
    code, _, _ = harness.run("inventory.py", "--project", "not-a-real-project",
                             testbed=testbed)
    assert code == 2, code


def case_inventory_unknown_argument_exits_two(testbed) -> None:
    code, _, _ = harness.run("inventory.py", "--project", testbed.path.name,
                             "--wat", testbed=testbed)
    assert code == 2, code


# --- dedup.py ----------------------------------------------------------------


def case_dedup_clean_manifest_exits_zero(testbed) -> None:
    """One clean bead: no pair to compare, no plan citing it."""
    path = _manifest(testbed, "dedup_clean.json", "tb-ind1")
    code, _, err = harness.run("dedup.py", "--manifest", path, "--project",
                               testbed.path.name, "--plans-dir",
                               str(testbed.corpus), testbed=testbed)
    assert code == 0, (code, err)


def case_dedup_candidates_exit_one(testbed) -> None:
    path = _manifest(testbed, "dedup_pair.json", "tb-dup1", "tb-dup2")
    code, out, err = harness.run("dedup.py", "--manifest", path, "--project",
                                 testbed.path.name, "--plans-dir",
                                 str(testbed.corpus), "--brief",
                                 str(harness.scratch_path(testbed, "judge.md")),
                                 testbed=testbed)
    assert code == 1, (code, err)
    assert "candidate cluster" in out, out


def case_dedup_missing_manifest_flag_exits_two(testbed) -> None:
    code, _, _ = harness.run("dedup.py", "--project", testbed.path.name,
                             "--plans-dir", str(testbed.corpus), testbed=testbed)
    assert code == 2, code


def case_dedup_non_numeric_threshold_exits_two(testbed) -> None:
    path = _manifest(testbed, "dedup_threshold.json", "tb-ind1")
    code, _, _ = harness.run("dedup.py", "--manifest", path, "--project",
                             testbed.path.name, "--plans-dir",
                             str(testbed.corpus), "--threshold", "high",
                             testbed=testbed)
    assert code == 2, code


def case_dedup_unknown_argument_exits_two(testbed) -> None:
    path = _manifest(testbed, "dedup_unknown.json", "tb-ind1")
    code, _, _ = harness.run("dedup.py", "--manifest", path, "--project",
                             testbed.path.name, "--plans-dir",
                             str(testbed.corpus), "--wat", "1", testbed=testbed)
    assert code == 2, code


# --- lint_investigation.py ---------------------------------------------------


def case_lint_investigation_clean_artifact_exits_zero(testbed) -> None:
    code, _, err = harness.run(
        "lint_investigation.py", _fixture("investigation_ok"),
        "--root", _fixture("investigation_ok"), "--repo", str(testbed.path),
        "--no-tree-check", testbed=testbed)
    assert code == 0, (code, err)


def case_lint_investigation_defective_artifact_exits_one(testbed) -> None:
    code, out, _ = harness.run(
        "lint_investigation.py", _fixture("investigation_bad"),
        "--root", _fixture("investigation_bad"), "--repo", str(testbed.path),
        "--no-tree-check", testbed=testbed)
    assert code == 1, code
    assert "section-missing" in out and "assumption-language" in out, out


def case_lint_investigation_missing_path_exits_two(testbed) -> None:
    code, _, _ = harness.run("lint_investigation.py", _fixture("no_such_dir"),
                             testbed=testbed)
    assert code == 2, code


# --- lint_plan.py ------------------------------------------------------------


def case_lint_plan_clean_folder_exits_zero(testbed) -> None:
    code, _, err = harness.run(
        "lint_plan.py", _fixture("plan_ok", "triage-testbed_feat_config_override"),
        "--project-root", str(testbed.path), testbed=testbed)
    assert code == 0, (code, err)


def case_lint_plan_defective_folder_exits_one(testbed) -> None:
    code, out, _ = harness.run(
        "lint_plan.py",
        _fixture("plan_bad", "triage-testbed_feat_broken_verification"),
        "--project-root", str(testbed.path), testbed=testbed)
    assert code == 1, code
    assert "verification" in out, out


def case_lint_plan_missing_path_exits_two(testbed) -> None:
    code, _, _ = harness.run("lint_plan.py", _fixture("no_such_plan"),
                             testbed=testbed)
    assert code == 2, code


# --- validate_verdict.py -----------------------------------------------------


def case_validate_verdict_valid_exits_zero(testbed) -> None:
    code, _, err = harness.run("validate_verdict.py", _fixture("verdict_valid.json"),
                               testbed=testbed)
    assert code == 0, (code, err)


def case_validate_verdict_invalid_exits_one(testbed) -> None:
    code, _, err = harness.run("validate_verdict.py",
                               _fixture("verdict_invalid.json"), testbed=testbed)
    assert code == 1, code
    assert "empty defects array" in err, err


def case_validate_verdict_no_argument_exits_two(testbed) -> None:
    code, _, _ = harness.run("validate_verdict.py", testbed=testbed)
    assert code == 2, code


def case_validate_verdict_history_wrong_arity_exits_two(testbed) -> None:
    code, _, _ = harness.run("validate_verdict.py", "--history", testbed=testbed)
    assert code == 2, code


# --- promote.py (0 and 1 belong to Phase 3) ----------------------------------


def case_promote_run_id_matches_zero_runs_exits_two(testbed) -> None:
    runs = harness.scratch_path(testbed, "runs_empty")
    runs.mkdir(parents=True, exist_ok=True)
    code, _, err = harness.run("promote.py", "--run-id", "nosuchrun",
                               "--runs-dir", str(runs),
                               "--plans-dir", str(harness.scratch_path(testbed, "plans")),
                               "--repo-root", str(testbed.path),
                               "--system-plan-dir", str(harness.scratch_path(testbed, "system_plans")),
                               testbed=testbed)
    assert code == 2, (code, err)


def case_promote_run_id_matches_multiple_runs_exits_two(testbed) -> None:
    runs = harness.scratch_path(testbed, "runs_ambiguous")
    for name in ("2026-08-29_a_dup", "2026-08-29_b_dup"):
        (runs / name).mkdir(parents=True, exist_ok=True)
    code, _, err = harness.run("promote.py", "--run-id", "dup",
                               "--runs-dir", str(runs),
                               "--plans-dir", str(harness.scratch_path(testbed, "plans")),
                               "--repo-root", str(testbed.path),
                               "--system-plan-dir", str(harness.scratch_path(testbed, "system_plans")),
                               testbed=testbed)
    assert code == 2, (code, err)
    assert "matches 2 runs" in err, err


# --- collide.py --------------------------------------------------------------


def case_collide_no_merge_no_duplicate_exits_zero(testbed) -> None:
    path = _manifest(testbed, "collide_clean.json", "tb-ind1")
    code, _, err = harness.run(
        "collide.py", "--manifest", path, "--footprints", _fixture("footprints.json"),
        "--report", str(harness.scratch_path(testbed, "collide_clean.md")),
        testbed=testbed)
    assert code == 0, (code, err)


def case_collide_merge_or_unclassified_exits_one(testbed) -> None:
    path = _manifest(testbed, "collide_merge.json", "tb-col1", "tb-col2")
    code, out, _ = harness.run(
        "collide.py", "--manifest", path,
        "--footprints", _fixture("footprints_merge.json"),
        "--report", str(harness.scratch_path(testbed, "collide_merge.md")),
        testbed=testbed)
    assert code == 1, code
    assert "merge=1" in out, out


def case_collide_missing_manifest_exits_two(testbed) -> None:
    code, _, _ = harness.run("collide.py", "--footprints",
                             _fixture("footprints.json"), testbed=testbed)
    assert code == 2, code


# --- the four brief generators ----------------------------------------------


def case_brief_invest_wrong_arity_exits_two(testbed) -> None:
    code, _, _ = harness.run("brief_invest.sh", "tb-pln1", testbed=testbed)
    assert code == 2, code


def case_brief_plan_wrong_arity_exits_two(testbed) -> None:
    code, _, _ = harness.run("brief_plan.sh", "tb-pln1", testbed=testbed)
    assert code == 2, code


def case_brief_qc_wrong_arity_exits_two(testbed) -> None:
    code, _, _ = harness.run("brief_qc.sh", "artifact.md", testbed=testbed)
    assert code == 2, code


def case_brief_judge_wrong_arity_exits_two(testbed) -> None:
    code, _, _ = harness.run("brief_judge.sh", testbed=testbed)
    assert code == 2, code


def case_brief_invest_correct_arity_exits_zero(testbed) -> None:
    args = _brief_args(testbed)["brief_invest.sh"]
    code, out, err = harness.run("brief_invest.sh", *args, testbed=testbed)
    assert code == 0, (code, err)
    assert "tb-pln1" in out, out


def case_brief_plan_correct_arity_exits_zero(testbed) -> None:
    args = _brief_args(testbed)["brief_plan.sh"]
    code, _, err = harness.run("brief_plan.sh", *args, testbed=testbed)
    assert code == 0, (code, err)


def case_brief_qc_correct_arity_exits_zero(testbed) -> None:
    args = _brief_args(testbed)["brief_qc.sh"]
    code, _, err = harness.run("brief_qc.sh", *args, testbed=testbed)
    assert code == 0, (code, err)


def case_brief_judge_correct_arity_exits_zero(testbed) -> None:
    args = _brief_args(testbed)["brief_judge.sh"]
    code, _, err = harness.run("brief_judge.sh", *args, testbed=testbed)
    assert code == 0, (code, err)


def case_all_brief_generators_take_repo_root_last(testbed) -> None:
    """The orchestrator dispatches all four the same way; a generator that
    moved the repo root would be caught by nothing else."""
    for script in _brief_args(testbed):
        _, _, err = harness.run(script, "only-one-argument", testbed=testbed)
        usage = next((l for l in err.splitlines() if l.startswith("usage:")), "")
        assert usage.split()[-1] == "<repo-root>", (script, err)


def case_no_brief_generator_prints_the_contract_token(testbed) -> None:
    """A brief that hands the worker the token turns a proof of reading into a
    copy-paste. The omission is a contract, not an oversight."""
    for script, args in _brief_args(testbed).items():
        code, out, err = harness.run(script, *args, testbed=testbed)
        assert code == 0, (script, code, err)
        found = CONTRACT_TOKEN.search(out)
        assert not found, (script, found.group(0) if found else "")


CASES = [v for k, v in sorted(globals().items()) if k.startswith("case_")]
