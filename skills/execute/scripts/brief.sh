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
#   WORKSPACE_AGENTS  path to the workspace-level AGENTS.md
#                     (default: <repo-root>/../AGENTS.md)
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

WORKSPACE_AGENTS=${WORKSPACE_AGENTS:-$(dirname "$REPO")/AGENTS.md}
REPO_AGENTS="$REPO/AGENTS.md"

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
	commit_line='Commit permission: GRANTED for your own bead files only. Stage explicit paths — your source files and `ledger` — never `git add -A`, never `git commit -a`. Never push, never `bd dolt push`.'
fi

cat <<BRIEF
# Read first (in this order, before any other tool call)

1. \`cat $SKILL_MD\` — the execute skill. Follow its \`<delegated-mode>\` block end to end. Skip the \`cat\` only if this skill is already in your context (some harnesses preload it) — never skip reading it.
2. \`cat $WORKSPACE_AGENTS\`
3. \`cat $REPO_AGENTS\`
4. Your working file: $SLICE

# Constraints (decided by the main session — do NOT re-decide)

Bead: $BEAD
Repo: $REPO
Branch: \`$BRANCH\` — already checked out. Verify you are on it. Never switch, never create, never touch \`main\`.
$commit_line
Tracker: \`bd\` cwd does not persist between your shell calls — pass \`-C $REPO\` on every \`bd\` command.
Escalation: you cannot ask the user. Send the question to the main session and stop that thread. Never guess, never shrink the bead to avoid asking.

# Validation — mandatory, not a judgement call

When the slice's work is done, run from $REPO:

  ./validate run phase-exit

That stage is:

$phase_block

Those rows are fixed. Never add, edit or delete one — a row you cannot pass is a code defect to fix, or a \`deferred\` item for the human, never a row to change.

Any FAIL opens a Bug Round or Refactoring Round (Step 4), you fix it, and you re-run the whole stage. You may only report when every row is PASS. After three failed rounds, stop and escalate with the failing ledger and the directory its header's \`log=\` names — a failed run keeps every row's full output there, and the row's single line is a summary nobody can act on.

The run writes \`$REPO/ledger\` — the header and rows it just printed. You
transcribe nothing. Then confirm it:

  ./validate verify phase-exit

That takes no file argument: it reads \`ledger\`. Record two lines under
\`### Validation\` in $SLICE, inside this phase's \`## Architecture Gate Results\`
block — the verdict line \`verify\` printed, verbatim, and the sha of the commit
carrying \`ledger\`.

Run the stage after your last edit, not before, and stage \`ledger\` with the
source it proves in the same commit: verification measures staleness from the
ledger's own commit, which is exactly how a fix applied after the run gets
caught. A \`DRIFT\` line is not a failure — it means the stage gained a row after
the ledger ran.

If the stage outruns your shell tool's timeout, launch it as a supervised
process under a name nothing else has used, then read \`$REPO/ledger\` when it
exits — never the process log. A supervisor can replay a reused name's old
buffer, so a log may show another run's rows under a live process.
$(if [ -n "$user_rows" ]; then
	printf '\nHanded to the user, never run by you:\n\n'
	printf '%s\n' "$user_rows" | sed 's/^/  /'
fi)
# Report (at most 15 lines, no diffs, no logs)

contract: the version token named on the \`Contract version:\` line of \`<delegated-mode>\` — look it up, do not guess
files created / modified
tests + validation: the \`verify\` verdict line, verbatim, and the commit carrying \`ledger\`
architecture gate: the Overall line
bead: id + status + commit shas
deferred: every check you did not run, with who owns it
locale keys needing translation
open questions
blockers
BRIEF
