# Skills

Reusable markdown skills for agent workflows.

## Included Skills

- `investigate`: Evidence-driven debugging with explicit root-cause and fix approval gates.
- `plan`: Vertical-slice planning workflow that creates and updates implementation plans.
- `execute`: Phase-by-phase implementation workflow that executes plan files or tracker tasks.
- `marketer`: Research-first marketing analysis toolkit with browser-driven data collection.
- `prompt-wizard`: Prompt engineering toolkit for prompts, skills, CLAUDE/AGENTS files, and sub-agents.

## Installation

Copy the skill folder you want to use into your agent's skills directory.

## Configuration

Skills that ship with `skill.config.example.md` can be configured in either of two ways:

1. On first invocation, follow the setup flow the skill presents.
2. Copy `skill.config.example.md` to `skill.config.md`, then edit the values manually.

`skill.config.md` is intentionally gitignored so local paths and tool choices stay private.

## How They Fit Together

The core workflow is:

`investigate` -> `plan` -> `execute`

Each skill is independent, but they are designed to compose into that pipeline:

- `investigate` finds and proves the root cause.
- `plan` turns the approved fix into an executable vertical-slice plan.
- `execute` carries out one phase at a time and records progress.
