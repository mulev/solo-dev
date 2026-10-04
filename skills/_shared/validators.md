# Validators

Automated proof that a phase is actually finished. Every repo owns three files at its root:

| File | What it is |
|---|---|
| `validate` | generic runner — placed verbatim at the repo root, never edited per repo |
| `validators.conf` | the repo's rules: which command runs at which stage |
| `ledger` | generated — the repo's last validation state, written by `validate run`, read by `validate verify`, committed with the work it proves |

The runner decides nothing. The config decides everything. Tests, builds and native suites are the repo's business; the skill only knows *when* they must run and *who* runs them.

**The runner is placed, never edited.** It goes to a repo's root byte for byte and nothing about it is tuned per repo: behaviour lives in `validators.conf`, which is the repo's own file. The copy carries a version, and `./validate version` prints it, which is how you tell a current copy from one placed months ago and left behind. That matters because of a real failure: a repo sat on a runner 84 lines behind for months and nothing in the system could say so, because the file carried no version at all.

---

## Stages

| Stage | Who runs it | When |
|---|---|---|
| `phase-exit` | whoever executed the phase (worker, or main when working solo) | after the phase's work is complete — **before** plan update, commit, and bead close. Main also runs it once before dispatching an epic, as the baseline. |
| `finalize` | main session | Step 5, once per execution, over everything the execution changed |
| `user` | the user | never run automatically; recorded as `PENDING-USER` and handed over with the exact command |

**The stage column is the only tuning knob.** A row too slow for every phase moves to `finalize`. A row needing hardware nobody guarantees moves to `user`. There is no per-file conditioning: a Dart change can break an iOS build, so "you only touched Dart" is never a reason to skip a row.

Stages are deliberately coarse. The fast changed-file test runs belong to the TDD inner loop (execute Step 2.1), not here.

**A repo may define its own on-demand stage, and `validate` already allows it.** The three stages above are the ones the execute skill drives; the runner treats the stage column as data everywhere except the `user` special case, so a name it has never heard of works with no change to `validate` — and none should be made, since that file goes into every repo verbatim. Use this for a check that is genuinely worth having and genuinely too slow for `phase-exit`: the skills repo's `e2e` stage builds three real issue databases and takes minutes. **The trade-off is real and must be written down where the stage is defined:** a stage nothing invokes rots, and unlike `phase-exit` no workflow will notice. So an on-demand stage names, at its definition, what change should send someone to run it — the skills repo's names changes under `triage/e2e/` or `triage/scripts/`. A stage with no such note is one nobody will think to run.

---

## `validators.conf`

```
# stage | id | command
phase-exit | static | dart format --output=none --set-exit-if-changed . && flutter analyze
phase-exit | suites | ./scripts/run_all_tests.sh --skip-integration --no-rerun
finalize   | all    | ./scripts/run_all_tests.sh
```

- Three fields separated by `|`. `#` comments and blank lines are ignored. Rows run top to bottom.
- `id` — `[a-z0-9-]+`, unique within its stage. It is the ledger key, so renaming an id invalidates old ledgers.
- `command` — any shell, executed from the repo root by `sh -c`; `cd` where you need to. Everything after the second `|` is byte-exact, so `|` and `||` inside a command are fine.
- **Reuse the repo's existing runner scripts with flags** instead of writing new pipelines. If a runner already builds what it needs (most native test runners build the app first), do not add a separate build row — it pays twice.
- Check a runner's defaults before trusting them: a runner that defaults to a clean rebuild belongs in `finalize` with defaults and in `phase-exit` with a cache-reuse flag.

**The config is not yours to write.** `validators.conf` and `validate` are human-owned. Never add, edit, reorder or delete a row in any repo — not to add a check you think is missing, and above all not to remove one you cannot pass. A gate its own subject can redefine proves nothing, so editing this file invalidates every ledger you produce afterwards. A failing row is a code defect: Bug Round or Refactoring Round, fix, re-run the whole stage. A config that is genuinely wrong or missing goes in your report as a `deferred` item owned by the human, and you continue with the rest of your work — never escalate about this file, never block on it, never stop a thread over it.

**A row that did not run is a failed row.** `validate` sees an exit code and nothing else, so this guarantee has to live in the command: a runner that can skip part of its work MUST exit non-zero when the skip was not asked for. "No device found", "no JDK", "no ChromeDriver", "wrong OS" are environment failures — the check the stage promised did not execute, so the row is FAIL, not PASS. A skip the caller *requested* — a `--skip-web` flag, a human answering "skip" at a prompt — is a decision and may exit 0. Nothing else may.

Read a runner's skip paths once before you trust a row:

```
# WRONG — warns, exits 0, and the ledger records PASS for a suite that never ran
if ! resolve_device; then log "Skipped — no device found"; fi

# RIGHT — the run fails and says how to make it pass
if ! resolve_device; then
  log "NOT RUN — no device found. Boot a simulator, or pass --skip-ios."
  OVERALL_EXIT=1
fi
```

Measured cost of getting this wrong, on a multi-package Flutter plugin: its integration runner listed devices without booting one, so with nothing booted it skipped the entire iOS suite and still exited 0. Every ledger row said `PASS`. The first run that actually executed that suite found two defects in the epic that had just shipped, one of them a thirty-minute hang on the feature's happy path.

**No config, no pass.** A repo without `validators.conf` fails the phase-exit gate. The only escape is an explicit ledger line `validators: none — <reason>` in the working file, which is a visible decision rather than a silent skip.

---

## The ledger

Run the script **from the repo root** — the config's commands `cd` from there, and `./validate` only exists there:

```
cd <repo root> && ./validate run phase-exit
```

It prints a provenance header, then one tab-separated line per row — id, result, the UTC timestamp the row finished, and the last meaningful output line:

```
# stage=phase-exit conf=1524238371-412 commit=25fec33 dirty=no started=2026-08-19T11:47:12Z finished=2026-08-19T11:55:46Z finished_epoch=1786010146 rows=static,suites,device
static  PASS          2026-08-19T11:47:15Z  No issues found!
suites  PASS          2026-08-19T11:55:44Z  All tests passed!
device  PENDING-USER  2026-08-19T11:55:46Z  cd example && flutter test integration_test/all_tests.dart -d <id>
```

That output is the artifact, and the run writes it to `./ledger` at the repo root as well as printing it. **Commit `ledger` in the same commit as the work it proves** — never on its own, never amended in afterwards, because the commit that carries it is the anchor `verify` measures staleness from. Earlier states are not lost: `git log -p ledger` is the repo's whole validation history, which is why the file holds one block and never grows.

**A failed run keeps its full output; a green one keeps nothing.** Field 4 is only the last meaningful line — the right amount for a `PASS`, and useless for a `FAIL`, where the line that explains the failure is usually buried hundreds of lines above the summary. So when any row fails, the header gains a trailing `log=<dir>`:

```
# stage=phase-exit conf=1524238371-412 commit=25fec33 dirty=no started=... finished=... finished_epoch=... rows=static,suites log=/var/folders/nm/.../T/tmp.zfFrIJDSjH
```

That directory holds one `<id>.log` per row that ran, each carrying the row's complete output. It lives outside the worktree, so `verify` never reads it as source that moved after the run — and now that the ledger itself lives *in* the worktree, that separation matters more, not less. It is machine-local and disposable: read it to diagnose the red row, never commit it. The `log=` key stays in the ledger's header even after the machine reaps that directory; `verify` ignores it, so never edit it out. A run where every row passed prints no `log=` and leaves nothing behind.

`./validate verify <stage>` takes no file — it reads `./ledger`, the file the run wrote. It asks four things the old date-only ledger could not:

| Question | How it is answered | Failure it catches |
|---|---|---|
| Is there a ledger, and is it this stage's? | `./ledger` must exist and its block must name the stage asked for | a stage nobody ran here, and a claim resting on a different stage's run |
| Did every row of this run pass *inside this run*? | each row's stamp must fall in `[started, finished]` | a row edited in from a different run, or typed by hand |
| Has the code moved since? | while the ledger is uncommitted, no source file in `git diff --name-only HEAD` or the untracked set may be newer than `finished_epoch`; once it is committed, no source file may appear in `git diff --name-only <the ledger's commit> HEAD` | "ran the stage, then kept editing" *and* "committed, then kept going" — the second is the hole a dirty-tree check cannot see |
| Did the stage gain rows afterwards? | `conf` fingerprint mismatch ⇒ rows absent from `rows=` are `DRIFT` | nothing: this is normal growth, not a defect |

Markdown newer than the run is a `NOTE`, not a failure — updating a plan file after the stage is the normal order of work. So is a `commit=` that no longer resolves, because amending or rebasing is not a validation defect.

**The ledger holds exactly one block.** A second run replaces it, whatever stage it was: the file answers "what did this repo last prove, when, at which commit", and nothing else. A red run writes its block too, so a failing state is on disk to read rather than a claim to relay — and `git log -p ledger` still holds every state before it, red ones included.

**The ledger is the only source of truth about this repo's validation state.** "What has this repo proved, and when?" is answered by `cat ledger` plus `./validate verify <stage>`, and by nothing else — not a transcript, not a process log, not memory, not `git log` alone. Read it before deciding to run anything: a stage you were about to run because you did not look is the busy work below, and a state you reported without looking is a guess.

**Exit codes**, and they mean different things:

| Code | Meaning | What to do |
|---|---|---|
| 0 | every row passed, or `list` found nothing to report | proceed |
| 1 | a row FAILed, verification found a row missing, mis-stamped or older than the code it claims, or this repo has no `ledger` for the stage | Bug Round or Refactoring Round, fix, re-run the whole stage. A missing ledger means the stage was never run here — run it |
| 2 | misconfigured: no `validators.conf`, unknown subcommand, a file path passed to `verify`, or `run`/`verify` on a stage this repo does not define | **do not loop** — record `validators: none — {reason}` in the report, say so, and fix the caller or the config |

`list` on an empty stage exits 0 in silence: "nothing to hand over" is an answer, not an error.

`DRIFT` and `NOTE` lines are reports, not failures: they explain the ledger, they do not condemn it. A `ledger` is generated and always stamped, so one carrying no provenance header is wrong rather than old — hand-written, truncated, or a paste of something else — and it fails.

**Long stages need a supervised process.** A `finalize` stage that runs native and integration suites takes tens of minutes (measured: 38m19s on a federated Flutter plugin with Dart, Kotlin, Swift and integration suites). Launch it through the harness's process supervisor — `hub` `start` plus `wait` in omp — and give the run a name nothing else has used (`<stage>-<HHMMSS>`). A plain shell call risks a tool timeout killing the run halfway, which leaves you with no ledger and no idea which suite was in flight.

When it exits, read the result from `./ledger` and confirm it with `./validate verify <stage>`. **Never read validation state out of a process log.** A supervisor may replay a reused name's buffer: measured, `hub logs` on a restarted name returned the *previous* process's output while reporting the new one `running; cursor=0` — a nine-day-old `FAIL` block read as if it were the live run. The log is for diagnosing a red row (as is the directory the header's `log=` names), never for learning what a run concluded.

---

## The rule that makes it work

> Finish the phase's work, then run `./validate run phase-exit`. **Any FAIL opens a Bug Round or Refactoring Round (execute Step 4), gets fixed, and the whole stage re-runs.** A phase may only be reported complete when every row is `PASS`. After three failed rounds, stop and escalate with the `ledger` block and the output kept in the directory its header's `log=` names — that directory holds the detail the row's one line cannot, so quoting the ledger alone hands over a summary nobody can act on.

Reporting a stage that was never run, or partially run, is a failed assignment — not a judgement call. `verify` makes the claim checkable in one command. `PASS` means the row's work executed: a row whose runner skipped the work and exited 0 is a lie the ledger cannot catch, which is why the command itself must fail on an unrequested skip (see `validators.conf` above).

---

## Two rules that keep verification from becoming busy work

A fail-closed gate with only one direction named — "never skip a check" — makes every ambiguity resolve toward running the stage again. These two name the other direction.

**A ledger is verified against the row set it names, never a later one.** A phase whose job is to add a validator row cannot have run that row, so an earlier phase's ledger is missing it by construction. That is `DRIFT`. **Never re-run a stage to refresh a stamp**: it produces no new information and replaces a ledger that was earned with one that was not. A stage is re-run because the code moved — which is exactly the condition `verify` now measures for you.

**A superset stage discharges its subset at the same commit.** `finalize` at commit X proves everything `phase-exit` would prove at commit X. The per-phase stage exists to catch breakage *before* a commit lands; the difference between them is *when* they run, not what they are worth afterwards. Once `finalize` is green on a tree, nothing on that tree needs re-running to look fresher — cite it instead: `subsumed by finalize @<sha>`. A `finalize` run also replaces the `ledger`, so `verify phase-exit` afterwards correctly reports that the stage on record is `finalize`: that is the citation working, not a gap.

The litmus, before any re-run: **would this run's outcome be knowable from an artifact already on this tree?** If yes, cite the artifact. If no, run it.

---

## Recipes

Starting points. Copy, adjust, move rows between stages until the timing is bearable.

**Flutter app**
```
phase-exit | static | dart format --output=none --set-exit-if-changed . && flutter analyze
phase-exit | suites | ./scripts/run_all_tests.sh --skip-integration --no-rerun
finalize   | all    | ./scripts/run_all_tests.sh
```

**Flutter plugin / multi-package repo** — loop the packages for static checks; let the runner handle the suites.
```
phase-exit | static | for d in pkg pkg_platform_interface pkg/example; do (cd "$d" && dart format --output=none --set-exit-if-changed . && flutter analyze) || exit 1; done
phase-exit | suites | cd pkg && ./scripts/run_all_tests.sh --skip-integration --no-rerun
finalize   | all    | cd pkg && ./scripts/run_all_tests.sh
```

**Pure Dart package**
```
phase-exit | static | dart format --output=none --set-exit-if-changed . && dart analyze
phase-exit | tests  | dart test
finalize   | tests  | dart test
```

**Node / TypeScript**
```
phase-exit | static | npm run lint && npx tsc --noEmit
phase-exit | tests  | npm test
finalize   | build  | npm run build && npm test
```

**Python**
```
phase-exit | static | ruff check . && mypy .
phase-exit | tests  | pytest -q
finalize   | tests  | pytest
```

**Ruby / Rails**
```
phase-exit | static | bundle exec rubocop
phase-exit | tests  | bundle exec rspec
finalize   | system | bundle exec rspec spec/system
```

**Jekyll / static site**
```
phase-exit | build | bundle exec jekyll build
finalize   | build | bundle exec jekyll build
```

**Shell / scripts repo**
```
phase-exit | syntax | find . -name '*.sh' -not -path './.git/*' -exec sh -n {} +
phase-exit | tests  | python3 scripts/run_tests.py
finalize   | syntax | find . -name '*.sh' -not -path './.git/*' -exec sh -n {} +
finalize   | tests  | python3 scripts/run_tests.py
```

**Go**
```
phase-exit | static | gofmt -l . | (! grep .) && go vet ./...
phase-exit | tests  | go test ./...
finalize   | tests  | go test -race ./...
```

**Rust**
```
phase-exit | static | cargo fmt --check && cargo clippy -- -D warnings
phase-exit | tests  | cargo test
finalize   | tests  | cargo test --all-features
```

---

## Positive controls

Some checks pass identically whether they ran or never loaded. A custom lint
plugin is the clearest case: the analyzer exits 0 when your rules found nothing
*and* when your rules were never wired in. A green row then proves nothing, and
it is the kind of nothing that stays green for months.

The fix is a second row that fails on purpose. Plant a known violation, run the
check, and require the diagnostic back:

```
phase-exit | lint-plugin | for d in pkg pkg_platform_interface pkg/example; do (cd "$d" && dart analyze --fatal-infos) || exit 1; done
phase-exit | lint-canary | ./scripts/check_lint_wiring.sh
```

where `check_lint_wiring.sh` writes a file that must trip each rule, runs the
analyzer, asserts every expected diagnostic appeared, and cleans up. It exits
non-zero when a rule is silent — which is exactly the state a bare `analyze`
reports as success.

Ask for a canary whenever a row's command could exit 0 without doing its work:
custom lint or codegen plugins, an assertion helper that might be compiled out,
a test runner whose discovery pattern could match nothing, a coverage gate whose
source list could be empty. This is the same rule as *"a row that did not run is
a failed row"* above, applied to a check that cannot tell you it did not run.

---

## Reading a repo's own runner before writing rows

Most repos already have a test script. Prefer calling it with flags over
reassembling its steps, and read what its flags actually do first:

- If the runner already builds what it needs — most native test runners compile
  the app before testing — do **not** add a separate build row. It pays twice.
- If the runner defaults to a clean rebuild, put it in `finalize` with defaults
  and in `phase-exit` with a cache-reuse flag.
- If one sub-package needs a different tool than the rest (a pure-language
  package inside a framework repo, where the framework's analyzer is the wrong
  binary), give it its own row rather than bending the loop.
- Leave a comment above each row explaining *why* it is shaped that way. The
  next person to touch the config is deciding whether to move a row between
  stages, and the timing rationale is the only thing that answers them.

---

## Device and simulator policy

A repo's runner may boot and use simulators or emulators; that is not "asking the machine owner for a favour", it is the runner doing its job. The user guarantees the simulators and emulators exist, and a failure caused by a missing one is theirs to resolve — not a blocker to escalate.

Only a suite that needs a **physically attached device**, or hardware nobody can guarantee, belongs in the `user` stage.
