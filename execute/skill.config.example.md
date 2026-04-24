---
name: execute-config
description: Configuration for the execute skill
type: config
---

# Execute Skill Configuration

## Plans Directory
<!-- Base directory for plan files, relative to the working directory. -->
<!-- {project} is replaced with the detected project name at runtime. -->
plans_dir: project_plans

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
<!-- Skills invoked during execution. Set to empty to disable. -->
plan_skill: /plan

## Companion Agents
<!-- Agents launched during execution. Set to empty to skip that step. -->
code_simplifier: code-simplifier:code-simplifier
code_reviewer: code-review:code-review

## Post-Processing
<!-- Skills applied to generated text before finalizing. Set to empty to skip. -->
commit_message_processor: /humanizer
