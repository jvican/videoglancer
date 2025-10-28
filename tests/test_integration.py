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

    if result.returncode != 0:
        if "Sign in to confirm you're not a bot" in result.stderr or "returned non-zero exit status" in result.stderr:
            pytest.skip(f"YouTube access blocked or yt-dlp issue: {result.stderr}")
        pytest.fail(f"glancer failed:\nstdout: {result.stdout}\nstderr: {result.stderr}")

    assert output_path.exists()
    html_content = output_path.read_text()
    assert "<!doctype html>" in html_content.lower()
    assert "slide-block" in html_content
