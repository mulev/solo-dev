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

# new_repo <conf-body> — sets REPO (a clean git repo) and OUT (scratch space
# outside it). Ledgers and captured output live in OUT so the fixture's own
# artifacts never look like uncommitted source to the runner, the same way a
# real repo keeps logs gitignored and plan files elsewhere.
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

start_case 'case 1: run stamps provenance, verify accepts its own ledger'
new_repo "$PASSING_CONF"
(cd "$REPO" && ./validate run phase-exit >"$OUT/ledger.txt" 2>"$OUT/err.txt")
assert_exit 0 $? 'run exits 0 when every row passes'
assert_has '# stage=phase-exit' "$OUT/ledger.txt" 'ledger carries a provenance header'
assert_has 'rows=alpha,beta' "$OUT/ledger.txt" 'header names the row set it ran'
assert_has 'finished_epoch=' "$OUT/ledger.txt" 'header carries a comparable finish stamp'
assert_has 'conf=' "$OUT/ledger.txt" 'header carries the config fingerprint'
if grep -qE '^alpha[[:space:]]+PASS[[:space:]]+[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z' "$OUT/ledger.txt"; then
	ok 'rows carry a full UTC timestamp'
else
	fail 'rows carry a full UTC timestamp'
	sed 's/^/       | /' "$OUT/ledger.txt"
fi
(cd "$REPO" && ./validate verify phase-exit "$OUT/ledger.txt" >"$OUT/v.txt" 2>&1)
assert_exit 0 $? 'verify accepts a ledger the runner just wrote'

start_case 'case 2: a row the config gained later is DRIFT, not failure'
(cd "$REPO" && printf 'phase-exit | gamma | true\n' >>validators.conf)
(cd "$REPO" && ./validate verify phase-exit "$OUT/ledger.txt" >"$OUT/v.txt" 2>&1)
assert_exit 0 $? 'verify passes when the stage grew after the ledger'
assert_has 'DRIFT' "$OUT/v.txt" 'the added row is reported as drift'
assert_has 'gamma' "$OUT/v.txt" 'drift names the row'

start_case 'case 3: a row missing while the config is unchanged fails'
new_repo "$PASSING_CONF"
(cd "$REPO" && ./validate run phase-exit >"$OUT/ledger.txt" 2>&1)
grep -v '^beta' "$OUT/ledger.txt" >"$OUT/trimmed.txt"
(cd "$REPO" && ./validate verify phase-exit "$OUT/trimmed.txt" >"$OUT/v.txt" 2>&1)
assert_exit 1 $? 'verify rejects a ledger with a row removed'
assert_lacks 'DRIFT' "$OUT/v.txt" 'a same-config gap is not excused as drift'

start_case 'case 4: a row stamped outside the run window fails'
new_repo "$PASSING_CONF"
(cd "$REPO" && ./validate run phase-exit >"$OUT/ledger.txt" 2>&1)
sed 's/^beta[[:space:]]*PASS[[:space:]]*[0-9T:Z-]*/beta	PASS	2001-01-01T00:00:00Z/' \
	"$OUT/ledger.txt" >"$OUT/pasted.txt"
(cd "$REPO" && ./validate verify phase-exit "$OUT/pasted.txt" >"$OUT/v.txt" 2>&1)
assert_exit 1 $? 'verify rejects a row pasted in from another run'
assert_has 'beta' "$OUT/v.txt" 'the rejection names the row'

start_case 'case 5: source edited after the run fails, and names the file'
new_repo "$PASSING_CONF"
(cd "$REPO" && ./validate run phase-exit >"$OUT/ledger.txt" 2>&1)
sleep 1
echo 'print("edited after the stage ran")' >>"$REPO/src.py"
(cd "$REPO" && ./validate verify phase-exit "$OUT/ledger.txt" >"$OUT/v.txt" 2>&1)
assert_exit 1 $? 'verify rejects a ledger older than the working tree'
assert_has 'src.py' "$OUT/v.txt" 'the rejection names the changed file'

start_case 'case 6: an untracked source file newer than the ledger fails'
new_repo "$PASSING_CONF"
(cd "$REPO" && ./validate run phase-exit >"$OUT/ledger.txt" 2>&1)
sleep 1
echo 'new' >"$REPO/added.py"
(cd "$REPO" && ./validate verify phase-exit "$OUT/ledger.txt" >"$OUT/v.txt" 2>&1)
assert_exit 1 $? 'verify rejects a ledger predating an untracked file'
assert_has 'added.py' "$OUT/v.txt" 'the rejection names the untracked file'

start_case 'case 7: an old ledger on an unchanged tree still verifies (no calendar rule)'
new_repo "$PASSING_CONF"
(cd "$REPO" && ./validate run phase-exit >"$OUT/ledger.txt" 2>&1)
sed -e 's/=20[0-9][0-9]-[0-9][0-9]-[0-9][0-9]T/=2001-01-01T/g' \
	-e 's/\(PASS[[:space:]]*\)20[0-9][0-9]-[0-9][0-9]-[0-9][0-9]T/\12001-01-01T/' \
	-e 's/finished_epoch=[0-9]*/finished_epoch=978307200/' \
	"$OUT/ledger.txt" >"$OUT/old.txt"
(cd "$REPO" && ./validate verify phase-exit "$OUT/old.txt" >"$OUT/v.txt" 2>&1)
assert_exit 0 $? 'a ledger from another day passes while the tree is untouched'

start_case 'case 8: a header-less ledger verifies as LEGACY'
new_repo "$PASSING_CONF"
printf 'alpha\tPASS\t2026-01-01\tfine\nbeta\tPASS\t2026-01-01\tfine\n' >"$OUT/legacy.txt"
(cd "$REPO" && ./validate verify phase-exit "$OUT/legacy.txt" >"$OUT/v.txt" 2>&1)
assert_exit 0 $? 'a pre-provenance ledger still verifies'
assert_has 'LEGACY' "$OUT/v.txt" 'the ledger is marked as unstamped'

start_case 'case 9: a FAIL row in the ledger fails verification'
new_repo "$PASSING_CONF"
(cd "$REPO" && ./validate run phase-exit >"$OUT/ledger.txt" 2>&1)
sed 's/^beta\(.*\)PASS/beta\1FAIL/' "$OUT/ledger.txt" >"$OUT/failed.txt"
(cd "$REPO" && ./validate verify phase-exit "$OUT/failed.txt" >"$OUT/v.txt" 2>&1)
assert_exit 1 $? 'verify rejects a ledger holding a FAIL row'

start_case 'case 10: a failing command makes the row FAIL and the stage exit 1'
new_repo 'phase-exit | alpha | true
phase-exit | broken | echo boom; exit 3'
(cd "$REPO" && ./validate run phase-exit >"$OUT/ledger.txt" 2>&1)
assert_exit 1 $? 'run exits 1 when a row fails'
assert_has 'FAIL' "$OUT/ledger.txt" 'the failing row is recorded FAIL'
assert_has 'boom' "$OUT/ledger.txt" "the row keeps the command's last output line"

start_case 'case 11: user rows are PENDING-USER and verify accepts them'
new_repo 'phase-exit | alpha | true
user | device | echo run me by hand'
(cd "$REPO" && ./validate run user >"$OUT/ledger.txt" 2>&1)
assert_exit 0 $? 'run on the user stage exits 0'
assert_has 'PENDING-USER' "$OUT/ledger.txt" 'the user row is handed over, not run'
(cd "$REPO" && ./validate verify user "$OUT/ledger.txt" >"$OUT/v.txt" 2>&1)
assert_exit 0 $? 'verify accepts a handed-over row'

start_case 'case 12: a ledger for another stage is rejected'
new_repo "$PASSING_CONF"
(cd "$REPO" && ./validate run phase-exit >"$OUT/ledger.txt" 2>&1)
(cd "$REPO" && ./validate verify finalize "$OUT/ledger.txt" >"$OUT/v.txt" 2>&1)
assert_exit 1 $? 'verify rejects a phase-exit ledger passed as finalize'
assert_has 'stage' "$OUT/v.txt" 'the rejection says the ledger is for another stage'

start_case 'case 13: a commit that no longer exists is a note, not a failure'
new_repo "$PASSING_CONF"
(cd "$REPO" && ./validate run phase-exit >"$OUT/ledger.txt" 2>&1)
sed 's/commit=[0-9a-f-]*/commit=deadbee/' "$OUT/ledger.txt" >"$OUT/rebased.txt"
(cd "$REPO" && ./validate verify phase-exit "$OUT/rebased.txt" >"$OUT/v.txt" 2>&1)
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

start_case 'case 15: a command holding pipes survives the parser'
new_repo 'phase-exit | piped | printf "a\nb\n" | grep -q b && echo both halves ran'
(cd "$REPO" && ./validate run phase-exit >"$OUT/ledger.txt" 2>&1)
assert_exit 0 $? 'a row whose command contains | and && runs whole'
assert_has 'both halves ran' "$OUT/ledger.txt" 'the command kept every byte after its id'

start_case 'case 17: a plan file keeping a red ledger as evidence still verifies'
new_repo "$PASSING_CONF"
(cd "$REPO" && ./validate run phase-exit >"$OUT/green.txt" 2>&1)
# What a real slice looks like: the red-state proof a phase deliberately records,
# then the run that actually earned the phase.
{
	echo 'Red-state proof, before the fix — the row must catch this:'
	echo '# stage=phase-exit conf=0-0 commit=old dirty=yes started=2001-01-01T00:00:00Z finished=2001-01-01T00:01:00Z finished_epoch=978307260 rows=alpha,beta'
	printf 'alpha\tPASS\t2001-01-01T00:00:30Z\tfine\n'
	printf 'beta\tFAIL\t2001-01-01T00:00:40Z\t2 issues found\n'
	echo 'Then, after the fix:'
	cat "$OUT/green.txt"
} >"$OUT/evidence.md"
(cd "$REPO" && ./validate verify phase-exit "$OUT/evidence.md" >"$OUT/v.txt" 2>&1)
assert_exit 0 $? 'a FAIL row from another run does not condemn the verified one'

start_case 'case 18: an unstamped ledger holding a red row is a note, not a failure'
new_repo "$PASSING_CONF"
{
	printf 'alpha\tPASS\t2026-01-01\tfine\n'
	printf 'beta\tFAIL\t2026-01-01\tred state proof\n'
	printf 'beta\tPASS\t2026-01-01\tfixed\n'
} >"$OUT/legacy_red.md"
(cd "$REPO" && ./validate verify phase-exit "$OUT/legacy_red.md" >"$OUT/v.txt" 2>&1)
assert_exit 0 $? 'a legacy ledger with a red row and a green one passes'
assert_has 'NOTE' "$OUT/v.txt" 'the unattributable red row is reported as a note'

start_case 'case 16: verify outside a git repo still checks the ledger'
work=$(mktemp -d)
OUT=$work
cp "$RUNNER" "$work/validate"
chmod +x "$work/validate"
printf '%s\n' "$PASSING_CONF" >"$work/validators.conf"
(cd "$work" && ./validate run phase-exit >"$OUT/ledger.txt" 2>&1)
assert_exit 0 $? 'run works with no git repo present'
(cd "$work" && ./validate verify phase-exit "$OUT/ledger.txt" >"$OUT/v.txt" 2>&1)
assert_exit 0 $? 'verify works with no git repo present'

echo
if [ "$failures" -eq 0 ]; then
	echo "validate: $cases cases, all assertions passed"
	exit 0
fi
echo "validate: $failures failed assertion(s) across $cases cases"
exit 1
