# Solo Dev

Agent skills for developers who ship alone.

Five workflow skills plus the doctrine they share. The point of the bundle is
not that an agent follows steps — it is that every claim it makes about your code
is checkable, and every gate it says it passed left an artifact behind.

## Install

```bash
npx skills add mulev/solo-dev
```

Works with Claude Code, Cursor, Codex, GitHub Copilot, and the other agents that
support the skills format. Also installable as a Claude Code plugin from
`.claude-plugin/marketplace.json`.

Install `_shared` alongside whichever workflow skills you take. It has no
workflow of its own — it holds the architecture principles, the validator
system, the conduct doctrine, and the runner that the others read by
relative path. `npx skills add mulev/solo-dev --all` gets everything; picking
individual skills without `_shared` leaves those references dangling.

## What's in here

Three of them form a pipeline:

```
investigate  →  plan  →  execute
```

**`investigate`** does root cause analysis. The agent traces the full execution
chain and cites evidence for every claim — no "probably", no "likely", no
guessing. Two hard gates before anything changes: you confirm the root cause,
then you approve the fix design. It writes the confirmed outcome to a file, so
planning can run in a fresh session with a full context budget instead of
inheriting a spent one.

**`plan`** turns work into vertical slices. Each slice is a self-contained
deliverable with its own tests, implementation, integration tests and docs.
Multi-phase plans split into a master plan plus one file per slice, so the agent
loads one slice at a time. Before a plan is approved, every component in it has
to pass a decomposition gate: a single-sentence responsibility with no "and", a
projected size, at least two callers or its own test, and an enumerated coupling
list.

**`execute`** runs one phase per invocation: write the test, watch it fail,
implement, watch it pass. Then three things have to be true before the phase can
close — an architecture gate with every row PASS, a validator ledger whose
provenance header verifies, and a plan file updated on disk. A bare epic ID is
the exception: it asks whether to dispatch the whole epic to workers or run a
single phase.

Two more sit beside the pipeline rather than inside it.

**`triage`** points the pipeline at a whole backlog and works through it on its
own. It investigates the issues nobody has proved a cause for, then plans all of
them. The gates that would normally wait for your answer are answered by an
independent reviewer instead, never by triage's own reading of its own work. It
stops in two places on purpose, which is what makes it safe to leave running: it
never executes code, and it never promotes. Everything a run produces lands in a
staging directory belonging to that run, so a run you don't like is one command
to delete and leaves nothing behind.

**`marketer`** is a research-first marketing toolkit — app store and search
optimisation, competitor analysis, pricing. It classifies how confident each
claim is and names the method that would validate it, rather than recommending
and hoping.

## Quick reference

| Skill | Trigger phrases |
|-------|-----------------|
| `investigate` | "debug", "investigate", "why does this happen", "find the bug" |
| `plan` | "plan", "create a plan", "plan this feature" |
| `execute` | "execute", "next task", "start implementing", "what's next" |
| `triage` | "triage the backlog", "work through the open issues" |
| `marketer` | "ASO", "SEO", "competitor research", "pricing strategy" |
| `_shared` | never — support files, read by the others |

## What these skills actually enforce

**Tests before implementation.** The plan template has the TDD order baked in
and `execute` follows it. Skipping is allowed only where it is genuinely
impossible, and the reason goes in the plan.

**Nothing ships on an unrun check.** Add a `validators.conf` to your repo naming
which commands run at which stage, copy the `validate` runner to the repo root,
and `execute` runs the stage before every phase exit and once over the finished
tree. The runner stamps each run with a provenance header, so `validate verify`
can tell you three things a date could not: whether every row passed inside that
run, whether the code has moved since, and whether the stage gained rows
afterwards. A ledger written by hand or copied from an earlier phase fails.

The corollary, and the rule that took a real outage to learn: **a check that did
not run is a failed check.** "No device found", "no JDK", "wrong OS" are
failures, not skips — the command must exit non-zero, because the runner sees an
exit code and nothing else. `_shared/validators.md` has the full account,
including how to write a positive control for a check that passes identically
whether it ran or never loaded.

**Architecture gates at design time and at file level.** Size, single
responsibility, duplication, coupling, testability, and re-export shims are
checked on every changed file, with the automated half scripted. Crossing a
threshold triggers a four-part Meaningfulness Test rather than a mechanical
split, and a split performed only to make a number pass always fails.

**No pre-existing-condition exemption.** A violation that was already there
still blocks the phase.

**Nothing happens without your sign-off.** Root cause confirmation, fix design
approval, plan structure, epic scope — the agent stops and asks through the
host's structured-question tool at each decision point. A turn that ends on gate
prose with no question attached has asked nothing, and the skills say so
explicitly. A cancelled question counts as the conservative answer, never as
permission to continue.

## Configuration

Skills that need local settings ship with `skill.config.example.md`. Either
invoke the skill and follow the setup prompts, or copy the example to
`skill.config.md` and edit it. That file is gitignored, so your paths and tool
choices stay yours.

Defaults assume no issue tracker (`enabled: false`) and no plan mirroring. The
tracker fields are shaped for [beads](https://github.com/steveyegge/beads) but
every command goes through a configurable CLI name, so any tracker with a
comparable command surface works. Turn it off and the plan files stand alone.

## Portability

The skills resolve their host at runtime rather than assuming one. The
structured-question tool, the skill-invocation mechanism, and the subagent
mechanism each have a documented resolution ladder covering Claude Code, Codex
CLI (both interactive and `codex exec`), MCP elicitation, omp, and a plain-text
fallback — because a gate that silently no-ops on the wrong host is worse than
no gate.

Stack-specific material is confined to `validators.conf` recipes, which are
examples to copy, not requirements. Nothing in the workflow assumes a language.

## License

MIT
