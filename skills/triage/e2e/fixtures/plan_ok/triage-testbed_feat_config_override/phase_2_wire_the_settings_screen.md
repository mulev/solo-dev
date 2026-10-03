# Phase 2: Wire the settings screen — call the new resolver from the settings screen

**Parent plan:** [plan.md](plan.md)
**Beads task:** `tb-clean1.2`
**Status:** 🔄 IN PROGRESS

## Prerequisites

Phase 1 delivers `read_override`.

## Component Decomposition

| Component | Responsibility (one sentence, no "and") | Public API | Callers (≥2 OR single-caller + own test) | Foreign modules touched | Projected LOC | Test approach |
|---|---|---|---|---|---|---|
| `lib/override_2.py` | Passes the resolved override to the settings screen | `read_override()` | `lonely_config.py`, its own test | none | 60 | pure function over the environment |

## Implementation Progress

- [ ] Read `lib/lonely_config.py` — understand how the path is resolved today. Done when you can name the single return statement.
- [ ] Create `lib/test_override_2.py` — one case for a set variable, one for an unset one. Done when it **fails**.
- [ ] Implement `read_override` in `lib/override_2.py`. Done when the two cases pass.
- [ ] Add an integration test covering the settings screen end to end in `lib/test_override_2.py`. Done when it passes.
- [ ] Update `docs/config.md` — describe the override. Done when saved.
- [ ] Run the formatter, then the polish pass. Done when the tree is clean.

## Implementation

### File: `lib/override_2.py`

One call site changes; the rest of the screen is untouched.

## Testing

### Unit Tests

**New file:** `lib/test_override_2.py`

### Integration Tests

- Scenario: the settings screen opens a config file named by the override.

## Documentation

- Update `docs/config.md` with the override's name and precedence.

## Verification

- TDD inner loop: `python3 lib/test_override_2.py`.
- Phase exit, from the repo root: `./validate run phase-exit` — every row PASS.

## Files Created

- `lib/override_2.py`

## Files Modified

- `lib/lonely_config.py`
