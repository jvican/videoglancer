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


def test_last_slide_includes_all_remaining_captions(tmp_path: Path) -> None:
    """Test that captions in the final partial interval are not cut off.

    Regression test for bug where captions after the last full 30-second
    interval were excluded. For example, with a 3988s video:
    - floor(3988/30) = 132, creating slides 0-131
    - Slide 131 covers 3930-3960s
    - Captions from 3960-3988s were being cut off

    The fix extends the last slide to include all remaining captions.
    """
    from glancer.slides import captions_per_slide

    # Simulate a video ending at 3988 seconds (like the bug report)
    # with captions extending to the end
    captions = [
        # Earlier captions in the last full interval (3930-3960s)
        Caption(start=3957.0, end=3960.0, text="caption at end of last full interval"),
        # Captions in the final partial interval (3960-3988s) that were being cut off
        Caption(start=3960.0, end=3963.0, text="first caption in partial interval"),
        Caption(start=3963.0, end=3966.0, text="second caption in partial interval"),
        Caption(start=3985.0, end=3988.0, text="last caption at very end"),
    ]

    slides = captions_per_slide(captions)

    # Should create floor(3988/30) = 132 slides (indices 0-131)
    assert len(slides) == 132

    # The last slide (index 131) should include ALL captions from 3930s onwards
    last_slide = slides[-1]
    assert len(last_slide) == 4, f"Expected 4 captions in last slide, got {len(last_slide)}"

    # Verify all captions are included, including those after 3960s
    caption_texts = [cap.text for cap in last_slide]
    assert "caption at end of last full interval" in caption_texts
    assert "first caption in partial interval" in caption_texts
    assert "second caption in partial interval" in caption_texts
    assert "last caption at very end" in caption_texts
