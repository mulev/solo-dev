# triage-testbed Investigation: RetryClient never resends a failed request

**Status:** ROOT CAUSE CONFIRMED — FIX APPROVED
**Date:** 2026-08-29
**Project:** triage-testbed
**Beads task:** `tb-pln1`

## Problem

A caller that hits a transient failure gets `NotImplementedError` instead of a
retry. The request is lost and the error names the wrong thing.

## Execution Chain

1. The caller invokes `RetryClient.send` at lib/retry_client.py:7.
2. `send` delegates to `_attempt` with retries=3 at lib/retry_client.py:8.
3. `_attempt` at lib/retry_client.py:10 raises immediately at
   lib/retry_client.py:11, so no attempt is ever made.

## Root Cause

`_attempt` has no body. The retry loop the class documents does not exist, so
every call through `send` terminates in the raise at lib/retry_client.py:11.

## Supporting Evidence

- lib/retry_client.py:10 defines `_attempt` with the signature `send` calls.
- lib/retry_client.py:11 is the whole body of that method.
- The class docstring at lib/retry_client.py:5 states the retry behaviour the
  code does not implement.

## Ruled Out

- **A caller passing the wrong argument count.** `send` at
  lib/retry_client.py:7 takes one request and forwards it with a keyword
  argument, so the signatures match.
- **A missing import.** The module imports nothing; the raise is unconditional
  and reached on the first call.

## Approved Fix

**Summary:** Give `_attempt` the retry loop the class already documents.

**What changes:** `_attempt` at lib/retry_client.py:10 gains a loop that
resends the request up to `retries` times and returns the first success.

**Why this fix is correct:** The raise at lib/retry_client.py:11 is the only
statement in the method, so replacing it removes the whole defect without
touching any caller.

**Side effects checked:** `send` at lib/retry_client.py:7 is the only caller
inside the module, and its call shape does not change.
