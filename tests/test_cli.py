from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
from pathlib import Path
import pytest
from PIL import Image
from glancer.cli import main
from glancer.content import ExtractedContent, VideoInfo, SlideData
from glancer.process import Video


def _create_test_image(path: Path, color: tuple[int, int, int]) -> None:
    """Create a simple test JPEG image."""
    image = Image.new("RGB", (64, 64), color=color)
    image.save(path, format="JPEG")


@pytest.fixture
def mock_process_video(tmp_path: Path):
    with patch("glancer.cli.process_video") as mock:
        video_dir = tmp_path / "glancer" / "video_id"
        video_dir.mkdir(parents=True, exist_ok=True)
        captions_path = video_dir / "video_id.en.srt"
        captions_path.touch()
        # Create test images
        _create_test_image(video_dir / "glancer-img0000.jpg", (200, 100, 100))
        _create_test_image(video_dir / "glancer-img0001.jpg", (100, 200, 100))
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
        "http://playlist.test",
        str(tmp_path),
        verbose=False,
        auto_cleanup=True,
        detect_duplicates=True,
        output_pdf=False,
        compact=False,
        slide_mode=False,
        extract_json=False,
        from_json=None,
    )


def test_main_extract_json(
    mock_process_video: MagicMock,
    mock_parse_srt: MagicMock,
    tmp_path: Path,
):
    """Test --extract-json outputs JSON instead of HTML."""
    output_path = tmp_path / "output.json"
    main(
        [
            "--extract-json",
            "http://example.com/video",
            str(output_path),
        ]
    )
    mock_process_video.assert_called_once()
    mock_parse_srt.assert_called_once()
    assert output_path.exists()
    # Verify valid JSON with new schema
    data = json.loads(output_path.read_text())
    assert "video" in data
    assert "slides" in data
    assert data["video"]["url"] == "http://example.com"


def test_main_from_json(tmp_path: Path):
    """Test --from-json generates HTML from existing JSON."""
    json_path = tmp_path / "content.json"
    content = ExtractedContent(
        video=VideoInfo(url="http://example.com", title="Test Video", id="test123"),
        slides=[],
        seconds_per_shot=30,
    )
    content.save(json_path)

    output_path = tmp_path / "output.html"
    with patch("glancer.cli.render_html_from_json") as mock_render:
        mock_render.return_value = "<html>from json</html>"
        main(["--from-json", str(json_path), str(output_path)])
    mock_render.assert_called_once()
    assert output_path.exists()


def test_main_from_json_pdf(tmp_path: Path):
    """Test --from-json with --pdf generates PDF from JSON."""
    json_path = tmp_path / "content.json"
    content = ExtractedContent(
        video=VideoInfo(url="http://example.com", title="Test Video", id="test123"),
        slides=[],
        seconds_per_shot=30,
    )
    content.save(json_path)

    output_path = tmp_path / "output.pdf"
    with patch("glancer.cli.render_pdf_from_json") as mock_render:
        main(["--from-json", str(json_path), "--pdf", str(output_path)])
    mock_render.assert_called_once()


def test_main_rejects_both_positional_args_with_from_json(tmp_path: Path):
    """Test that both positional args with --from-json is rejected."""
    json_path = tmp_path / "content.json"
    json_path.write_text('{"schema_version": 1}')

    with pytest.raises(SystemExit):
        main(["--from-json", str(json_path), "output.html", "extra_arg"])


def test_main_rejects_extract_json_with_pdf():
    """Test that --extract-json and --pdf cannot be used together."""
    with pytest.raises(SystemExit):
        main(["--extract-json", "--pdf", "http://example.com"])


def test_main_rejects_extract_json_with_from_json(tmp_path: Path):
    """Test that --extract-json and --from-json cannot be used together."""
    json_path = tmp_path / "content.json"
    json_path.write_text('{"schema_version": 1}')

    with pytest.raises(SystemExit):
        main(["--extract-json", "--from-json", str(json_path)])


def test_main_requires_url_or_from_json():
    """Test that either URL or --from-json is required."""
    with pytest.raises(SystemExit):
        main([])
