# Testbed fixture source tree

Copied verbatim into `triage-testbed/` by `make_testbed.sh` and committed as
the testbed's initial git history. Not a real application — five files, each
built to answer one wave's question:

- `lib/app_startup.py` — `tb-inv1` cites the unguarded `open()` at line 8. It
  exists because Suite B needs one bead a live worker can actually reach a
  cause on: `tb-inv1` used to assert a startup crash against a source tree with
  no entry point, so an honest worker returned `PARK` every time and Suite B's
  planning dispatch — the second half of the pipeline — never ran
  (`skills-24t`).
- `lib/shared_render.py` — `tb-col1` and `tb-col2` both cite this file (Wave 3
  collision grouping).
- `lib/lonely_config.py` — only `tb-ind1` cites this file (Wave 3 `INDEPENDENT`).
- `lib/retry_client.py` — `tb-dup1` and `tb-dup2` both cite this file and the
  same symbol (`RetryClient.send`), and carry a `duplicate-of` edge besides.
- `lib/theme_loader.py` — `tb-park` asserts a YAML-anchor crash; this loader
  only ever parses JSON, so the file can neither confirm nor refute the claim.

Line numbers are load-bearing: every bead title cites `file.py:line`, and the
citations have to land on the symbol they name.
