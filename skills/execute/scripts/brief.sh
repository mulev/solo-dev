#!/bin/sh
# Print the invariant part of an epic worker's brief.
#
# The main session appends the phase-specific `# Target`, `# Change` and
# `# Acceptance` sections and dispatches the result. Everything this script
# prints is identical for every worker of every epic, which is the point:
# hand-written briefs drift, generated ones do not.
#
# Usage:
#   brief.sh <bead-id> <slice-path> <branch> [repo-root]
#
# Environment:
#   TRACKER_CLI       issue-tracker CLI name from skill.config.md (default: bd).
#                     Set to empty when the repo has no tracker — the tracker
#                     lines are then omitted entirely.
#   WORKSPACE_AGENTS  path to an instruction file above the repo, for a workspace
#                     holding several repos side by side. Defaults to
#                     <repo-root>/../AGENTS.md and is omitted when absent, so a
#                     standalone repo needs no setting.
#   NO_COMMIT=1       tell the worker it may not commit
set -u

BEAD=${1:?usage: brief.sh <bead-id> <slice-path> <branch> [repo-root]}
SLICE=${2:?slice path required}
BRANCH=${3:?branch required}
REPO=${4:-$(pwd)}
REPO=$(cd "$REPO" && pwd) || exit 2

SKILL_DIR=$(cd "$(dirname "$0")/.." && pwd)
SKILL_MD="$SKILL_DIR/SKILL.md"
[ -f "$SKILL_MD" ] || {
	echo "brief.sh: no SKILL.md at $SKILL_MD" >&2
	exit 2
}

# The skill must carry a contract version, but this script never prints it: a token
# handed to the worker proves it can copy a brief, not that it read the contract.
# The worker looks it up; the main session compares it against the skill.
grep -qE 'Contract version: \*\*DM-[0-9]{4}-[0-9]{2}-v[0-9]+\*\*' "$SKILL_MD" || {
	echo "brief.sh: no contract version line in $SKILL_MD" >&2
	exit 2
}

TRACKER_CLI=${TRACKER_CLI-bd}
WORKSPACE_AGENTS=${WORKSPACE_AGENTS:-$(dirname "$REPO")/AGENTS.md}
REPO_AGENTS="$REPO/AGENTS.md"

# A brief that tells a worker to `cat` a file that does not exist teaches it that
# the brief is unreliable. Number only the files actually on disk.
n=1
read_list=$(printf '%d. `cat %s` — the execute skill. Follow its `<delegated-mode>` block end to end. Skip the `cat` only if this skill is already in your context (some harnesses preload it) — never skip reading it.\n' "$n" "$SKILL_MD")
for f in "$WORKSPACE_AGENTS" "$REPO_AGENTS"; do
	[ -f "$f" ] || continue
	n=$((n + 1))
	read_list=$(printf '%s\n%d. `cat %s`' "$read_list" "$n" "$f")
done
read_list=$(printf '%s\n%d. Your working file: %s' "$read_list" "$((n + 1))" "$SLICE")

if [ -n "$TRACKER_CLI" ]; then
	tracker_line=$(printf 'Tracker: `%s` cwd does not persist between your shell calls — pass `-C %s` on every `%s` command.' \
		"$TRACKER_CLI" "$REPO" "$TRACKER_CLI")
	no_push="Never push, never \`$TRACKER_CLI\` remote-sync commands."
else
	tracker_line='Tracker: none for this repo. The slice file is the only state you update.'
	no_push='Never push.'
fi

phase_rows=$(cd "$REPO" && ./validate list phase-exit 2>/dev/null) || phase_rows=''
user_rows=$(cd "$REPO" && ./validate list user 2>/dev/null) || user_rows=''

if [ -n "$phase_rows" ]; then
	phase_block=$(printf '%s\n' "$phase_rows" | sed 's/^/  /')
else
	phase_block='  (no phase-exit rows — repo has no validators.conf; record
  `validators: none — <reason>` in the ledger and say so in your report)'
fi

if [ "${NO_COMMIT:-0}" = 1 ]; then
	commit_line='Commit permission: NONE. Leave your work staged-free and uncommitted; main commits.'
else
	commit_line="Commit permission: GRANTED for your own bead files only. Stage explicit paths — never \`git add -A\`, never \`git commit -a\`. $no_push"
fi

cat <<BRIEF
# Read first (in this order, before any other tool call)

$read_list

# Constraints (decided by the main session — do NOT re-decide)

Bead: $BEAD
Repo: $REPO
Branch: \`$BRANCH\` — already checked out. Verify you are on it. Never switch, never create, never touch \`main\`.
$commit_line
$tracker_line
Escalation: you cannot ask the user. Send the question to the main session and stop that thread. Never guess, never shrink the bead to avoid asking.

# Validation — mandatory, not a judgement call

When the slice's work is done, run from $REPO:

  ./validate run phase-exit

That stage is:

$phase_block

Any FAIL opens a Bug Round or Refactoring Round (Step 4), you fix it, and you re-run the whole stage. You may only report when every row is PASS. After three failed rounds, stop and escalate with the failing ledger.

Paste the runner's output verbatim — provenance header line included — into $SLICE as a fenced block under \`### Validation\`, inside this phase's \`## Architecture Gate Results\` block, then confirm with:

  ./validate verify phase-exit $SLICE

Run the stage after your last edit, not before: verification fails a ledger that
predates a source file's mtime, which is exactly how a fix applied after the run
gets caught. A \`DRIFT\` line is not a failure — it means the stage gained a row
after some earlier ledger was written.
$(if [ -n "$user_rows" ]; then
	printf '\nHanded to the user, never run by you:\n\n'
	printf '%s\n' "$user_rows" | sed 's/^/  /'
fi)

# Report (at most 15 lines, no diffs, no logs)

contract: the version token named on the \`Contract version:\` line of \`<delegated-mode>\` — look it up, do not guess
files created / modified
tests + validation: the ledger lines, and whether \`verify\` exited 0
architecture gate: the Overall line
bead: id + status + commit shas
deferred: every check you did not run, with who owns it
locale keys needing translation
open questions
blockers
BRIEF
