#!/bin/sh
# Print the invariant part of a triage investigation worker's brief.
#
# The orchestrator appends the per-bead `# Target` section and dispatches the
# result. Everything this script prints is identical for every investigation
# worker of every run, which is the point: hand-written briefs drift, generated
# ones do not. Precedent: execute/scripts/brief.sh.
#
# Usage:
#   brief_invest.sh <bead-id> <artifact-path> <staging-root> <repo-root>
#
# Environment:
#   WORKSPACE_AGENTS  path to the workspace-level AGENTS.md
#                     (default: <repo-root>/../AGENTS.md)
#
# Exit: 0 brief printed · 2 usage or configuration error.
set -u

usage() {
	echo "usage: brief_invest.sh <bead-id> <artifact-path> <staging-root> <repo-root>" >&2
	exit 2
}

# `${1:?}` would be shorter, but its exit status is shell-dependent — bash exits
# 1, dash exits 2 — and this epic fixes 2 as the usage/configuration code.
[ $# -eq 4 ] || usage

BEAD=$1
ARTIFACT=$2
STAGING=$3
REPO=$4
REPO=$(cd "$REPO" && pwd) || exit 2

# The report the worker returns, assigned the same way its artifact is and
# derived from the two arguments already in hand — never a fifth positional,
# because five arguments is a pinned usage error and `<repo-root>` is pinned
# last for every generator. Round 1, because this script only ever dispatches
# a first round; a revision round's path is the orchestrator's to name.
REPORT="$STAGING/reports/${BEAD}_r1.md"

SKILLS_ROOT=$(cd "$(dirname "$0")/../.." && pwd) || exit 2
SKILL_MD="$SKILLS_ROOT/investigate/SKILL.md"
CONTRACT="$SKILLS_ROOT/_shared/autonomous-mode.md"
CHARTER="$SKILLS_ROOT/triage/references/autonomy-charter.md"
[ -f "$SKILL_MD" ] || {
	echo "brief_invest.sh: no investigate skill at $SKILL_MD" >&2
	exit 2
}
[ -f "$CONTRACT" ] || {
	echo "brief_invest.sh: no contract at $CONTRACT" >&2
	exit 2
}

# The contract must carry a version token, but this script never prints it: a
# token handed to the worker proves it can copy a brief, not that it read the
# contract. The worker looks it up; the orchestrator compares what it echoes.
grep -qE 'Contract version: \*\*SW-[0-9]{4}-[0-9]{2}-v[0-9]+\*\*' "$CONTRACT" || {
	echo "brief_invest.sh: no contract version line in $CONTRACT" >&2
	exit 2
}

WORKSPACE_AGENTS=${WORKSPACE_AGENTS:-$(dirname "$REPO")/AGENTS.md}
REPO_AGENTS="$REPO/AGENTS.md"

cat <<BRIEF
# Read first (in this order, before any other tool call)

1. \`cat $SKILL_MD\` — the investigate skill. Follow it end to end. Skip the \`cat\` only if it is already in your context (some harnesses preload it) — never skip reading it.
2. \`cat $CONTRACT\` — the autonomous-mode contract. It overrides every point where the skill would ask a human. Read it after the skill so you know what is being overridden.
3. \`cat $WORKSPACE_AGENTS\`
4. \`cat $REPO_AGENTS\`
5. \`bd -C $REPO show $BEAD\` — the bead under investigation. Read-only.

# Constraints (decided by the main session — do NOT re-decide)

Bead: $BEAD
Repo: $REPO — the only code you may read.
Staging root: $STAGING — the only directory you may write to.
Your two output files: $ARTIFACT — the investigation — and $REPORT, the report you return. Write those two files and nothing else, anywhere.
Write the report to $REPORT **before** you return it, with the same content. Your job leg is retained five minutes after you settle, and every quality-control verdict this system has produced arrived later than that — so a \`REVISE\` routed back to you finds the file or finds nothing.
Step 5 output location is overridden: the investigation outcome goes to $ARTIFACT, never to a project_plans/ directory and never to ~/.claude/plans.
Tracker: read-only. \`bd show\` and \`bd list\` only, always with \`-C $REPO\` — your cwd does not persist between shell calls. No \`bd update\`, no \`--claim\`, no status change: Step 5d does not fire for you, and the one correction it would have written you emit as the intent record below.
No commits, no pushes, no locale edits, no source edits. When your artifact is written, the repo is byte-identical to how you found it.
Parallel read-only research agents are permitted — investigate Step 1 allows them, and only there. They gather and report; they never write and never conclude. You write the artifact yourself.

# Escalation

You cannot ask the user. Send the question to the main session (\`SendMessage\` in Claude Code, \`hub\` send to \`Main\` in omp) with what you need and why, then stop that thread. Never guess, never narrow the bead to dodge the question.

# Gates

Gate 1 (root cause) and Gate 2 (approved fix) still fire, and you do not answer them. Write the gate payload into $ARTIFACT in the shape the skill prescribes, report that you are stopped at the gate, and stop. An independent quality-control pass rules on it and the main session routes the verdict back to you. Self-approval is not available; "the evidence is obviously sufficient" is not a verdict.

Your artifact is therefore written **before** the gate it is waiting on, and its header says so. When you proved the cause and chose a fix on the evidence, write:

- \`**Status:** ROOT CAUSE CONFIRMED — FIX PROPOSED\` — with \`## Approved Fix\` and its four subsections exactly as \`investigate\` Step 5b prescribes. That section is the Gate 2 payload the verdict rules on; the status says only that nobody has ruled yet.

Never \`FIX APPROVED\`: you cannot approve your own gates, so that status is a claim you have no standing to make. Do not invent a status either — the four \`lint_investigation.py\` accepts are the whole vocabulary, and an invented one fails tier 1 before a reviewer sees your work.

Gate 3 (handoff to implementation) never fires here. Do not invoke the plan skill and do not offer to.

# PARK — recognise your own exit

Park the bead, name the condition in your report, and stop when any of these is true. The first four are the contract's own list, restated so you can recognise your exit without re-reading it mid-flight:

- **Requirements are underdetermined** by the bead, the investigation, and the code taken together. This is \`plan\` Step 2 with nobody to ask, and inventing requirements is prohibited.
- **The tracker is unconfigured** (\`plan\` Step 8a).
- **Any STOP-LIST item** in $CHARTER is touched.
- **Your context budget is spent before the cause is proven.** A thinner answer is not an acceptable substitute for a proven one, and \`investigate\`'s evidence-only rule does not relax because you are running low.
- the evidence cannot establish a root cause and no further read-only evidence is reachable;
- the fix direction turns on a product, UX or policy call rather than on evidence;
- the work needs a mutation this brief forbids — a tracker write, a source edit, a commit, a locale edit.

Parking is a correct outcome and costs one worker. Inventing an answer is a failed assignment and costs the plan, its review, and the execution after it.

**Still write the artifact when you park.** It is retained and a human reads it; the work that got you to the question is the point of it. Write it exactly as \`investigate\` Step 5b-park says — everything up to \`## Ruled Out\` as usual, then one of these two Status lines and an \`## Open Question\` section in place of \`## Approved Fix\`:

- \`**Status:** ROOT CAUSE CONFIRMED — FIX PARKED\` — you proved the cause, the fix direction is not yours to pick.
- \`**Status:** ROOT CAUSE UNPROVEN — PARKED\` — the evidence ran out before the cause did.

\`## Open Question\` carries the question a human must answer, phrased as a question they can answer from where they stand — not a restatement of the defect. Do not reach for a fix status to get out of a park: \`FIX PROPOSED\` says you picked a fix on the evidence, and a park dressed up as one is the guess the stop-list exists to prevent.

# Before you return — lint your own artifact

Run tier 1 on your own artifact before you report, and report the exit code:

    python3 $SKILLS_ROOT/triage/scripts/lint_investigation.py $ARTIFACT --repo $REPO

Exit 0 passes, 1 is findings, 2 is a broken invocation. A non-zero exit is yours to fix first, before
you report at all.

This is a pre-flight, never a substitute. The orchestrator runs the same linter authoritatively and
its result is the gate; your run only saves a round trip that costs a re-wake at both ends. Fix what
is real, and never contort the artifact to silence a finding you believe is wrong — leave it, and say
so in your report, naming the finding and why the rule does not hold here.

# Footprint — required, the collision model reads it

Your artifact MUST end with a \`footprint:\` block naming what the approved fix
would touch. Repo-relative paths. **The block in your artifact is what the
collision model parses** — \`footprints.py\` reads it straight off the file you
wrote. Your report's footprint line carries the counts; nothing reads counts
into the model, so a path you leave out of the block is invisible to it. Every
\`files\` and \`symbols\` entry carries its own \`change:\`: an entry without one
still brings its path and its symbol in, and costs the signature-ordering rule
that decides which bead in a group is planned first. An empty list is written
\`[]\`.

footprint:
  bead: $BEAD
  files:
    - path: lib/features/reader/reader_page.dart
      module: lib/features/reader
      change: modify          # add | modify | delete
    - path: lib/core/storage/progress_store.dart
      module: lib/core/storage
      change: modify
  symbols:
    - name: ProgressStore.restore
      kind: method            # class | method | function | constant
      change: signature       # add | signature | behavior | remove
    - name: ReaderPage.build
      kind: method
      change: behavior
  modules:
    - lib/features/reader
    - lib/core/storage

\`change: signature\` is the load-bearing field. A symbol whose signature or
contract moves gets \`signature\`; a symbol that only behaves differently behind
an unchanged contract gets \`behavior\`. Beads in one ordered group are planned
signature-movers first, so everything else plans against the new contract. Mark
a contract move as \`behavior\` and your bead lands in the wrong slot, with the
next planner writing against a contract that is about to change.

Beads whose footprints overlap are merged into one plan instead of being
planned separately. A missing or vague block means your bead cannot be
grouped — report that as a defect, not as a detail.

# Tracker intent — one kind, and only on one condition

Step 5d's title rule survives the read-only override as a record. Emit it when — and only when —
\`investigate\` Step 5d's own condition holds: **your evidence disproved a cause the bead's title
asserts.** A title that states a wrong cause is worse than one that states only the symptom, and a
parked bead never reaches a planner, so this record is the only writer that correction will ever get.

One kind, one record, carrying the corrected string verbatim. The schema is
\`$SKILLS_ROOT/triage/scripts/intent_records.py\`; the orchestrator saves what you return under
$STAGING/intents/ and \`promote.py\` is what runs the \`bd\` call. Put the array in your report:

    [{"key": "retitle-$BEAD", "kind": "retitle", "bead": "$BEAD", "title": "<the corrected title>"}]

Emit no other kind. Everything else this run needs is the planner's or derived from the run's own
ledger, and a worker cannot get wrong an intent it is never asked for. A title the evidence leaves
standing gets no record at all — this is a correction, not a formality.

# Report (at most 15 lines, no diffs, no logs)

contract: the version token on the \`Contract version:\` line of $CONTRACT — look it up, do not guess
bead: $BEAD
artifact: $ARTIFACT
lint: the exit code of your pre-return lint_investigation.py run, plus what you fixed
root cause: one sentence
approved fix: one sentence
footprint: counts of files / modules / symbols
intents: the \`retitle\` array, or \`none\` plus the title the evidence left standing
gate: which gate you are stopped at — or PARK plus the condition that fired
open questions
blockers
BRIEF
