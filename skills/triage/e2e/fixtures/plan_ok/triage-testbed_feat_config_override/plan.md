# triage-testbed Feature: config override flag

**Status:** 🔄 IN PROGRESS
**System plan file:** /Users/demo/.claude/plans/triage-testbed_feat_config_override.md

A fixture plan folder. Its only job is to be structurally clean, so
`lint_plan.py`'s exit-0 case has something real to lint.

## Dependency Table

| Phase | Scope | Depends on | Slice |
|-------|-------|------------|-------|
| **1: Read the override** | environment lookup | — | [phase_1_read_the_override.md](phase_1_read_the_override.md) |
| **2: Wire the settings screen** | call site | Phase 1 | [phase_2_wire_the_settings_screen.md](phase_2_wire_the_settings_screen.md) |

## Progress

- [ ] [Phase 1: Read the override](phase_1_read_the_override.md) — `tb-clean1.1`
- [ ] [Phase 2: Wire the settings screen](phase_2_wire_the_settings_screen.md) — `tb-clean1.2`

## Objective

Let an operator point the settings screen at a config file of their choosing.

## Success Criteria

- [ ] The override is read once and cached.
