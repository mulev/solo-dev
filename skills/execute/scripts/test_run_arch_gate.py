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
            "export 'package:demo/core/models/book.dart';",
            "export 'package:demo/features/library/services/book_file_picker.dart';",
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


def case_python_docstring_prose_is_not_code(tmp: Path) -> None:
    """A docstring is a string literal, not a comment and not `/*` delimited,
    so the line filter never saw one and charged 43 lines of explanation to a
    3-line module."""
    prose = "\n".join(f"    line {n} of explanation." for n in range(1, 41))
    body = (
        f'"""Module summary.\n\n{prose}\n"""\n'
        "import os\n"
        "\n"
        "def f(path):\n"
        '    """One-line docstring."""\n'
        "    return os.path.basename(path)\n"
    )
    f = write(tmp, "prose.py", body)
    code, out = run(f, "--max-loc", "10")
    assert "LOC=PASS(3+43doc)" in out, out
    assert code == 0, (code, out)


def case_python_data_blob_is_still_code(tmp: Path) -> None:
    """Only a docstring is prose. An assigned triple-quoted literal is content
    the file carries — `prompt-wizard/scripts/init_skill.py` holds an 86-line
    one — and a triple-quote scanner would erase it from the count."""
    blob = "\n".join(f"row {n}" for n in range(1, 41))
    body = f'BLOB = """\n{blob}\n"""\n'
    f = write(tmp, "blob.py", body)
    code, out = run(f, "--max-loc", "10")
    assert "LOC=FAIL(42>10)" in out, out
    assert "doc)" not in out, out
    assert code == 1, (code, out)


def case_python_shim_denominator_excludes_prose(tmp: Path) -> None:
    """Prose in the denominator dilutes the export ratio, so a barrel behind a
    long docstring reads as a normal module: 4/37 instead of 4/5."""
    prose = "\n".join(f"line {n}." for n in range(1, 31))
    body = (
        f'"""Barrel.\n\n{prose}\n"""\n'
        "from a import *\n"
        "from b import *\n"
        "from c import *\n"
        "from d import *\n"
        "x = 1\n"
    )
    f = write(tmp, "barrel.py", body)
    code, out = run(f)
    assert "SHIM=FAIL(reexport=4/5)" in out, out
    assert code == 1, (code, out)


def case_unparsable_python_counts_every_line(tmp: Path) -> None:
    """A gate that crashes on a half-edited or py2 file is worse than one that
    overcounts it, so a file that will not parse counts as it always did.

    The fixture carries a docstring ahead of the syntax error on purpose: with
    no prose in it the assertion would hold even if `prose_lines` were deleted,
    and could not tell the `SyntaxError` fallback from any other empty result.
    """
    body = (
        '"""Module summary.\n\nline one.\nline two.\n"""\n'
        "def broken(:\n" + "\n".join(["x = 1"] * 20) + "\n"
    )
    f = write(tmp, "broken.py", body)
    code, out = run(f, "--max-loc", "10")
    assert "LOC=FAIL(25>10)" in out, out
    assert code == 1, (code, out)


def case_python_over_the_limit_keeps_the_doc_suffix(tmp: Path) -> None:
    """The suffix goes into both banner branches, and the FAIL branch ends in
    `>` rather than `)` — so a `"doc)" not in out` assertion cannot catch a
    regression that drops it there. This pins the FAIL render itself."""
    prose = "\n".join(f"line {n}." for n in range(1, 21))
    body = f'"""Summary.\n\n{prose}\n"""\n' + "\n".join(["x = 1"] * 12) + "\n"
    f = write(tmp, "over.py", body)
    code, out = run(f, "--max-loc", "10")
    assert "LOC=FAIL(12+22doc>10)" in out, out
    assert code == 1, (code, out)


def case_a_block_comment_scanner_does_not_run_over_python(tmp: Path) -> None:
    """Python has no `/* */`, so scanning for one reads a string literal as a
    comment. Here `/*` sits in an assigned blob and the `*/` sits in a
    docstring the prose filter removes, so the block never closes and the rest
    of the file disappears from the count."""
    body = (
        'BLOB = """\n'
        "/* opens a block\n"
        '"""\n'
        "\n"
        "\n"
        "def f():\n"
        '    """closes */ here"""\n'
        "    return 2\n"
        "\n"
        "\n"
        "z = 3\n"
    )
    f = write(tmp, "blocks.py", body)
    code, out = run(f)
    assert "LOC=PASS(6+1doc)" in out, out
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
