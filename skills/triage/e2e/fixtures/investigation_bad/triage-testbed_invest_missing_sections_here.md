# triage-testbed Investigation: config path resolution

**Status:** ROOT CAUSE CONFIRMED — FIX APPROVED
**Date:** 2026-08-29
**Project:** triage-testbed
**Beads task:** `tb-drf1`

Two defects on purpose, one per finding code the exit-1 case asserts:
`## Ruled Out` is absent (section-missing), and the Root Cause below hedges
(assumption-language). Everything else is well-formed, so a red run names
those two codes and nothing else.

## Problem

The settings screen resolves a config path that ignores the environment.

## Execution Chain

1. The settings screen calls `default_config_path` at lib/lonely_config.py:4.
2. That function returns a constant at lib/lonely_config.py:6.

## Root Cause

The return at lib/lonely_config.py:6 is probably hardcoded, which would
explain why the environment variable never takes effect.

## Supporting Evidence

- lib/lonely_config.py:4 defines the function with no parameters.
- lib/lonely_config.py:6 returns a literal path.

## Approved Fix

**Summary:** Read the environment before falling back to the literal.

**What changes:** `default_config_path` at lib/lonely_config.py:4 consults the
environment first.

**Why this fix is correct:** The literal at lib/lonely_config.py:6 is the only
value the function can return today.

**Side effects checked:** Nothing else in the tree calls this function.
