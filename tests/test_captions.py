from __future__ import annotations
from pathlib import Path
import pytest
from PIL import Image
from glancer.slides import (
    Slide,
    generate_slides,
    render_slides,
    captions_to_html,
    normalize_caption_text,
)
from glancer.parser import Caption
from glancer.process import Video


@pytest.fixture
def sample_captions() -> list[Caption]:
    return [
        Caption(start=0.0, end=1.0, text="Hello"),
        Caption(start=1.0, end=2.0, text="World"),
    ]


@pytest.fixture
def sample_video() -> Video:
    return Video(url="http://example.com", title="Sample Video", video_id="sample")


def create_test_image(path: Path, color: tuple[int, int, int] = (100, 100, 100)) -> None:
    img = Image.new('RGB', (640, 480), color=color)
    img.save(path)


def test_generate_slides(sample_captions: list[Caption], tmp_path: Path) -> None:
    slides = generate_slides(sample_captions, tmp_path)
    assert len(slides) > 0
    assert all(isinstance(slide, Slide) for slide in slides)


def test_render_slides(sample_captions: list[Caption], tmp_path: Path) -> None:
    for i in range(2):
        create_test_image(tmp_path / f"glancer-img{i:04d}.jpg")
    slides = generate_slides(sample_captions, tmp_path)
    rendered_html = render_slides(slides, "http://example.com", tmp_path)
    assert isinstance(rendered_html, str)
    assert "slide-block" in rendered_html
    assert "data:image/jpeg;base64" in rendered_html


def test_captions_to_html(
    sample_captions: list[Caption], sample_video: Video, tmp_path: Path
) -> None:
    for i in range(2):
        create_test_image(tmp_path / f"glancer-img{i:04d}.jpg")

    html = captions_to_html(sample_video, tmp_path, sample_captions)
    assert isinstance(html, str)
    assert "Sample Video" in html
    assert "slide-block" in html


def test_missing_image_returns_empty(tmp_path: Path) -> None:
    from glancer.slides import slide_block
    result = slide_block("http://example.com", tmp_path, 99, False)
    assert result == ""


def test_normalize_caption_text() -> None:
    assert normalize_caption_text("  hello\nworld  ") == "hello world"
    assert normalize_caption_text("") == ""
