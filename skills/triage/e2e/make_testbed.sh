#!/usr/bin/env bash
# triage/e2e/make_testbed.sh — build the disposable e2e testbed from fixtures/.
#
# Usage: make_testbed.sh [--root DIR]     (default DIR: the skills repo root)
#
# Builds three gitignored, disposable trees, from scratch, every run:
#   $ROOT/triage-testbed          a real git repo + a real bd database
#   $ROOT/triage-testbed-plans    the plan corpus, project name "triage-testbed"
#   $ROOT/triage-testbed-clean    a second, smaller bd database holding one
#                                 clean bead — inventory.py's exit-0 case
#                                 cannot be produced from the main testbed,
#                                 which carries a drift bead (tb-drf1) by
#                                 design. Reached through the same
#                                 TRIAGE_PROJECTS_ROOT=$ROOT seam, with
#                                 --project triage-testbed-clean — no new CLI
#                                 surface.
#
# Two guards, because both failures are unrecoverable:
#
#   Wipe guard. A target is wiped only if it already carries the
#   `.triage-testbed` file this script writes as the first thing in a fresh
#   tree. A path without that marker is refused, never deleted — including one
#   named by --root.
#
#   Database guard. `bd` finds its database by walking UP from the working
#   directory, stopping at a git root. The testbed lives inside the skills
#   repo, so a testbed missing both `.beads` and `.git` resolves to the skills
#   repo's OWN tracker, and every `bd create` below would write a real bead
#   into it. Verified, not assumed: `bd info` reports the resolved path, and
#   this script asserts that path lies inside the testbed before the first bead
#   is created and again after the last one. Anything else exits 2.
#
# And one promise, which the per-worker tripwire in triage/e2e/live_dispatch.py
# depends on as much as it depends on the guards: every tree this script builds
# is CLEAN when it exits. `git status --porcelain` is the worktree half of that
# tripwire, so a dirty baseline would make it fire on every run. Two things had
# to be handled for that to hold — Python bytecode, and `.beads/interactions.
# jsonl`, a log `bd` rewrites on every command including a read. Both are
# ignored, and `settle_tree` asserts each tree is clean before the script
# returns.
#
# `bd create` takes `--id <string>` plus `--force` (see `bd create --help`);
# --force is required because the testbed database's own prefix will not be
# `tb`. So the fixture's `id` field (e.g. `tb-inv1`) becomes the bead's real,
# literal database ID — no separate label -> real-ID mapping exists anywhere.
#
# Isolation seams a caller points at the built testbed (plan.md's guard #1):
#   TRIAGE_PROJECTS_ROOT=$ROOT               (inventory.resolve_repo_root reads this)
#   --plans-dir $ROOT/triage-testbed-plans   (dedup.py / promote.py take this)
set -eu

HERE="$(cd "$(dirname "$0")" && pwd)"
FIXTURES="$HERE/fixtures"
ROOT="$(cd "$HERE/../.." && pwd)"

while [ $# -gt 0 ]; do
  case "$1" in
    --root) ROOT="$2"; shift 2 ;;
    *) echo "usage: make_testbed.sh [--root DIR]" >&2; exit 2 ;;
  esac
done

mkdir -p "$ROOT"
ROOT="$(cd "$ROOT" && pwd)"
TESTBED="$ROOT/triage-testbed"
CORPUS="$ROOT/triage-testbed-plans"
CLEAN="$ROOT/triage-testbed-clean"
PROJECT="triage-testbed"

die() { echo "make_testbed: $*" >&2; exit 2; }

# --- guard 1: never delete a tree this script did not create ------------------
refuse_unless_ours() {
  if [ -e "$1" ] && [ ! -f "$1/.triage-testbed" ]; then
    die "refusing to wipe $1 — no .triage-testbed marker"
  fi
  rm -rf "$1"
  mkdir -p "$1"
  : > "$1/.triage-testbed"
}

# --- guard 2: never let a bd call reach a tracker outside the testbed ---------
assert_db_inside() {
  resolved=$(cd "$1" && bd info 2>/dev/null | sed -n 's/^Database: *//p' | head -1) \
    || resolved=""
  case "$resolved" in
    "$1"/*) ;;
    *) die "bd in $1 resolves to '${resolved:-<no database>}' — outside the testbed" ;;
  esac
}

refuse_unless_ours "$TESTBED"
refuse_unless_ours "$CORPUS"
refuse_unless_ours "$CLEAN"

# --- the citable source tree, in a real git repo ------------------------------
# The commit is the point: a bead citing `retry_client.py:7` needs a file at
# that line with history behind it. apply_beads relies on the repo too.
cp -Rf "$FIXTURES/src/." "$TESTBED/"
git -C "$TESTBED" init -q
# Every real repo in this workspace ignores Python bytecode, and the testbed
# has to as well: the per-worker guard's worktree half is `git status
# --porcelain`, so a worker that merely *imports* a fixture module leaves
# lib/__pycache__/ behind and reads as a write. A guard that fires on reading
# is one whose findings get discounted, which is how a real write gets
# through. bd init writes a minimal .gitignore; this appends to it.
printf '__pycache__/\n*.py[cod]\n' >>"$TESTBED/.gitignore"
git -C "$TESTBED" add -A
git -C "$TESTBED" -c user.email=e2e@testbed -c user.name=e2e \
  commit -qm "testbed: initial source tree"
[ -z "$(git -C "$TESTBED" status --porcelain)" ] \
  || die "testbed tree not clean after commit"

# --- load one fixture file into one bd database -------------------------------
apply_beads() {
  beads_json="$1"; db_dir="$2"; plans_root="$3"
  # The git root is what makes this database its own. bd walks UP for a
  # database and stops at a git root; without one, a directory inside the
  # skills repo resolves to the skills tracker, and `bd init` there aborts
  # with "This workspace is already initialized" instead of creating anything.
  [ -d "$db_dir/.git" ] || git -C "$db_dir" init -q
  # A git root is not enough. `bd init` copies the *enclosing* workspace's
  # `.beads/config.yaml` verbatim, `sync.remote` included, and then clones the
  # history that remote names — so a testbed built inside the skills repo came
  # up holding 80 real beads at the testbed's own path, where every
  # path-checking guard passes it by construction. Measured both ways: an
  # outer repo with a git remote and no `.beads/` yields `Issue Count: 0`,
  # while an outer `.beads/config.yaml` carrying `sync.remote` and no git
  # remote at all yields 80. So it is the config file that travels, not the
  # git remote, and writing our own first is what stops the copy — `bd init`
  # leaves an existing config alone. Do not delete this seed on the theory
  # that the testbed's own repo has no remote: that is true and irrelevant.
  mkdir -p "$db_dir/.beads"
  printf 'sync.remote: ""\n' >"$db_dir/.beads/config.yaml"
  # `--non-interactive` because bd only auto-detects that from a non-TTY: run
  # this generator by hand in a terminal without it and `bd init` opens a role
  # wizard and spins forever. Measured — a 36-minute hang with one line of log.
  (cd "$db_dir" && bd init --non-interactive >/dev/null) \
    || die "bd init failed in $db_dir"
  assert_db_inside "$db_dir"

  python3 - "$beads_json" "$db_dir" "$plans_root" <<'PY' || die "loading $beads_json failed"
import json
import subprocess
import sys

beads_path, db_dir, plans_root = sys.argv[1], sys.argv[2], sys.argv[3]
beads = json.load(open(beads_path))

# `bd statuses` calls these built-in; every other status a fixture uses has to
# be registered before `bd update --status` will accept it. Derived from the
# fixture so a new status needs no edit here.
BUILTIN = {"open", "in_progress", "blocked", "deferred", "closed", "pinned", "hooked"}


def bd(*args):
    proc = subprocess.run(["bd", *args], cwd=db_dir, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.exit(f"bd {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout


custom = sorted({b["status"] for b in beads} - BUILTIN)
if custom:
    bd("config", "set", "status.custom", ",".join(f"{s}:wip" for s in custom))

for b in beads:
    bd("create", b["title"], "--id", b["id"], "--force", "-t", b["issue_type"],
       "-p", str(b.get("priority", 2)), "-d", b.get("description", ""))

for b in beads:
    if b.get("notes"):
        bd("update", b["id"], "--notes",
           b["notes"].replace("__TESTBED_PLANS__", plans_root))
    if b.get("parent"):
        bd("update", b["id"], "--parent", b["parent"])
    for dep in b.get("deps", []):
        bd("dep", "add", b["id"], dep["target"], "-t", dep["type"])

# Status goes last: a bead set `closed` or `blocked` first would refuse the
# edits above.
for b in beads:
    if b["status"] != "open":
        bd("update", b["id"], "--status", b["status"])

print(f"loaded {len(beads)} beads into {db_dir}")
PY

  assert_db_inside "$db_dir"
}

apply_beads "$FIXTURES/beads.json" "$TESTBED" "$CORPUS/$PROJECT"
apply_beads "$FIXTURES/beads_clean.json" "$CLEAN" "$CORPUS/$PROJECT"

# --- leave every testbed worktree clean --------------------------------------
# `bd init` scaffolds files and commits them, and `.beads/interactions.jsonl`
# is among them — a telemetry log `bd` rewrites on EVERY command, including a
# read. Tracked, it makes the worktree dirty the moment a worker runs `bd show`,
# and the per-worker guard's worktree half is `git status --porcelain`. A guard
# that fires when a worker merely reads is one whose findings get discounted,
# which is how a real write gets through unnoticed.
settle_tree() {
  printf '.beads/interactions.jsonl\n' >>"$1/.gitignore"
  git -C "$1" rm -r --cached --quiet --ignore-unmatch .beads/interactions.jsonl
  git -C "$1" add -A
  git -C "$1" -c user.email=e2e@testbed -c user.name=e2e \
    commit -qm "testbed: untrack the tracker's own telemetry log" || true
  [ -z "$(git -C "$1" status --porcelain)" ] \
    || die "$1 is dirty straight after a build: $(git -C "$1" status --porcelain)"
}

settle_tree "$TESTBED"
settle_tree "$CLEAN"

# --- the plan corpus ----------------------------------------------------------
mkdir -p "$CORPUS/$PROJECT"
cp -Rf "$FIXTURES/plans/." "$CORPUS/$PROJECT/"
python3 - "$CORPUS/$PROJECT" <<'PY' || die "corpus substitution failed"
import sys
from pathlib import Path

root = Path(sys.argv[1])
for path in sorted(root.rglob("*.md")):
    text = path.read_text(encoding="utf-8")
    if "__TESTBED_PLANS__" in text:
        path.write_text(text.replace("__TESTBED_PLANS__", str(root)), encoding="utf-8")
PY

CORPUS_COUNT=$(find "$CORPUS/$PROJECT" -name '*.md' | wc -l | tr -d ' ')
echo "testbed built: $TESTBED (git + bd), $CLEAN (bd), $CORPUS_COUNT corpus files at $CORPUS/$PROJECT"
