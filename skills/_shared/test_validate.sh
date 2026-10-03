#!/bin/sh
# Tests for _shared/validate — the generic validator runner.
#
# Run: sh _shared/test_validate.sh
#
# Every case builds a throwaway git repo, copies the runner into it, and asserts
# the runner's exit code and output. No framework, no fixtures directory: a case
# that needs a repo state writes that state itself, so a failure names one thing.
set -u

RUNNER=$(cd "$(dirname "$0")" && pwd)/validate
[ -f "$RUNNER" ] || {
	echo "no runner at $RUNNER" >&2
	exit 2
}

failures=0
cases=0

fail() {
	echo "  FAIL: $1"
	failures=$((failures + 1))
}

ok() {
	printf '  ok: %s\n' "$1"
}

# assert_exit <expected> <actual> <label>
assert_exit() {
	if [ "$1" = "$2" ]; then
		ok "$3 (exit $2)"
	else
		fail "$3 — expected exit $1, got $2"
	fi
}

# assert_has <text> <file> <label>
assert_has() {
	if grep -qF "$1" "$2"; then
		ok "$3"
	else
		fail "$3 — '$1' missing from $2"
		sed 's/^/       | /' "$2"
	fi
}

# assert_lacks <text> <file> <label>
assert_lacks() {
	if grep -qF "$1" "$2"; then
		fail "$3 — '$1' present in $2"
		sed 's/^/       | /' "$2"
	else
		ok "$3"
	fi
}

# assert_row <id> <text> <file> <label> — <text> must appear on <id>'s own row.
# `assert_has` greps the whole file, so it cannot tell a row's line from a
# neighbour's; every claim about a row's evidence field needs this instead.
assert_row() {
	row=$(grep -E "^$1[[:space:]]" "$3" | head -n1)
	case $row in
	*"$2"*) ok "$4" ;;
	*) fail "$4 — '$2' not on row '$1' (got: ${row:-<no such row>})" ;;
	esac
}

# assert_kept <path> <text> <label> — <path> must exist and contain <text>.
# Not `assert_has`: a kept-output path that does not exist yet is the expected
# red state, and `assert_has` would answer it with grep's and sed's own "no such
# file" noise, then dump a whole captured log on any real mismatch.
assert_kept() {
	if [ -f "$1" ] && grep -qF "$2" "$1"; then
		ok "$3"
	else
		fail "$3 — '$2' not in $1"
	fi
}

# new_repo <conf-body> — sets REPO (a clean git repo holding the runner, the
# config and one committed src.py) and OUT (scratch space outside it, for
# captured stdout and stderr). The ledger lives in $REPO, exactly where a real
# repo keeps it: `run` writes it there and `verify` reads it from there, and the
# staleness loop skips it by name so it never looks like source that moved.
new_repo() {
	work=$(mktemp -d)
	REPO=$work/repo
	OUT=$work/out
	mkdir -p "$REPO" "$OUT"
	cp "$RUNNER" "$REPO/validate"
	chmod +x "$REPO/validate"
	printf '%s\n' "$1" >"$REPO/validators.conf"
	(
		cd "$REPO" || exit 1
		git init -q .
		git config user.email t@t.t
		git config user.name t
		echo 'print("source")' >src.py
		git add -A
		git commit -qm init
	)
}

start_case() {
	cases=$((cases + 1))
	printf '%s\n' "$1"
}

PASSING_CONF='phase-exit | alpha | true
phase-exit | beta  | echo beta ran
finalize   | all   | true'

# ---------------------------------------------------------------- run + verify

start_case 'case 1: run stamps provenance, writes the ledger, and verifies it'
new_repo "$PASSING_CONF"
(cd "$REPO" && ./validate run phase-exit >"$OUT/run.txt" 2>"$OUT/err.txt")
assert_exit 0 $? 'run exits 0 when every row passes'
assert_has '# stage=phase-exit' "$OUT/run.txt" 'stdout carries a provenance header'
assert_has '# stage=phase-exit' "$REPO/ledger" 'the run wrote the ledger to the repo root'
assert_has 'rows=alpha,beta' "$REPO/ledger" 'header names the row set it ran'
assert_has 'finished_epoch=' "$REPO/ledger" 'header carries a comparable finish stamp'
assert_has 'conf=' "$REPO/ledger" 'header carries the config fingerprint'
if cmp -s "$OUT/run.txt" "$REPO/ledger"; then
	ok 'the ledger holds exactly what the run printed'
else
	fail 'stdout and the ledger disagree'
	diff "$OUT/run.txt" "$REPO/ledger" | sed 's/^/       | /'
fi
if grep -qE '^alpha[[:space:]]+PASS[[:space:]]+[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z' "$REPO/ledger"; then
	ok 'rows carry a full UTC timestamp'
else
	fail 'rows carry a full UTC timestamp'
	sed 's/^/       | /' "$REPO/ledger"
fi
(cd "$REPO" && ./validate verify phase-exit >"$OUT/v.txt" 2>&1)
assert_exit 0 $? 'verify accepts the ledger the runner just wrote'
assert_has 'phase-exit verified' "$OUT/v.txt" 'the verdict names the stage'
assert_has 'rows alpha,beta' "$OUT/v.txt" 'the verdict names the rows'
assert_has 'run 2' "$OUT/v.txt" 'the verdict names the run window'

start_case 'case 2: a row the config gained later is DRIFT, not failure'
(cd "$REPO" && printf 'phase-exit | gamma | true\n' >>validators.conf)
(cd "$REPO" && ./validate verify phase-exit >"$OUT/v.txt" 2>&1)
assert_exit 0 $? 'verify passes when the stage grew after the ledger'
assert_has 'DRIFT' "$OUT/v.txt" 'the added row is reported as drift'
assert_has 'gamma' "$OUT/v.txt" 'drift names the row'

start_case 'case 3: a row missing while the config is unchanged fails'
new_repo "$PASSING_CONF"
(cd "$REPO" && ./validate run phase-exit >"$OUT/run.txt" 2>&1)
grep -v '^beta' "$REPO/ledger" >"$OUT/trimmed.txt" && cp "$OUT/trimmed.txt" "$REPO/ledger"
(cd "$REPO" && ./validate verify phase-exit >"$OUT/v.txt" 2>&1)
assert_exit 1 $? 'verify rejects a ledger with a row removed'
assert_lacks 'DRIFT' "$OUT/v.txt" 'a same-config gap is not excused as drift'

start_case 'case 4: a row stamped outside the run window fails'
new_repo "$PASSING_CONF"
(cd "$REPO" && ./validate run phase-exit >"$OUT/run.txt" 2>&1)
sed 's/^beta[[:space:]]*PASS[[:space:]]*[0-9T:Z-]*/beta	PASS	2001-01-01T00:00:00Z/' \
	"$REPO/ledger" >"$OUT/pasted.txt" && cp "$OUT/pasted.txt" "$REPO/ledger"
(cd "$REPO" && ./validate verify phase-exit >"$OUT/v.txt" 2>&1)
assert_exit 1 $? 'verify rejects a row pasted in from another run'
assert_has 'beta' "$OUT/v.txt" 'the rejection names the row'

start_case 'case 5: source edited after the run fails, and names the file'
new_repo "$PASSING_CONF"
(cd "$REPO" && ./validate run phase-exit >"$OUT/run.txt" 2>&1)
sleep 1
echo 'print("edited after the stage ran")' >>"$REPO/src.py"
(cd "$REPO" && ./validate verify phase-exit >"$OUT/v.txt" 2>&1)
assert_exit 1 $? 'verify rejects a ledger older than the working tree'
assert_has 'src.py' "$OUT/v.txt" 'the rejection names the changed file'

start_case 'case 6: an untracked source file newer than the ledger fails'
new_repo "$PASSING_CONF"
(cd "$REPO" && ./validate run phase-exit >"$OUT/run.txt" 2>&1)
sleep 1
echo 'new' >"$REPO/added.py"
(cd "$REPO" && ./validate verify phase-exit >"$OUT/v.txt" 2>&1)
assert_exit 1 $? 'verify rejects a ledger predating an untracked file'
assert_has 'added.py' "$OUT/v.txt" 'the rejection names the untracked file'

start_case 'case 7: an old ledger on an unchanged tree still verifies (no calendar rule)'
new_repo "$PASSING_CONF"
(cd "$REPO" && ./validate run phase-exit >"$OUT/run.txt" 2>&1)
sed -e 's/=20[0-9][0-9]-[0-9][0-9]-[0-9][0-9]T/=2001-01-01T/g' \
	-e 's/\(PASS[[:space:]]*\)20[0-9][0-9]-[0-9][0-9]-[0-9][0-9]T/\12001-01-01T/' \
	-e 's/finished_epoch=[0-9]*/finished_epoch=978307200/' \
	"$REPO/ledger" >"$OUT/old.txt" && cp "$OUT/old.txt" "$REPO/ledger"
(cd "$REPO" && ./validate verify phase-exit >"$OUT/v.txt" 2>&1)
assert_exit 0 $? 'a ledger from another day passes while the tree is untouched'

start_case 'case 9: a FAIL row in the ledger fails verification'
new_repo "$PASSING_CONF"
(cd "$REPO" && ./validate run phase-exit >"$OUT/run.txt" 2>&1)
sed 's/^beta\(.*\)PASS/beta\1FAIL/' "$REPO/ledger" >"$OUT/failed.txt" && cp "$OUT/failed.txt" "$REPO/ledger"
(cd "$REPO" && ./validate verify phase-exit >"$OUT/v.txt" 2>&1)
assert_exit 1 $? 'verify rejects a ledger holding a FAIL row'

start_case 'case 10: a failing command makes the row FAIL and the stage exit 1'
new_repo 'phase-exit | alpha | true
phase-exit | broken | echo boom; exit 3'
(cd "$REPO" && ./validate run phase-exit >"$OUT/run.txt" 2>&1)
assert_exit 1 $? 'run exits 1 when a row fails'
assert_has 'FAIL' "$REPO/ledger" 'the failing row is recorded FAIL in the ledger'
assert_has 'boom' "$REPO/ledger" "the row keeps the command's last output line"

start_case 'case 11: user rows are PENDING-USER and verify accepts them'
new_repo 'phase-exit | alpha | true
user | device | echo run me by hand'
(cd "$REPO" && ./validate run user >"$OUT/run.txt" 2>&1)
assert_exit 0 $? 'run on the user stage exits 0'
assert_has 'PENDING-USER' "$REPO/ledger" 'the user row is handed over, not run'
(cd "$REPO" && ./validate verify user >"$OUT/v.txt" 2>&1)
assert_exit 0 $? 'verify accepts a handed-over row'

start_case 'case 12: a ledger recording another stage is rejected, and says which'
new_repo "$PASSING_CONF"
(cd "$REPO" && ./validate run phase-exit >"$OUT/run.txt" 2>&1)
(cd "$REPO" && ./validate verify finalize >"$OUT/v.txt" 2>&1)
assert_exit 1 $? 'verify rejects a phase-exit ledger when asked for finalize'
assert_has "phase-exit" "$OUT/v.txt" 'the rejection names the stage the ledger holds'

start_case 'case 13: a commit that no longer exists is a note, not a failure'
new_repo "$PASSING_CONF"
(cd "$REPO" && ./validate run phase-exit >"$OUT/run.txt" 2>&1)
sed 's/commit=[0-9a-f-]*/commit=deadbee/' "$REPO/ledger" >"$OUT/rebased.txt" && cp "$OUT/rebased.txt" "$REPO/ledger"
(cd "$REPO" && ./validate verify phase-exit >"$OUT/v.txt" 2>&1)
assert_exit 0 $? 'a rewritten or amended commit does not fail verification'
assert_has 'deadbee' "$OUT/v.txt" 'the note names the unresolvable commit'

start_case 'case 14: config and usage errors exit 2, an empty list exits 0'
new_repo "$PASSING_CONF"
(cd "$REPO" && ./validate run nosuchstage >"$OUT/v.txt" 2>&1)
assert_exit 2 $? 'run on an undefined stage exits 2'
(cd "$REPO" && ./validate list user >"$OUT/v.txt" 2>&1)
assert_exit 0 $? 'list on an empty stage exits 0'
(cd "$REPO" && ./validate bogus phase-exit >"$OUT/v.txt" 2>&1)
assert_exit 2 $? 'an unknown subcommand exits 2'
(cd "$REPO" && rm validators.conf && ./validate run phase-exit >"$OUT/v.txt" 2>&1)
assert_exit 2 $? 'a missing config exits 2'
# Guard ordering: this repo now has neither a config nor a ledger. The config
# verdict must win — 2 says "fix the setup", 1 would say "run the stage", and
# running it is impossible without a config.
(cd "$REPO" && ./validate verify phase-exit >"$OUT/v.txt" 2>&1)
assert_exit 2 $? 'a missing config outranks a missing ledger'

start_case 'case 15: a command holding pipes survives the parser'
new_repo 'phase-exit | piped | printf "a\nb\n" | grep -q b && echo both halves ran'
(cd "$REPO" && ./validate run phase-exit >"$OUT/run.txt" 2>&1)
assert_exit 0 $? 'a row whose command contains | and && runs whole'
assert_has 'both halves ran' "$REPO/ledger" 'the command kept every byte after its id'

start_case 'case 16: verify outside a git repo still checks the ledger'
work=$(mktemp -d)
OUT=$work
cp "$RUNNER" "$work/validate"
chmod +x "$work/validate"
printf '%s\n' "$PASSING_CONF" >"$work/validators.conf"
(cd "$work" && ./validate run phase-exit >"$OUT/run.txt" 2>&1)
assert_exit 0 $? 'run works with no git repo present'
assert_has '# stage=phase-exit' "$work/ledger" 'the ledger is written with no git repo present'
(cd "$work" && ./validate verify phase-exit >"$OUT/v.txt" 2>&1)
assert_exit 0 $? 'verify works with no git repo present'

# --------------------------------------------------------------- the interface

start_case 'case 23: no ledger, or one with no header, fails'
new_repo "$PASSING_CONF"
(cd "$REPO" && ./validate verify phase-exit >"$OUT/v.txt" 2>&1)
assert_exit 1 $? 'verify fails when the stage was never run here'
assert_has 'validate run' "$OUT/v.txt" 'the failure names the command that fixes it'
printf 'alpha\tPASS\t2026-01-01\tfine\n' >"$REPO/ledger"
(cd "$REPO" && ./validate verify phase-exit >"$OUT/v.txt" 2>&1)
assert_exit 1 $? 'an unstamped ledger is wrong, not old'
assert_has 'no provenance header' "$OUT/v.txt" 'the failure says the header is missing'

start_case 'case 24: a file argument is refused, whether or not it exists'
new_repo "$PASSING_CONF"
(cd "$REPO" && ./validate run phase-exit >"$OUT/run.txt" 2>&1)
(cd "$REPO" && ./validate verify phase-exit some/plan.md >"$OUT/v.txt" 2>&1)
assert_exit 2 $? 'a path argument is a caller on the old interface'
assert_has 'drop the file argument' "$OUT/v.txt" 'the refusal names the new form'
(cd "$REPO" && ./validate verify phase-exit "$REPO/ledger" >"$OUT/v.txt" 2>&1)
assert_exit 2 $? 'the guard rejects the form, it never stats the argument'

start_case 'case 25: a second run replaces the ledger, it does not append'
new_repo "$PASSING_CONF"
(cd "$REPO" && ./validate run phase-exit >"$OUT/run.txt" 2>&1)
(cd "$REPO" && ./validate run finalize >"$OUT/run.txt" 2>&1)
blocks=$(grep -c '^# stage=' "$REPO/ledger")
assert_exit 1 "$blocks" 'the ledger holds exactly one block'
assert_has '# stage=finalize' "$REPO/ledger" 'the block is the most recent run'
(cd "$REPO" && ./validate verify finalize >"$OUT/v.txt" 2>&1)
assert_exit 0 $? 'the stage that ran last verifies'
(cd "$REPO" && ./validate verify phase-exit >"$OUT/v.txt" 2>&1)
assert_exit 1 $? 'the stage it replaced no longer does'
assert_has 'finalize' "$OUT/v.txt" 'the rejection names the stage now on record'

# ------------------------------------------------------------ committed ledger

start_case 'case 26: work and its ledger committed together verify clean'
new_repo "$PASSING_CONF"
echo 'print("phase work")' >>"$REPO/src.py"
(cd "$REPO" && ./validate run phase-exit >"$OUT/run.txt" 2>&1)
assert_exit 0 $? 'the stage passes on the phase work'
(cd "$REPO" && git add src.py ledger && git commit -qm 'phase work + ledger')
(cd "$REPO" && ./validate verify phase-exit >"$OUT/v.txt" 2>&1)
assert_exit 0 $? 'a ledger committed with its work is not stale'

start_case 'case 27: source committed after the ledger is stale, on a clean tree'
sleep 1
echo 'print("changed after the proof")' >>"$REPO/src.py"
(cd "$REPO" && git commit -qam 'later change')
(cd "$REPO" && ./validate verify phase-exit >"$OUT/v.txt" 2>&1)
assert_exit 1 $? 'the commit range catches what a dirty-tree check cannot'
assert_has 'src.py' "$OUT/v.txt" 'the rejection names the file that moved'

start_case 'case 28: prose committed after the ledger is a note, not a failure'
new_repo "$PASSING_CONF"
echo 'print("phase work")' >>"$REPO/src.py"
(cd "$REPO" && ./validate run phase-exit >"$OUT/run.txt" 2>&1)
(cd "$REPO" && git add src.py ledger && git commit -qm 'phase work + ledger')
echo 'notes' >"$REPO/notes.md"
(cd "$REPO" && git add notes.md && git commit -qm 'plan update')
(cd "$REPO" && ./validate verify phase-exit >"$OUT/v.txt" 2>&1)
assert_exit 0 $? 'updating a plan file after the stage is the normal order of work'
assert_has 'NOTE' "$OUT/v.txt" 'the prose change is reported'
assert_has 'notes.md' "$OUT/v.txt" 'the note names the file'

start_case 'case 29: a run leaves the ledger and nothing else at the repo root'
new_repo "$PASSING_CONF"
(cd "$REPO" && ./validate run phase-exit >"$OUT/run.txt" 2>&1)
strays=$(find "$REPO" -maxdepth 1 \( -name 'tmp.*' -o -name 'ledger.*' -o -name '.ledger.*' \))
if [ -z "$strays" ]; then
	ok 'no staging file survives in the worktree'
else
	fail "the run left a staging file behind: $strays"
fi
untracked=$(cd "$REPO" && git status --porcelain)
if [ "$untracked" = '?? ledger' ]; then
	ok 'the ledger is the only thing the run added to the tree'
else
	fail "the run changed more than the ledger: $untracked"
fi

# ------------------------------------------------------------ mangled headers

# `run` writes every one of these fields on every ledger. A header missing one
# is invented or truncated, never merely old — and the empty `rows=` case is not
# hypothetical: with a conf fingerprint that no longer matches, every configured
# row counts as newly added, the drift rule waves them all through, and a header
# recording no run at all used to verify green.

start_case 'case 30: a header claiming no rows fails, even when the config moved on'
new_repo "$PASSING_CONF"
(cd "$REPO" && ./validate run phase-exit >/dev/null 2>&1)
sed 's/ rows=.*/ rows=/; s/conf=[0-9-]*/conf=1-1/' "$REPO/ledger" | sed -n '1p' >"$OUT/mangled" \
	&& cp "$OUT/mangled" "$REPO/ledger"
(cd "$REPO" && ./validate verify phase-exit >"$OUT/v.txt" 2>&1)
assert_exit 1 $? 'a ledger claiming zero rows is refused'
assert_has "no 'rows='" "$OUT/v.txt" 'the refusal names the missing field'

start_case 'case 31: a header missing its finish stamp fails'
new_repo "$PASSING_CONF"
(cd "$REPO" && ./validate run phase-exit >/dev/null 2>&1)
sed 's/ finished_epoch=[0-9]*//' "$REPO/ledger" >"$OUT/noepoch" && cp "$OUT/noepoch" "$REPO/ledger"
(cd "$REPO" && ./validate verify phase-exit >"$OUT/v.txt" 2>&1)
assert_exit 1 $? 'a header without finished_epoch is refused'

# ------------------------------------------------------- a failing row's output

# The shape the defect was measured in: the line that explains the failure comes
# first, an unbounded run of uninteresting lines follows, and the summary is last.
BURIED_CONF='phase-exit | alpha | true
phase-exit | buried | printf "buried detail\n"; i=0; while [ $i -lt 30 ]; do echo filler; i=$((i + 1)); done; printf "summary tail\n"; exit 1'

start_case 'case 19: a failing row keeps every line, not just the last'
new_repo "$BURIED_CONF"
(cd "$REPO" && ./validate run phase-exit >"$OUT/run.txt" 2>&1)
assert_exit 1 $? 'run exits 1 when a row fails'
assert_row buried 'summary tail' "$REPO/ledger" 'the row still reduces to its last meaningful line'
assert_lacks 'buried detail' "$REPO/ledger" 'field 4 is unchanged — the row stays one line'
logdir=$(sed -n 's/^# .*log=\([^ ]*\).*/\1/p' "$REPO/ledger" | head -n1)
assert_kept "$logdir/buried.log" 'buried detail' 'the buried first line survives the run'
assert_kept "$logdir/buried.log" 'summary tail' 'and so does everything after it'

start_case 'case 20: a failing run names its kept output in the header'
assert_has 'log=' "$REPO/ledger" 'the header says where the output was kept'
if [ -d "$logdir" ]; then
	ok 'the path the header names is a directory that exists'
else
	fail "the header's log= path is not a directory (got: ${logdir:-<absent>})"
fi
case $logdir in
"$REPO"/*) fail 'kept output sits in the worktree, where verify reads it as source' ;;
*) ok 'kept output lives outside the worktree' ;;
esac
[ -d "$logdir" ] && rm -rf "$logdir"

# The row id carries this process's pid, so no other suite run — an older one
# whose leftovers the OS has not reaped, or a concurrent `validate run` — can
# write a file of this name. Without that, a leftover from a red run poisons
# every later green run, since the temp root is shared and long-lived.
start_case 'case 21: a clean run keeps nothing and says nothing'
new_repo "phase-exit | alpha | true
phase-exit | chatty$$ | printf 'line one\nline two\nline three\n'"
(cd "$REPO" && ./validate run phase-exit >"$OUT/run.txt" 2>&1)
assert_exit 0 $? 'a clean run exits 0'
assert_row "chatty$$" 'line three' "$REPO/ledger" 'a passing row still reduces to its last line'
assert_lacks 'log=' "$REPO/ledger" 'a green run names no kept output'
probe=$(mktemp -d)
tmp_root=$(dirname "$probe")
rmdir "$probe"
if [ -z "$(find "$tmp_root" -maxdepth 2 -name "chatty$$.log" 2>/dev/null)" ]; then
	ok 'a green run leaves nothing behind'
else
	fail 'a green run left its captured output on disk'
fi

start_case 'case 22: a user stage records its rows without touching the capture path'
new_repo 'phase-exit | alpha | true
user | device | echo run me by hand'
(cd "$REPO" && ./validate run user >"$OUT/run.txt" 2>&1)
assert_exit 0 $? 'the user stage exits 0 having run nothing'
assert_row device 'run me by hand' "$REPO/ledger" 'the handed-over row records its command'
assert_has 'PENDING-USER' "$REPO/ledger" 'the row is handed over, not run'
assert_lacks 'log=' "$REPO/ledger" 'a stage that ran nothing keeps nothing'
# The branch this case actually guards: `user` rows `continue` before the
# capture, so `logdir` is still unset when the cleanup block tests it. Drop its
# initialiser and `set -u` aborts with "logdir: parameter not set" — before the
# ledger is written, so the message lands on stdout and no ledger exists at all.
assert_lacks 'logdir' "$OUT/run.txt" 'the unset capture directory never reaches the shell'
if [ -f "$REPO/ledger" ]; then
	ok 'the ledger exists, so the run reached its write'
else
	fail 'no ledger — the run died before writing it'
fi

start_case 'case 23: version prints the stamp without a stage or a config'
bare=$(mktemp -d)
cp "$RUNNER" "$bare/validate"
chmod +x "$bare/validate"
(cd "$bare" && ./validate version >"$bare/v.txt" 2>&1)
assert_exit 0 $? 'version exits 0 with no validators.conf and no stage argument'
if grep -qE '^[0-9][0-9]*$' "$bare/v.txt"; then
	ok 'version prints a bare integer stamp'
else
	fail "version prints a bare integer stamp — got: $(cat "$bare/v.txt")"
fi
(cd "$bare" && ./validate bogus >"$bare/u.txt" 2>&1)
assert_exit 2 $? 'an unknown subcommand still exits 2'
assert_has 'version' "$bare/u.txt" 'the usage line advertises version'

echo
if [ "$failures" -eq 0 ]; then
	echo "validate: $cases cases, all assertions passed"
	exit 0
fi
echo "validate: $failures failed assertion(s) across $cases cases"
exit 1
