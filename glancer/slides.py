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
from .image_similarity import find_similar_shots, find_similar_shots_from_data
from .parser import Caption
from .process import Video

if TYPE_CHECKING:
    from .content import ExtractedContent

logger = logging.getLogger(__name__)

SECONDS_PER_SHOT = 30


@dataclass(frozen=True)
class Slide:
    index: int
    captions: list[Caption]
    duplicate: bool


def convert_to_html(
    video: Video,
    directory: Path,
    captions: list[Caption],
    detect_duplicates: bool = True,
) -> str:
    return captions_to_html(video, directory, captions, detect_duplicates)


def captions_to_html(
    video: Video,
    directory: Path,
    captions: list[Caption],
    detect_duplicates: bool = True,
) -> str:
    slides = generate_slides(captions, directory, detect_duplicates)
    slides_html = render_slides(slides, video.url, directory)
    return embody(video, slides_html)


def generate_slides(
    captions: list[Caption], directory: Path, detect_duplicates: bool = True
) -> list[Slide]:
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
    blocks = [render_slide(slide, url, directory) for slide in slides]
    return "\n".join(blocks)


def render_slide(slide: Slide, url: str, directory: Path) -> str:
    image_block = slide_block(url, directory, slide.index, slide.duplicate)
    if not image_block:
        return ""
    text_block = caps(slide.captions)
    to_video = to_video_block(url, slide.index)
    return f"{image_block}{text_block}{to_video}</div>"


def slide_block(url: str, directory: Path, shot: int, duplicate: bool) -> str:
    img_path = directory / f"glancer-img{shot:04d}.jpg"
    if not img_path.exists():
        # Log available images around this slide number
        all_images = sorted(directory.glob("glancer-img*.jpg"))
        image_numbers = []
        for img in all_images:
            try:
                num = int(img.stem.replace("glancer-img", ""))
                image_numbers.append(num)
            except ValueError:
                pass

        context = []
        for num in image_numbers:
            if abs(num - shot) <= 5:
                context.append(num)

        logger.warning(
            f"Missing image for slide {shot}: {img_path}\n"
            f"  Expected timestamp: {shot * SECONDS_PER_SHOT}s\n"
            f"  Total images available: {len(all_images)}\n"
            f"  Image numbers near slide {shot}: {context if context else 'none'}"
        )
        return ""
    data = img_path.read_bytes()
    encoded = base64.b64encode(data).decode("ascii")
    classes = ["slide-block"]
    if duplicate:
        classes.append("duplicate")
    class_attr = " ".join(classes)
    return (
        f"<div id='slide{shot}' class='{class_attr}'>\n"
        "\t<div class='img'>\n"
        f"\t\t<img src='data:image/jpeg;base64, {encoded}'/></a>\n"
        "\t</div>\n"
    )


def to_video_block(url: str, shot: int) -> str:
    when = shot_seconds(shot, SECONDS_PER_SHOT)
    return (
        f"<div class='to-video'><a title='Go to video at timestamp {when}s' "
        f"href='{url}&t={when}s'>&#8688;</a></div>"
    )


def caps(captions: list[Caption]) -> str:
    if not captions:
        return "\t<div class='txt'>\n\t</div>"

    paragraphs = [normalize_caption_text(caption.text) for caption in captions]
    paragraphs = [text for text in paragraphs if text]
    if not paragraphs:
        return "\t<div class='txt'>\n\t</div>"
    combined = " ".join(paragraphs)
    combined = " ".join(combined.split())
    return f"\t<div class='txt'>\n\t\t{combined}\n\t</div>"


def normalize_caption_text(text: str) -> str:
    return " ".join(text.strip().replace("\n", " ").split())


def captions_per_slide(captions: list[Caption]) -> list[list[Caption]]:
    cleaned = [clean_caption(caption) for caption in captions]
    cleaned = [caption for caption in cleaned if caption.text]
    total_shots = num_shots(cleaned, SECONDS_PER_SHOT)
    if total_shots <= 0:
        return []

    slides: list[list[Caption]] = []
    for shot_index in range(total_shots):
        shot_start = shot_index * SECONDS_PER_SHOT
        # For the last slide, extend to capture all remaining captions
        # instead of cutting off at the next 30-second boundary
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
    return shot_number * secs_per_shot


def num_shots(captions: list[Caption], secs_per_shot: int) -> int:
    if not captions:
        return 0

    last_end = captions[-1].end
    # Use floor to match ffmpeg's behavior with fps=1/30
    # ffmpeg generates frames at 0s, 30s, 60s, ... and stops when time exceeds duration
    shots = int(math.floor(last_end / secs_per_shot))
    return max(1, shots)


def clean_caption(caption: Caption) -> Caption:
    unescaped = html.unescape(caption.text)
    cleaned_text = strip_tags(unescaped)
    normalized = cleaned_text.replace("\u00a0", " ")
    return replace(caption, text=normalized.strip())


TAG_RE = re.compile(r"<[^>]+>")


def strip_tags(text: str) -> str:
    return TAG_RE.sub("", text)


def overlaps_interval(
    start_a: float, end_a: float, start_b: float, end_b: float
) -> bool:
    return start_a <= end_b and end_a >= start_b


# === Functions for generating HTML from ExtractedContent ===


def convert_to_html_from_content(
    content: "ExtractedContent",
    detect_duplicates: bool = True,
) -> str:
    """Generate HTML from ExtractedContent (Phase 2 workflow).

    This function works with pre-extracted content from JSON, avoiding
    the need to re-download or re-process the video.
    """
    video = content.get_video()
    captions = content.get_captions()

    # Build image data lookup: index -> base64 data
    image_data: dict[int, str] = {
        img["index"]: img["data_base64"] for img in content.images
    }

    slides = generate_slides_from_content(captions, image_data, detect_duplicates)
    slides_html = render_slides_from_content(slides, video.url, image_data)
    return embody(video, slides_html)


def generate_slides_from_content(
    captions: list[Caption],
    image_data: dict[int, str],
    detect_duplicates: bool = True,
) -> list[Slide]:
    """Generate slides from captions and pre-extracted image data."""
    if not captions:
        return []

    per_slide = captions_per_slide(captions)
    logger.debug(f"Generated {len(per_slide)} slides from captions")

    if detect_duplicates:
        # Use the image data directly for similarity detection
        duplicate_shots = find_similar_shots_from_data(image_data)
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


def render_slides_from_content(
    slides: list[Slide], url: str, image_data: dict[int, str]
) -> str:
    """Render all slides to HTML using pre-extracted image data."""
    blocks = [render_slide_from_content(slide, url, image_data) for slide in slides]
    return "\n".join(blocks)


def render_slide_from_content(
    slide: Slide, url: str, image_data: dict[int, str]
) -> str:
    """Render a single slide using pre-extracted image data."""
    image_block = slide_block_from_content(url, slide.index, slide.duplicate, image_data)
    if not image_block:
        return ""
    text_block = caps(slide.captions)
    to_video = to_video_block(url, slide.index)
    return f"{image_block}{text_block}{to_video}</div>"


def slide_block_from_content(
    url: str, shot: int, duplicate: bool, image_data: dict[int, str]
) -> str:
    """Generate HTML for a slide image using pre-extracted base64 data."""
    if shot not in image_data:
        logger.warning(f"Missing image data for slide {shot}")
        return ""

    encoded = image_data[shot]
    classes = ["slide-block"]
    if duplicate:
        classes.append("duplicate")
    class_attr = " ".join(classes)
    return (
        f"<div id='slide{shot}' class='{class_attr}'>\n"
        "\t<div class='img'>\n"
        f"\t\t<img src='data:image/jpeg;base64, {encoded}'/></a>\n"
        "\t</div>\n"
    )
