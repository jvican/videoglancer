from __future__ import annotations
import base64
import html
import logging
import math
import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING

from .html_builder import embody
from .image_similarity import find_similar_shots
from .parser import Caption
from .process import Video

if TYPE_CHECKING:
    from .content import SlideData

logger = logging.getLogger(__name__)

SECONDS_PER_SHOT = 30


@dataclass(frozen=True)
class Slide:
    index: int
    captions: list[Caption]
    duplicate: bool


# === Phase 1: Generate HTML from video processing ===


def convert_to_html(
    video: Video,
    directory: Path,
    captions: list[Caption],
    detect_duplicates: bool = True,
) -> str:
    """Generate HTML from video processing results (Phase 1 or standalone)."""
    slides = generate_slides(captions, directory, detect_duplicates)
    slides_html = render_slides(slides, video.url, directory)
    return embody(video, slides_html)


def generate_slides(
    captions: list[Caption], directory: Path, detect_duplicates: bool = True
) -> list[Slide]:
    """Generate Slide objects from captions and image directory."""
    if not captions:
        return []

    per_slide = captions_per_slide(captions)
    logger.debug(f"Generated {len(per_slide)} slides from captions")

    if detect_duplicates:
        duplicate_shots = find_similar_shots(directory.glob("glancer-img*.jpg"))
    else:
        duplicate_shots = set()

    slides: list[Slide] = []
    for index, slide_captions in enumerate(per_slide):
        is_duplicate = index in duplicate_shots
        slides.append(
            Slide(index=index, captions=slide_captions, duplicate=is_duplicate)
        )

    if slides:
        logger.debug(f"Created {len(slides)} slides (indices 0-{len(slides) - 1})")

    return slides


def render_slides(slides: list[Slide], url: str, directory: Path) -> str:
    """Render all slides to HTML."""
    blocks = [render_slide(slide, url, directory) for slide in slides]
    return "\n".join(blocks)


def render_slide(slide: Slide, url: str, directory: Path) -> str:
    """Render a single slide to HTML."""
    image_block = slide_block(url, directory, slide.index, slide.duplicate)
    if not image_block:
        return ""
    text_block = caps(slide.captions)
    to_video = to_video_block(url, slide.index)
    return f"{image_block}{text_block}{to_video}</div>"


def slide_block(url: str, directory: Path, shot: int, duplicate: bool) -> str:
    """Generate HTML for a slide image from file."""
    img_path = directory / f"glancer-img{shot:04d}.jpg"
    if not img_path.exists():
        all_images = sorted(directory.glob("glancer-img*.jpg"))
        image_numbers = []
        for img in all_images:
            try:
                num = int(img.stem.replace("glancer-img", ""))
                image_numbers.append(num)
            except ValueError:
                pass

        context = [num for num in image_numbers if abs(num - shot) <= 5]

        logger.warning(
            f"Missing image for slide {shot}: {img_path}\n"
            f"  Expected timestamp: {shot * SECONDS_PER_SHOT}s\n"
            f"  Total images available: {len(all_images)}\n"
            f"  Image numbers near slide {shot}: {context if context else 'none'}"
        )
        return ""
    data = img_path.read_bytes()
    encoded = base64.b64encode(data).decode("ascii")
    return _slide_block_html(shot, encoded, duplicate)


# === Phase 2: Generate HTML from extracted JSON ===


def render_html_from_json(video_url: str, video_title: str, slides: list["SlideData"]) -> str:
    """Generate HTML from pre-extracted slide data (Phase 2).

    Args:
        video_url: Video URL for links
        video_title: Video title for page header
        slides: Pre-processed slide data from JSON

    Returns:
        Complete HTML document
    """
    from .process import Video
    video = Video(url=video_url, title=video_title, video_id="")
    slides_html = _render_slides_from_data(slides, video_url)
    return embody(video, slides_html)


def _render_slides_from_data(slides: list["SlideData"], url: str) -> str:
    """Render pre-extracted slides to HTML."""
    blocks = []
    for slide in slides:
        block = _render_slide_from_data(slide, url)
        if block:
            blocks.append(block)
    return "\n".join(blocks)


def _render_slide_from_data(slide: "SlideData", url: str) -> str:
    """Render a single pre-extracted slide to HTML."""
    image_block = _slide_block_html(slide.index, slide.image_base64, slide.is_duplicate)
    text_block = f"\t<div class='txt'>\n\t\t{slide.caption_text}\n\t</div>" if slide.caption_text else "\t<div class='txt'>\n\t</div>"
    to_video = to_video_block(url, slide.index)
    return f"{image_block}{text_block}{to_video}</div>"


def _slide_block_html(shot: int, image_base64: str, duplicate: bool) -> str:
    """Generate HTML for a slide image from base64 data."""
    classes = ["slide-block"]
    if duplicate:
        classes.append("duplicate")
    class_attr = " ".join(classes)
    return (
        f"<div id='slide{shot}' class='{class_attr}'>\n"
        "\t<div class='img'>\n"
        f"\t\t<img src='data:image/jpeg;base64, {image_base64}'/></a>\n"
        "\t</div>\n"
    )


# === Caption processing (shared) ===


def to_video_block(url: str, shot: int) -> str:
    """Generate the "go to video" link block."""
    when = shot_seconds(shot, SECONDS_PER_SHOT)
    return (
        f"<div class='to-video'><a title='Go to video at timestamp {when}s' "
        f"href='{url}&t={when}s'>&#8688;</a></div>"
    )


def caps(captions: list[Caption]) -> str:
    """Generate caption text HTML from Caption objects."""
    if not captions:
        return "\t<div class='txt'>\n\t</div>"

    paragraphs = [normalize_caption_text(caption.text) for caption in captions]
    paragraphs = [text for text in paragraphs if text]
    if not paragraphs:
        return "\t<div class='txt'>\n\t</div>"
    combined = " ".join(paragraphs)
    combined = " ".join(combined.split())
    return f"\t<div class='txt'>\n\t\t{combined}\n\t</div>"


def get_caption_texts(captions: list[Caption]) -> list[str]:
    """Get combined caption text for each slide (for JSON extraction).

    Returns:
        List of caption texts, one per slide index
    """
    per_slide = captions_per_slide(captions)
    texts = []
    for slide_captions in per_slide:
        paragraphs = [normalize_caption_text(c.text) for c in slide_captions]
        paragraphs = [t for t in paragraphs if t]
        combined = " ".join(paragraphs)
        combined = " ".join(combined.split())
        texts.append(combined)
    return texts


def normalize_caption_text(text: str) -> str:
    """Normalize caption text (remove extra whitespace)."""
    return " ".join(text.strip().replace("\n", " ").split())


def captions_per_slide(captions: list[Caption]) -> list[list[Caption]]:
    """Group captions by slide (30-second intervals)."""
    cleaned = [clean_caption(caption) for caption in captions]
    cleaned = [caption for caption in cleaned if caption.text]
    total_shots = num_shots(cleaned, SECONDS_PER_SHOT)
    if total_shots <= 0:
        return []

    slides: list[list[Caption]] = []
    for shot_index in range(total_shots):
        shot_start = shot_index * SECONDS_PER_SHOT
        if shot_index == total_shots - 1:
            shot_end = cleaned[-1].end
        else:
            shot_end = shot_start + SECONDS_PER_SHOT
        overlapping = [
            caption
            for caption in cleaned
            if overlaps_interval(shot_start, shot_end, caption.start, caption.end)
        ]
        slides.append(overlapping)
    return slides


def shot_seconds(shot_number: int, secs_per_shot: int) -> int:
    """Convert shot number to seconds."""
    return shot_number * secs_per_shot


def num_shots(captions: list[Caption], secs_per_shot: int) -> int:
    """Calculate number of shots needed for captions."""
    if not captions:
        return 0

    last_end = captions[-1].end
    shots = int(math.floor(last_end / secs_per_shot))
    return max(1, shots)


def clean_caption(caption: Caption) -> Caption:
    """Clean HTML tags and normalize whitespace in caption."""
    unescaped = html.unescape(caption.text)
    cleaned_text = strip_tags(unescaped)
    normalized = cleaned_text.replace("\u00a0", " ")
    return replace(caption, text=normalized.strip())


TAG_RE = re.compile(r"<[^>]+>")


def strip_tags(text: str) -> str:
    """Remove HTML tags from text."""
    return TAG_RE.sub("", text)


def overlaps_interval(
    start_a: float, end_a: float, start_b: float, end_b: float
) -> bool:
    """Check if two time intervals overlap."""
    return start_a <= end_b and end_a >= start_b
