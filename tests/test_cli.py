from __future__ import annotations

from unittest.mock import MagicMock, patch
from pathlib import Path
import pytest
from glancer.cli import main
from glancer.process import Video


@pytest.fixture
def mock_process_video(tmp_path: Path):
    with patch("glancer.cli.process_video") as mock:
        video_dir = tmp_path / "glancer" / "video_id"
        video_dir.mkdir(parents=True, exist_ok=True)
        captions_path = video_dir / "video_id.en.srt"
        captions_path.touch()
        mock.return_value = (
            video_dir,
            Video(url="http://example.com", title="Test Video", video_id="video_id"),
            captions_path,
        )
        yield mock


@pytest.fixture
def mock_parse_srt():
    with patch("glancer.cli.parse_srt") as mock:
        mock.return_value = []
        yield mock


@pytest.fixture
def mock_convert_to_html():
    with patch("glancer.cli.convert_to_html") as mock:
        mock.return_value = "<html></html>"
        yield mock


def test_main(
    mock_process_video: MagicMock,
    mock_parse_srt: MagicMock,
    mock_convert_to_html: MagicMock,
    tmp_path: Path,
):
    output_path = tmp_path / "output.html"
    main(
        [
            "http://example.com/video",
            str(output_path),
        ]
    )
    mock_process_video.assert_called_once()
    mock_parse_srt.assert_called_once()
    mock_convert_to_html.assert_called_once()
    assert output_path.exists()
    assert output_path.read_text() == "<html></html>"

def test_main_playlist(tmp_path: Path) -> None:
    with patch("glancer.cli.run") as mock_run:
        main(["--auto-cleanup", "http://playlist.test", str(tmp_path)])
    mock_run.assert_called_once_with(
        "http://playlist.test", str(tmp_path), verbose=False, auto_cleanup=True, detect_duplicates=True
    )
