"""Exercise consent transitions through the actual browser loader."""

import shutil
import subprocess
from pathlib import Path


def test_clarity_consent_behavior():
    node = shutil.which("node")
    assert node is not None, "Node.js is required for site behavior tests"
    result = subprocess.run(
        [node, "--test", "tests/clarity_consent_harness.mjs"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_every_analytics_entry_point_has_a_place_to_change_consent():
    for name in ("index.html", "404.html", "logos.html"):
        html = Path("site", name).read_text(encoding="utf-8")
        assert 'class="privacy-note"' in html, name
