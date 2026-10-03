# Update & Complete Workflows

Both workflows operate on plans already created via the Create workflow in `SKILL.md`. Shorthands (`{plans_dir}`, `{project}`, `{tracker_cli}`, `{system_plan_dir}`) come from `skill.config.md`.

---

## Update Workflow

### Step 1: Locate the plan

Find the plan via, in priority order:
1. User provides the file name or path
2. Search `{plans_dir}/{project}/todo/` matching conversation context — check both `.md` files and folder names
3. If ambiguous — `AskUserQuestion` with plan names as options (label = name, description = full path). Limit to 4; if more exist, show the 4 most recently modified and note in the question text that others were omitted.

For multi-phase plans (folders), the master plan is at `{folder}/plan.md`. Phase-specific updates target the relevant slice file `{folder}/phase_N_{slug}.md`.

### Step 2: Determine what changed

Infer from context first (completed phases, files mentioned, errors described). If unclear, `AskUserQuestion`:

```
question: "What needs to be recorded in the plan?"
header: "Update type"
multiSelect: true
options:
  - label: "Phase completed"
    description: "Mark steps [x] and add ✅ COMPLETED to a phase header."
  - label: "Bug found / bug round"
    description: "Add a Bug Round section with root cause and fix."
  - label: "Files added or modified"
    description: "Update the Files Created / Files Modified sections."
  - label: "Plan needs restructuring"
    description: "Add phases, reorder steps, or revise scope."
```

Follow up with specific questions (`AskUserQuestion`) only for the selected update types.

### Step 3: Apply updates

<update-rules>
- Mark completed steps with `[x]`
- Add ✅ COMPLETED and date to finished phase headers
- Add bug round sections: `## Bug Round N: {description}` with sub-items for root cause, fix, and regression test
- Add files to "Files Created" or "Files Modified" sections
- Update dates on phase completion headers
- Never remove existing content — append or modify status markers only

**Multi-phase plan specifics:**
- Phase completion: update slice file status to `✅ COMPLETED — {YYYY-MM-DD}` AND mark the corresponding line in master plan's `## Progress` section with `[x]`
- Delegated phases: add the worker's row to the master plan's `## Dispatch Log` — bead, worker, dispatched, returned, commits, gate, ledger, bead state. Dispatched and returned are UTC timestamps to the second (`date -u +%Y-%m-%dT%H:%M:%SZ`), so each row can be lined up against that bead's ledger header; a bare date proves nothing about ordering. That table is the epic's state on disk after a compaction.
- Bug rounds: append to the affected **slice file**, not the master plan
- Files created/modified: update both the slice file (phase-specific) and master plan (consolidated)
</update-rules>

**Restructuring: single-file to folder conversion.** If restructuring adds phases to a single-file plan: create folder at `{plans_dir}/{project}/todo/{foldername}/`, extract shared context into `plan.md`, move implementation detail into `phase_1_{slug}.md`, create new `phase_N_{slug}.md` files for added phases, update the system plan pointer to `{folder}/plan.md`, and create a tracker epic if the project uses task tracking.

### Step 3b: Check for missing tracker decomposition

If the project uses task tracking (check the tracker declaration in the project's agent instructions or a `{tracker_data}/` directory) and the plan has no `## Beads` section (or empty with no task IDs):

```
question: "This plan has no tracker tasks yet. Want to create them now?"
header: "Task tracking"
options:
  - label: "Yes, create tracker tasks (Recommended)"
    description: "Create a tracker epic and tasks matching the plan's phases."
  - label: "Not now"
    description: "Skip task tracking for now."
```

If "Yes": follow Step 8b from the Create workflow in `SKILL.md` to create the tracker tasks, then update the plan's `## Beads` section.
If "Not now": continue with Step 4.

### Step 4: Sync tracker (if applicable)

If the project has task tracking initialized and the plan's `## Beads` section contains task IDs:
- **Phase completed:** run the close → epic auto-close → persist sequence:
  ```
  {tracker_cli} close {task-id} --reason "Phase {N} complete: {one-line summary}" --suggest-next
  ```
  Then, once every child's artifacts are verified, the main session — never a worker — closes the parent with `{tracker_cli} epic close-eligible`. That subcommand is an action: it closes every eligible epic and prints `Closed N epic(s)`, so it is not a way to check eligibility. Inspect with `{tracker_cli} show {epic-id}` instead. See `execute/references/tracker-templates.md` (Epic close) for the canonical sequence.
- **Bug round added:** `{tracker_cli} note {task-id} "Bug round {N}: {short description}"` on the affected task.
- **Plan restructured (phases added/removed):** Create or close tracker tasks to match. Update the plan's `## Beads` table.

---

## Complete Workflow

### Step 1: Update status
Set `**Status:** ✅ COMPLETED — {YYYY-MM-DD}`. For multi-phase plans, also update status in each slice file and mark all progress lines with `[x]` in the master plan (see Completion Format in `references/bug-and-completion.md`).

### Step 2: Verify progress
Confirm all Implementation Progress checkboxes are checked. For multi-phase plans, check across all slice files.

### Step 3: Verify files
Confirm Files Created/Modified sections are complete.

### Step 4: Verify success criteria
Confirm all Success Criteria checkboxes are checked.

### Step 5: Move the plan
- Single-file: move `{plans_dir}/{project}/todo/{file}.md` → `{plans_dir}/{project}/done/{file}.md`
- Folder: move `{plans_dir}/{project}/todo/{folder}/` → `{plans_dir}/{project}/done/{folder}/`

### Step 6: Update system plan
Update `{system_plan_dir}/{slug}.md` link if it references the old `todo/` path.

### Step 7: Close tracker tasks
If the plan's `## Beads` section contains task IDs:
1. Close all child tasks first: `{tracker_cli} close {task-id}` for each.
2. Close the epic (if one exists): `{tracker_cli} close {epic-id}`.
3. If the `## Beads` section is empty or missing, skip — the plan predates task tracking.
