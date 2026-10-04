#!/usr/bin/env python3
"""Reject a QC verdict that does not match the schema; decide the next action
from round history.

Two pure functions and a command line. `validate()` reports what is wrong with
one verdict object — including the contradictions a JSON schema cannot express,
such as a PASS that carries defects. `next_action()` reads the completed rounds
and returns the action the orchestrator must take, so the decision to spend a
third review round is a set comparison rather than an agent's opinion that
things are getting better.

Neither function edits the verdict. Where the two disagree — a hard defect
class carrying a non-PARK verdict — `validate()` reports the contradiction and
`next_action()` applies the correction, and `next_action()` is authoritative.

Schema interpretation is deliberately hand-rolled against the subset of JSON
Schema `verdict.schema.json` uses: no `jsonschema` dependency, stdlib only. A
keyword the schema uses and this interpreter does not support is itself an
error, because a silently ignored keyword is a rule that stopped being enforced.

Exit: 0 valid · 1 findings · 2 usage or configuration error. Bad input data is
always a finding, never a usage error.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCHEMA_PATH = Path(__file__).with_name("verdict.schema.json")

HARD_CLASSES = ("root-cause-unproven", "requirement-invented", "stop-list")

USAGE = (
    "usage: validate_verdict.py <path>|-\n"
    "       validate_verdict.py --history <path>"
)

# Keywords carrying no constraint. Listing them is what lets an unsupported
# constraint keyword be an error rather than a shrug.
ANNOTATIONS = ("$schema", "title", "description")

SUPPORTED = ("type", "required", "properties", "additionalProperties", "enum",
             "items", "minLength", "minimum", "maximum")

TYPES = {
    "object": dict,
    "array": list,
    "string": str,
    "number": (int, float),
    "integer": int,
    "boolean": bool,
}


def validate(verdict_dict) -> list[str]:
    """Return a list of error strings. Empty list means the verdict is well-formed."""
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    errors = _check(verdict_dict, schema, "$")
    if isinstance(verdict_dict, dict):
        errors.extend(_cross_field(verdict_dict))
    return errors


def next_action(round_history) -> str:
    """Return PASS, REVISE or PARK for the completed rounds, oldest first."""
    if not round_history:
        raise ValueError("round_history must contain at least one verdict")
    last = round_history[-1]
    if last.get("verdict") == "PASS":
        return "PASS"
    if last.get("defect_class") in HARD_CLASSES:
        return "PARK"
    rounds = len(round_history)
    if rounds == 1:
        return "REVISE"
    if rounds == 2 and _converged(round_history[0], round_history[1]):
        return "REVISE"
    return "PARK"


# --- schema interpretation ----------------------------------------------------


def _type_error(value, wanted: str, path: str) -> str | None:
    # Python's bool is an int subclass, so an unguarded isinstance would let
    # `true` satisfy `integer` and `number`.
    if wanted in ("integer", "number") and isinstance(value, bool):
        return f"{path}: expected {wanted}, got boolean"
    if wanted == "integer" and isinstance(value, float):
        return f"{path}: expected integer, got {value!r}"
    if not isinstance(value, TYPES[wanted]):
        return f"{path}: expected {wanted}, got {type(value).__name__}"
    return None


def _constraint_errors(value, schema, path: str) -> list[str]:
    """Errors from the keywords that constrain one value rather than a container."""
    errors: list[str] = []
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: {value!r} is not one of {schema['enum']}")

    min_length = schema.get("minLength")
    if min_length is not None and isinstance(value, str) and len(value) < min_length:
        errors.append(f"{path}: is empty or shorter than {min_length}")

    if isinstance(value, (int, float)):
        minimum = schema.get("minimum")
        maximum = schema.get("maximum")
        if minimum is not None and value < minimum:
            errors.append(f"{path}: {value!r} is below the minimum {minimum}")
        if maximum is not None and value > maximum:
            errors.append(f"{path}: {value!r} is above the maximum {maximum}")
    return errors


def _check(value, schema, path: str) -> list[str]:
    errors: list[str] = []
    for keyword in schema:
        if keyword not in ANNOTATIONS and keyword not in SUPPORTED:
            errors.append(f"{path}: schema keyword {keyword!r} is not supported")

    wanted = schema.get("type")
    if wanted is not None:
        if wanted not in TYPES:
            return errors + [f"{path}: schema type {wanted!r} is not supported"]
        failure = _type_error(value, wanted, path)
        if failure:
            return errors + [failure]

    errors.extend(_constraint_errors(value, schema, path))
    if isinstance(value, dict):
        errors.extend(_check_object(value, schema, path))
    if isinstance(value, list) and "items" in schema:
        for index, item in enumerate(value):
            errors.extend(_check(item, schema["items"], f"{path}[{index}]"))
    return errors


def _check_object(value: dict, schema, path: str) -> list[str]:
    errors: list[str] = []
    properties = schema.get("properties", {})
    for key in schema.get("required", []):
        if key not in value:
            errors.append(f"{path}: required property {key!r} is missing")

    extra = schema.get("additionalProperties")
    if extra is False:
        for key in value:
            if key not in properties:
                errors.append(f"{path}: unknown property {key!r}")
    elif extra is not None:
        errors.append(f"{path}: additionalProperties must be false, got {extra!r}")

    for key, subschema in properties.items():
        if key in value:
            errors.extend(_check(value[key], subschema, f"{path}.{key}"))
    return errors


# --- rules a schema cannot express -------------------------------------------


def _cross_field(verdict_dict: dict) -> list[str]:
    """Errors for the contradictions between fields that a schema cannot state."""
    verdict = verdict_dict.get("verdict")
    defect_class = verdict_dict.get("defect_class")
    defects = verdict_dict.get("defects")

    errors: list[str] = []
    if verdict == "PASS" and defects:
        errors.append("PASS requires an empty defects array")
    if verdict == "PASS" and defect_class != "none":
        errors.append(f"PASS requires defect_class 'none', got {defect_class!r}")
    if verdict == "REVISE" and not defects:
        errors.append("REVISE requires at least one defect")
    if defect_class in HARD_CLASSES and verdict != "PARK":
        errors.append(
            f"defect_class {defect_class!r} forces verdict PARK, got {verdict!r}"
        )
    if defect_class == "none" and verdict != "PASS":
        errors.append("defect_class 'none' is only legal with verdict PASS")
    return errors


# --- convergence --------------------------------------------------------------


def _locations(verdict_dict) -> set:
    return {d["location"].strip() for d in verdict_dict.get("defects", [])}


def _converged(previous, current) -> bool:
    before, after = _locations(previous), _locations(current)
    return bool(after) and after < before


# --- command line -------------------------------------------------------------


class Usage(Exception):
    """Raised for an argument or path problem — exit 2, never a data finding."""


def _read(source: str) -> str:
    if source == "-":
        return sys.stdin.read()
    try:
        return Path(source).read_text(encoding="utf-8")
    except OSError as exc:
        raise Usage(f"cannot read {source}: {exc.strerror}") from exc


def _parse(source: str):
    """Return (value, findings). A parse failure is data, so it is a finding."""
    try:
        return json.loads(_read(source)), []
    except json.JSONDecodeError as exc:
        return None, [f"{source}: not valid JSON — {exc}"]


def _report(findings: list[str]) -> int:
    for finding in findings:
        print(finding, file=sys.stderr)
    return 1 if findings else 0


def _one(source: str) -> int:
    value, findings = _parse(source)
    if findings:
        return _report(findings)
    if not isinstance(value, dict):
        return _report([f"{source}: expected one verdict object, got a "
                        f"{type(value).__name__} — did you mean --history?"])
    return _report(validate(value))


def _round_findings(source: str, rounds: list) -> list[str]:
    """Validate every round, tagging each finding with the round's index."""
    findings: list[str] = []
    for index, item in enumerate(rounds):
        if isinstance(item, dict):
            findings.extend(f"{source}[{index}] {e}" for e in validate(item))
        else:
            findings.append(f"{source}[{index}]: expected an object")
    return findings


def _history(source: str) -> int:
    value, findings = _parse(source)
    if findings:
        return _report(findings)
    if not isinstance(value, list) or not value:
        return _report([f"{source}: --history expects a non-empty JSON array "
                        f"of verdicts, got {type(value).__name__}"])
    findings = _round_findings(source, value)
    if findings:
        return _report(findings)
    print(f"next_action: {next_action(value)}")
    return 0


def _is_source(arg: str) -> bool:
    """`-` is stdin. Any other leading dash is a flag, not a path."""
    return arg == "-" or not arg.startswith("-")


def main(argv: list[str]) -> int:
    try:
        if len(argv) == 2 and argv[0] == "--history":
            return _history(argv[1])
        if len(argv) == 1 and _is_source(argv[0]):
            return _one(argv[0])
        raise Usage(USAGE)
    except Usage as exc:
        print(exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
