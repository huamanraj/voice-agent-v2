"""Pytest hooks shared across the test suite."""

from __future__ import annotations

import os
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_PYTEST_TMP = _PROJECT_ROOT / ".pytest-tmp"


def pytest_configure(config) -> None:
    """Use a writable project-local temp root on Windows."""
    _PYTEST_TMP.mkdir(parents=True, exist_ok=True)
    # Some tools still read TEMP/TMP even when --basetemp is set.
    os.environ.setdefault("TMP", str(_PYTEST_TMP))
    os.environ.setdefault("TEMP", str(_PYTEST_TMP))
    os.environ.setdefault("TMPDIR", str(_PYTEST_TMP))
