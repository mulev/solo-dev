#!/usr/bin/env python3
"""Bracket one live worker so the only thing it can change is its own run.

This is the assertion Phase 5 exists to make, and it is the reason the phase
spends agents at all. Every agent the epic used before this one was read-only
by construction; a worker running `investigate` or `plan` has write tools and a
brief, and the brief is the only thing between it and the user's real backlog.

`oracles.artifact_is_inside` cannot make it: that one inspects the paths a
worker *reported*, so a worker that writes a file it never mentions passes it.
A wider window cannot make it either. A filesystem before/after says a write
landed somewhere inside the window and nothing about who left it, so a bracket
around a whole run — minutes wide, over `project_plans` and `~/.claude/plans`,
which the operator writes to continuously — reports a neighbouring session in
the words it would use for a leak. This bracket is one dispatch wide, and it
holds exactly one writer.

So it is taken immediately before the process and immediately after it, with
nothing in between, over three things, and each tracker is read **once** per
sample point, with the hash that decides whether anything moved and the facts
that name what did coming out of that one read:

* every guarded tree `suite_invariant` declares, via `sample_guarded_trees` —
  the testbed, `~/.claude/plans`, `project_plans`, demo and plugin;
* the **skills repo's** tracker and worktree, because that is where the sandbox
  lives: a `bd create` run without `-C` walks up into the real tracker, and
  that write appears in none of the trees above;
* a path-to-hash map of the whole plan corpus, where the only permitted delta
  is inside the run directory the orchestrator assigned.

Which is also why workers run one at a time. The bracket is only sound while
nothing else touches those trees between its two samples.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import harness
import oracles
import suite_invariant

sys.path.insert(0, str(harness.SCRIPTS))

import staged_run  # noqa: E402

# A worker that has not answered in this long is not going to. Generous rather
# than tight: a real investigation reads a skill, a contract and a source tree
# before it writes anything, and a timeout that fired on a slow-but-working run
# would be indistinguishable from the failure it is meant to catch.
TIMEOUT = int(os.environ.get("TRIAGE_E2E_WORKER_TIMEOUT", "1800"))
MODEL = os.environ.get("TRIAGE_E2E_MODEL", "")

# One agent driving the whole skill is not one worker, and capping it like one
# is what killed a run that was working: it reached Wave 4, had two plans on
# disk and a third in flight, and was cut off at 1800s with everything still to
# do. A sweep is six waves and every worker they dispatch, in sequence — the
# cap has to be a sweep's, not a worker's.
SWEEP_TIMEOUT = int(os.environ.get("TRIAGE_E2E_SWEEP_TIMEOUT", "7200"))


# The guarded trees a live worker is refused on rather than merely watched on,
# named the way `suite_invariant` names them so a rename there arrives as a
# failure instead of as an empty deny list.
#
# Every guarded tree except the testbed, which is the one the worker is
# supposed to write in. The two plan trees are the leak this epic was filed
# for; any external repo on the roster is there because `suite_invariant`
# calls those the blast radius and a dispatched worker has no business in one.
#
# Not because the bracket misses them — it does not, `sample_guarded_trees`
# samples every watched tree on every dispatch. Because a deny rule and a
# bracket are different things: the rule refuses the write, the bracket
# reports it after the fact. Watching a tree you can simply make unreachable
# is a worse boundary for the same money.
#
# Derived rather than restated, and computed per call rather than at import:
# a tree added to the roster and forgotten here would ship as
# watched-but-reachable, and the roster's external half is configuration that
# a caller may set after this module loads.
def denied_trees() -> tuple:
    return tuple(tree.name for tree in suite_invariant.guarded_trees()
                 if tree.name != "testbed")


def permission_settings(names: tuple = None) -> str:
    """The `--settings` blob one dispatched worker runs under.

    `dispatch` passes no `env=`, so the session inherits this machine's real
    `HOME` — which is how it finds its credentials, and also how it picks up
    `~/.claude/settings.json`'s `"defaultMode": "auto"` and an
    `additionalDirectories` list that already grants `~/.claude/plans`. A
    classifier-approved worker holding the operator's real plan mirror as a
    working directory is not a path-bounded one, so the boundary is stated
    here instead of assumed.

    What deny covers, per https://code.claude.com/docs/en/permissions: these
    rules are "enforced by Claude Code, not by the model", so a brief that
    asks nicely is not a boundary and this is. Evaluation is deny, then ask,
    then allow, first match deciding — a deny cannot be reopened by an allow
    further down and cannot carry exceptions. `Edit(...)` is the rule name
    every file-modifying built-in is checked against; a path rule written for
    `Write`, `NotebookEdit` or `MultiEdit` is accepted, never consulted, and
    warned about at startup. `Read(...)` is written too: it blocks Edit and
    Write on the same path and keeps the operator's real backlog out of the
    worker's context, but it does not cover NotebookEdit, which is why both
    names appear for every path. Redirection targets (`>`, `>>`, `2>`) are
    checked as file writes against the Edit rules, so a shell redirect into a
    denied tree is refused as well. `//` and not `/`: a single leading slash
    anchors at the settings source, not the filesystem root.

    What it does not cover: a subprocess that opens a file itself. The same
    page says so outright — Read and Edit deny rules "don't apply to
    arbitrary subprocesses that read or write files indirectly, like a Python
    or Node script that opens files itself" — and `python3 -c 'open(p, "w")'`
    matches no path rule. There is no Bash rule worth writing for it either:
    Bash patterns that try to constrain command arguments are documented as
    fragile. **The per-worker bracket in `dispatch` below is the backstop for
    that residual, and it is the only thing that catches it.**

    Closing it properly needs an OS boundary — Claude Code's own sandbox
    (https://code.claude.com/docs/en/sandboxing), or a hand-rolled
    `sandbox-exec` deny-write profile. Considered and rejected at this epic's
    fix gate, 2026-09-04, by the epic's approver: on macOS both routes buy a
    platform-specific dependency on an Apple-deprecated facility, for a
    residual the bracket already reports by name. Revisit the day the bracket
    actually catches a `python3 -c` write.

    `defaultMode` is stated rather than inherited. Measured on the installed
    CLI, 2026-09-04: a `--settings` naming only `permissions.deny` left the
    user file's `"defaultMode": "auto"` in force — a probe session's allowed
    write landed with no prompt while its denied write came back in
    `permission_denials` — so the override reaches inside the `permissions`
    object rather than replacing it. Stated anyway, because that is one CLI
    version's behaviour and a worker that silently fell back to Manual mode
    under `-p` would have every tool call denied and fail for a reason that
    looks nothing like this.
    """
    trees = {tree.name: tree.path for tree in suite_invariant.guarded_trees()}
    rules = []
    for name in denied_trees() if names is None else names:
        path = trees.get(name)
        assert path is not None, (
            f"no guarded tree named {name!r}: the deny list would be short a "
            f"tree, which is a guard that silently stopped guarding")
        text = str(path)
        assert not set("*?[]") & set(text), (
            f"{text} carries a gitignore metacharacter, so the rule would "
            f"match a pattern rather than its own path")
        anchored = text.lstrip("/")
        rules += [f"Read(//{anchored}/**)", f"Edit(//{anchored}/**)"]
    return json.dumps({"permissions": {"deny": rules,
                                       "defaultMode": "auto"}})


def sample_guarded_trees(testbed) -> dict:
    """Every guarded tree a worker must leave alone, sampled once each.

    One pass per tree, so a tree's tripwire and its adjudicator describe one
    moment. Hashing every root and then reading their facts left a window the
    width of a `content_map` of the corpus: a `bd` write landing inside it was
    in the facts and not in the hash, so `dispatch` saw the hash move, found
    nothing to name, and filed the write as `noise/` (`skills-rjb`).

    `root=testbed.root` is load-bearing: under `--root DIR` the testbed is
    built under `DIR`, and resolving it from a constant fingerprints a
    directory this run never touched — passing while guarding nothing
    (`skills-yc7`).

    The skills repo is added by hand, and that hand-add is the precedent this
    composition generalises rather than an exception to it. It is where the
    sandbox lives — a `bd create` without `-C` walks up into the real tracker
    — and it is not a tree `guarded_trees` can list, because the run builds
    the testbed inside it: stable across one worker's window, never across a
    run. What used to be one tree plus that hand-add is now every guarded tree
    plus the same hand-add.

    `--skip-external` is not plumbed in and must not be: `sample` is called
    with its default, and an absent external repo reads `ABSENT` on both sides of a
    bracket, so `compare` never fires on it.

    The measured cost, per dispatch rather than concurrent — workers run one
    at a time: two walks of `project_plans` (1091 hashed files after the
    `.git/` exclusion) and two of `~/.claude/plans`, plus two `git status` and
    two `bd list` against each of the testbed, demo, plugin and the
    skills repo.

    The facts adjudicate a fire rather than decide it, and that is measured:
    one worker window reported the skills repo's fingerprint moving while `git
    status` was byte-identical either side of it and no bead's `updated_at`
    fell inside it; forty back-to-back samples under concurrent `bd` load
    never reproduced it. The hash moved and nothing guarded did.
    """
    out = suite_invariant.sample(root=testbed.root)
    out["skills-repo"] = suite_invariant.sample_tracker(harness.SKILLS_ROOT)
    return out


def strayed(before: dict, after: dict, run, corpus) -> list:
    """Corpus paths a worker changed that sit outside its own run directory."""
    moved = [name for name in set(before) | set(after)
             if before.get(name) != after.get(name)]
    return sorted(name for name in moved
                  if not oracles.artifact_is_inside(run, Path(corpus) / name))


def dispatch(testbed, run: Path, name: str, brief: str, target: str,
             permit: Path | None = None, timeout: int | None = None) -> str:
    """Spend one worker on `brief` + `target`, and return its report text.

    `permit` widens the bracket to a directory tree, for the one caller that
    cannot name the run directory in advance: an agent driving the whole skill
    chooses its own, so the tightest thing knowable before dispatch is the
    staging root. That caller then asserts the tighter condition afterwards —
    everything landed inside the single run the agent created. Every other
    caller assigns the path itself and leaves this alone.

    A real session in its own process, reading the generated brief as its
    prompt, under the permission floor `permission_settings` states. The
    working directory is the testbed repo, which has its own `.git` and
    `.beads`, so even a bare `bd` resolves inside the sandbox instead of
    walking up to the skills repo's tracker.

    Both the dispatch and the return reach the ledger before the result is used
    — SKILL.md's wave discipline — so a failed suite is readable after the fact
    instead of needing a re-run to diagnose.
    """
    staged_run.record_step(run, f"dispatch/{name}", "live worker")
    allowed = permit or run
    limit = timeout or TIMEOUT
    before = sample_guarded_trees(testbed)
    before_files = suite_invariant.content_map(testbed.corpus)

    cmd = ["claude", "-p", f"{brief}\n\n# Target\n\n{target}",
           "--output-format", "json",
           "--settings", permission_settings(),
           "--add-dir", str(testbed.corpus), "--add-dir", str(harness.SKILLS_ROOT)]
    if MODEL:
        cmd += ["--model", MODEL]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              cwd=str(testbed.path), timeout=limit)
    except subprocess.TimeoutExpired:
        staged_run.record_step(run, f"return/{name}", f"timeout after {limit}s")
        raise AssertionError(f"{name}: no answer within {limit}s")

    if proc.returncode != 0:
        # Both streams, because the interesting failures put nothing on stderr:
        # a usage limit, an auth prompt and a refused tool all come back as a
        # non-zero exit with the reason on stdout. A message that showed only
        # stderr reported an empty string and sent the reader looking in the
        # wrong place.
        staged_run.record_step(run, f"return/{name}",
                               f"exit {proc.returncode}")
        raise AssertionError(
            f"{name}: claude exited {proc.returncode}\n"
            f"stderr: {proc.stderr[-600:] or '(empty)'}\n"
            f"stdout: {proc.stdout[-600:] or '(empty)'}")
    payload = json.loads(proc.stdout)
    staged_run.record_step(run, f"return/{name}",
                           f"${payload.get('total_cost_usd', 0):.2f}, "
                           f"{payload.get('num_turns', 0)} turns")

    after = sample_guarded_trees(testbed)
    moved = suite_invariant.compare(suite_invariant.fingerprints(before),
                                    suite_invariant.fingerprints(after))
    if moved:
        # The tripwire fired; the facts decide. Both halves came out of one
        # read, so a write cannot be in one and missing from the other. This
        # can forgive noise in the hashed command output and can never forgive
        # a leak. Never silent — the ledger names what moved.
        delta = [line for tree in sorted(before)
                 for line in suite_invariant.delta_lines(
                     tree, before[tree].detail, after[tree].detail)]
        assert not delta, f"{name} changed a guarded tree: {delta}"
        staged_run.record_step(
            run, f"noise/{name}",
            f"tripwire fired, no tracked file and no bead changed: "
            f"{[line.split(':')[0] for line in moved]}")
    after_files = suite_invariant.content_map(testbed.corpus)
    outside = strayed(before_files, after_files, allowed, testbed.corpus)
    assert not outside, f"{name} wrote outside its own run directory: {outside}"
    return payload.get("result") or ""
