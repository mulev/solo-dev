# Architecture Principles

Every plan and every executed phase must produce or extend a **modular monolith** — one deployable application composed of small, atomic, single-purpose modules. These are enforcement criteria, not aspirations.

The plan skill enforces these rules at the design level: a plan that schedules a 600-LOC god-object cannot be approved.
The execute skill enforces them at the file level: a phase ends with a green test suite **and** a clean architecture gate, or it does not end.

---

## Core principles

### Single Responsibility (SRP)
One module = one logical action. If the purpose can't be described in a single sentence without "and", it has more than one responsibility — split it. At plan time, split before drafting steps. At execution time, extract the second responsibility into its own module before closing the phase.

### Don't Repeat Yourself (DRY)
Before adding a new helper, search for an existing one. Reuse over re-create. The plan skill's exploration step (Step 4) surfaces candidates; the execute skill greps before adding helpers. Two near-duplicate paths are acceptable only when they are likely to diverge — say so explicitly.

### Keep It Simple (KISS)
Default to the most direct implementation. No frameworks, no patterns, no abstractions until a concrete second use case exists in the codebase today.

### You Aren't Gonna Need It (YAGNI)
Plan-time: requirements only. Execution-time: plan only. No "future hooks", no extensibility points, no parameters with no caller, no configuration toggles for behaviors no one asked for. If the plan specifies them, push back before coding.

### Modular monolith
One binary, decomposed by feature/domain — not by horizontal layer. Each module owns its data, its tests, and its public API. Cross-module access goes through that public API. Do not introduce or grow `services/`, `repositories/`, `controllers/` folders that cut across features.

### Testability
Every module is testable in isolation. Dependencies enter through constructors / parameters, not globals. If a module is hard to test (singletons, hidden state, private collaborators), redesign — do not patch around it with mocks-for-statics.

---

## Smell thresholds

These numbers are **signals to investigate, not gates to pass**. Crossing one triggers the Meaningfulness Test below — never a mechanical split. The configured `{max_file_loc}` value (default 300) governs the file-length signal.

| Signal | Threshold | What it usually means |
|--------|-----------|----------------------|
| File length | >`{max_file_loc}` LOC (excluding comments and blank lines) | Possibly multiple responsibilities — apply the Meaningfulness Test before splitting |
| Function length | >40 LOC | Likely nested concerns — extract only if the extractee earns its own name and its own test |
| Cyclomatic complexity | >10 per function | Replace nesting with early returns or polymorphism, not extraction-for-extraction's-sake |
| Cross-module coupling | references to >5 distinct foreign feature/domain modules from this file's behavior | Module spans too many domains — split by responsibility, not by relocating imports |

Coupling is measured by the **set of foreign feature/domain modules this file's behavior actually touches**, not by counting `import` lines. Moving imports through a re-export shim, barrel file, or dependency-aggregator file does not reduce coupling — it hides it. Such moves are anti-patterns (see below) and must be reverted.

When a component legitimately exceeds a threshold (generated parser, exhaustive enum mapping, cohesive state machine that any split would worsen), record a `**LOC waiver:**` (or `**coupling waiver:**`) with one-sentence reasoning and the alternatives considered. A waiver is not a failure — it is the correct outcome when the cohesive form beats every candidate decomposition.

**Two file kinds are outside the LOC signal entirely: shell runner scripts and prose.** A test/build runner is a sequence — parse arguments, resolve the environment, then one section per target — and sharding it into sourced fragments buys a smaller number and a worse script. Documentation pages are read top to bottom by humans, and splitting them breaks links. Do not measure either against `{max_file_loc}`, do not open a Refactoring Round for them, and do not write a waiver paragraph each time one grows: note the length in passing if it matters and move on. A little duplication between sibling runners is likewise accepted — they are read one at a time.

---

## Meaningfulness Test

Before any split — at plan time or during a Refactoring Round — every new module must satisfy **all four** conditions. If any fails, do not split; take a waiver.

1. **Independent name** — describes a single concrete domain action. Forbidden: `*_dependencies`, `*_imports`, `*_helpers`, `*_utils`, `*_common`, project-local `*_shared`, `index` used as a barrel, or any noun that just echoes the only parent file (e.g. `book_service_dependencies` for parent `book_service`).
2. **Plural callers OR independent test** — imported by ≥2 unrelated callers, OR carries its own behavior-level test that exercises it without going through the parent. A re-export smoke test does not count.
3. **Reduces real coupling** — the parent's set of transitively-reachable foreign feature modules shrinks after the split. Relocating imports does not count; behavior must move.
4. **Survives the inline-back test** — mentally inline the new module into its parent. If the parent does not become harder to reason about, the split was cosmetic — do not perform it.

Single-caller satellites with no independent test are the dominant smell. Inline them on sight.

---

## Component decomposition

Every phase MUST list its components before listing implementation steps. A component is the smallest atomic unit — typically one file, one class, or one function group with shared state.

For each component, capture:

- **Name** — module/file path (must satisfy Meaningfulness Test #1)
- **Responsibility** — one sentence, no "and"
- **Public API** — the symbols other modules will import
- **Callers** — list ≥2 unrelated callers, OR explicitly mark `single-caller + independent test` and name the test file
- **Foreign modules touched** — feature/domain modules the behavior reaches (the coupling enumeration), not raw import lines
- **Projected LOC** — under `{max_file_loc}` (or note the waiver and the alternative considered)
- **Test approach** — how it is unit-testable in isolation; if tests need extensive setup or globals, the design is wrong

If a component listing requires "and", projects LOC over the limit, touches >5 foreign modules, or has a single caller without an independent test — apply the Meaningfulness Test. Either fold it back into its caller, or split further so each piece earns independent existence. Do not list a component that fails the test.

---

## Anti-patterns

Reject during planning; refactor on sight during execution:

- **God objects/files** — anything named `*Manager`, `*Helper`, `*Util`, `*Service` without a concrete domain prefix. Force a concrete responsibility into the name; rename or split.
- **Horizontal layers** — `services/`, `repositories/`, `controllers/` folders that group by mechanism instead of feature. Group by feature/domain instead.
- **Premature abstraction** — generic `<T>` types, strategy patterns, factory hierarchies introduced before a second concrete case exists today. Inline until the second case appears.
- **Hidden state** — singletons, static mutables, module-level state. Replace with injected dependencies.
- **Pass-through wrappers** — modules that exist only to forward calls without adding behavior. Inline them.
- **Parallel hierarchies** — when changing module A always requires a matching change in module B, fold them into one module.
- **Speculative parameters** — function arguments with no current caller. Remove until the caller exists.
- **Catch-all files** — `utils.dart`, `common.py`, `helpers.ts`. Move each helper next to its single user or into a focused, named module.
- **Re-export shim** — file whose body is overwhelmingly `export` / re-export / barrel statements (≥80% of non-blank, non-comment lines), created to drop a parent file's import count. Always FAIL the gate. Inline back into the parent and take a coupling waiver if the parent legitimately needs the imports.
- **Barrel index** — `index.{ts,js,dart}` (or equivalent) introduced to collapse multiple imports into one for the sole purpose of dropping a coupling number. Same fix as re-export shim.
- **Single-caller satellite** — module imported by exactly one parent and tested only through that parent. FAIL unless the extractee carries an independent behavior-level test. Inline back.
- **Rename bypass** — renaming `*Manager` / `*Helper` / `*Util` to a domain noun without removing the god-object behavior. The check is responsibility count, not the name.
- **Lockstep pair** — two modules where every change to A requires a matching change to B. Fold them into one.
- **Metric-laundering split** — any split performed to make a number pass without changing the system's actual coupling, cohesion, or testability. Always FAIL.

---

## Design-time application (plan skill)

| Plan step | What to do |
|-----------|------------|
| Step 4 (Explore) | Map existing module boundaries. Note feature/domain folders. Locate reusable helpers (DRY). Identify the natural module home for new code. |
| Step 5 (Structure) | Place each phase's deliverables into existing or new feature modules. Reject phases that span unrelated modules — they are not vertical slices. |
| Step 5b (Re-slice) | Add architectural smells to the re-slice triggers: a phase that grows a single module past `{max_file_loc}`, or touches 3+ feature modules, **must apply the Meaningfulness Test** before splitting. A re-slice that produces single-caller satellites or re-export shims is rejected. |
| Step 5c (Decompose) | Produce the Component Decomposition table for every phase. Every new component must pass the Meaningfulness Test (independent name, plural callers or independent test, real coupling reduction, survives inline-back). Components that fail the test are folded back before the plan exits self-review. |
| Step 6 (Self-review) | Run the Architecture self-review checklist below. Fix every violation. |
| Step 8 (Tasks) | Tracker task descriptions reference the slice file's Component Decomposition — do not duplicate it. |

---

## Runtime application (execute skill)

Run the architecture verification gate as Step 2.3 of execute, after the simplifier (Step 2.2) finishes and before format (Step 2.4). The gate produces a **required artifact** — the `## Architecture Gate Results` block in the working file. No artifact, no phase exit. See `../execute/references/update-format.md` (Adding the Architecture Gate Results) for the block template.

**No pre-existing-condition exemption.** Every file in `git diff --name-only` is subject to all six checks against its current state. A violation introduced before this phase is not grounds to skip or waive it — open a Refactoring Round and fix it. "It was already there" is never an acceptable gate result.

For every file in `git diff --name-only` for this phase, run the six checks below and emit one banner line per file. The banner is captured into the working file alongside the results table.

### Banner format (one line per file)

```
[arch-gate] file={path} LOC={status} SHIM={status} DEPS={status} SRP={status} DRY={status} TEST={status}
```

Each `{status}` is `PASS` or `FAIL(<reason>)`. Automated checks (LOC, SHIM) come from the helper script below; DEPS, SRP, DRY, TEST are model/human judgments — record the one-sentence reasoning (and for DEPS, the foreign-module enumeration) in the results block, not the banner.

### Helper script (LOC + SHIM)

```
python3 {skills_dir}/execute/scripts/run_arch_gate.py <file> --max-loc {max_file_loc}
```

The script emits the banner and exits non-zero if LOC or SHIM fail. Run it on every changed file. SHIM detection flags any file whose non-blank, non-comment lines are ≥80% `export` / re-export statements — the canonical metric-laundering pattern. If the script does not cover the language (no import or export pattern), do the LOC count manually with `wc -l` minus blanks/comments and report `SHIM=MANUAL` after a visual inspection.

### Six checks

1. **LOC check** — run helper; on FAIL apply the Meaningfulness Test. If every candidate split fails the test, record a `**LOC waiver:**` with one-sentence reasoning and pass the row. Do not split for the sake of the number.
2. **SHIM check** — helper flags any file whose non-blank, non-comment lines are ≥80% re-export statements. On FAIL inline the file back into its parent and take a coupling waiver if needed. No exceptions — re-export shims are always wrong.
3. **SRP check** — describe the file's purpose in one sentence. If "and" is required, apply the Meaningfulness Test before splitting. Record the sentence.
4. **DRY check** — for each new helper, run `rg '<helper-name>'` and `rg '<near-synonym>'` across the project. If a near-duplicate exists, FAIL — replace your helper with the existing one and re-run tests. Record the grep terms.
5. **Coupling (DEPS) check** — enumerate the foreign feature/domain modules this file's behavior touches. Read the code; do not just count `import` lines. On FAIL (>5 distinct foreign modules) split by responsibility — never by relocating imports into a shim. Record the enumeration in the results block.
6. **Testability check** — confirm the file's tests run without global setup, static patching, or singleton resets. On FAIL redesign with constructor-injected dependencies. Record the test strategy.

If any check FAILs, treat the violation as a Refactoring Round (see `../execute/references/update-format.md`). Do not flip the phase status until every changed file's row in the results table is PASS.

| Execute step | What to do |
|--------------|------------|
| Step 2.2 (Simplify) | If the `{code_simplifier}` spawn fails or config is empty, apply the simplification checklist locally and record the skip in Step 2.3's Companion-skill status line. A policy rule is never the trigger — the skill's own invocation authorizes the agent. |
| Step 2.3 (Architecture Gate) | Run the gate on every changed file. Capture each file's `[arch-gate]` banner. Write the `## Architecture Gate Results` block into the working file. Required artifact — phase cannot exit without it. |
| Step 2 (Refactoring Round) | If any row is FAIL, open a Refactoring Round in the working file, perform the split/inline/extract, re-run the changed tests, then regenerate the gate block from the post-refactor file set. |
| Step 3.0 (Fail-closed precondition) | Verify the working file contains the `## Architecture Gate Results` block with **Overall: PASS** before any commit, status flip, or tracker close. |
| Step 3 (Update plan) | When recording Files Created/Modified, include the LOC count. Flag any file under a `**LOC waiver:**`. |
| Step 4 (Bug Round) | Architectural violations are tracked as Refactoring Rounds, not Bug Rounds. Bug Rounds are for failing tests. |
| Step 5 (Finalize, hard tier) | Re-run the gate on the entire `git diff --name-only` for the execution, append/update a final-sweep `## Architecture Gate Results` block, and confirm Overall: PASS before format + final test suite. |

---

## Architecture self-review checklist (plan)

Run this as part of the plan skill's Step 6 self-review. Every item must pass before approval.

- [ ] Each phase has a Component Decomposition section
- [ ] Every listed component has a single-sentence responsibility (no "and")
- [ ] Every component's projected LOC ≤ `{max_file_loc}` (or has a `**LOC waiver:**` note)
- [ ] Every component touches ≤5 foreign feature modules (or has a `**coupling waiver:**` note); coupling is enumerated, not import-line-counted
- [ ] Every new component passes the Meaningfulness Test (independent name, ≥2 unrelated callers OR independent test, real coupling reduction, survives inline-back)
- [ ] No component is a re-export shim, barrel index, dependency aggregator, or single-caller satellite
- [ ] No new horizontal-layer folders introduced (no new `services/`, `utils/`, etc.)
- [ ] No new file named `*Manager`, `*Helper`, `*Util` without a concrete domain prefix; no rename-bypass of existing god-objects
- [ ] Every reusable helper checked for existing equivalents (DRY)
- [ ] No abstractions introduced without a second concrete caller (YAGNI)
- [ ] No speculative parameters, hooks, or extensibility points
- [ ] Every component is testable in isolation — dependencies are injectable
- [ ] Each phase touches one feature module, or explicitly justifies multi-module scope

---

## Architecture verification checklist (execute)

Run after the simplifier and before marking the phase complete. Every item must pass.

- [ ] Every changed file ≤ `{max_file_loc}` LOC (or has a `**LOC waiver:**`)
- [ ] Every changed file's purpose fits in one sentence with no "and"
- [ ] Every new helper checked against existing helpers (DRY)
- [ ] Every changed file's coupling enumeration recorded (foreign feature modules its behavior touches) and ≤5 (or has a `**coupling waiver:**`)
- [ ] No file in this phase is a re-export shim (≥80% export-only lines), barrel index, or dependency aggregator
- [ ] No file in this phase is a single-caller satellite without an independent behavior-level test
- [ ] Every split performed in this phase passes the Meaningfulness Test — none was performed solely to drop a metric
- [ ] No new horizontal-layer folders created
- [ ] No new file named `*Manager`, `*Helper`, `*Util` without a concrete domain prefix; no rename-bypass
- [ ] No abstractions added without a second concrete caller (YAGNI)
- [ ] No speculative parameters, hooks, or extensibility points
- [ ] Every changed file's tests run without global setup or static patching
- [ ] Phase touches one feature module, or the plan explicitly justifies multi-module scope
