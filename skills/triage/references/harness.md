# Harness plumbing: asking, and invoking a companion skill

Both are cold path for triage. A run asks the user once at most — an escalation nothing else
answers — and companion skills are invoked only inside worker dispatch, which Waves 2 and 4
already specify. `triage/SKILL.md` carries the rules; the resolution ladders live here.

## Asking the user

Every question you ask the user MUST go through the host's structured-question tool. Plain-text
questions are a last-resort fallback only.

**Tool resolution (try in order, first hit wins for the session):**

1. **Claude Code** — `AskUserQuestion`. Deferred tool. Load its schema once per session:
   ```
   ToolSearch(query="select:AskUserQuestion", max_results=1)
   ```
   If the schema loads, call `AskUserQuestion` directly for the rest of the session.
2. **Codex CLI (interactive TUI)** — `ask_user_question` (preferred, structured single/multi-choice)
   or `request_user_input` (free text). Native, no loader. If callable, use it.
3. **MCP elicitation** — if any connected MCP server exposes `elicitation/create`, use it (form mode
   with `requestedSchema` for structured choices).
4. **omp (Oh My Pi)** — `ask`, native, no loader. Emit it as the only tool call in its message; the
   runtime runs it exclusively. Cancellation raises `ToolAbortError`; headless runs have no `ask`,
   so use 5 there.
5. **Fallback** — clearly-formatted numbered plain-text question, then wait for the user's reply.
   Use only when 1–4 are unavailable (e.g. `codex exec` non-interactive runs strip native question
   tools).

Verify resolution every session — never assume the prior choice still applies. Batch up to 4
questions per call. Provide likely answers as options; the user picks "Other" for custom input.

**Ask in the same message.** Attach the question call to the message carrying the prose. A turn that
ends on a question in prose has asked nothing.

**Treat a cancelled or timed-out question as the conservative answer.** Take the option that proceeds
no further, name it, and stop. A cancellation is never permission to continue.

See `../_shared/tooling-examples.md` for the canonical call shape.

**Triage asks the user nothing by design.** Exactly one thing reaches them mid-run: an escalation
neither the brief nor `references/autonomy-charter.md` answers. Everything else already has a
standing answer — take it.

### Why there is no run-scope confirmation

Wave 1 used to stop a full run and ask the user to approve N beads before Wave 2 dispatched
anything. It was removed, and what it was standing in for is worth naming so it does not come back:

- **It re-asked what the invocation had already said.** `/triage {project}` with no `--ids`, no
  `--only` and no `--max` *is* the scope. Those three flags are how a narrower run is requested, and
  a user who wanted one of them would have typed it.
- **It fired after the spend it was guarding.** Waves 0 and 1 are already done by then — inventory,
  dedup and one judge agent. The only thing left to decline is the work the invocation asked for.
- **`--dry-run` is the cheap preview it was imitating**, and it is already the documented first run
  on any backlog: one judge, no workers, the full picture of what a sweep would cost.
- **A gate with no real decision behind it turns into a menu.** A live run rendered it as four
  options, two of them bead subsets nobody had mentioned — an orchestrator inventing scope choices
  because the gate demanded something to choose between.

What the gate actually carried is one number, so the run prints it and keeps going. A user who
wants to stop still can; the difference is that stopping is now their move, not a toll on every run.
The reasoning generalises: a confirmation that only re-states what the invocation authorised charges
a full round trip for nothing, which is the same rule the *Escalation* section applies to workers.

## Invoking companion skills

Workers are dispatched with briefs that name `investigate` and `plan`. Configured shorthands hold
the **bare skill name** with no prefix — the prefix is harness convention, never written into
config.

- **Claude Code:** call the `Skill` tool with `skill: "investigate"` and pass the brief as `args`.
  Text-emitting `Use the investigate skill.` does **not** invoke a skill on Claude Code. If `Skill`
  is unavailable but the skill is a user-runnable slash command, write `/investigate` as a literal
  first-line message.
- **Codex (interactive TUI):** invoke as `$investigate`.
- **Codex (`codex exec` non-interactive):** emit the literal sentence `Use the investigate skill.`
  as the next assistant message, immediately followed by the brief.
- **Fallback (any harness):** read `{skills_dir}/investigate/SKILL.md` directly and follow its
  workflow inline, with the brief as the first message. This branch is what makes a brief work on a
  harness with no skill-invocation mechanism at all, so never drop it.

Do not write a literal `/` or `$` inside config values — the harness adds it.

