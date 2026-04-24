---
name: investigate-config
description: Configuration for the investigate skill
type: config
---

# Investigate Skill Configuration

## Plans Directory
<!-- Base directory for plan files, relative to the working directory. -->
<!-- Only used when the planning skill is unavailable (fallback handoff). -->
<!-- {project} is replaced with the detected project name at runtime. -->
plans_dir: project_plans

## Companion Skills
<!-- Skills invoked for handoff after investigation. Set to empty to disable. -->
plan_skill: /plan
execute_skill: /execute
