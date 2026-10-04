#!/bin/sh
# Print the invariant part of a triage planning worker's brief.
#
# The orchestrator appends the per-group `# Target` section and dispatches the
# result. Everything this script prints is identical for every planning worker
# of every run, which is the point: hand-written briefs drift, generated ones
# do not. Precedent: execute/scripts/brief.sh.
#
# Usage:
#   brief_plan.sh <bead-ids> <investigation-paths> <staging-root> <repo-root>
#
#   <bead-ids> and <investigation-paths> are comma-separated and aligned:
#   one collision group, one plan, one investigation per bead.
#
# Environment:
#   WORKSPACE_AGENTS  path to the workspace-level AGENTS.md
#                     (default: <repo-root>/../AGENTS.md)
#
# Exit: 0 brief printed · 2 usage or configuration error.
set -u

usage() {
	echo "usage: brief_plan.sh <bead-ids> <investigation-paths> <staging-root> <repo-root>" >&2
	exit 2
}

# `${1:?}` would be shorter, but its exit status is shell-dependent — bash exits
# 1, dash exits 2 — and this epic fixes 2 as the usage/configuration code.
[ $# -eq 4 ] || usage

BEADS=$1
INVESTIGATIONS=$2
STAGING=$3
REPO=$4
REPO=$(cd "$REPO" && pwd) || exit 2

# The report the worker returns, keyed by the group's first bead — the same id
# Wave 4 keys the group's brief by — and derived from arguments already in
# hand. Never a fifth positional: five arguments is a pinned usage error and
# `<repo-root>` is pinned last for every generator. Round 1, because this
# script only ever dispatches a first round; a revision round's path is the
# orchestrator's to name.
REPORT="$STAGING/reports/${BEADS%%,*}_plan_r1.md"

SKILLS_ROOT=$(cd "$(dirname "$0")/../.." && pwd) || exit 2
SKILL_MD="$SKILLS_ROOT/plan/SKILL.md"
CONTRACT="$SKILLS_ROOT/_shared/autonomous-mode.md"
CHARTER="$SKILLS_ROOT/triage/references/autonomy-charter.md"
[ -f "$SKILL_MD" ] || {
	echo "brief_plan.sh: no plan skill at $SKILL_MD" >&2
	exit 2
}
[ -f "$CONTRACT" ] || {
	echo "brief_plan.sh: no contract at $CONTRACT" >&2
	exit 2
}

# The contract must carry a version token, but this script never prints it: a
# token handed to the worker proves it can copy a brief, not that it read the
# contract. The worker looks it up; the orchestrator compares what it echoes.
grep -qE 'Contract version: \*\*SW-[0-9]{4}-[0-9]{2}-v[0-9]+\*\*' "$CONTRACT" || {
	echo "brief_plan.sh: no contract version line in $CONTRACT" >&2
	exit 2
}

WORKSPACE_AGENTS=${WORKSPACE_AGENTS:-$(dirname "$REPO")/AGENTS.md}
REPO_AGENTS="$REPO/AGENTS.md"
INVESTIGATION_LIST=$(printf '%s\n' "$INVESTIGATIONS" | tr ',' '\n' | sed 's/^/   - /')

cat <<BRIEF
# Read first (in this order, before any other tool call)

1. \`cat $SKILL_MD\` — the plan skill. Follow it end to end. Skip the \`cat\` only if it is already in your context (some harnesses preload it) — never skip reading it.
2. \`cat $CONTRACT\` — the autonomous-mode contract. It overrides every point where the skill would ask a human. Read it after the skill so you know what is being overridden.
3. \`cat $WORKSPACE_AGENTS\`
4. \`cat $REPO_AGENTS\`
5. Your inputs, one investigation artifact per bead:
$INVESTIGATION_LIST

# Constraints (decided by the main session — do NOT re-decide)

Beads: $BEADS — one plan covers all of them. They were grouped because their approved work touches the same files, modules or symbols; planning them separately is what this grouping exists to prevent.
Repo: $REPO
Staging root: $STAGING — the only directory you may write to.
Your report file: $REPORT. Write the report you return to that path **before** you return it, with the same content. Your job leg is retained five minutes after you settle, and every quality-control verdict this system has produced arrived later than that — so a \`REVISE\` routed back to you finds the file or finds nothing.

**Output root swap — the line that matters most in this brief.** Everything Step 7b would write under \`project_plans/<project>/todo/\` goes under $STAGING/todo/ instead, with identical folder and file naming — the run directory's own \`todo/\`, with no project segment under it, because the run directory already belongs to one project. The system plan mirror is OFF: write nothing to ~/.claude/plans, and point \`**System plan file:**\` at the staged path.

Write the slice files yourself, sequentially. Step 7b's parallel slice subagents are not used here — nested delegation is not available in every harness, and a slice a subagent could not write is a slice you still owe.
Investigations are input, never scratch: never edit, move or overwrite a file listed above. Link to it by absolute path from the plan's \`## Background\`.
Tracker: you never run \`bd\`. Step 8 is replaced by the intent records below.
No commits, no pushes, no locale edits, no source edits.

# Escalation

You cannot ask the user. Send the question to the main session (\`SendMessage\` in Claude Code, \`hub\` send to \`Main\` in omp) with what you need and why, then stop that thread. Never guess, never narrow the task to dodge the question.

# Gates

Step 7's approval loop fires and you do not answer it. Write the plan files, report that you are stopped at the approval gate, and stop. An independent quality-control pass rules on the artifact and the main session routes the verdict back. Self-approval is not available.
Step 8a's tracker question never fires — the tracker is untouched in this run. Step 9's execution handoff never fires; do not invoke the execute skill and do not offer to.

# PARK — recognise your own exit

Park the group, name the condition in your report, and stop when any of these is true. The first four are the contract's own list, restated so you can recognise your exit without re-reading it mid-flight:

- **Requirements are underdetermined** by the bead, the investigation, and the code taken together. This is \`plan\` Step 2 with nobody to ask, and inventing requirements is prohibited.
- **The tracker is unconfigured** (\`plan\` Step 8a).
- **Any STOP-LIST item** in $CHARTER is touched.
- **Your context budget is spent before the cause is proven.** A thinner answer is not an acceptable substitute for a proven one, and \`investigate\`'s evidence-only rule does not relax because you are running low.
- the investigations you were given do not agree on a fix direction, and reconciling them is a new decision rather than a reading.

Parking is a correct outcome and costs one worker. Inventing an answer is a failed assignment and costs the plan, its review, and the execution after it.

# Before you return — lint your own plan

Run tier 1 on the plan you wrote before you report, and report the exit code:

    python3 $SKILLS_ROOT/triage/scripts/lint_plan.py $STAGING/todo/<the folder you wrote> --project-root $REPO

Exit 0 passes, 1 is findings, 2 is a broken invocation. A non-zero exit is yours to fix first, before
you report at all. Measured: three of three plans in one live run bounced on findings this command
names outright — a missing \`**LOC waiver:**\`, a phase carrying 26 implementation steps against a
limit of 8, four unlisted locales, and step categories out of order.

This is a pre-flight, never a substitute. The orchestrator runs the same linter authoritatively and
its result is the gate; your run only saves a round trip that costs a re-wake at both ends. Fix what
is real, and never contort the artifact to silence a finding you believe is wrong — leave it, and say
so in your report, naming the finding and why the rule does not hold here.

# Tracker intents — required, replaces every \`bd\` call

Emit **intent records**, not prose. The schema is \`$SKILLS_ROOT/triage/scripts/intent_records.py\`; it validates what you write and \`promote.py\` applies it. Write the array into a fenced \`\`\`json block under a \`## Tracker Intent\` heading at the end of the staged master plan, and repeat it in your report. The orchestrator saves what you return under $STAGING/intents/, because a record that lives only in a report is one the promote step cannot read.

Four kinds are yours, because no script can derive them:

- \`create-epic\` — one per multi-phase plan.
- \`create-task\` — one per phase of a multi-phase plan. A **single-phase plan creates nothing**: its source bead already exists and is the task, and the derived \`flip-source\` is what makes it workable. \`plan\` Step 8b's "create a single tracker task" assumes a plan with no bead behind it, which never happens in a triage run.
- \`open\` — one per bead this array creates. \`bd create\` lands a bead in \`needs-plan\`; this is the flip that makes it workable, and only you know the plan path that justifies it.
- \`retitle\` — a condition, not an option: one record per bead whose title the plan's own evidence contradicts, carrying the corrected string verbatim in \`title\`. A title that states a wrong cause misroutes every later reader, and a correction your plan argues for but never records is one the promote step drops on the floor.

Never write \`investigation\`, \`flip-source\`, \`dep\`, \`supersede\` or \`close\` records. The run derives those from its own ledger, its collision report and the epic it created for a merged group, and a worker cannot get wrong an intent it is never asked for.

Field rules are \`plan\` Step 8b's, unchanged by the schema: \`--notes\` carries absolute paths, so \`master\`, \`slice\` and \`plan\` hold the staged absolute paths you actually wrote; \`--description\` carries the step checklist, so \`description\` holds that text and never a file reference. \`key\` is unique across the array. \`ref\` names a bead this array creates, and \`parent\` and each \`open\` record point at it by that name; \`bead\` names one that already exists, which is why \`retitle\` carries it instead.
Wherever a staged plan file names a bead this array has not created yet — a slice's \`**Beads task:**\`, a \`## Progress\` row, a \`## Beads\` table cell — write the token \`<bead:{ref}>\` with that record's own \`ref\`, and nothing else: promote substitutes the created ID into it, and a token it cannot resolve is a \`promote-writeback-incomplete\` error rather than a placeholder that ships.

\`\`\`json
[
  {"key": "epic", "kind": "create-epic", "ref": "epic", "type": "epic", "priority": 1,
   "title": "OPDS mount injection integrity",
   "master": "$STAGING/todo/demo_epic_opds_mount_injection_integrity/plan.md"},
  {"key": "phase-1", "kind": "create-task", "ref": "phase-1", "parent": "epic", "type": "task", "priority": 2,
   "title": "Phase 1: Required catalog repository",
   "description": "- [ ] Make buildCatalogScreen's bookRepository required\n- [ ] Pass StubBookRepository() at the 33 indifferent mounts",
   "slice": "$STAGING/todo/demo_epic_opds_mount_injection_integrity/phase_1_required_catalog_repository.md",
   "master": "$STAGING/todo/demo_epic_opds_mount_injection_integrity/plan.md"},
  {"key": "epic-open", "kind": "open", "ref": "epic"},
  {"key": "phase-1-open", "kind": "open", "ref": "phase-1"},
  {"key": "retitle-demo-7qm", "kind": "retitle", "bead": "demo-7qm",
   "title": "OPDS mounts inject no catalog repository"}
]
\`\`\`

A real array carries one \`create-task\` plus one \`open\` per phase. Paths are the staged ones you wrote; promote rewrites them when the run moves into the real plan directories.

# Report (at most 15 lines, no diffs, no logs)

contract: the version token on the \`Contract version:\` line of $CONTRACT — look it up, do not guess
beads: $BEADS
master plan: the staged path
slices: count + paths
lint: the exit code of your pre-return lint_plan.py run, plus what you fixed
phases: count, and the dependency shape in one line
intents: the JSON array, and the master-plan section you wrote it into
gate: stopped at the Step 7 approval gate — or PARK plus the condition that fired
open questions
blockers
BRIEF
