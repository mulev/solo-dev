# QC gates: the two tiers, the verdict, and the revision policy

Quality control for a triage run. This file is self-contained on purpose: a reviewer dispatch is
runnable from here alone, without the plan slice that specified it and without the orchestrator that
routes the answer.

One sentence of context. A delegated `investigate` or `plan` worker cannot ask the user, so every
gate its skill would have put to a human is answered by an independent verdict instead
(`../../_shared/autonomous-mode.md`, section A). Quality control is the whole reason that
substitution is safe: a worker never approves its own work, and the orchestrator only routes a
verdict it did not form.

---

## 1. Two-tier order

Tier 1 is mechanical and gates tier 2.

| Tier | What runs | On what |
|---|---|---|
| 1 | `../scripts/lint_investigation.py` | an investigation artifact |
| 1 | `../scripts/lint_plan.py` | a plan artifact — folder or single-phase file |
| 2 | the registered `triage-qc` agent (`../agents/triage-qc.md`) | an artifact that passed tier 1, on a harness whose roster carries that agent |
| 2 | a worker briefed by `../scripts/brief_qc.sh`, first read `../agents/triage-qc.md` | the same artifact, on a harness whose roster does not |

A non-zero tier-1 exit sends the artifact back to its producing worker **without an agent ever being
spawned**. Tier 2 runs only on a tier-1 pass.

**The orchestrator holds the briefed branch to the definition's own restrictions**, which frontmatter
enforces only where a registry loads it: it spawns that worker on model `opus`, with tools `Read`,
`Grep` and `Glob`, and nothing written anywhere (`../agents/triage-qc.md`). Two of those are fixed at
spawn and a worker cannot impose them on itself however carefully it reads the definition — the model
and the tool set — so an orchestrator that skips them downgrades the review without any row saying
so. What tier 2 exists for — independence — is carried by the brief and not by the agent type:
`../scripts/brief_qc.sh` already withholds the producing worker's transcript and already forbids
writing. **The orchestrator names the branch it took in its Wave 6 close-out** (`../SKILL.md` Wave 6
carries the obligation), so a reader of the close-out knows which reviewer produced each verdict. The
branch needs no ledger column: `references/ledger.md` keeps its ten, and the close-out is prose.

The reason to record: an adversarial reviewer's time is the expensive resource in this system, and
an artifact missing a required section does not need judgment to fail. Spending a reviewer on a
structural defect a linter already names costs a round and teaches the reviewer nothing.

The division of labour follows from that. Tier 1 owns structure — sections present, citations
resolvable, thresholds respected, links intact. Tier 2 owns truth — whether the chain actually holds
in the code, whether the requirements actually came from somewhere. A reviewer that re-reports a
missing section is doing tier 1's job with a language model, and its finding should be dropped.

### A reviewer that returns no verdict

A reviewer process can exit without emitting a verdict object — one did, at 3m47s, having read the
brief, the artifact, the checklists and the schema. That is not a verdict of any kind. It is not a
`PARK`, it is not a `REVISE`, and it is above all not a licence for the orchestrator to form its own
opinion of the artifact.

**Re-dispatch it at the same round, against the same brief and the same artifact path.** The round
counter does not advance: no verdict was produced, so no round was spent, and § 3's convergence
comparison needs the round numbers to mean rounds that actually happened.

Never split one review into two scoped reviews, and never invent a worker name to carry a piece of
it. Both were improvised on the live run this rule comes from: the review went out to
`triage-qc-ordering` and `triage-qc-counts`, two names no script produces, and the run gained two
extra round-1 rows next to the failed one. Scoping a review is methodology, and methodology belongs
to the scripts (`../SKILL.md` constraint 7).

Recording it needs no new column. The failed reviewer's ledger row keeps its **empty `returned`**
until the re-dispatch comes back — which is exactly the shape the resume protocol already reads, in
`ledger.md` under *Resume protocol*: "A row dispatched but never returned is re-dispatched, and its
stale artifact, if one exists, is overwritten at the same assigned path." For a dead reviewer there
is nothing to overwrite and nothing to discard: the `artifact` cell names the artifact **under
review**, which the re-dispatch reads rather than regenerates. Deleting it would leave the
re-dispatched worker with nothing to review and `preflight` reporting the artifact missing at
promote. Write **nothing** into `final` for a dead process: the row is unfinished, not concluded,
and `final` is the bead's outcome, not a report on a subprocess.

**Two consecutive deaths on the same artifact end the loop.** Stop, and escalate to the user with the
artifact path and both failure outputs. A third re-dispatch spends context on a reviewer that cannot
finish; the honest reading at that point is that the artifact or the brief is the problem, and only a
human can say which.

---

## 2. Verdict-to-gate mapping

A `PASS` verdict is the answer to exactly one of three gates, and to nothing else:

| Gate | Skill and step | Payload the reviewer reads |
|---|---|---|
| Gate 1 — root cause confirmed | `investigate` Step 2 | the `<analysis-format>` block |
| Gate 2 — fix approach approved | `investigate` Step 4 | the `<fix-format>` block |
| Approval loop | `plan` Step 7 | the Step 7 summary and the plan files it names |

`REVISE` and `PARK` answer none of them. The gate stays unanswered, the bead does not advance, and
the producing worker stays stopped at exactly the step it stopped at.

**The orchestrator never overrules this mapping.** Not when it disagrees with the verdict, not when
the verdict looks harsh, not when another round would be cheaper than a park. An orchestrator that
can overrule its own quality control has no quality control — it has a second opinion from the party
with an interest in the run finishing. § 1 says the same thing about a reviewer that returned
nothing: no verdict is not an opening for the orchestrator's own opinion either.

### Routing a verdict back — the whole mechanic

The verdict is a file before it is an action: validate the reviewer's object with `validate()` from
`../scripts/validate_verdict.py`, write it to `{run}/verdicts/<bead-id>_r<round>.json`, and take the
action from `next_action(history)` over that directory sorted by round. The reviewer's own `verdict`
field never decides on its own — § 3 says why.

A `REVISE` then has to reach a worker that is no longer running. Every verdict this system has
produced arrived more than ten minutes after its producing worker settled — measured tier-2 passes
of 9m55s to 13m11s, against settlement-to-verdict gaps of 13m24s and 10m31s on the two rounds that
returned `REVISE` — while a harness retains a settled job leg for about five minutes. So the return
channel is not the job leg:

1. **Revive the worker by its agent id**, the id its dispatch row records in `worker`. Reviving is
   what carries its own history back; a fresh worker on the same brief re-does the round instead of
   revising it. Where the harness cannot revive, the round is a PARK, not a re-run.
2. **Hand it the verdict object and the round number**, and re-state the artifact path it was
   assigned. That path never changes on a revision: a second one orphans the first artifact and
   breaks its ledger row's link to its own output.
3. **Read the revision off the round's report file** — `{run}/reports/<bead-id>_r<round>.md` for an
   investigation, `{run}/reports/<first-bead-id>_plan_r<round>.md` for a plan, matching the path that
   lane's brief generator assigned. `../../_shared/autonomous-mode.md` § I requires the worker to
   write it before it returns. The file is the return; whatever the harness hands back is a
   convenience copy.
4. **Stamp the row at the moment you read it.** `returned` is the output of `date -u` taken then,
   never an artifact's or a report's mtime — `ledger.md`, § *Row format*.
5. **A report whose contract fields do not parse is not a return.** Treat it exactly as § 1 treats a
   reviewer that returned nothing: leave `returned` empty and re-dispatch at the same round.

A file inside the run directory is the carrier because it is the only one that works on all five
dispatch mechanisms `harness.md` covers, and the only one `discard` can reach.

---

## 3. Revision policy

1. **Hard classes park immediately, zero revision rounds.** Verdict classes `root-cause-unproven`,
   `requirement-invented`, and any stop-list hit → PARK on round 1. Revision cannot repair these.
   More rounds produce a better-argued wrong answer, and the worker begins writing toward the
   reviewer's phrasing rather than toward the evidence.
2. **Repairable defects get at most 2 rounds.** A missing citation, an absent section, an oversized
   phase, a missing locale list — these are repairable. Round 1 always unlocks round 2.
3. **A third round is unlocked only by convergence.** Round 2's defect set must be a *strict subset*
   of round 1's, at the same locations, with fewer members. New locations, or the same defect merely
   restated, ends the loop at PARK immediately rather than spending the cap. Round 4 never exists.
4. **PARK is a success outcome, not a failure.** The bead keeps its `needs-plan` status, gains a
   `needs-human` label intent, retains its artifact, and appears in the run report with the exact
   question a human must answer.
5. **Each round has its own report file.** Round 1's is the path the brief assigned —
   `{run}/reports/<bead-id>_r1.md` from `brief_invest.sh`, `{run}/reports/<first-bead-id>_plan_r1.md`
   from `brief_plan.sh`. Rounds 2 and 3 are `_r2` and `_r3` beside it, in that lane's own naming,
   named by the orchestrator when it revives the worker. One file per worker per round and never
   overwritten — the convergence comparison below is between two rounds, so round 1's report has to
   still be on disk when round 2's is read, and reading a plan's round 1 from the investigation
   lane's name would compare a plan against an investigation.

### Convergence is a set comparison, not an impression

Take the `location` field of every defect in round 1 and in round 2. Compare the two sets of exact
strings:

- round 2 ⊂ round 1, and round 2 is non-empty → **converged**, spend the third round.
- the sets are equal → the same defect restated → **PARK**.
- round 2 contains any location round 1 did not → **PARK**, even when the count went down.
- round 2 is empty while the verdict is not PASS → **PARK**; nothing converged, the reviewer just
  stopped naming locations.

Locations compare as exact strings after `strip()`. `x.md:12` and `x.md:40` are two locations, not
one. That is deliberate: an approximate comparison would let a reviewer drift a defect down the file
and still claim convergence.

`../scripts/validate_verdict.py`'s `next_action(round_history)` is this rule as code, and it is
authoritative. The orchestrator compares the reviewer's own `verdict` field against what
`next_action()` returns and follows the second. A reviewer that writes `REVISE` under a hard defect
class does not get a revision round; it gets a PARK and a schema error.

---

## 4. Defect-class table

| `defect_class` | Meaning | Rounds allowed | Outcome |
|---|---|---|---|
| `root-cause-unproven` | a link in the execution chain is not confirmable from the code, or the counter-hypothesis stands | 0 | PARK |
| `requirement-invented` | a plan step traces to neither the bead nor the investigation | 0 | PARK |
| `stop-list` | the artifact hit a standing prohibition from the autonomy contract | 0 | PARK |
| `repairable` | missing citation, absent section, oversized phase, missing locale list | ≤2, third only on convergence | REVISE, then PASS or PARK |
| `none` | no defects found | — | PASS |

Pick the class by the worst defect found, not by the most common one. One `requirement-invented`
step in a plan whose other twelve steps are clean is still `requirement-invented`.

`stop-list` means one of the eight items in `autonomy-charter.md` § 2. Name the item number in the
defect's `why`.

### The materiality bar — what may enter `defects` at all

A finding must be true **and** material. The test:

> If a competent worker executed this artifact exactly as written, would the result be wrong,
> incomplete, or built on an unproven cause?

If no, it is not a defect. It belongs in the reviewer's report prose, and `defects` stays empty.

This is structural, not a courtesy. `PASS` requires an empty `defects` array, so a true-but-immaterial
note written into `defects` is not an aside — it forces `REVISE`, bounces a correct artifact, and
spends one of the two rounds the policy allows. Calibration runs of this reviewer against two
human-approved artifacts produced `REVISE` on both, entirely from accurate but immaterial findings:
a background statistic that was off, and a "two places mention `X`" that missed a third mention in an
example that needed no change. Neither would have changed what the worker built.

Severity is consequence, not confidence:

| Severity | The executing worker would… |
|---|---|
| `critical` | build on a cause that was never proven, or on a requirement nobody asked for |
| `major` | build the wrong thing, or leave required work undone |
| `minor` | build the right thing, but be actively misled at a specific step by a wrong stated fact |

Findings below `minor` do not enter the object. The verdict is `PASS`, and the observations go in the
prose.

---

## 5. The verdict object

Emit exactly one JSON object matching `../scripts/verdict.schema.json`. No prose around it, no
preamble, no closing summary — the orchestrator pipes the object into `validate_verdict.py`, and
anything outside it is a parse failure that wastes the round.

Each validated object is written to `{run}/verdicts/<bead-id>_r<round>.json`, one file per round per
artifact. `next_action(history)` takes that directory's objects sorted by round — the history is a
file set, not an orchestrator's memory of the rounds it ran. Validate with `validate()` before
writing: an object that fails the schema is a wasted round, and a wasted round appended to the
history corrupts the convergence comparison in § 3.

The path is inside the run directory for two reasons, both operational. `discard` deletes a run by
deleting its directory, so a verdict written anywhere else survives the discard that was supposed to
erase it. And a resumed run reconstructs the round count from disk, so a history in `/tmp` — where a
live run put it — makes a resumed Wave 5 start again from round 1 against an artifact already twice
reviewed.

```json
{
  "verdict": "REVISE",
  "defect_class": "repairable",
  "defects": [
    {
      "severity": "major",
      "location": "project_plans/demo/investigations/x.md:42",
      "why": "The cited line does not contain the quoted call."
    }
  ],
  "confidence": 0.75,
  "round": 2
}
```

| Field | Rule |
|---|---|
| `verdict` | `PASS`, `REVISE` or `PARK` |
| `defect_class` | one row of § 4 |
| `defects` | empty exactly when `verdict` is `PASS`; non-empty for `REVISE` |
| `defects[].severity` | `critical`, `major` or `minor` |
| `defects[].location` | a file path with an optional `:line` suffix, e.g. `.../x.md:42` |
| `defects[].why` | one sentence, actionable — a finding a worker cannot act on is not a finding |
| `confidence` | a number in `[0, 1]` |
| `round` | the round number from the brief, an integer ≥ 1 |

Rules the schema enforces and a reviewer routinely trips over: `PASS` requires `defect_class: none`
**and** an empty `defects` array; `defect_class: none` is legal only with `PASS`; a hard class forces
`PARK`. Check your object before emitting it:

```sh
python3 triage/scripts/validate_verdict.py -   # object on stdin; 0 valid, 1 findings
```

`PARK` with `defect_class: repairable` is legal and is not a contradiction: it is what
non-convergence looks like. A single verdict cannot know the round history, so the schema does not
reject it — `next_action()` is what judges it.

---

## 6. Gate checklists

### Kind: `investigation`

1. **Reproduce the chain.** Open every file the artifact cites, at the cited line, and confirm the
   line says what the artifact claims. Any link you cannot confirm from the code itself is a defect;
   "plausible" is not "confirmed".
2. **Produce exactly one counter-hypothesis** — a different cause that would produce the same
   observed behaviour — and either refute it with evidence from the repository or fail the gate. A
   root cause that survived no attempt on its life has not been tested. One is the number: zero is no
   test, and a list of five is a survey rather than an attack.
3. **Check what was ruled out.** `investigate`'s `<analysis-format>` requires the alternatives the
   worker disproved. An empty or hand-waved "what was ruled out" is a defect.
4. **Check scope.** Does the approved fix touch files the execution chain does not justify? A fix
   reaching beyond the chain is a defect against the fix, not against the cause.
5. An unconfirmable link, or a counter-hypothesis left standing, is `defect_class:
   root-cause-unproven` → PARK.

### Kind: `plan`

1. **Forward coverage.** Every requirement stated in the bead and in the investigation maps to at
   least one implementation step. A requirement with no step is `repairable`.
2. **Backward traceability — the harder direction, and the one that matters here.** Take each step
   and ask where it came from. A step that traces to neither the bead nor the investigation is an
   invented requirement. This is the mechanical detector for this system's defining failure mode: a
   worker with no user to ask fills the gap with plausible fiction, and plausible fiction reads
   exactly like a good plan. A step with no source is `defect_class: requirement-invented` → PARK.
3. **Cited-fact check.** Where the plan asserts something about the repository — a file's length, a
   symbol's existence, a test's current behaviour — read it and confirm it.
4. **Stop-list.** Would executing this plan touch any of the eight items in `autonomy-charter.md`
   § 2? If so, `defect_class: stop-list` → PARK, naming the item number.

### Both kinds: cross-artifact overlap

Does this artifact overlap another artifact in the same run, or a plan already sitting in the
project's live `todo/` directory? Overlap is a defect, not a note: two plans editing the same files
are a merge conflict scheduled in advance. Report it with both paths in `location`.

---

## 7. PARK handling contract

PARK is a success outcome. Concretely, on a PARK:

- The bead **keeps** its `needs-plan` status. It is not closed, not failed, not reopened.
- A `needs-human` label intent is emitted **as text**. No worker and no reviewer touches the tracker;
  `promote.py` is the only writer.
- The artifact is **retained in staging** and never deleted. A human answering the question needs the
  work that produced it.
- The run report lists the bead with **the exact question a human must answer**, phrased as a
  question. "The root cause is unproven" is a summary of the defect; "Does the reader hold a second
  navigator reference after `onReaderReady`, or is `_navigator` the only one?" is the question. The
  first makes a human re-read the artifact; the second can be answered from where they stand.

A reviewer that parks has not failed. A reviewer that guesses a verdict to avoid parking has, and
worse than failing: it approves a gate nobody actually checked.
