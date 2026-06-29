"""
Regression test for the runtime guards in commit()/rollback().

These checks used to be ``assert`` statements, which ``python -O`` strips: under
optimized mode a commit/rollback with no active transaction would raise an
AttributeError on ``None`` instead of a clear error. They are now explicit
``raise`` statements, so they must survive ``python -O``.

This is a hand-written sync-only test (it shells out to ``python -O``) and is not
transpiled. It does not need a live database: a truthy dummy driver lets
``ensure_connection`` skip real connection setup, and the guard fires before any
driver call.
"""

import subprocess
import sys


def _run_guard_under_optimized_mode(method: str) -> str:
    script = (
        "from neomodel import db\n"
        # Truthy dummy driver so ensure_connection does not try to connect.
        "db.driver = object()\n"
        "try:\n"
        f"    db.{method}()\n"
        "except RuntimeError:\n"
        "    print('RUNTIME_ERROR')\n"
        "except Exception as exc:\n"
        "    print('OTHER:' + type(exc).__name__)\n"
        "else:\n"
        "    print('NO_ERROR')\n"
    )
    result = subprocess.run(
        [sys.executable, "-O", "-c", script],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def test_commit_guard_survives_optimized_mode():
    # Under -O an assert would be stripped and we'd get AttributeError on None.
    assert _run_guard_under_optimized_mode("commit") == "RUNTIME_ERROR"


def test_rollback_guard_survives_optimized_mode():
    assert _run_guard_under_optimized_mode("rollback") == "RUNTIME_ERROR"
