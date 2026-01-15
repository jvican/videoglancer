#!/usr/bin/env python3
"""glancer-render: Render extracted content to HTML or PDF.

This tool takes a JSON file produced by glancer-extract and
renders it to HTML or PDF format.

Usage:
    glancer-render INPUT [OUTPUT]
    glancer-render content.json output.html
    glancer-render content.json --pdf output.pdf
"""
from __future__ import annotations

import argparse
import base64
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from jinja2 import Template

from .schema import ExtractedContent, SlideData

# === HTML rendering ===

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }}</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }
        h1 { text-align: center; margin-bottom: 30px; }
        h1 a { color: #333; text-decoration: none; }
        h1 a:hover { text-decoration: underline; }
        .slides { max-width: 1200px; margin: 0 auto; display: grid; grid-template-columns: repeat(auto-fill, minmax(400px, 1fr)); gap: 20px; }
        .slide-block { background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .slide-block.duplicate { opacity: 0.5; }
        .slide-block img { width: 100%; display: block; }
        .txt { padding: 15px; font-size: 14px; line-height: 1.5; color: #333; }
        .to-video { padding: 10px 15px; text-align: right; border-top: 1px solid #eee; }
        .to-video a { color: #0066cc; text-decoration: none; font-size: 13px; }
    </style>
</head>
<body>
    <h1><a href="{{ url }}">{{ title }}</a></h1>
    <div class="slides">
        {{ slides_html }}
    </div>
</body>
</html>
"""


def render_html(content: ExtractedContent) -> str:
    """Render ExtractedContent to HTML."""
    slides_html = "\n".join(_render_slide_html(s, content.video.url) for s in content.slides)
    return Template(HTML_TEMPLATE).render(
        title=content.video.title,
        url=content.video.url,
        slides_html=slides_html,
    )


def _render_slide_html(slide: SlideData, url: str) -> str:
    classes = "slide-block duplicate" if slide.is_duplicate else "slide-block"
    return f"""<div id="slide{slide.index}" class="{classes}">
    <div class="img"><img src="data:image/jpeg;base64,{slide.image_base64}"/></div>
    <div class="txt">{slide.caption_text}</div>
    <div class="to-video"><a href="{url}&t={slide.timestamp_seconds}s">▶ {_format_time(slide.timestamp_seconds)}</a></div>
</div>"""


def _format_time(seconds: int) -> str:
    h, m, s = seconds // 3600, (seconds % 3600) // 60, seconds % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


# === PDF rendering ===


def render_pdf(content: ExtractedContent, output_path: Path, compact: bool = False, slide_mode: bool = False) -> None:
    """Render ExtractedContent to PDF using Typst."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)

        # Write images
        for slide in content.slides:
            (tmp / f"img{slide.index:04d}.jpg").write_bytes(base64.b64decode(slide.image_base64))

        # Generate Typst
        typst = _generate_typst(content, tmp, compact, slide_mode)
        typst_file = tmp / "output.typ"
        typst_file.write_text(typst, encoding="utf-8")

        # Compile
        subprocess.run(["typst", "compile", str(typst_file), str(output_path)], check=True)


def _generate_typst(content: ExtractedContent, img_dir: Path, compact: bool, slide_mode: bool) -> str:
    title = _escape_typst(content.video.title)
    url = content.video.url

    if slide_mode:
        header = f"""#set page(width: 20cm, height: 11.25cm, margin: 0.6cm)
#set text(size: 9pt)
#set par(leading: 0.5em, justify: true)
#align(center)[#text(12pt, weight: "bold")[#link("{url}")[{title}]]]
"""
        slides = "\n".join(_render_slide_typst_page(s, url) for s in content.slides)
        return f"{header}\n{slides}"
    else:
        margin = "0.3cm" if compact else "0.5cm"
        font = "8pt" if compact else "9pt"
        title_size = "12pt" if compact else "14pt"
        gutter = "0.3cm" if compact else "0.4cm"

        header = f"""#set page(margin: {margin}, paper: "a4")
#set text(size: {font})
#set par(leading: 0.4em, justify: true)
#align(center)[#text({title_size}, weight: "bold")[#link("{url}")[{title}]]]
#v(0.3cm)
"""
        render_fn = _render_slide_typst_compact if compact else _render_slide_typst
        slides = "\n".join(render_fn(s, url) for s in content.slides)
        return f"{header}\n#columns(2, gutter: {gutter})[\n{slides}\n]"


def _render_slide_typst(slide: SlideData, url: str) -> str:
    caption = _escape_typst(slide.caption_text)
    link = f"{url}&t={slide.timestamp_seconds}s"
    return f"""#block(breakable: false, width: 100%)[
  #image("img{slide.index:04d}.jpg", width: 100%)
  #v(0.1cm)
  #text(size: 8pt)[{caption}]
  #v(0.05cm)
  #align(right)[#text(size: 7pt)[#link("{link}")[▶ {_format_time(slide.timestamp_seconds)}]]]
  #v(0.2cm)
]
"""


def _render_slide_typst_compact(slide: SlideData, url: str) -> str:
    caption = _escape_typst(slide.caption_text)
    link = f"{url}&t={slide.timestamp_seconds}s"
    return f"""#block(breakable: false, width: 100%)[
  #grid(columns: (1fr, 1fr), gutter: 0.15cm,
    image("img{slide.index:04d}.jpg", width: 100%),
    [#text(size: 7pt)[{caption}] #v(0.05cm) #align(right)[#text(size: 6pt)[#link("{link}")[▶ {_format_time(slide.timestamp_seconds)}]]]]
  )
  #v(0.1cm)
]
"""


def _render_slide_typst_page(slide: SlideData, url: str) -> str:
    caption = _escape_typst(slide.caption_text)
    link = f"{url}&t={slide.timestamp_seconds}s"
    return f"""
#block(width: 100%, height: 48%, breakable: false, inset: (y: 2pt), spacing: 0pt)[
  #grid(columns: (0.6fr, 1.4fr), column-gutter: 6pt, align: top,
    [#set par(leading: 0.4em) #text(size: 8pt)[{caption}] #v(2pt) #text(size: 7pt)[#link("{link}")[▶ {_format_time(slide.timestamp_seconds)}]]],
    align(right + top)[#image("img{slide.index:04d}.jpg", width: 100%, height: 100%, fit: "contain")]
  )
]
"""


def _escape_typst(text: str) -> str:
    for old, new in [("\\", "\\\\"), ("#", "\\#"), ("$", "\\$"), ("*", "\\*"), ("_", "\\_"),
                     ("<", "\\<"), (">", "\\>"), ("@", "\\@"), ("[", "\\["), ("]", "\\]")]:
        text = text.replace(old, new)
    return text


# === CLI ===


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="glancer-render",
        description="Render extracted content to HTML or PDF",
    )
    parser.add_argument("input", help="Input JSON file from glancer-extract")
    parser.add_argument("output", nargs="?", help="Output file (default: VIDEO_TITLE.html)")
    parser.add_argument("--pdf", action="store_true", help="Output PDF instead of HTML")
    parser.add_argument("--compact", action="store_true", help="Compact PDF layout")
    parser.add_argument("--slide-mode", action="store_true", help="One slide per page (PDF)")
    args = parser.parse_args(argv)

    content = ExtractedContent.load(Path(args.input))
    print(f"Rendering: '{content.video.title}'", file=sys.stderr)
    print(f"  {len(content.slides)} slides", file=sys.stderr)

    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        safe_title = re.sub(r'[<>:"/\\|?*]', '_', content.video.title)
        output_path = Path(f"{safe_title}.pdf" if args.pdf else f"{safe_title}.html")

    # Render
    if args.pdf:
        render_pdf(content, output_path, compact=args.compact, slide_mode=args.slide_mode)
    else:
        output_path.write_text(render_html(content), encoding="utf-8")

    print(f"Saved: {output_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
