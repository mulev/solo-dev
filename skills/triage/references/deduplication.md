# Deduplication

`triage/scripts/dedup.py` runs once, between the inventory and the first
investigation. The plan-corpus half of its work — deciding which plan files
already cite a bead, and how strongly — lives beside it in
`triage/scripts/plan_coverage.py`, because scanning a documentation corpus
is a different job from clustering a backlog. It is the only place in the pipeline where deduplication can
still save anything: after planning starts, the budget for the duplicate has
already been spent.

Its job is to reduce the routed manifest to one representative per duplicate
cluster. It does not decide what a duplicate is.

---

## 1. The three sources

The script unions three independent signals over the manifest's **spend set** —
the beads routed `investigate` or `plan`. A bead routed `skip` is already out of
the run, and a `drift-report` bead is a reporting line, not work to schedule;
neither is worth a judge's attention.

**Mechanical similarity.** `bd find-duplicates --method mechanical` tokenizes
titles and descriptions and computes Jaccard similarity between every pair. The
script filters the result to pairs whose ends are both in the spend set, then
again by threshold, so a lowered `bd` default cannot leak pairs past the gate.

**Plan coverage.** A walk of `{plans_dir}/{project}/todo/` **and**
`{plans_dir}/{project}/done/`. Both, always: work that shipped last month covers
a bead exactly as thoroughly as work that is queued, and scanning only `todo/`
is how a closed problem gets planned a second time.

**Explicit tracker links.** Any two spend-set beads joined by a `duplicate-of`
or `discovered-from` edge pair up regardless of similarity. The tracker already
said they are related; a score cannot overrule that. Two beads with no shared
vocabulary at all still cluster if an edge joins them.

The three feed one union-find pass. A cluster records every source that
contributed to it, so `sources: ["dependency", "mechanical"]` is a stronger
candidate than either alone.

---

## 2. Why threshold 0.35

`bd`'s default is 0.5. This gate runs at **0.35**, and the reason is the cost
asymmetry rather than any belief that 0.35 is accurate.

Output goes to a judge agent, not to a deletion. A false positive therefore
costs one paragraph of reading. A missed duplicate costs a full investigation
plus a full planning run on a problem already being solved elsewhere. Recall is
worth an order of magnitude more than precision here, so the threshold sits
below the point where precision is respectable.

The live demo run makes that concrete: at 0.35 the five mechanical pairs were
all OPDS-subsystem neighbours, and a judge reading them will very likely rule
every one `distinct`. That is the gate working as designed, not failing.

**`--method ai` is unavailable and is never used.** This machine has no
`ANTHROPIC_API_KEY` and `bd config get ai.api_key` reports it unset. Mechanical
is the only supported method. If semantic comparison is ever wanted it is a new
phase with its own credential story — never a fallback branch inside this
script.

---

## 3. Citation strength: what may retire a bead unattended

Coverage is the one source that can remove a bead from the run rather than
merely group it, so it is held to a higher standard than the other two.

Strength is a property of the **(line, bead) pair**, never of the line on its
own. `citation_form(line, bead_id)` asks how strongly this line claims to own
*this* bead, so one line can be strong for one ID and weak for every other ID
printed on it.

| Form | Example | Strength | Effect |
|---|---|---|---|
| `beads-task` | ``**Beads task:** `demo-7k1` `` | strong | `action: "drop"` |
| `beads-table` | ``\| Not this epic \| `demo-87w` \| … \|`` | weak | `action: "review"` |
| `bare-id` | ``Filed as `demo-y0k` rather than smuggled in.`` | weak | `action: "review"` |

`**Beads task:**` is the plan skill's ownership field: a plan file writing it is
declaring which bead it implements. That is a structural claim, and it is the
only one strong enough to retire a bead with nobody watching.

It declares ownership of exactly **one** bead — the ID immediately after the
field, with only markdown decoration between. Everything past that ID is prose,
and prose is never an ownership claim however strong the line it sits on. On

```
**Beads task:** demo-abc (epic) — supersedes demo-def, which this plan replaces
```

`demo-abc` is `beads-task` and drops; `demo-def` is `bare-id` and goes to
review. Reading the whole line instead — matching the field anywhere on it and
the ID anywhere on it as two unrelated questions — made `demo-def` inherit the
field's strength, and a real, unplanned bead left the run with no report line.

A Beads **table** row is not, and the live corpus is unambiguous about why.
Those tables list de-scoped and discovered work beside work the plan owns, and
the column that separates them is free prose — `| Not this epic |`,
`| Discovered (de-scoped) |`, `| Known residue (planning) |`, `| Review |`. No
mechanical rule tells those from ownership. Measured on the demo corpus,
reading table rows as ownership dropped **7 of 9** real beads, every one of
them cited by a plan that had explicitly pushed it out of scope.

So the drop rule is narrow on purpose, and everything else becomes a section in
the judge brief. Under-dropping costs a paragraph; over-dropping silently
cancels work nobody asked to cancel.

### Matching the ID itself

A bead ID is matched exactly, with boundaries that reject four specific
near-misses seen in the real corpus:

- `demo-lproj-2026` is not a citation of `demo-lproj` — no trailing
  `[0-9A-Za-z_-]`.
- `demo-g65.3` is not a citation of its parent `demo-g65` — no trailing
  `.<digit>`; the child is a different bead.
- `/project_plans/demo-site/todo/x.md` is not a citation of a bead called
  `demo-site` — no leading `/`, because a path segment is never an ownership
  claim.
- A second ID further along a `Beads task:` line is not what the field names —
  the ID must be the first token after it. This is the only one of the four
  that was losing beads rather than merely mismatching them: the other three
  fail to *find* a citation, this one manufactured a strong one.

These boundaries and the citation grammar live in `plan_coverage.py` and are
tested on a fixture tree with no tracker and no subprocess.

Sibling project trees are out of reach for the same reason: the walk roots at
`{plans_dir}/{project}/`, an exact path join, so scanning `demo` never
descends into `demo-site`.

---

## 4. The representative rule

Every cluster names one bead to carry the work. Four tiers, applied in order,
first tier that leaves exactly one bead wins:

1. **Carries an `Investigation:` path in its notes.** Its work is furthest
   along, so planning it wastes the least.
2. **Lowest priority number.** P0 beats P3. A missing or non-integer priority
   sorts last, never ahead of a real one.
3. **Oldest `created_at`.** The original report, not the re-report.
4. **Lexicographically smallest bead ID.**

Tier 4 is load-bearing, not decorative. Without it, dict iteration order can
name a different representative on a second run, and a resumed run then plans a
bead the first run had deduped — paying for the duplicate anyway, after
correctly identifying it. Rerun determinism is what makes the run resumable.

---

## 5. Propose versus decide

**The script never rules on sameness.** Every cluster it writes carries
`verdict: "candidate"`, and no code path in `dedup.py` writes any other value —
a test asserts that against the source text.

The reason is a limitation, honestly stated: Jaccard similarity over titles
cannot separate *same bug* from *same subsystem*. "OPDS download stalls on
redirect" and "OPDS download shows no progress" score nearly identically whether
they are one bug or two. A script that ruled on that would be guessing with a
number attached.

| Who | Decides |
|---|---|
| `dedup.py` | which pairs are worth a human-grade look, who the representative would be, what the covering plan is |
| the Wave 1 judge agent | whether each candidate pair is actually the same problem, and whether a citing plan actually covers the bead it cites |

**`review` is an instruction, not a note.** `coverage_action` returns it for every weak citation, and
the judge owes a `covered` / `not-covered` line for each one. The first live demo run flagged nine
beads and answered none: four were cited by `demo_fix_opds_widget_tests_real_db`, and a full run
would have investigated and planned all four from scratch with no step ever comparing the result
against the plan that already covered them. Under-dropping is supposed to cost a paragraph — it cost
a paragraph nobody read. `plan_coverage.validate_coverage` refuses an incomplete answer and
`plan_coverage.skipped` is what Wave 1 acts on.

The handoff artifact is **`judge_brief.md`**, written beside the manifest. One
section per candidate cluster carrying both beads' IDs, titles and full
descriptions, the source and score, the proposed representative and its reason,
and a ruling line to fill in — plus a closing section listing every covered
bead with its citing line.

**A ruling is a partition, not a verdict.** Every member of a cluster lands in
exactly one group and each group carries its own verdict, because clustering is
loose on purpose: the threshold is 0.35, and the first live demo run put four
beads in one cluster at 0.468 on the strength of the word "OPDS". Loose
clustering is only cheap if the judge can answer "these two are the same, those
two are not". With one verdict per cluster the only safe answer to a mixed
cluster is to keep everything, so a real duplicate sitting inside a mostly
distinct cluster is never found. A cluster ruled one way collapses to a single
group, so the common case is unchanged.

`cluster_ruling.py` validates the partition and reads the drops off it. A
member ruled twice, ruled not at all, or a `duplicate` group with no
representative is a malformed ruling that goes back to the judge — it is an
incomplete answer rather than a judgment the orchestrator may complete itself. It is ready to dispatch with no further assembly.
The script writes the file; it dispatches nothing. Phase 9 wires the judge and
is what turns a `candidate` into a `duplicate` or a `distinct`.

Keeping the model out of the script is also what makes this phase testable:
every function here is pure, or a pure function of files plus read-only `bd`
queries.

---

## 6. Exit codes and the write-back contract

| Code | Meaning |
|---|---|
| 0 | no clusters, no covered beads — the manifest gains only empty `clusters` and `covered` |
| 1 | clusters or covered beads found — findings written back, `judge_brief.md` emitted |
| 2 | usage or environment error: missing `--manifest` or `--plans-dir`, unreadable manifest, unknown flag, non-numeric threshold, unresolvable project, `bd` missing or failing |

Exit 2 is **never** produced by bad input data. A manifest with zero beads, or
with nothing in the spend set, is a legitimate answer and exits 0 — it does not
even invoke `bd`.

Writes are strictly additive. `dedup.py` never rewrites a field the inventory
owns — not `route`, not `reason`, not a bead record. It adds two top-level keys,
`clusters` and `covered`, and a `dedup` object on the covered beads' entries:

```json
{"dedup": {"action": "drop", "covered_by": "/abs/.../done/opds_retry.md"}}
```

Acting on `action: "drop"` — removing those beads from dispatch — is Wave 1's
job in Phase 9, not this script's. Keeping the write additive is what lets the
inventory's schema test stay a one-liner.

The inventory's manifest does not carry `notes`, `created_at`, `description` or
`dependencies`, and three of those are needed here. The script re-reads them
with one `bd list --limit 0 --json` and merges them in memory only; the manifest
entry on disk is never enriched. That keeps the inventory the single owner of
the manifest's bead schema.

---

## 7. The late duplicate check in Phase 8

Phase 8 runs a **second, later** duplicate check on a different signal: two
beads whose approved work has identical footprints are the same bug, whatever
their titles said. It exists because this phase compares words and Phase 8
compares plans.

A duplicate that Phase 8 catches is therefore **not** a defect in this phase. It
is the intended second net, positioned where a signal exists that could not
exist here — a bead has no footprint until someone has planned it. Do not read a
Phase 8 finding as evidence that the threshold here is wrong.
