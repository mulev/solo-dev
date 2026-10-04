---
name: triage-config
description: Configuration for the triage skill
type: config
---

# Triage Skill Configuration

<!-- Copy this file to `skill.config.md` and fill in the absolute paths. The
     skill reads `skill.config.md` on every invocation and never this file. -->

## Plans Directory
<!-- Base directory for plan files. {project} is replaced at runtime. -->
<!-- A triage run stages under {plans_dir}/{project}/{staging_subdir}/ and
     writes nowhere else. The live backlog at {plans_dir}/{project}/todo/ is
     read-only until the explicit promote step. -->
plans_dir: project_plans

## Skills Directory
<!-- Where SKILL.md files live. Used to locate triage's own scripts, and as
     the cross-harness fallback for reading a companion skill directly when
     the harness has no skill-invocation mechanism. Absolute path. Empty
     default forces explicit configuration over silent failure. -->
skills_dir:

## Known Projects
<!-- Map project names to their root code paths for automatic detection. -->
<!-- Detection priority: explicit mention > IDE context > conversation context > ask user. -->
<!-- Remove the placeholder row and add your projects. -->
| Project | Code Path |
|---------|-----------|
| <!-- add your projects here --> | |

## Issue Tracker
<!-- A triage run reads the backlog through this CLI and never writes to it.
     With enabled: false there is no backlog to sweep, so /triage stops. -->
enabled: false
cli_command: bd
data_dir: .beads

## Staging
<!-- Directory name, under {plans_dir}/{project}/, holding run directories.
     Every artifact a run produces lands inside one of them, which is what
     makes `discard` a complete undo. -->
staging_subdir: triage

## Dispatch
<!-- parallel_cap: most workers in flight at once. Raise it only as far as
     the harness can actually schedule; every worker holds its own context.
     max_beads: run-wide bead cap, 0 meaning unlimited. -->
parallel_cap: 3
max_beads: 0
