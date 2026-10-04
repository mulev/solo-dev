#!/bin/sh
# Print the invariant part of a triage quality-control reviewer's brief.
#
# The orchestrator appends nothing per-bead here — the artifact under review is
# an argument. Everything this script prints is identical for every reviewer of
# every run, which is the point: hand-written briefs drift, generated ones do
# not. Precedent: execute/scripts/brief.sh.
#
# Usage:
#   brief_qc.sh <artifact-path> <kind> <round> <repo-root>
#
#   <kind> is `investigation` or `plan`; <round> is a positive integer.
#
# Environment:
#   WORKSPACE_AGENTS  path to the workspace-level AGENTS.md
#                     (default: <repo-root>/../AGENTS.md)
#
# Exit: 0 brief printed · 2 usage or configuration error.
set -u

usage() {
	echo "usage: brief_qc.sh <artifact-path> <kind> <round> <repo-root>" >&2
	exit 2
}

# `${1:?}` would be shorter, but its exit status is shell-dependent — bash exits
# 1, dash exits 2 — and this epic fixes 2 as the usage/configuration code.
[ $# -eq 4 ] || usage

ARTIFACT=$1
KIND=$2
ROUND=$3
REPO=$4

case "$KIND" in
	investigation | plan) ;;
	*)
		echo "brief_qc.sh: kind must be 'investigation' or 'plan', got '$KIND'" >&2
		exit 2
		;;
esac
case "$ROUND" in
	'' | *[!0-9]* | 0)
		echo "brief_qc.sh: round must be a positive integer, got '$ROUND'" >&2
		exit 2
		;;
esac

REPO=$(cd "$REPO" && pwd) || exit 2

SKILLS_ROOT=$(cd "$(dirname "$0")/../.." && pwd) || exit 2
CONTRACT="$SKILLS_ROOT/_shared/autonomous-mode.md"
CHARTER="$SKILLS_ROOT/triage/references/autonomy-charter.md"
# GATES is named in the brief but deliberately not checked for existence: the
# reviewer wave that consumes it ships later than this generator, and a missing
# file surfaces at the reviewer's first `cat`. The contract below is the one
# mandatory-existence check here.
GATES="$SKILLS_ROOT/triage/references/qc-gates.md"
[ -f "$CONTRACT" ] || {
	echo "brief_qc.sh: no contract at $CONTRACT" >&2
	exit 2
}

# The contract must carry a version token, but this script never prints it: a
# token handed to the reviewer proves it can copy a brief, not that it read the
# contract. The reviewer looks it up; the orchestrator compares what it echoes.
grep -qE 'Contract version: \*\*SW-[0-9]{4}-[0-9]{2}-v[0-9]+\*\*' "$CONTRACT" || {
	echo "brief_qc.sh: no contract version line in $CONTRACT" >&2
	exit 2
}

WORKSPACE_AGENTS=${WORKSPACE_AGENTS:-$(dirname "$REPO")/AGENTS.md}
REPO_AGENTS="$REPO/AGENTS.md"

cat <<BRIEF
# Read first (in this order, before any other tool call)

1. \`cat $GATES\` — the gate checklists for kind=$KIND and the verdict schema you must return.
2. \`cat $CONTRACT\` — the autonomous-mode contract.
3. \`cat $WORKSPACE_AGENTS\`
4. \`cat $REPO_AGENTS\`
5. The artifact under review: $ARTIFACT
6. The repository it makes claims about: $REPO — read whatever the artifact cites, and read it yourself.

# Constraints (decided by the main session — do NOT re-decide)

Artifact: $ARTIFACT
Kind: $KIND
Round: $ROUND
Repo: $REPO

You receive the artifact and the repository. You do NOT receive the producing worker's transcript, its reasoning or its report — deliberately. A reviewer who reads how a conclusion was reached grades the reasoning; your job is to grade the artifact against the code. Do not ask for the transcript; a request for it is itself a finding that the artifact is not self-contained.
Your job is to refute, not to agree. Open every claim with the intent of breaking it: every cited file:line, every symbol, every alternative the artifact says it ruled out. PASS is what is left when refutation failed — never a default, never a courtesy.
Tier 1 already passed: the mechanical linter ran before you. Missing sections and structural defects are its job, not yours — do not re-report them. Spend your pass on whether the content is true.
Write nothing. No files, no edits to the artifact. A reviewer that edits the artifact stops being independent; findings go in your verdict and the producing worker fixes them.
No commits, no pushes, no tracker commands, no locale edits.

# Escalation

You cannot ask the user. Send the question to the main session (\`SendMessage\` in Claude Code, \`hub\` send to \`Main\` in omp) with what you need and why, then stop that thread. Never guess, never narrow the review to dodge the question.

# Verdict — the gate answer

This verdict is what answers the gate the producing worker is stopped at. Return it in the schema in \`qc-gates.md\`, exactly: a verdict that fails schema validation is sent back and the round is wasted. Echo round $ROUND in it. Every finding names a file and a line or a quoted claim — a finding a worker cannot act on is not a finding.

# Round $ROUND

This is round $ROUND for this artifact. The revision and convergence policy in \`qc-gates.md\` decides what happens when a round fails; applying it is the orchestrator's call, not yours. Never soften a finding because the artifact has already been revised once, and never manufacture one because it has not.

# PARK — recognise your own exit

Park the review, name the condition in your report, and stop when any of these is true. The first four are the contract's own list, restated so you can recognise your exit without re-reading it mid-flight:

- **Requirements are underdetermined** by the bead, the investigation, and the code taken together. This is \`plan\` Step 2 with nobody to ask, and inventing requirements is prohibited.
- **The tracker is unconfigured** (\`plan\` Step 8a).
- **Any STOP-LIST item** in $CHARTER is touched.
- **Your context budget is spent before the cause is proven.** A thinner answer is not an acceptable substitute for a proven one, and \`investigate\`'s evidence-only rule does not relax because you are running low.
- the artifact's claims cannot be checked against this repository at all — say so instead of guessing a verdict.

Parking is a correct outcome and costs one reviewer. Inventing a verdict is a failed assignment, and it is worse than a park: it approves a gate nobody actually checked.

# Report (at most 15 lines, no diffs, no logs)

contract: the version token on the \`Contract version:\` line of $CONTRACT — look it up, do not guess
artifact: $ARTIFACT
kind: $KIND
round: $ROUND
verdict: the schema value
findings: one line each, file:line or quoted claim first
what you tried to refute and could not
open questions
blockers
BRIEF
