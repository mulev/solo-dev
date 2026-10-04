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
     skill's own invocation authorizes them, so dispatch without asking. Each
     value is an ordered candidate list, most specific first; an empty value
     forces the step's local fallback rather than skipping it. How a candidate
     becomes a dispatch is in SKILL.md, "Dispatching companion agents". Never
     assert here which name a given harness carries; the roster answers that at
     dispatch. -->
code_simplifier: code-simplifier:code-simplifier, code-simplifier
code_reviewer: code-review:code-review, reviewer

## Post-Processing
<!-- Bare skill name applied to generated text before finalizing. Set to empty to skip. -->
commit_message_processor: humanizer

## Architecture
<!-- Hard limit for file length (LOC, excluding comments, doc prose, and blank lines). -->
<!-- Used by the architecture verification gate after each implementation step. -->
<!-- Files over this limit must be split or carry an explicit LOC waiver in the plan. -->
max_file_loc: 300
