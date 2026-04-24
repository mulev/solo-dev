---
name: plan-config
description: Configuration for the plan skill
type: config
---

# Plan Skill Configuration

## Plans Directory
<!-- Base directory for plan files, relative to the working directory. -->
<!-- {project} is replaced with the detected project name at runtime. -->
<!-- Active: {plans_dir}/{project}/todo/ | Done: {plans_dir}/{project}/done/ -->
plans_dir: project_plans

## System Plan Mirror
<!-- Secondary location for plan file pointers (agent/IDE discovery). -->
<!-- Leave empty to disable system plan mirroring. -->
system_plan_dir: ~/.claude/plans

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
<!-- Skills invoked for handoff after planning. Set to empty to disable. -->
execute_skill: /execute
