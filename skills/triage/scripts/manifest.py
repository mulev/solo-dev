#!/usr/bin/env python3
"""Persist the triage run manifest.

`save` is byte-faithful: it writes exactly the mapping it is handed and adds
nothing — no stamped version, no normalised key order, no injected defaults.
That is what makes migrating inventory.py and dedup.py onto this module
provably behaviour-free, and their existing tests are the proof.

`load` preserves unknown keys, so a manifest that has been through a later
phase still round-trips through an earlier caller unharmed. Every phase's
contribution is additive: Phase 1 writes `beads`, Phase 2 writes
`clusters`/`covered`, Phase 8 writes `groups`.

This module was deliberately not extracted at Phase 1, where it would have
had one caller and been a single-caller satellite. It has three now.
"""

from __future__ import annotations

import json
from pathlib import Path

schema_version = 1


class ManifestError(Exception):
    """The manifest could not be read as a manifest.

    Callers turn this into their exit-2 usage error; `except ManifestError`
    covers every load failure, the version mismatch included.
    """


class ManifestVersionError(ManifestError):
    """The manifest declares a schema version this code does not speak."""


def load(path) -> dict:
    """Return the manifest mapping at `path`.

    A manifest carrying `schema_version` must match the module constant
    exactly; anything else raises ManifestVersionError rather than being
    coerced. A manifest with no version key is a pre-versioning manifest —
    inventory.py wrote those before this module existed — and loads as-is.
    """
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as err:
        raise ManifestError(f"cannot read manifest {path}: {err}") from err
    if not isinstance(data, dict):
        raise ManifestError(
            f"cannot read manifest {path}: top level is {type(data).__name__}, "
            "not an object"
        )
    declared = data.get("schema_version")
    if declared is not None and declared != schema_version:
        raise ManifestVersionError(
            f"manifest {path} declares schema_version {declared};"
            f" this code speaks {schema_version}"
        )
    return data


def save(path, manifest: dict) -> None:
    """Write `manifest` to `path` in the form inventory.py and dedup.py emit.

    Unknown keys are preserved verbatim and key order is insertion order,
    because a key nobody wrote must never appear.
    """
    Path(path).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def in_run(entry: dict) -> bool:
    """True when this run actually works the bead.

    `inventory.select` marks an excluded bead and leaves its entry in place, so
    the manifest keeps describing the whole backlog. Every consumer therefore
    has to ask, and the route alone is not the answer: a bead can be routed
    `plan` and still be outside this run because `--ids`, `--only` or `--max`
    excluded it.

    Missing key means selected. A manifest written before selection existed has
    no `selected` field, and reading its absence as "excluded" would silently
    empty an older run.
    """
    return entry.get("selected", True)
