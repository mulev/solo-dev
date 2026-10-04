"""Own the testbed's lifecycle and the environment every e2e suite runs in.

Three jobs, and nothing else lives here: build the generated trees, hand a
suite the two isolation seams that point a triage script at them, and prove —
before any of that is trusted — that `bd` resolves the testbed's own database.

The guard is the reason this module exists rather than a handful of
`subprocess.run` calls in each suite. `bd` finds its database by walking *up*
from the working directory, and the testbed is built inside the skills repo,
so a testbed whose `.beads` is missing resolves to the skills repo's own
tracker and every `bd` call in a suite writes into real work. That is not
recoverable, so `assert_db_inside` raises and never warns.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

SKILLS_ROOT = Path(__file__).resolve().parents[2]
E2E = SKILLS_ROOT / "triage" / "e2e"
FIXTURES = E2E / "fixtures"
SCRIPTS = SKILLS_ROOT / "triage" / "scripts"
MAKE_TESTBED = E2E / "make_testbed.sh"

MARKER = ".triage-testbed"
PROJECT = "triage-testbed"
CLEAN_PROJECT = "triage-testbed-clean"
CORPUS = "triage-testbed-plans"
SCRATCH = "_scratch"


@dataclass(frozen=True)
class Testbed:
    root: Path      # where the three generated trees sit side by side
    path: Path      # triage-testbed/ — a real git repo with a real bd database
    clean: Path     # triage-testbed-clean/ — one clean bead, inventory's exit 0
    corpus: Path    # triage-testbed-plans/ — the plan corpus
    scratch: Path   # a writable directory no triage script reads as a project
    bead_ids: tuple


class Busy(RuntimeError):
    """Another run holds the testbed. Never wait, never proceed."""


class Missing(RuntimeError):
    """`--reuse` was asked for and there is nothing on disk to reuse."""


def _alive(pid: str) -> bool:
    """Whether the pid in a lock file still names a running process.

    Signal 0 checks existence without delivering anything. A malformed pid, or
    one this user cannot signal, counts as alive: refusing is recoverable,
    reclaiming a lock somebody holds is not.
    """
    try:
        os.kill(int(pid), 0)
    except (ValueError, TypeError):
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _lock(root: Path):
    """Refuse to build while another run owns the trees.

    Two drivers rebuilding the same testbed corrupt it: the generator wipes
    while the other process has the Dolt database open, and the second run dies
    with a missing-manifest fatal error that reads like a fixture bug. Measured
    the hard way. Failing fast with the owner's pid is the only useful answer —
    waiting would just queue up a nine-minute run behind another one.
    """
    lock = root / ".triage-testbed.lock"
    try:
        handle = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        owner = lock.read_text(encoding="utf-8").strip()
        if _alive(owner):
            raise Busy(f"another e2e run holds {lock} (pid {owner})") from None
        # The owner is gone. Reclaim rather than making a human delete the
        # file: the only recovery used to be `rm -f`, and a workaround reached
        # for often enough stops being read as the symptom it is — this lock
        # leaked on a failed build for a day, and the fix arrived through a
        # review rather than through the two times it was cleared by hand.
        lock.unlink(missing_ok=True)
        handle = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    os.write(handle, str(os.getpid()).encode())
    os.close(handle)
    return lock


def release(root: Path | None = None) -> None:
    lock = (Path(root).resolve() if root else SKILLS_ROOT) / ".triage-testbed.lock"
    lock.unlink(missing_ok=True)


def _assemble(root: Path) -> Testbed:
    """The `Testbed` value for trees that are already on disk."""
    matrix = json.loads((FIXTURES / "beads.json").read_text(encoding="utf-8"))
    scratch = root / CORPUS / SCRATCH
    scratch.mkdir(parents=True, exist_ok=True)
    return Testbed(
        root=root,
        path=root / PROJECT,
        clean=root / CLEAN_PROJECT,
        corpus=root / CORPUS,
        scratch=scratch,
        bead_ids=tuple(sorted(entry["id"] for entry in matrix)),
    )


def assert_fixture_roster(testbed: Testbed) -> None:
    """Refuse a database holding a bead its fixture never declared.

    The companion to `assert_db_inside`, and the only one of the two that can
    see the defect `skills-d96` was filed for: `bd init` copies an enclosing
    workspace's `.beads/config.yaml`, `sync.remote` included, then clones that
    remote's history — so a generated database came up holding eighty real
    beads at exactly the path a path check expects. The generator seeds an
    empty remote to stop that, but a seed can only protect the run that
    builds; `reuse` adopts trees an older generator left, so the question has
    to be asked again at run start, on both paths.

    Extra ids only: a status filter may legitimately hide a declared bead,
    nothing may add one. A database this cannot read is refused rather than
    passed — an unreadable roster is not an empty one.
    """
    for tree, fixture in ((testbed.path, "beads.json"),
                          (testbed.clean, "beads_clean.json")):
        proc = subprocess.run(["bd", "list", "--all", "--limit", "0", "--json"],
                              cwd=str(tree), capture_output=True, text=True)
        if proc.returncode != 0:
            raise AssertionError(f"cannot read bd's roster in {tree}: "
                                 f"{proc.stderr.strip()}")
        try:
            rows = json.loads(proc.stdout or "[]")
        except ValueError as err:
            raise AssertionError(f"bd in {tree} returned non-JSON: {err}") from err
        matrix = json.loads((FIXTURES / fixture).read_text(encoding="utf-8"))
        declared = {entry["id"] for entry in matrix}
        leaked = sorted({row["id"] for row in rows} - declared)
        if leaked:
            raise AssertionError(
                f"bd in {tree} holds beads the fixture never declared: {leaked}")


def build(root: Path | None = None) -> Testbed:
    """Invoke make_testbed.sh and return the trees it built.

    The generator wipes and rebuilds every run — its own contract — so one
    call per driver run is a full rebuild and no suite inherits another's
    writes. A lock makes that contract safe: see `_lock`.
    """
    root = Path(root).resolve() if root else SKILLS_ROOT
    _lock(root)
    # Everything after the lock is released on failure. A build that dies —
    # a flaky `bd init`, a full disk — otherwise leaves the lock behind with a
    # dead pid in it, and every later run refuses to start until a human
    # deletes the file. Failing fast is only useful while the failure is real;
    # a lock nobody holds turns a transient error into a permanent one.
    try:
        proc = subprocess.run(["sh", str(MAKE_TESTBED), "--root", str(root)],
                              capture_output=True, text=True, cwd=str(SKILLS_ROOT))
        if proc.returncode != 0:
            raise RuntimeError(f"make_testbed.sh failed ({proc.returncode}): "
                               f"{proc.stdout}{proc.stderr}")
        return _assemble(root)
    except BaseException:
        release(root)
        raise


def reuse(root: Path | None = None) -> Testbed:
    """Adopt the trees a previous run left behind, without rebuilding them.

    The one thing `build` cannot do, and the reason a limit hit used to cost a
    whole live run: the generator wipes and rebuilds, so starting the driver
    again to continue a sweep destroyed the sweep. With the trees kept on
    failure, the run directory and its ledger survive — and a triage run is
    resumable by design, from that ledger. This is what lets the harness use
    that.

    The marker check is the same one `teardown` and the generator apply, and it
    is what keeps `--reuse` from silently adopting some unrelated directory
    that happens to sit at the expected path. It says nothing about what is
    *inside* the databases it adopts — the trees may predate the seed that
    stops `bd init` inheriting a real tracker — so the driver asks
    `assert_fixture_roster` that question at run start, on this path and on
    the build path alike.
    """
    root = Path(root).resolve() if root else SKILLS_ROOT
    _lock(root)
    try:
        for tree in (root / PROJECT, root / CLEAN_PROJECT, root / CORPUS):
            if not (tree / MARKER).is_file():
                raise Missing(f"{tree} carries no {MARKER} marker — "
                              f"there is nothing to reuse, build instead")
        return _assemble(root)
    except BaseException:
        release(root)
        raise


def env(testbed: Testbed) -> dict:
    """`TRIAGE_PROJECTS_ROOT` is `inventory.resolve_repo_root`'s only source,
    and it is the testbed's parent, so `--project triage-testbed` and
    `--project triage-testbed-clean` both resolve inside the testbed."""
    return {**os.environ, "TRIAGE_PROJECTS_ROOT": str(testbed.root)}


def run(script: str, *args: str, testbed: Testbed,
        cwd: Path | None = None) -> tuple[int, str, str]:
    """(exit code, stdout, stderr) from one triage CLI, run as a real process.

    `script` is a name under triage/scripts/ or an absolute path, resolved
    against the repo's own `scripts/` — a suite runs those files, never a copy.
    The launcher is picked by suffix, this interpreter for a `.py` CLI and `sh`
    for a shell generator, so a launch depends on neither the file's shebang
    nor its mode.

    The default working directory is the testbed's scratch directory, never
    the skills repo: a script that writes relative to its caller — the defect
    commit 4e94681 fixed in `inventory.py` — must land inside the testbed even
    when a case forgets to say where it is standing.
    """
    target = Path(script)
    if not target.is_absolute():
        target = SCRIPTS / script
    launcher = sys.executable if target.suffix == ".py" else "sh"
    proc = subprocess.run([launcher, str(target), *args],
                          capture_output=True, text=True,
                          cwd=str(cwd or testbed.scratch), env=env(testbed))
    return proc.returncode, proc.stdout, proc.stderr


def _opened_database(tree: Path) -> str:
    """The database `bd` opens in `tree`, as `bd info` reports it, or `""`.

    Asked rather than recomputed. The replica this replaced walked for a
    `.beads` directory and stopped at a git root — which agrees with `bd` about
    paths and knows nothing about contents, so it passed a testbed whose
    database was a clone of the real skills tracker at the testbed's own path.
    A non-zero exit is an answer too: no database.
    """
    proc = subprocess.run(["bd", "info"], cwd=str(tree),
                          capture_output=True, text=True)
    return next((line.split(":", 1)[1].strip()
                 for line in proc.stdout.splitlines()
                 if line.startswith("Database:")), "")


def assert_db_inside(testbed: Testbed) -> None:
    """Hard stop — plan.md guard #1. Call after build() and before any suite."""
    for tree in (testbed.path, testbed.clean):
        opened = _opened_database(tree)
        if not opened:
            raise AssertionError(
                f"bd reports no database in {tree} — a testbed without one "
                f"would reach {SKILLS_ROOT / '.beads'}")
        if not opened.startswith(str(tree / ".beads")):
            raise AssertionError(
                f"bd in {tree} opened {opened}, outside the testbed")


def scratch_path(testbed: Testbed, name: str) -> Path:
    """A path under the testbed no triage script can mistake for a project."""
    return testbed.scratch / name


def teardown(testbed: Testbed) -> None:
    """Delete only what make_testbed.sh marked as its own — the same rule the
    generator applies, because the driver deletes on the same paths it does."""
    for tree in (testbed.path, testbed.clean, testbed.corpus):
        if not tree.exists():
            continue
        if not (tree / MARKER).is_file():
            raise AssertionError(f"refusing to remove {tree} — no {MARKER} marker")
        shutil.rmtree(tree)
