# Autonomy charter: standing answers and the stop-list

A delegated triage worker cannot ask the user. This file is the lookup table that answers, in
advance, every user-facing question `investigate` and `plan` would otherwise raise — plus the
stop-list of subjects no standing answer covers.

It does not restate the contract. `../../_shared/autonomous-mode.md` states the overrides and their
reasoning; this file is the index a worker consults question by question. Read the contract first.

Three answer shapes appear in the table, and they are not interchangeable:

- **Decide** — take the stated answer and keep going. No report line needed beyond the artifact.
- **QC verdict** — present the gate payload, stop that thread, wait for an independent verdict
  (contract section A). Never self-approve.
- **PARK** — stop and return the exact question a human must answer (contract section F). Never
  guess, and never shrink the task until the question stops applying.

---

## 1. Decision table

| Skill | Question | Standing answer |
|---|---|---|
| both | Configuration — `skill.config.md` missing or incomplete | Decide: the brief supplies the values; never run the interactive setup flow. PARK if the brief omits one you need |
| investigate | Step 0 — missing expected behaviour, actual behaviour, repro steps, or logs | Decide: answer from the bead and the code. PARK if neither answers it — a repro you invented is not evidence |
| investigate | Gate 1 (Step 2) — is the root cause correct? | QC verdict; stop with the full `<analysis-format>` payload |
| investigate | Step 3 — which candidate fix? | Decide: the one the evidence supports; present the alternatives you ruled out inside the Gate 2 payload. A bead that lists candidate fixes is handing you the shortlist, not asking you to PARK — see the note under stop-list item 8 |
| investigate | Gate 2 (Step 4) — is the fix approach right? | QC verdict; stop with the full `<fix-format>` payload |
| investigate | Step 5a — where does the investigation file go? | Decide: the staging path from the brief, under the assigned filename. Never `{plans_dir}/{project}/{investigations_subdir}/`, never a `_v2` suffix of your own |
| investigate | Step 5d — write the bead's notes | Suspended. Emit nothing: the run derives the `investigation` record from its own ledger |
| investigate | Gate 3 (Step 6) — continue to `plan` now? | Decide: always stop. The orchestrator sequences the lane |
| plan | Step 1 — which project? | Decide: the brief names it. PARK if the bead spans projects (stop-list item 6) |
| plan | Step 2 — requirements, scope, motivation | Decide from bead + investigation + code together. PARK if underdetermined — inventing requirements is prohibited |
| plan | Step 3 — a plan for this topic already exists | Decide: update the existing plan. Never write a parallel one |
| plan | Step 5.2 — re-slice this phase? | Decide by threshold, no discretion: >8 steps, >5 unrelated files, any file past `{max_file_loc}` LOC, >1 feature module without justification, or an anti-pattern from `../../_shared/architecture-principles.md` |
| plan | Step 7 — how does the plan look? | QC verdict; stop with the Step 7 summary. Apply requested changes and re-present |
| plan | Step 7b — delegate the slice files to subagents? | Decide: no. A delegated worker writes its own slices; it does not spawn further workers |
| plan | Step 8a — tracker unconfigured | PARK. Never run `{tracker_cli} init` |
| plan | Steps 8b / 8c — create tasks, verify notes, flip the source bead | Suspended. Emit the `intent_records.WORKER_KINDS` records those steps would have run, notes preserved verbatim |
| plan | Step 9 — start executing now? | Decide: always "Not now" |

Anything not in this table and not in the stop-list is a question the contract did not anticipate.
PARK it and say so — a worker inventing a seventeenth standing answer is exactly the drift this
file exists to prevent.

---

## 2. STOP-LIST — always PARK

Eight subjects. Touching one is enough: the bead does not need to be *about* it. PARK the moment
your analysis or your plan would reach into one of these, and name which item fired.

1. **Database schema changes or data migrations** — irreversible against real data, and the
   rollback story is a human decision.
2. **Public API breaks** — the blast radius lives in callers this run cannot enumerate.
3. **Dependency major-version bumps** — the changelog, not the code, decides whether this is safe.
4. **Anything touching `main` or CI** — the workspace instructions forbid it outright, and a broken
   pipeline blocks everyone.
5. **Security and auth changes** — credentials, permissions, token handling, crypto. A plausible
   plan here is more dangerous than no plan.
6. **Cross-project changes** — a bead whose fix spans two repositories has two backlogs, two test
   suites, and no single owner in this run.
7. **Product or UX judgment calls** — what the user *should* see is not derivable from the code.
8. **Any bead whose own notes flag uncertainty about what is wanted** — the author already said they
   did not know. Answering for them is guessing with extra steps.

   **Item 8 is about the outcome, never the implementation.** A bead that is unsure whether the
   change is wanted, or what the correct behaviour would be, is a PARK. A bead that states the
   outcome and then weighs two ways to reach it — "fix directions to weigh: A, or B" — has settled
   what is wanted and is handing you a shortlist; that is an ordinary `investigate` Step 3 or `plan`
   Step 5 decision, made on evidence and reviewed at the next gate. Read the item this way in both
   directions: PARKing every bead that names alternatives would park most of the backlog, and
   deciding an outcome the author left open is the guess the whole stop-list exists to prevent.
