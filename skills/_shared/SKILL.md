---
name: _shared
description: >
  Support files for the skill bundle — agent conduct, architecture principles,
  the validator system, the autonomous-run contract, and canonical tooling call
  shapes. NEVER invoke this skill directly and NEVER treat it as a workflow.
  It exists so the workflow skills can read the doctrine they share from a
  sibling directory instead of each carrying its own drifting copy. Install it
  whenever you install any of them.
---

# _shared

Not a workflow. A directory of documents the workflow skills read by relative
path, plus the generic validator runner they all drive.

## Why this is packaged as a skill

The bundle's skills reference these files as `../_shared/<file>`. Skill
installers only copy a directory when it contains a `SKILL.md`, so without this
file `_shared/` is silently dropped and every one of those references dangles —
the architecture gate, the validator doctrine, and the conduct rules all vanish
while the workflows still claim to enforce them.

This file makes `_shared/` a directory an installer will carry. It is not an
entry point.

## Contents

| File | What reads it |
|---|---|
| `agent-conduct.md` | every workflow skill, as required reading before any work |
| `architecture-principles.md` | `plan` (design-time gates), `execute` (per-file gate) |
| `validators.md` | `plan` (Verification sections), `execute` (phase-exit + finalize stages) |
| `autonomous-mode.md` | `triage`, and any worker dispatched by it — the contract a run answers its own gates under |
| `tooling-examples.md` | every workflow skill, for the structured-question call shape |
| `validate` | the generic runner — placed verbatim at a repo root, never edited per repo |
| `test_validate.sh` | the runner's own test suite |

## Putting the runner in your own repo

`validate` is the only file here meant to leave this directory. Place it at the
root of a repo you are working in, write that repo's rules in a sibling
`validators.conf`, and read `validators.md` for the config format, the stage
semantics, and per-stack starting points.

```sh
cp <this directory>/validate <your repo>/validate
chmod +x <your repo>/validate
```

**Place it verbatim and never edit it per repo.** The runner decides nothing;
the config decides everything, so a repo that needs different behaviour needs a
different `validators.conf`, not a modified runner. A copy that has been edited,
or that was placed once and left behind while this one moved on, is the failure
this is guarding against — `./validate version` prints the version a copy
carries, which is how you tell a current one from a stale one.
