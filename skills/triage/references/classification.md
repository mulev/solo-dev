# Bead classification: which skill comes next

This file is the single definition of the triage routing rubric. Given an arbitrary
bead, it answers one question: **which skill runs next — `investigate`, `plan`, or
neither?**

Two halves, and they do different jobs:

- The **routing table** is mechanical. `triage/scripts/inventory.py` executes it in
  `classify(bead, notes)`, a pure function with no I/O. Run the script and you get
  the table's answer, with the reason recorded next to it.
- The **investigate-vs-plan rubric** is the judgment the table cannot make. It
  decides, inside the `investigate → plan` lane, whether the investigate step is
  actually needed or the bead can go straight to planning.

---

## 1. The routing table

| Bead state | Route | Reason recorded |
|---|---|---|
| status `needs-plan`, no `Investigation:` and no `Plan:`/`Slice:`/`Master:` | `investigate` (then plan, sequenced by the orchestrator) | `no investigation on record` |
| status `needs-plan`, notes carry `Investigation:` | `plan` | `investigation on record` |
| status `open`, notes carry `Plan:` or `Slice:` or `Master:` | `skip` | `already planned` |
| status `open`, no plan path in notes | `drift-report` | `open with no plan path` |
| bead is an epic, or a child of an epic, whose notes carry a plan path | `skip` | `owned by its master plan` |
| status `blocked`, `deferred`, `closed`, `pinned` | `skip` | `status: {status}` (`closed` never arrives — see precedence rule 1) |

Row order is not the deciding order. Precedence is explicit, and it is what the
tests assert:

1. **Terminal status wins over everything.** A closed epic is skipped as closed,
   not as an epic. **`closed` is reachable only through `classify()`, never
   through a run.** The roster query is `bd list --limit 0 --json`, and plain
   `bd list` omits closed issues — on any repo with history, `--all` returns
   dramatically more. So no closed bead ever reaches a manifest, and this rule
   is a property of the function rather than a case the backlog produces. The
   branch stays because `classify` is total over any input, and `--all` is
   deliberately *not* passed: it would drag every bead a project has ever
   closed through clustering and coverage scanning on every run, to route them
   all `skip`.
2. **Epic membership wins over status — but only with a plan path on record.**
   The master plan owns the bead, so triage does not re-plan a phase a plan
   already covers, and `has_plan` is the only plan-coverage evidence
   `classify` holds. An epic gains children two ways, and they are disjoint:
   `plan` Step 8b gives every phase a `Slice:`+`Master:` note at creation,
   while a followup parented under the workspace `AGENTS.md` Scope RULE
   carries no plan path because no plan covers it. Gated on `has_plan`, this
   row therefore never changes a route — it selects the more specific of two
   `skip` reasons, the same kind of function property rule 1's retained
   `closed` arm states. Ungated, it dropped every plan-less epic child out of
   triage while recording that a master plan owned it (`skills-viw`).
3. **A plan path wins over an investigation path.** A bead carrying both
   `Investigation:` and `Plan:` routes `skip`, not `plan` — the plan already
   consumed the investigation.
4. **An unrecognised status still gets a route** (`skip`, reason
   `status not routed in v1: {status}`). `classify` is total. "No bead is
   unroutable" is a property of the function, not of the backlog it happens to
   see today.

Drift beads — `open` with no plan path — are counted and reported. Nothing acts
on them in v1; the run exits `1` so the report is not silently ignored.

**Where the fields come from.** `bd list --limit 0 --json` is the roster, and it
is the only call that carries `parent` and `dependencies` — the two keys that
identify epic membership. `bd show <ids> --json` is the notes source; the `notes`
key is simply absent when a bead has none. Never drop `--limit 0`: bd's default
of 50 truncates a real backlog without saying so.

---

## 2. The investigate-vs-plan rubric

The table's first row sends a bare `needs-plan` bead into the `investigate → plan`
lane. That is the safe default, not a verdict. This rubric is what a human — or
the orchestrator's worker — reads before spending an investigation:

- `issue_type` `bug`, or a crash, or a test failure, or a title that **asserts a
  cause that is not yet proven** → `investigate`.
- `issue_type` `task` or `feature` whose title **is the whole specification** of a
  mechanical change → `plan` directly; skip the investigate step.
- Ambiguous → `investigate`. Over-proving costs one worker. Planning a fiction
  costs a plan, its review, and the execution that follows it.

The asymmetry is the whole point. An unnecessary investigation wastes one agent's
run and produces a document nobody needed. A plan built on an unproven cause
produces phases that implement the wrong fix, and the cost lands after the code
is written.

---

## 3. Worked examples

All three are real beads from the demo backlog, and all three arrive in the
`investigate → plan` lane with the same mechanical reason —
`no investigation on record`. The rubric is what separates them.

**`demo-7qm` — "Split integration_test/file_import_flow_test.dart (716 LOC) into
per-flow files" → `plan`.** The title is the entire specification: the file, its
size, and the shape of the result. Nothing about the change is unproven. There is
no cause to find, only work to sequence.

**`demo-y0k` — "Split the completion arm out of AudiobookPlaybackService
(301 LOC)" → `plan`.** Same shape: a named symbol, a named seam, a measured size.
A mechanical refactor whose title is its own spec.

**`demo-13xd` — the counter-example → `investigate`.** It carries file:line
evidence in its description *and* explicitly weighs two competing fix directions.
The cause is largely evident, so the temptation is to route it straight to `plan`.
It routes `investigate` anyway: choosing between two fix directions is precisely
what investigate's Gate 2 exists to do, and a plan that picks one arbitrarily
buries the choice where no gate will catch it.

**A rich description is not a proven fix.** The question is never how much the
bead says — it is whether the fix decision has already been made.

---

## 4. Source of truth

This file is the single definition of the routing rubric. The prose in the
workspace `CLAUDE.md` `[Beads]` block is a pointer to it, not a second copy — if
the two ever disagree, this file is right and the pointer is stale.

`triage/scripts/inventory.py` is the executable form of section 1. Seven files
execute or pin these rows, and a change in one alone is a defect:

- `triage/scripts/inventory.py` — `classify`, the rubric itself
- `triage/scripts/test_inventory.py` — at least one case per row, plus the precedence cases
- `triage/scripts/test_inventory_cli.py` — `REASONS`, the closed set of reason
  strings, asserted against a captured live backlog
- `triage/e2e/fixtures/beads.json` — at least one bead per row, each with its `expect` block
- `triage/e2e/fixtures/beads_clean.json` — the clean-testbed bead, carrying row
  1's reason in its own `expect` block, run through `classify` by
  `test_e2e_matrix.py::case_clean_sibling_bead_is_clean`
- `triage/e2e/suite_routing.py` — `ROUTING_TABLE` and the precedence assertions
- `triage/scripts/test_e2e_matrix.py` — the row and rule coverage maps, plus
  `case_expected_route_matches_classify`

Change the rubric here and in all seven together.

One more file follows a row without executing it: `triage/e2e/README.md`
records how the 20-bead corpus decomposes — nine beads behind these rows,
because three rows carry two each; two more that exist only for a precedence
rule, rules 1 and 2 being covered by beads already among the nine; and nine
wave beads. Adding or removing a row, or moving a bead between rows, changes
those figures, so correct them in the same edit.
