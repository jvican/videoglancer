from __future__ import annotations
from pathlib import Path
from unittest.mock import MagicMock
import pytest
from glancer.captions import (
    Slide,
    generate_slides,
    render_slides,
    captions_to_html,
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
    return Video(url="http://example.com", title="Sample Video", file="sample.mp4")


def test_generate_slides(sample_captions: list[Caption], tmp_path: Path) -> None:
    slides = generate_slides(sample_captions, tmp_path)
    assert len(slides) > 0
    assert all(isinstance(slide, Slide) for slide in slides)


def test_render_slides(sample_captions: list[Caption], tmp_path: Path) -> None:
    # Create dummy image files for the test to pass
    for i in range(2):
        (tmp_path / f"glancer-img{i:04d}.jpg").touch()
    slides = generate_slides(sample_captions, tmp_path)
    rendered_html = render_slides(slides, "http://example.com", tmp_path)
    assert isinstance(rendered_html, str)
    assert "slide-block" in rendered_html


def test_captions_to_html(
    sample_captions: list[Caption], sample_video: Video, tmp_path: Path
) -> None:
    # Create dummy image files for the test to pass
    for i in range(2):
        (tmp_path / f"glancer-img{i:04d}.jpg").touch()

    html = captions_to_html(sample_video, tmp_path, sample_captions)
    assert isinstance(html, str)
    assert "Sample Video" in html
    assert "slide-block" in html
