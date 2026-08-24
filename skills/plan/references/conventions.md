# Plan Conventions

## Directory Structure

```
{plans_dir}/
  {project}/
    todo/                                       ← active plans
      {single_phase_plan}.md                    ← single-file plan (1 phase)
      {multi_phase_plan}/                       ← folder plan (2+ phases)
        plan.md                                 ← master plan (epic references this)
        phase_1_{slug}.md                       ← slice files (tasks reference these)
        phase_2_{slug}.md
    done/                                       ← completed plans (moved from todo/)
      {single_phase_plan}.md
      {multi_phase_plan}/                       ← entire folder moves to done/
    investigations/                             ← outcome files from the investigate skill
      {project}_invest_{short_name}.md          ← root cause + approved fix (reference only)
```

Investigation files are written by the `investigate` skill before handoff. Plans created from an investigation MUST link to the investigation file from their `## Background` section and MUST NOT overwrite it. Investigations stay in place after the plan moves through `todo/` → `done/`.

System plan mirror:
```
{system_plan_dir}/
  {slug}.md   ← pointer to project plan (or folder/plan.md for multi-phase)
```

---

## File Naming

### Single-Phase Plans

Pattern: `{project}_{type}_{short_name}.md`

- All lowercase
- Underscores between segments
- Hyphens within segments are acceptable for multi-word names
- Keep short_name to 3-5 words maximum

Examples:
- `project_feat_epub_table_of_contents.md`
- `project_fix_scroll_mode_disposal.md`
- `project_tech_ci_cd.md`
- `project_feat_configurable_edge_tap.md`

### Multi-Phase Plans (Folders)

Folder pattern: `{project}_{type}_{short_name}/` (same as single-file, without `.md`)

Inside the folder:
- `plan.md` — master plan (always this exact name)
- `phase_{N}_{slug}.md` — one slice file per phase

Slug: derived from the phase's slice name — lowercase, spaces to underscores, 2-4 words.

Example:
```
project_fix_integration_test_flakiness/
  plan.md
  phase_1_core_flow.md
  phase_2_secondary_path.md
  phase_3_state_guard.md
  phase_4_error_handling.md
  phase_5_test_isolation.md
  phase_6_polish.md
```

### Type Codes & Values

Filename code (lowercase) ↔ plan-header label (`# {Project} {Type}: {Title}`) ↔ when to use:

| Code | Type label | When to use |
|------|------------|-------------|
| feat | Feature | New user-facing capability |
| fix | Fix | Bug fix |
| refactor | Refactor | Code restructuring without behavior change |
| tech | Tech | Infrastructure, CI/CD, tooling, dependencies |
| docs | Docs | Documentation-only changes |
| epic | Epic | Multi-slice plan spanning multiple independent deliverables |

For epics, the filename/folder uses the `epic` type code: `{project}_epic_{short_name}/`
Example: `project_epic_full_coverage/`

---

## Project Detection

Read known projects from `skill.config.md` → Known Projects table.

Detection priority:
1. Explicit mention by user
2. Files opened in the IDE (check `ide_opened_file` tags in conversation)
3. File paths referenced in the user's request or recent conversation
4. Ask the user

Do not assume a specific working directory — use the Known Projects table from config for project detection.

When a new project is encountered that isn't in the config, ask the user for the project name and code path. Add it to the Known Projects table in `skill.config.md` for future detection.

---

## System Plan File

The system plan file at `{system_plan_dir}/{slug}.md` is a pointer. It contains:

```markdown
# {Short title}

Full plan: `{plans_dir}/{project}/todo/{filename}.md`
```

For multi-phase folder plans, point to the master plan:

```markdown
# {Short title}

Full plan: `{plans_dir}/{project}/todo/{foldername}/plan.md`
```

The project plan links back with:

```markdown
**System plan file:** {system_plan_dir}/{slug}.md
```

---

## Moving to Done

When completing a plan:
1. Update status in the plan file to `✅ COMPLETED — {YYYY-MM-DD}`
2. Move the plan to done/:
   - Single-file: `{plans_dir}/{project}/todo/{file}.md` → `{plans_dir}/{project}/done/{file}.md`
   - Folder: `{plans_dir}/{project}/todo/{folder}/` → `{plans_dir}/{project}/done/{folder}/`
3. Update system plan file link if it references the old `todo/` path

---
