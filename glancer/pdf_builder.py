from __future__ import annotations

import base64
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from .parser import Caption
from .process import Video
from .slides import Slide, generate_slides

if TYPE_CHECKING:
    from .content import SlideData

SECONDS_PER_SHOT = 30


# === Phase 1: Generate PDF from video processing ===


def convert_to_pdf(
    video: Video,
    directory: Path,
    captions: list[Caption],
    output_path: Path,
    detect_duplicates: bool = True,
    compact: bool = False,
    slide_mode: bool = False,
) -> None:
    """Generate PDF from video processing results (Phase 1 or standalone)."""
    slides = generate_slides(captions, directory, detect_duplicates)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # Copy images to temp directory
        for slide in slides:
            src_img = directory / f"glancer-img{slide.index:04d}.jpg"
            if src_img.exists():
                dst_img = tmp_path / f"img{slide.index:04d}.jpg"
                shutil.copy(src_img, dst_img)

        _compile_pdf(video, slides, tmp_path, output_path, compact, slide_mode)


# === Phase 2: Generate PDF from extracted JSON ===


def render_pdf_from_json(
    video_url: str,
    video_title: str,
    slides: list["SlideData"],
    output_path: Path,
    compact: bool = False,
    slide_mode: bool = False,
) -> None:
    """Generate PDF from pre-extracted slide data (Phase 2).

    Args:
        video_url: Video URL for links
        video_title: Video title for page header
        slides: Pre-processed slide data from JSON
        output_path: Output PDF file path
        compact: Use compact layout
        slide_mode: One slide per page
    """
    video = Video(url=video_url, title=video_title, video_id="")

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # Write images from base64 to temp directory
        for slide in slides:
            img_bytes = base64.b64decode(slide.image_base64)
            dst_img = tmp_path / f"img{slide.index:04d}.jpg"
            dst_img.write_bytes(img_bytes)

        _compile_pdf_from_data(video, slides, tmp_path, output_path, compact, slide_mode)


def _compile_pdf(
    video: Video,
    slides: list[Slide],
    image_dir: Path,
    output_path: Path,
    compact: bool,
    slide_mode: bool,
) -> None:
    """Compile PDF using Typst from Slide objects."""
    typst_content = generate_typst(video, slides, image_dir, compact, slide_mode)
    typst_file = image_dir / "output.typ"
    typst_file.write_text(typst_content, encoding="utf-8")
    subprocess.run(
        ["typst", "compile", str(typst_file), str(output_path)],
        check=True,
    )


def _compile_pdf_from_data(
    video: Video,
    slides: list["SlideData"],
    image_dir: Path,
    output_path: Path,
    compact: bool,
    slide_mode: bool,
) -> None:
    """Compile PDF using Typst from SlideData objects."""
    typst_content = _generate_typst_from_data(video, slides, image_dir, compact, slide_mode)
    typst_file = image_dir / "output.typ"
    typst_file.write_text(typst_content, encoding="utf-8")
    subprocess.run(
        ["typst", "compile", str(typst_file), str(output_path)],
        check=True,
    )


# === Typst generation for Phase 1 (Slide objects) ===


def generate_typst(
    video: Video,
    slides: list[Slide],
    image_dir: Path,
    compact: bool = False,
    slide_mode: bool = False,
) -> str:
    """Generate complete Typst document from Slide objects."""
    if slide_mode:
        header = generate_header_slide_mode(video)
        slides_content = generate_slides_typst(
            slides, video.url, image_dir, compact=False, slide_mode=True
        )
        return f"{header}\n\n{slides_content}\n"
    else:
        header = generate_header(video, compact)
        slides_content = generate_slides_typst(slides, video.url, image_dir, compact)
        gutter = "0.3cm" if compact else "0.4cm"
        return f"{header}\n\n#columns(2, gutter: {gutter})[\n{slides_content}\n]\n"


def generate_slides_typst(
    slides: list[Slide],
    url: str,
    image_dir: Path,
    compact: bool = False,
    slide_mode: bool = False,
) -> str:
    """Generate Typst content for all slides."""
    blocks = []
    for slide in slides:
        if slide_mode:
            block = render_slide_page(slide, url, image_dir)
        elif compact:
            block = render_slide_compact(slide, url, image_dir)
        else:
            block = render_slide_typst(slide, url, image_dir)
        if block:
            blocks.append(block)
    return "\n".join(blocks)


# === Typst generation for Phase 2 (SlideData objects) ===


def _generate_typst_from_data(
    video: Video,
    slides: list["SlideData"],
    image_dir: Path,
    compact: bool = False,
    slide_mode: bool = False,
) -> str:
    """Generate complete Typst document from SlideData objects."""
    if slide_mode:
        header = generate_header_slide_mode(video)
        slides_content = _generate_slides_typst_from_data(
            slides, video.url, image_dir, compact=False, slide_mode=True
        )
        return f"{header}\n\n{slides_content}\n"
    else:
        header = generate_header(video, compact)
        slides_content = _generate_slides_typst_from_data(slides, video.url, image_dir, compact)
        gutter = "0.3cm" if compact else "0.4cm"
        return f"{header}\n\n#columns(2, gutter: {gutter})[\n{slides_content}\n]\n"


def _generate_slides_typst_from_data(
    slides: list["SlideData"],
    url: str,
    image_dir: Path,
    compact: bool = False,
    slide_mode: bool = False,
) -> str:
    """Generate Typst content for all SlideData slides."""
    blocks = []
    for slide in slides:
        if slide_mode:
            block = _render_slide_page_from_data(slide, url, image_dir)
        elif compact:
            block = _render_slide_compact_from_data(slide, url, image_dir)
        else:
            block = _render_slide_typst_from_data(slide, url, image_dir)
        if block:
            blocks.append(block)
    return "\n".join(blocks)


# === Shared header generation ===


def generate_header(video: Video, compact: bool = False) -> str:
    """Generate Typst document header with page setup."""
    escaped_title = escape_typst(video.title)
    escaped_url = video.url

    margin = "0.3cm" if compact else "0.5cm"
    font_size = "8pt" if compact else "9pt"
    title_size = "12pt" if compact else "14pt"
    spacing = "0.2cm" if compact else "0.3cm"

    return f"""#set page(margin: {margin}, paper: "a4")
#set text(size: {font_size})
#set par(leading: 0.4em, justify: true)

#align(center)[
  #text({title_size}, weight: "bold")[#link("{escaped_url}")[{escaped_title}]]
]
#v({spacing})
"""


def generate_header_slide_mode(video: Video) -> str:
    """Generate Typst header for slide mode (16:9 presentation size)."""
    escaped_title = escape_typst(video.title)
    escaped_url = video.url

    return f"""#set page(width: 20cm, height: 11.25cm, margin: 0.6cm)
#set text(size: 9pt)
#set par(leading: 0.5em, justify: true)

#align(center)[
  #text(12pt, weight: "bold")[#link("{escaped_url}")[{escaped_title}]]
]
"""


# === Slide renderers for Phase 1 (Slide objects) ===


def render_slide_typst(slide: Slide, url: str, image_dir: Path) -> str:
    """Render a single slide as Typst (standard layout)."""
    img_filename = f"img{slide.index:04d}.jpg"
    img_path = image_dir / img_filename
    if not img_path.exists():
        return ""

    caption_text = get_slide_text(slide.captions)
    escaped_caption = escape_typst(caption_text)

    timestamp = slide.index * SECONDS_PER_SHOT
    video_link = f"{url}&t={timestamp}s"

    return f"""#block(breakable: false, width: 100%)[
  #image("{img_filename}", width: 100%)
  #v(0.1cm)
  #text(size: 8pt)[{escaped_caption}]
  #v(0.05cm)
  #align(right)[#text(size: 7pt)[#link("{video_link}")[▶ {format_timestamp(timestamp)}]]]
  #v(0.2cm)
]
"""


def render_slide_compact(slide: Slide, url: str, image_dir: Path) -> str:
    """Render a slide in compact side-by-side layout."""
    img_filename = f"img{slide.index:04d}.jpg"
    img_path = image_dir / img_filename
    if not img_path.exists():
        return ""

    caption_text = get_slide_text(slide.captions)
    escaped_caption = escape_typst(caption_text)

    timestamp = slide.index * SECONDS_PER_SHOT
    video_link = f"{url}&t={timestamp}s"

    return f"""#block(breakable: false, width: 100%)[
  #grid(
    columns: (1fr, 1fr),
    gutter: 0.15cm,
    image("{img_filename}", width: 100%),
    [
      #text(size: 7pt)[{escaped_caption}]
      #v(0.05cm)
      #align(right)[#text(size: 6pt)[#link("{video_link}")[▶ {format_timestamp(timestamp)}]]]
    ]
  )
  #v(0.1cm)
]
"""


def render_slide_page(slide: Slide, url: str, image_dir: Path) -> str:
    """Render a slide in page mode (one slide per page)."""
    img_filename = f"img{slide.index:04d}.jpg"
    img_path = image_dir / img_filename
    if not img_path.exists():
        return ""

    caption_text = get_slide_text(slide.captions)
    escaped_caption = escape_typst(caption_text)
    timestamp = slide.index * SECONDS_PER_SHOT
    video_link = f"{url}&t={timestamp}s"

    return f"""
#block(
  width: 100%,
  height: 48%,
  breakable: false,
  inset: (y: 2pt),
  spacing: 0pt
)[
  #grid(
    columns: (0.6fr, 1.4fr),
    column-gutter: 6pt,
    align: top,
    [
      #set par(leading: 0.4em)
      #text(size: 8pt)[{escaped_caption}]
      #v(2pt)
      #text(size: 7pt)[#link("{video_link}")[▶ {format_timestamp(timestamp)}]]
    ],
    align(right + top)[
      #image("{img_filename}", width: 100%, height: 100%, fit: "contain")
    ]
  )
]
"""


# === Slide renderers for Phase 2 (SlideData objects) ===


def _render_slide_typst_from_data(slide: "SlideData", url: str, image_dir: Path) -> str:
    """Render a SlideData as Typst (standard layout)."""
    img_filename = f"img{slide.index:04d}.jpg"
    escaped_caption = escape_typst(slide.caption_text)
    video_link = f"{url}&t={slide.timestamp_seconds}s"

    return f"""#block(breakable: false, width: 100%)[
  #image("{img_filename}", width: 100%)
  #v(0.1cm)
  #text(size: 8pt)[{escaped_caption}]
  #v(0.05cm)
  #align(right)[#text(size: 7pt)[#link("{video_link}")[▶ {format_timestamp(slide.timestamp_seconds)}]]]
  #v(0.2cm)
]
"""


def _render_slide_compact_from_data(slide: "SlideData", url: str, image_dir: Path) -> str:
    """Render a SlideData in compact side-by-side layout."""
    img_filename = f"img{slide.index:04d}.jpg"
    escaped_caption = escape_typst(slide.caption_text)
    video_link = f"{url}&t={slide.timestamp_seconds}s"

    return f"""#block(breakable: false, width: 100%)[
  #grid(
    columns: (1fr, 1fr),
    gutter: 0.15cm,
    image("{img_filename}", width: 100%),
    [
      #text(size: 7pt)[{escaped_caption}]
      #v(0.05cm)
      #align(right)[#text(size: 6pt)[#link("{video_link}")[▶ {format_timestamp(slide.timestamp_seconds)}]]]
    ]
  )
  #v(0.1cm)
]
"""


def _render_slide_page_from_data(slide: "SlideData", url: str, image_dir: Path) -> str:
    """Render a SlideData in page mode (one slide per page)."""
    img_filename = f"img{slide.index:04d}.jpg"
    escaped_caption = escape_typst(slide.caption_text)
    video_link = f"{url}&t={slide.timestamp_seconds}s"

    return f"""
#block(
  width: 100%,
  height: 48%,
  breakable: false,
  inset: (y: 2pt),
  spacing: 0pt
)[
  #grid(
    columns: (0.6fr, 1.4fr),
    column-gutter: 6pt,
    align: top,
    [
      #set par(leading: 0.4em)
      #text(size: 8pt)[{escaped_caption}]
      #v(2pt)
      #text(size: 7pt)[#link("{video_link}")[▶ {format_timestamp(slide.timestamp_seconds)}]]
    ],
    align(right + top)[
      #image("{img_filename}", width: 100%, height: 100%, fit: "contain")
    ]
  )
]
"""


# === Helpers ===


def get_slide_text(captions: list[Caption]) -> str:
    """Combine captions into a single text block."""
    if not captions:
        return ""
    texts = [cap.text.strip().replace("\n", " ") for cap in captions]
    combined = " ".join(texts)
    return " ".join(combined.split())


def escape_typst(text: str) -> str:
    """Escape special Typst characters."""
    replacements = [
        ("\\", "\\\\"),
        ("#", "\\#"),
        ("$", "\\$"),
        ("*", "\\*"),
        ("_", "\\_"),
        ("<", "\\<"),
        (">", "\\>"),
        ("@", "\\@"),
        ("[", "\\["),
        ("]", "\\]"),
    ]
    for old, new in replacements:
        text = text.replace(old, new)
    return text


def format_timestamp(seconds: int) -> str:
    """Format seconds as MM:SS or H:MM:SS."""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"
