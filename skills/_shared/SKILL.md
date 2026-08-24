---
name: _shared
description: >
  Support files for the solo-dev skill bundle — architecture principles, the
  validator system, the agent conduct doctrine, and canonical tooling call
  shapes. NEVER invoke this skill directly and NEVER treat it as a workflow.
  It exists so that `investigate`, `plan`, and `execute` can read the doctrine
  they share from a sibling directory instead of each carrying its own drifting
  copy. Install it whenever you install any of those three.
---

# _shared

Not a workflow. A directory of documents the three workflow skills read by
relative path, plus the generic validator runner they all drive.

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
| `agent-conduct.md` | all three skills, as required reading before any work |
| `architecture-principles.md` | `plan` (design-time gates), `execute` (per-file gate) |
| `validators.md` | `plan` (Verification sections), `execute` (phase-exit + finalize stages) |
| `tooling-examples.md` | all three skills, for the structured-question call shape |
| `validate` | the generic runner — copy verbatim to a repo root, never edit per repo |
| `test_validate.sh` | the runner's own test suite |

## Installing the runner into your own repo

`validate` is the only file here meant to leave this directory. Copy it to the
root of a repo you are working in, write that repo's rules in a sibling
`validators.conf`, and read `validators.md` for the config format, the stage
semantics, and per-stack starting points.

```sh
cp <this directory>/validate <your repo>/validate
chmod +x <your repo>/validate
```
