from __future__ import annotations
from unittest.mock import patch, MagicMock
from pathlib import Path
import pytest
from glancer.cli import main


@pytest.fixture
def mock_process_url(tmp_path: Path):
    with patch("glancer.cli.process_url") as mock:
        video_dir = tmp_path / "glancer" / "video_id"
        video_dir.mkdir(parents=True, exist_ok=True)
        captions_path = video_dir / "video_id.en.vtt"
        captions_path.touch()
        mock.return_value = (
            video_dir,
            MagicMock(url="http://example.com", title="Test Video", file="video_id"),
            captions_path,
        )
        yield mock


@pytest.fixture
def mock_parse_vtt():
    with patch("glancer.cli.parse_vtt") as mock:
        mock.return_value = []
        yield mock


@pytest.fixture
def mock_convert_to_html():
    with patch("glancer.cli.convert_to_html") as mock:
        mock.return_value = "<html></html>"
        yield mock


def test_main(
    mock_process_url: MagicMock,
    mock_parse_vtt: MagicMock,
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
    mock_process_url.assert_called_once()
    mock_parse_vtt.assert_called_once()
    mock_convert_to_html.assert_called_once()
    assert output_path.exists()
    assert output_path.read_text() == "<html></html>"
