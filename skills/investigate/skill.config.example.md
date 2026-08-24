---
name: investigate-config
description: Configuration for the investigate skill
type: config
---

# Investigate Skill Configuration

<!-- Companion skill values are bare skill names (no prefix). The harness adds
     the prefix at invocation time (`/` in Claude Code, `$` in Codex). See
     "Invoking companion skills" in SKILL.md. -->

## Plans Directory
<!-- Absolute base directory for plan files. {project} is replaced at runtime. -->
<!-- Used to derive the investigation-outcome file path and as the fallback
     handoff target when no planning skill is configured. -->
plans_dir:

## Investigations Directory
<!-- Subdirectory (relative to {plans_dir}/{project}/) where investigation
     outcome files are written. Created on first save if missing.
     Leave empty to use the default `investigations`. -->
investigations_subdir:

## Skills Directory
<!-- Where this bundle's SKILL.md files live, used as the cross-harness fallback
     (read the companion skill's SKILL.md directly when the harness has no
     skill-invocation mechanism) and to locate execute/scripts/. The default is
     where `npx skills add --global` installs; a project-scoped install puts them
     in `.agents/skills` relative to the repo. Adjust if you installed elsewhere. -->
skills_dir: ~/.agents/skills

## Known Projects
<!-- Map project names to their root code paths for automatic detection.
     Investigate inherits this list from the plan/execute config bundle so
     project detection stays consistent across all three skills. -->
| Project | Code Path |
|---------|-----------|
| <!-- add your projects here --> | |

## Issue Tracker
<!-- When enabled, Step 0 reads the bead behind a bare tracker ID and Step 5d
     writes the confirmed outcome back to it. Set enabled: false to skip every
     tracker command and treat all investigations as untracked. -->
enabled: false
cli_command: bd
init_command: bd init
data_dir: .beads

## Formatter
<!-- Bundle-consistency block. Leave empty to infer from project instructions. -->
command:

## Test Command
<!-- Bundle-consistency block. Leave empty to infer from project instructions. -->
command:

## Companion Skills
<!-- Bare skill names, no `/` or `$`. Set to empty to disable handoff. -->
plan_skill: plan
execute_skill: execute
