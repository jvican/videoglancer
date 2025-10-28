from __future__ import annotations
import subprocess
from pathlib import Path
import pytest

def test_glancer_integration(tmp_path: Path):
    output_path = tmp_path / "output.html"
    result = subprocess.run(
        [
            "glancer",
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            str(output_path),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert output_path.exists()
    html_content = output_path.read_text()
    assert "Rick Astley" in html_content
