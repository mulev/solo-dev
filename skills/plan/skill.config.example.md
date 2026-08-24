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
<!-- Optional second location for plan-file pointers, so an agent or IDE that
     scans a fixed directory can discover plans living inside a project repo.
     Off by default — the plan file in {plans_dir} is the source of truth and
     the mirror is only a pointer. Set it if your harness has such a directory:
     Claude Code uses `~/.claude/plans`. Leave empty to disable mirroring. -->
system_plan_dir:

## Skills Directory
<!-- Where this bundle's SKILL.md files live, used as the cross-harness fallback
     (read the companion skill's SKILL.md directly when the harness has no
     skill-invocation mechanism) and to locate execute/scripts/. The default is
     where `npx skills add --global` installs; a project-scoped install puts them
     in `.agents/skills` relative to the repo. Adjust if you installed elsewhere. -->
skills_dir: ~/.agents/skills

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
<!-- Hard limit for file length (LOC, excluding comments and blank lines). -->
<!-- Used by the architecture self-review checklist and component decomposition gates. -->
<!-- Components projected to exceed this must be split or carry an explicit LOC waiver. -->
max_file_loc: 300
