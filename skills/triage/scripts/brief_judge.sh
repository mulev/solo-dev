#!/bin/sh
# Print the Wave 1 duplicate judge's brief.
#
# The judge is the only Wave 1 worker, and it was the only worker without a
# generator: its prompt was improvised per run. On the first live demo run
# that improvisation happened to carry the rules that made the ruling
# trustworthy — read the code rather than the brief's prose, treat similarity
# as an input, rule `related-not-duplicate` when unsure. None of that was in
# the skill, so the next run got whatever the next orchestrator thought of.
#
# Usage:
#   brief_judge.sh <judge-brief-path> <repo-root>
#
# Environment:
#   WORKSPACE_AGENTS  path to the workspace-level AGENTS.md
#                     (default: <repo-root>/../AGENTS.md)
#
# Exit: 0 brief printed · 2 usage or configuration error.
set -u

usage() {
	echo "usage: brief_judge.sh <judge-brief-path> <repo-root>" >&2
	exit 2
}

[ $# -eq 2 ] || usage

JUDGE_BRIEF=$1
REPO=$2

REPO=$(cd "$REPO" && pwd) || exit 2

SKILLS_ROOT=$(cd "$(dirname "$0")/../.." && pwd) || exit 2
CONTRACT="$SKILLS_ROOT/_shared/autonomous-mode.md"
CHARTER="$SKILLS_ROOT/triage/references/autonomy-charter.md"
DOCTRINE="$SKILLS_ROOT/triage/references/deduplication.md"
[ -f "$CONTRACT" ] || {
	echo "brief_judge.sh: no contract at $CONTRACT" >&2
	exit 2
}

grep -qE 'Contract version: \*\*SW-[0-9]{4}-[0-9]{2}-v[0-9]+\*\*' "$CONTRACT" || {
	echo "brief_judge.sh: no contract version line in $CONTRACT" >&2
	exit 2
}

WORKSPACE_AGENTS=${WORKSPACE_AGENTS:-$(dirname "$REPO")/AGENTS.md}
REPO_AGENTS="$REPO/AGENTS.md"

cat <<BRIEF
# Read first (in this order, before any other tool call)

1. \`cat $JUDGE_BRIEF\` — the candidates and the covered beads. It is your whole input.
2. \`cat $DOCTRINE\` — why a table row is weak evidence and a \`Beads task:\` field is not.
3. \`cat $CONTRACT\` — the autonomous-mode contract.
4. \`cat $WORKSPACE_AGENTS\`
5. \`cat $REPO_AGENTS\`
6. The repository the beads are about: $REPO

# Constraints (decided by the main session — do NOT re-decide)

Judge brief: $JUDGE_BRIEF
Repo: $REPO

You are read-only. Do not write any file, do not run any \`bd\` command that mutates, do not edit source. Your ruling is your return value.
No commits, no pushes, no tracker writes, no locale edits.
The similarity score is an input, not an answer. Two beads that share a subsystem share vocabulary, and the mechanical stage cannot tell that from sharing a bug — which is exactly why the cluster reached you.
Read the code before ruling. The brief's descriptions are what their authors believed; $REPO is what is true. Where a ruling turns on whether two beads name the same place, open both places.
Beads fixed by one edit in one place are duplicates. Beads that each need their own edit, even in the same file, are not.

# Your ruling — a partition per cluster

Per cluster, put every member in exactly one group. Each group carries a verdict:

- \`duplicate\` — the same work. Name the representative, which must be one of that group's own members.
- \`distinct\` — different work that shares vocabulary or a subsystem.
- \`related-not-duplicate\` — genuinely connected, each still needing its own change. Say what the relationship is; it feeds collision grouping in Wave 3.

One group holding every member is the normal answer. Split only where the cluster genuinely splits — a cluster that is part duplicate and part not is the case the partition exists for.

**When unsure, rule \`related-not-duplicate\` and say what you could not settle.** A wrong \`duplicate\` silently deletes real work from the backlog and nobody reconstructs it; a wrong \`related-not-duplicate\` costs one extra plan. The errors are not symmetric.

# Your ruling — coverage

The brief's closing section lists beads an existing plan already cites. **Every bead listed there needs a line**, or it is investigated from scratch while a plan already covers that ground:

- \`covered\` — the plan really covers this bead's work. Name the plan. Open it first: the citation in the brief is a mention, not proof.
- \`not-covered\` — the citation is a mention, a de-scoped table row, or about something else. The bead is dispatched as if it had never been flagged.

# Escalation

You cannot ask the user. Send the question to the main session (\`SendMessage\` in Claude Code, \`hub\` send to \`Main\` in omp) with what you need and why, then stop that thread. Never guess, never shrink the ruling to dodge the question.

# PARK — recognise your own exit

Park, name the condition, and stop when any of these is true:

- The beads cannot be checked against this repository at all.
- Any STOP-LIST item in $CHARTER is touched.
- Your context budget is spent before you have read what a ruling turns on. A guessed verdict is worse than a park: it retires a bead nobody checked.

# Report (at most 15 lines, no diffs, no logs)

contract: the version token on the \`Contract version:\` line of $CONTRACT — look it up, do not guess
clusters: one line per group — cluster id, members, verdict, representative when duplicate
coverage: one line per flagged bead — id, covered with its plan, or not-covered
reasoning: the code or the difference that decided each ruling, two to four sentences per cluster
open questions
blockers
BRIEF
