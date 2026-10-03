# skills Investigation: flaky retry loop in retry_client.py

**Status:** ROOT CAUSE CONFIRMED
**Beads task:** `tb-pln1`

## Root Cause
`RetryClient._attempt` (retry_client.py:10) is unimplemented, so every retry
raises `NotImplementedError` instead of resending the request.

## Approved Fix
Implement `_attempt` to resend `request` up to `retries` times.
