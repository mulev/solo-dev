# Solo Dev

Agent skills for developers who ship alone.

## Install

```bash
npx skills add mulev/solo-dev
```

Works with Claude Code, Cursor, GitHub Copilot, and other agents that support the skills format.

## What's in here

Four skills. The first three form a pipeline:

```
investigate  →  plan  →  execute
```

`investigate` does root cause analysis. The agent traces the full execution chain and cites evidence for every claim — no "probably," no "likely," no guessing. Two hard gates before anything changes: you confirm the root cause, then you approve the fix design.

`plan` turns work into vertical slices. Each slice is a self-contained deliverable with its own tests, implementation, integration tests, and docs. When a plan has multiple phases, it gets split into a master plan and individual slice files so the agent works with one slice at a time instead of loading a giant markdown file into context.

`execute` picks the next unblocked phase and runs the TDD cycle: write test, watch it fail, implement, watch it pass. Then it updates the plan and closes the tracker task. One phase per invocation — you stay in the loop after every deliverable.

`marketer` is separate from the pipeline. Structured research for ASO, SEO, competitor analysis, and pricing. It collects data through browser automation, stores intermediary results as JSON, and produces self-contained HTML reports. Every recommendation comes with a confidence level and what you'd need to do to validate it.

## Quick reference

| Skill | Trigger phrases |
|-------|-----------------|
| `investigate` | "debug", "investigate", "why does this happen", "find the bug" |
| `plan` | "plan", "create a plan", "plan this feature" |
| `execute` | "execute", "next task", "start implementing", "what's next" |
| `marketer` | "ASO", "SEO", "competitor research", "pricing strategy" |

## Configuration

Skills that need local settings ship with `skill.config.example.md`. Either invoke the skill and follow the setup prompts, or copy the example to `skill.config.md` and edit it by hand. The config file is gitignored.

## What these skills actually enforce

Tests before implementation. The plan template has the TDD order baked in, and `execute` follows it. If skipping is genuinely impossible for some step, the agent has to say why.

Nothing happens without your sign-off. Root cause confirmation, fix design approval, plan structure — the agent stops and asks at each decision point. There's no "I went ahead and refactored the whole module" moment.

## License

MIT
