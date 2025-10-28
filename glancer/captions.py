from __future__ import annotations

import base64
import html
import math
import re
from dataclasses import replace

from .html_builder import heading, embody
from .image_similarity import find_similar_shots
from .parser import Caption
from .process import Dir, Url, Video, delete_images

SECONDS_PER_SHOT = 30


def convert_to_html(video: Video, directory: Dir, captions: list[Caption]) -> str:
    try:
        return captions_to_html(video, directory, captions)
    finally:
        delete_images(directory)


def captions_to_html(video: Video, directory: Dir, captions: list[Caption]) -> str:
    slides = generate_slides(captions, video.url, directory)
    return heading + embody(video, slides)


def generate_slides(captions: list[Caption], url: Url, directory: Dir) -> str:
    if not captions:
        return ""

    merged = merge_captions(captions)
    per_slide = captions_per_slide(merged)
    deduped_slides = deduplicate_slides(per_slide)

    duplicate_shots = find_similar_shots(directory.value.glob("glancer-img*.jpg"))

    blocks: list[str] = []
    for index, slide_captions in enumerate(deduped_slides):
        is_duplicate = index in duplicate_shots
        block = img_caps(url, directory, index, slide_captions, is_duplicate)
        blocks.append(block)

    return "\n".join(blocks)


def img_caps(
    url: Url, directory: Dir, index: int, captions: list[Caption], duplicate: bool
) -> str:
    image_block = slide_block(url, directory, index, duplicate)
    text_block = caps(captions)
    to_video = to_video_block(url, index)
    return image_block + text_block + to_video + "</div>"


def slide_block(url: Url, directory: Dir, shot: int, duplicate: bool) -> str:
    img_path = directory.value / f"glancer-img{shot:04d}.jpg"
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


def to_video_block(url: Url, shot: int) -> str:
    when = shot_seconds(shot, SECONDS_PER_SHOT)
    return (
        f"<div class='to-video'><a title='Go to video at timestamp {when}s' "
        f"href='{url.value}&t={when}s'>&#8688;</a></div>"
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


def format_caption(caption: Caption) -> str:
    text = caption.text.strip()
    text = text.replace("\n", "<br/>")
    return text


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
    shots = int(math.ceil(last_end / secs_per_shot))
    return max(1, shots)


def clean_caption(caption: Caption) -> Caption:
    unescaped = html.unescape(caption.text)
    cleaned_text = strip_tags(unescaped)
    normalized = cleaned_text.replace("\u00a0", " ")
    return replace(caption, text=normalized.strip())


TAG_RE = re.compile(r"<[^>]+>")


def strip_tags(text: str) -> str:
    return TAG_RE.sub("", text)


def merge_captions(captions: list[Caption]) -> list[Caption]:
    merged: list[Caption] = []
    for caption in captions:
        lines = [line for line in caption.text.splitlines() if line.strip()]
        combined = "\n".join(lines)
        merged.append(replace(caption, text=combined))
    return merged


def deduplicate_slides(slides: list[list[Caption]]) -> list[list[Caption]]:
    seen: set[tuple[float, float, str]] = set()
    result: list[list[Caption]] = []
    for slide in slides:
        unique: list[Caption] = []
        for caption in slide:
            key = (caption.start, caption.end, caption.text)
            if key in seen:
                continue
            seen.add(key)
            unique.append(caption)
        result.append(unique)
    return result


def overlaps_interval(
    start_a: float, end_a: float, start_b: float, end_b: float
) -> bool:
    return start_a <= end_b and end_a >= start_b
