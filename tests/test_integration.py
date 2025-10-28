from __future__ import annotations
import subprocess
from pathlib import Path
import pytest


@pytest.mark.integration
def test_glancer_integration_real(tmp_path: Path):
    """Integration test with real YouTube URL - slow, requires network."""
    output_path = tmp_path / "output.html"
    result = subprocess.run(
        [
            "glancer",
            "https://www.youtube.com/watch?v=yd37O-xu2-4",
            str(output_path),
        ],
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    assert output_path.exists()
    html_content = output_path.read_text()
    assert "<!doctype html>" in html_content.lower()
    assert "slide-block" in html_content
