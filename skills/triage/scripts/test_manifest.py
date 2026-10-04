"""Tests for manifest.py — the round trip, the version check, and the
promise that `save` adds nothing to the mapping it is handed.

That last promise is what makes migrating inventory.py and dedup.py onto
this module provably behaviour-free, so it is asserted byte for byte
against the exact form those two scripts emitted before the migration.

Run with `python3 test_manifest.py` (no pytest dependency).
"""

from __future__ import annotations

import json
import sys
import tempfile
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import manifest  # noqa: E402

# The exact form inventory.py and dedup.py wrote before the migration.
LEGACY_BYTES = lambda m: json.dumps(m, indent=2) + "\n"  # noqa: E731

SAMPLE = {
    "project": "demo",
    "generated_at": "2026-08-28T00:00:00Z",
    "counts": {"investigate": 1, "plan": 0, "skip": 0, "drift-report": 0},
    "beads": [{"id": "d-1", "route": "investigate", "reason": "no investigation"}],
}


def expect(got, want) -> None:
    assert got == want, f"got {got!r}, want {want!r}"


def write(tmp: Path, payload, name: str = "manifest.json") -> Path:
    path = tmp / name
    path.write_text(
        payload if isinstance(payload, str) else LEGACY_BYTES(payload),
        encoding="utf-8",
    )
    return path


# --- round trip --------------------------------------------------------------


def case_save_then_load_returns_an_equal_mapping(tmp: Path) -> None:
    path = tmp / "out.json"
    manifest.save(path, SAMPLE)
    expect(manifest.load(path), SAMPLE)


def case_save_writes_the_bytes_inventory_wrote_before_the_migration(tmp: Path) -> None:
    path = tmp / "out.json"
    manifest.save(path, SAMPLE)
    expect(path.read_text(encoding="utf-8"), LEGACY_BYTES(SAMPLE))


def case_save_accepts_a_string_path(tmp: Path) -> None:
    path = tmp / "out.json"
    manifest.save(str(path), SAMPLE)
    expect(manifest.load(str(path)), SAMPLE)


# --- the version check -------------------------------------------------------


def case_matching_schema_version_loads(tmp: Path) -> None:
    payload = {**SAMPLE, "schema_version": manifest.schema_version}
    expect(manifest.load(write(tmp, payload)), payload)


def case_mismatched_schema_version_is_rejected_not_coerced(tmp: Path) -> None:
    path = write(tmp, {**SAMPLE, "schema_version": manifest.schema_version + 1})
    try:
        manifest.load(path)
    except manifest.ManifestVersionError as err:
        assert str(manifest.schema_version + 1) in str(err), err
        return
    raise AssertionError("a future schema_version loaded without complaint")


def case_manifest_with_no_schema_version_loads_unchanged(tmp: Path) -> None:
    """Pre-versioning manifests — everything inventory.py wrote before today."""
    loaded = manifest.load(write(tmp, SAMPLE))
    expect(loaded, SAMPLE)
    assert "schema_version" not in loaded, loaded


# --- additive safety ---------------------------------------------------------


def case_unknown_top_level_keys_survive_a_round_trip_byte_identically(
    tmp: Path,
) -> None:
    payload = {**SAMPLE, "clusters": [{"cluster_id": "c1"}], "nonsense_key": [1, 2]}
    src = write(tmp, payload)
    out = tmp / "out.json"
    manifest.save(out, manifest.load(src))
    expect(out.read_bytes(), src.read_bytes())


def case_save_adds_no_key_that_was_not_handed_to_it(tmp: Path) -> None:
    path = tmp / "out.json"
    manifest.save(path, SAMPLE)
    expect(sorted(json.loads(path.read_text(encoding="utf-8"))), sorted(SAMPLE))


def case_key_order_is_insertion_order_not_sorted(tmp: Path) -> None:
    payload = {"zeta": 1, "alpha": 2}
    path = tmp / "out.json"
    manifest.save(path, payload)
    expect(list(json.loads(path.read_text(encoding="utf-8"))), ["zeta", "alpha"])


# --- the errors a caller turns into exit 2 -----------------------------------


def case_missing_file_raises_manifest_error(tmp: Path) -> None:
    try:
        manifest.load(tmp / "gone.json")
    except manifest.ManifestError:
        return
    raise AssertionError("a missing manifest loaded")


def case_malformed_json_raises_manifest_error(tmp: Path) -> None:
    try:
        manifest.load(write(tmp, "{not json", "bad.json"))
    except manifest.ManifestError:
        return
    raise AssertionError("malformed JSON loaded")


def case_a_json_list_is_not_a_manifest(tmp: Path) -> None:
    """A top-level list parses as JSON but has no manifest shape at all."""
    try:
        manifest.load(write(tmp, "[1, 2, 3]", "list.json"))
    except manifest.ManifestError:
        return
    raise AssertionError("a JSON list loaded as a manifest")


def case_version_error_is_a_manifest_error(tmp: Path) -> None:
    """One `except ManifestError` in a caller covers every load failure."""
    assert issubclass(manifest.ManifestVersionError, manifest.ManifestError)



def case_in_run_honours_an_explicit_exclusion(tmp) -> None:
    assert manifest.in_run({"id": "a", "route": "plan", "selected": True})
    assert not manifest.in_run({"id": "a", "route": "plan", "selected": False})


def case_in_run_defaults_to_selected_when_the_key_is_absent(tmp) -> None:
    """A manifest written before `inventory.select` existed has no `selected`
    field; reading its absence as excluded would silently empty an older run."""
    assert manifest.in_run({"id": "a", "route": "plan"})


CASES = [v for k, v in sorted(globals().items()) if k.startswith("case_")]


def main() -> int:
    failed = 0
    for case in CASES:
        with tempfile.TemporaryDirectory() as td:
            try:
                case(Path(td))
                print(f"PASS  {case.__name__}")
            except AssertionError as e:
                failed += 1
                print(f"FAIL  {case.__name__}: {e}")
            except Exception:
                failed += 1
                print(f"ERROR {case.__name__}")
                traceback.print_exc()
    print(f"\n{len(CASES) - failed}/{len(CASES)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
