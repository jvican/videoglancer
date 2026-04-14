from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from .parser import Caption
from .process import Video
from .slides import combine_caption_texts
from .slides import Slide, generate_slides

SECONDS_PER_SHOT = 30


def convert_to_pdf(
    video: Video,
    directory: Path,
    captions: list[Caption],
    output_path: Path,
    detect_duplicates: bool = True,
    compact: bool = False,
    slide_mode: bool = False,
) -> None:
    """Generate a dense PDF from video slides using Typst."""
    slides = generate_slides(captions, directory, detect_duplicates)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # Copy images to temp directory
        for slide in slides:
            src_img = directory / f"glancer-img{slide.index:04d}.jpg"
            if src_img.exists():
                dst_img = tmp_path / f"img{slide.index:04d}.jpg"
                shutil.copy(src_img, dst_img)

        # Generate Typst content
        typst_content = generate_typst(video, slides, tmp_path, compact, slide_mode)

        # Write Typst file
        typst_file = tmp_path / "output.typ"
        typst_file.write_text(typst_content, encoding="utf-8")

        # Compile to PDF
        subprocess.run(
            ["typst", "compile", str(typst_file), str(output_path)],
            check=True,
        )


def generate_typst(
    video: Video,
    slides: list[Slide],
    image_dir: Path,
    compact: bool = False,
    slide_mode: bool = False,
) -> str:
    """Generate complete Typst document content."""
    if slide_mode:
        header = generate_header_slide_mode(video)
        slides_content = generate_slides_typst(
            slides, video.url, image_dir, compact=False, slide_mode=True
        )
        return f"""{header}

{slides_content}
"""
    else:
        header = generate_header(video, compact)
        slides_content = generate_slides_typst(slides, video.url, image_dir, compact)

        gutter = "0.3cm" if compact else "0.4cm"
        return f"""{header}

#columns(2, gutter: {gutter})[
{slides_content}
]
"""


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
    """Generate Typst header for slide mode (one page per slide, presentation size)."""
    escaped_title = escape_typst(video.title)
    escaped_url = video.url

    # 16:9 aspect ratio page, similar to presentation slides
    return f"""#set page(width: 20cm, height: 11.25cm, margin: 0.6cm)
#set text(size: 9pt)
#set par(leading: 0.5em, justify: true)

#align(center)[
  #text(12pt, weight: "bold")[#link("{escaped_url}")[{escaped_title}]]
]
"""


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


def render_slide_typst(slide: Slide, url: str, image_dir: Path) -> str:
    """Render a single slide as a Typst block."""
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
    """Render a slide in compact side-by-side layout (image left, text right)."""
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


def get_slide_text(captions: list[Caption]) -> str:
    """Combine captions into a single text block."""
    if not captions:
        return ""
    texts = [cap.text for cap in captions]
    return combine_caption_texts(texts)


def escape_typst(text: str) -> str:
    """Escape special Typst characters."""
    # Typst special characters that need escaping
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
