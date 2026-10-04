---
name: plan-config
description: Configuration for the plan skill
type: config
---

# Plan Skill Configuration

<!-- Companion skill values are bare skill names (no prefix). The harness adds
     the prefix at invocation time (`/` in Claude Code, `$` in Codex). See
     "Invoking companion skills" in SKILL.md. -->

## Plans Directory
<!-- Base directory for plan files, relative to the working directory. -->
<!-- {project} is replaced with the detected project name at runtime. -->
<!-- Active: {plans_dir}/{project}/todo/ | Done: {plans_dir}/{project}/done/ -->
plans_dir: project_plans

## System Plan Mirror
<!-- Secondary location for plan file pointers (agent/IDE discovery). -->
<!-- Leave empty to disable system plan mirroring. -->
system_plan_dir: ~/.claude/plans

## Skills Directory
<!-- Where SKILL.md files live, used as the cross-harness fallback (read the
     companion skill's SKILL.md directly when the harness has no skill-invocation
     mechanism). Set to an absolute path during setup. Empty default forces
     explicit configuration over silent failure. -->
skills_dir:

## Known Projects
<!-- Map project names to their root code paths for automatic detection. -->
<!-- Detection priority: explicit mention > IDE context > conversation context > ask user. -->
<!-- Remove the placeholder row and add your projects. -->
| Project | Code Path |
|---------|-----------|
| <!-- add your projects here --> | |

## Issue Tracker
<!-- CLI-based issue tracker for decomposing plans into tasks. -->
<!-- Set enabled: false to skip all tracker commands (default). -->
enabled: false
cli_command: bd
init_command: bd init
data_dir: .beads

## Formatter
<!-- Code formatter command. Leave empty to infer from project instructions. -->
command:

## Test Command
<!-- Full test suite command. Leave empty to infer from project instructions. -->
command:

## Companion Skills
<!-- Bare skill names, no `/` or `$`. Set to empty to disable handoff. -->
execute_skill: execute

## Architecture
<!-- Hard limit for file length (LOC, excluding comments, doc prose, and blank lines). -->
<!-- Used by the architecture self-review checklist and component decomposition gates. -->
<!-- Components projected to exceed this must be split or carry an explicit LOC waiver. -->
max_file_loc: 300
