"""Assert how Wave 5 routes a verdict: which tier runs, whether a reviewer is
spawned at all, and what the convergence policy decides.

Wave 5 is orchestrator prose, not a callable. `_qc_round` below is that prose
made executable — tier 1 as a real subprocess, tier 2 as an injected stub, and
`validate_verdict` for both the schema check and the routing decision. What is
under test is the routing, so the verdicts are fixtures and the reviewer never
exists: see the README's "Why verdicts are fixtures here". A live reviewer
belongs to Suite C, where a red run means an agent misbehaved rather than a
router regressed.

The reviewer stub is the instrument. It counts its own calls, so "tier 2 never
ran" is asserted rather than assumed, and it raises when a case asks it for a
verdict the case never queued — a router that spent an unplanned round fails
loudly instead of reading a fixture off the end of a list.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import harness

sys.path.insert(0, str(harness.SCRIPTS))

import validate_verdict  # noqa: E402

VERDICTS = harness.FIXTURES / "artifacts" / "verdicts"
INVEST_OK = harness.FIXTURES / "investigation_ok"
INVEST_BAD = harness.FIXTURES / "investigation_bad"
PLAN_OK = harness.FIXTURES / "plan_ok" / "triage-testbed_feat_config_override"
PLAN_BAD = harness.FIXTURES / "plan_bad" / "triage-testbed_feat_broken_verification"


def _load(name: str) -> dict:
    return json.loads((VERDICTS / name).read_text(encoding="utf-8"))


class Reviewer:
    """A tier-2 stub. `calls` is what proves tier 2 ran, or did not."""

    def __init__(self, *names: str):
        self.queue = [_load(name) for name in names]
        self.calls = 0

    def __call__(self) -> dict:
        if self.calls >= len(self.queue):
            raise AssertionError(
                f"the router spent round {self.calls + 1}; the case queued "
                f"{len(self.queue)}")
        verdict = self.queue[self.calls]
        self.calls += 1
        return verdict


def _lint(testbed, artifact: Path, kind: str) -> int:
    """Tier 1, as the real command line. `--repo`/`--project-root` name the
    testbed explicitly, the way SKILL.md Wave 5 step 1 requires: derived from a
    staging path they would resolve to the wrong tree."""
    if kind == "investigation":
        code, _, _ = harness.run(
            "lint_investigation.py", str(artifact), "--root", str(artifact),
            "--repo", str(testbed.path), "--no-tree-check", testbed=testbed)
    else:
        code, _, _ = harness.run("lint_plan.py", str(artifact),
                                 "--project-root", str(testbed.path),
                                 testbed=testbed)
    return code


def _qc_round(testbed, artifact: Path, kind: str, reviewer, history=None):
    """One full Wave 5 pass: tier 1, then tier 2 only on a tier-1 pass.

    Returns `(action, history)`. `action` is `next_action`'s verdict, or
    `tier1-fail` when the linter rejected the artifact, or `invalid` when the
    reviewer's object did not match the schema. Neither of those two reaches
    `next_action`: an unvalidated verdict appended to the history would poison
    every later round's convergence comparison.
    """
    history = list(history or [])
    if _lint(testbed, artifact, kind) != 0:
        return "tier1-fail", history
    verdict = reviewer()
    if validate_verdict.validate(verdict):
        return "invalid", history
    history.append(verdict)
    return validate_verdict.next_action(history), history


# --- tier 1 gates tier 2 -----------------------------------------------------


def case_tier1_failure_never_spawns_a_reviewer(testbed) -> None:
    reviewer = Reviewer("pass.json")
    action, history = _qc_round(testbed, INVEST_BAD, "investigation", reviewer)
    assert action == "tier1-fail", action
    assert reviewer.calls == 0, "a reviewer was spent on a tier-1 failure"
    assert history == [], history


def case_tier1_pass_dispatches_the_reviewer_once(testbed) -> None:
    reviewer = Reviewer("pass.json")
    action, history = _qc_round(testbed, INVEST_OK, "investigation", reviewer)
    assert action == "PASS", action
    assert reviewer.calls == 1, reviewer.calls
    assert len(history) == 1 and history[0]["verdict"] == "PASS", history


def case_plan_kind_is_gated_by_the_plan_linter(testbed) -> None:
    """`kind` picks the tier-1 command, and picking the wrong one would pass a
    broken plan through to a reviewer."""
    ok = Reviewer("pass.json")
    assert _qc_round(testbed, PLAN_OK, "plan", ok)[0] == "PASS"
    bad = Reviewer("pass.json")
    action, _ = _qc_round(testbed, PLAN_BAD, "plan", bad)
    assert action == "tier1-fail", action
    assert bad.calls == 0, bad.calls


# --- the verdict is validated before it is routed ----------------------------


def case_invalid_verdict_is_rejected_before_routing(testbed) -> None:
    """A verdict that fails the schema must not enter the round history:
    `next_action` would then compare locations against an object nobody
    checked, and the convergence rule is a set comparison over exactly those
    locations."""
    reviewer = Reviewer("invalid_missing_confidence.json")
    action, history = _qc_round(testbed, INVEST_OK, "investigation", reviewer)
    assert action == "invalid", action
    assert history == [], history
    assert validate_verdict.validate(_load("invalid_missing_confidence.json"))


# --- the revision policy -----------------------------------------------------


def case_round_one_revise_sends_it_back(testbed) -> None:
    reviewer = Reviewer("revise_round1.json")
    action, history = _qc_round(testbed, INVEST_OK, "investigation", reviewer)
    assert action == "REVISE", action
    assert len(history) == 1, history


def case_converged_round_two_unlocks_a_third_round(testbed) -> None:
    """qc-gates.md §3.3 — round 2 a strict subset of round 1 buys round 3."""
    reviewer = Reviewer("revise_round1.json", "revise_round2_converged.json")
    action, history = _qc_round(testbed, INVEST_OK, "investigation", reviewer)
    assert action == "REVISE", action
    action, history = _qc_round(testbed, INVEST_OK, "investigation", reviewer,
                                history)
    assert action == "REVISE", action
    assert len(history) == 2, history
    assert reviewer.calls == 2, reviewer.calls


def case_restated_round_two_parks(testbed) -> None:
    """Equal location sets are the same defect restated, not convergence."""
    history = [_load("revise_round1.json"), _load("revise_round2_restated.json")]
    assert validate_verdict.next_action(history) == "PARK"


def case_diverged_round_two_parks(testbed) -> None:
    """A location round 1 never named ends the loop even though the count fell."""
    history = [_load("revise_round1.json"), _load("park_round2_diverged.json")]
    assert validate_verdict.next_action(history) == "PARK"


def case_hard_class_parks_without_spending_a_second_round(testbed) -> None:
    """A hard class costs one round, never two — the reviewer queue holds a
    second verdict precisely so a router that asks for it fails."""
    reviewer = Reviewer("park_root_cause_unproven.json", "pass.json")
    action, history = _qc_round(testbed, INVEST_OK, "investigation", reviewer)
    assert action == "PARK", action
    assert reviewer.calls == 1, reviewer.calls
    assert len(history) == 1, history


def case_park_carries_a_question(testbed) -> None:
    """qc-gates.md §7 — a park whose `why` is a summary is a dropped bead."""
    verdict = _load("park_with_question.json")
    assert validate_verdict.next_action([verdict]) == "PARK"
    why = verdict["defects"][0]["why"].strip()
    assert why and why.endswith("?"), why


def _hard_class_case(defect_class: str):
    """One case per member of HARD_CLASSES, built the way `run_tests.py`
    builds its own list — a class added to the tuple gains a case for free."""
    name = defect_class.replace("-", "_")

    def case(testbed) -> None:
        history = [_load(f"park_{name}.json")]
        assert history[0]["defect_class"] == defect_class, history
        assert validate_verdict.next_action(history) == "PARK"

    case.__name__ = f"case_hard_defect_class_parks_on_round_one_{name}"
    case.__doc__ = f"qc-gates.md §4 — {defect_class} allows zero rounds."
    return case


for _cls in validate_verdict.HARD_CLASSES:
    _generated = _hard_class_case(_cls)
    globals()[_generated.__name__] = _generated

CASES = [v for k, v in sorted(globals().items()) if k.startswith("case_")]
