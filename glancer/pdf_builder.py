from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from .parser import Caption
from .process import Video
from .slides import Slide, generate_slides

SECONDS_PER_SHOT = 30


def convert_to_pdf(
    video: Video,
    directory: Path,
    captions: list[Caption],
    output_path: Path,
    detect_duplicates: bool = True,
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
        typst_content = generate_typst(video, slides, tmp_path)

        # Write Typst file
        typst_file = tmp_path / "output.typ"
        typst_file.write_text(typst_content, encoding="utf-8")

        # Compile to PDF
        subprocess.run(
            ["typst", "compile", str(typst_file), str(output_path)],
            check=True,
        )


def generate_typst(video: Video, slides: list[Slide], image_dir: Path) -> str:
    """Generate complete Typst document content."""
    header = generate_header(video)
    slides_content = generate_slides_typst(slides, video.url, image_dir)

    return f"""{header}

#columns(2, gutter: 0.4cm)[
{slides_content}
]
"""


def generate_header(video: Video) -> str:
    """Generate Typst document header with page setup."""
    # Escape special Typst characters in title
    escaped_title = escape_typst(video.title)
    escaped_url = video.url

    return f"""#set page(margin: 0.5cm, paper: "a4")
#set text(size: 9pt)
#set par(leading: 0.5em, justify: true)

#align(center)[
  #text(14pt, weight: "bold")[#link("{escaped_url}")[{escaped_title}]]
]
#v(0.3cm)
"""


def generate_slides_typst(slides: list[Slide], url: str, image_dir: Path) -> str:
    """Generate Typst content for all slides."""
    blocks = []
    for slide in slides:
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

    # Get caption text
    caption_text = get_slide_text(slide.captions)
    escaped_caption = escape_typst(caption_text)

    # Calculate timestamp for YouTube link
    timestamp = slide.index * SECONDS_PER_SHOT
    video_link = f"{url}&t={timestamp}s"

    # Use relative path for Typst (relative to the .typ file location)
    return f"""#block(breakable: false, width: 100%)[
  #image("{img_filename}", width: 100%)
  #v(0.1cm)
  #text(size: 8pt)[{escaped_caption}]
  #v(0.05cm)
  #align(right)[#text(size: 7pt)[#link("{video_link}")[▶ {format_timestamp(timestamp)}]]]
  #v(0.2cm)
]
"""


def get_slide_text(captions: list[Caption]) -> str:
    """Combine captions into a single text block."""
    if not captions:
        return ""
    texts = [cap.text.strip().replace("\n", " ") for cap in captions]
    combined = " ".join(texts)
    return " ".join(combined.split())


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
