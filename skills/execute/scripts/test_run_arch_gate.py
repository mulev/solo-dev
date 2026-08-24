"""Tests for run_arch_gate.py — focused on shim detection and exit codes.

Run with `python3 test_run_arch_gate.py` (no pytest dependency).
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

SCRIPT = Path(__file__).parent / "run_arch_gate.py"


def run(file: Path, *extra: str) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), str(file), *extra],
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout.strip()


def write(tmp: Path, name: str, body: str) -> Path:
    p = tmp / name
    p.write_text(body, encoding="utf-8")
    return p


def case_dart_reexport_shim_fails(tmp: Path) -> None:
    body = "\n".join(
        [
            "export 'dart:async';",
            "export 'dart:io';",
            "export 'package:myapp/core/models/book.dart';",
            "export 'package:myapp/features/library/services/book_file_picker.dart';",
            "export 'package:flutter/material.dart';",
        ]
    )
    f = write(tmp, "book_service_dependencies.dart", body)
    code, out = run(f)
    assert "SHIM=FAIL" in out, out
    assert code == 1, (code, out)


def case_dart_test_dependencies_shim_fails(tmp: Path) -> None:
    body = "\n".join(
        [
            "export 'package:flutter_test/flutter_test.dart';",
            "export 'package:integration_test/integration_test.dart';",
            "export 'test_helpers.dart';",
        ]
    )
    f = write(tmp, "file_import_limit_flow_test_dependencies.dart", body)
    code, out = run(f)
    assert "SHIM=FAIL" in out, out
    assert code == 1, (code, out)


def case_normal_dart_passes_shim(tmp: Path) -> None:
    body = "\n".join(
        [
            "import 'package:flutter/material.dart';",
            "",
            "class Reader {",
            "  final int pageCount;",
            "  Reader(this.pageCount);",
            "  bool get isEmpty => pageCount == 0;",
            "}",
        ]
    )
    f = write(tmp, "reader.dart", body)
    code, out = run(f)
    assert "SHIM=PASS" in out, out
    assert "LOC=PASS" in out, out
    assert code == 0, (code, out)


def case_typescript_barrel_fails(tmp: Path) -> None:
    body = "\n".join(
        [
            "export * from './reader';",
            "export * from './library';",
            "export { Book } from './book';",
        ]
    )
    f = write(tmp, "index.ts", body)
    code, out = run(f)
    assert "SHIM=FAIL" in out, out
    assert code == 1, (code, out)


def case_loc_overage_fails(tmp: Path) -> None:
    body = "\n".join(["x = 1"] * 50)
    f = write(tmp, "big.py", body)
    code, out = run(f, "--max-loc", "10")
    assert "LOC=FAIL" in out, out
    assert code == 1, (code, out)


def case_deps_marked_manual(tmp: Path) -> None:
    body = "\n".join(
        [
            "import os",
            "x = 1",
        ]
    )
    f = write(tmp, "ok.py", body)
    code, out = run(f)
    assert "DEPS=MANUAL" in out, out
    assert code == 0, (code, out)


def case_missing_file_returns_2(tmp: Path) -> None:
    code, out = run(tmp / "nope.dart")
    assert code == 2, (code, out)
    assert "ERROR=file_not_found" in out, out


def case_unknown_extension_marks_shim_manual(tmp: Path) -> None:
    body = "header line\n" * 5
    f = write(tmp, "weird.xyz", body)
    code, out = run(f)
    assert "SHIM=MANUAL" in out, out
    assert "DEPS=MANUAL" in out, out
    assert code == 0, (code, out)


def case_mostly_export_with_one_function_still_shim(tmp: Path) -> None:
    body = "\n".join(
        [
            "export 'a.dart';",
            "export 'b.dart';",
            "export 'c.dart';",
            "export 'd.dart';",
            "export 'e.dart';",
            "export 'f.dart';",
            "export 'g.dart';",
            "export 'h.dart';",
            "void noop() {}",
        ]
    )
    f = write(tmp, "shimmy.dart", body)
    code, out = run(f)
    assert "SHIM=FAIL" in out, out
    assert code == 1, (code, out)


def case_balanced_exports_and_code_passes(tmp: Path) -> None:
    body = "\n".join(
        [
            "export 'reader.dart';",
            "import 'package:flutter/material.dart';",
            "class App extends StatelessWidget {",
            "  const App({super.key});",
            "  @override",
            "  Widget build(BuildContext c) => const SizedBox();",
            "}",
        ]
    )
    f = write(tmp, "app.dart", body)
    code, out = run(f)
    assert "SHIM=PASS" in out, out
    assert code == 0, (code, out)


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
