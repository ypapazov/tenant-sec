"""Thin pytest wrapper around the Node source-link unit checks."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = Path(__file__).resolve().parent / "test_source_links.js"


@pytest.mark.skipif(shutil.which("node") is None, reason="node is required")
def test_source_links_js():
    result = subprocess.run(
        ["node", str(SCRIPT)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "All source-link checks passed" in result.stdout
