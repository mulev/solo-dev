---
name: execute-config
description: Configuration for the execute skill
type: config
---

# Execute Skill Configuration

<!-- Companion skill values are bare skill names (no prefix). The harness adds
     the prefix at invocation time (`/` in Claude Code, `$` in Codex). See
     "Invoking companion skills" in SKILL.md. -->

## Plans Directory
<!-- Base directory for plan files, relative to the working directory. -->
<!-- {project} is replaced with the detected project name at runtime. -->
plans_dir: project_plans

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
<!-- CLI-based issue tracker for task lifecycle management. -->
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
<!-- Bare skill names, no `/` or `$`. Set to empty to disable. -->
plan_skill: plan

## Companion Agents
<!-- Agents launched during execution — prescribed steps, not optional extras: the
     skill's own invocation authorizes them, so dispatch without asking. Set a
     value to empty to skip that step. Values here are Claude Code plugin:agent
     form; resolve to the running harness's roster name at dispatch. -->
code_simplifier: code-simplifier:code-simplifier
code_reviewer: code-review:code-review

## Post-Processing
<!-- Bare skill name applied to generated text before finalizing. Set to empty to skip. -->
commit_message_processor: humanizer

## Architecture
<!-- Hard limit for file length (LOC, excluding comments and blank lines). -->
<!-- Used by the architecture verification gate after each implementation step. -->
<!-- Files over this limit must be split or carry an explicit LOC waiver in the plan. -->
max_file_loc: 300
