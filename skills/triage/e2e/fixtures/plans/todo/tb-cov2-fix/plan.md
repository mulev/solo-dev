# skills Fix: retry_client.py exponential backoff

**Status:** ✅ COMPLETE
**Beads task:** `tb-cov2-epic-placeholder`

## Objective
Add exponential backoff between `RetryClient.send` attempts so callers stop
hammering a failing endpoint.

## Beads

| Role | ID | Title |
|---|---|---|
| Task | `tb-cov2` | RetryClient.send has no backoff between attempts |
