"""Only the known Models route recovers through the working root document."""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_models_404_recovery_preserves_filters_and_leaves_unknown_paths_alone():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    subprocess.run([node, "tests/route_recovery_harness.mjs"], cwd=ROOT, check=True, timeout=30)
    page = (ROOT / "site/404.html").read_text()
    assert '<script src="/assets/route-recovery.js"></script>' in page
    assert '<meta name="robots" content="noindex">' in page
    assert 'href="/?view=models"' in page
