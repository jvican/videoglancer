from __future__ import annotations
from pathlib import Path
import pytest
from PIL import Image
from glancer.slides import (
    Slide,
    combine_caption_texts,
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


def test_combine_caption_texts_removes_rolling_caption_overlap() -> None:
    texts = [
        (
            "Are we Oh, >> yes. Okay, we are we are live. Um, so hello everyone. "
            "Uh, bear with us I guess uh as we kind of figure all of these things "
            "out. Um, so I can kind of go over just for today like uh the main "
            "speaker will be coming in 10 minutes but we will be giving kind of a "
            "brief intro of of what this all is uh what you guys can expect for "
            "uh the coming few days. Um and yeah uh so basically uh this"
        ),
        (
            "can expect for uh the coming few days. Um and yeah uh so basically "
            "uh this series um is going to be as you already know uh on this "
            "YouTube channel for the next 5 days."
        ),
    ]

    combined = combine_caption_texts(texts)

    assert combined.count(
        "can expect for uh the coming few days. Um and yeah uh so basically uh this"
    ) == 1
    assert "this series um is going to be as you already know" in combined


def test_combine_caption_texts_does_not_merge_short_common_prefix() -> None:
    texts = [
        "I think this works well for most examples",
        "I think we should test a different case too",
    ]

    combined = combine_caption_texts(texts)

    assert combined == (
        "I think this works well for most examples "
        "I think we should test a different case too"
    )


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


def test_caption_ending_on_boundary_is_not_duplicated() -> None:
    from glancer.slides import captions_per_slide

    captions = [
        Caption(start=20.0, end=30.0, text="ends on boundary"),
        Caption(start=30.0, end=35.0, text="starts at boundary"),
        Caption(start=58.0, end=61.0, text="crosses second boundary"),
    ]

    slides = captions_per_slide(captions)

    assert len(slides) == 2
    assert [cap.text for cap in slides[0]] == ["ends on boundary"]
    assert [cap.text for cap in slides[1]] == [
        "starts at boundary",
        "crosses second boundary",
    ]


def test_caption_starting_on_boundary_belongs_to_next_slide() -> None:
    from glancer.slides import captions_per_slide

    captions = [
        Caption(start=0.0, end=10.0, text="first slide"),
        Caption(start=30.0, end=31.0, text="next slide"),
        Caption(start=31.0, end=32.0, text="also next slide"),
        Caption(start=59.0, end=61.0, text="final slide anchor"),
    ]

    slides = captions_per_slide(captions)

    assert len(slides) == 2
    assert [cap.text for cap in slides[0]] == ["first slide"]
    assert [cap.text for cap in slides[1]] == [
        "next slide",
        "also next slide",
        "final slide anchor",
    ]


def test_caption_spanning_boundary_moves_to_later_slide() -> None:
    from glancer.slides import captions_per_slide

    captions = [
        Caption(start=24.560, end=32.800, text="can expect for uh the coming few days."),
        Caption(start=27.439, end=36.640, text="Um and yeah uh so basically uh this"),
        Caption(start=32.800, end=38.800, text="series um is going to be as you already know"),
        Caption(start=58.000, end=61.000, text="later caption to force second slide"),
    ]

    slides = captions_per_slide(captions)

    assert len(slides) == 2
    assert slides[0] == []
    assert [cap.text for cap in slides[1]] == [
        "can expect for uh the coming few days.",
        "Um and yeah uh so basically uh this",
        "series um is going to be as you already know",
        "later caption to force second slide",
    ]


def test_caption_text_that_rolls_across_boundary_is_rendered_once() -> None:
    from glancer.slides import captions_per_slide

    captions = [
        Caption(
            start=24.560,
            end=32.800,
            text="can expect for uh the coming few days.",
        ),
        Caption(
            start=27.439,
            end=36.640,
            text="can expect for uh the coming few days. Um and yeah uh so basically uh this",
        ),
        Caption(
            start=32.800,
            end=38.800,
            text="Um and yeah uh so basically uh this series um is going to be as you already know",
        ),
        Caption(start=58.000, end=61.000, text="later caption to force second slide"),
    ]

    slides = captions_per_slide(captions)

    assert slides[0] == []
    assert combine_caption_texts([cap.text for cap in slides[1]]) == (
        "can expect for uh the coming few days. Um and yeah uh so basically uh this "
        "series um is going to be as you already know later caption to force second slide"
    )


def test_rolling_caption_overlap_moves_to_later_slide() -> None:
    from glancer.slides import captions_per_slide

    captions = [
        Caption(
            start=20.0,
            end=28.0,
            text=(
                "popular choice in modern ams including llama from Madam Quinn "
                "from Alibaba and"
            ),
        ),
        Caption(
            start=31.0,
            end=39.0,
            text=(
                "popular choice in modern ams including llama from Madam Quinn "
                "from Alibaba and Gamma from Google."
            ),
        ),
        Caption(start=58.0, end=61.0, text="final slide anchor"),
    ]

    slides = captions_per_slide(captions)

    assert [cap.text for cap in slides[0]] == [
        "popular choice in modern ams including llama from Madam Quinn from Alibaba and"
    ]
    assert [cap.text for cap in slides[1]] == [
        "popular choice in modern ams including llama from Madam Quinn from Alibaba and Gamma from Google.",
        "final slide anchor",
    ]


def test_boundary_crossing_cues_move_to_later_slide_from_real_srt_pattern() -> None:
    from glancer.slides import captions_per_slide

    captions = [
        Caption(start=18.400, end=24.640, text="costs cutting API pricing by 50%. But"),
        Caption(start=22.320, end=27.119, text="how can we make attention mechanism so"),
        Caption(start=24.640, end=29.760, text="efficient? As usual, let's build out the"),
        Caption(start=27.119, end=31.519, text="method from the first principle. But if"),
        Caption(start=29.760, end=33.840, text="you are already familiar with some of"),
        Caption(start=31.519, end=35.920, text="the basics, feel free to jump ahead to"),
        Caption(start=33.840, end=37.920, text="the relevant chapters."),
        Caption(start=58.000, end=61.000, text="final slide anchor"),
    ]

    slides = captions_per_slide(captions)

    assert [cap.text for cap in slides[0]] == [
        "costs cutting API pricing by 50%. But",
        "how can we make attention mechanism so",
        "efficient? As usual, let's build out the",
    ]
    assert [cap.text for cap in slides[1]] == [
        "method from the first principle. But if",
        "you are already familiar with some of",
        "the basics, feel free to jump ahead to",
        "the relevant chapters.",
        "final slide anchor",
    ]
