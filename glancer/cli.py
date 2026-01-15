from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path

from .content import ExtractedContent, extract_content
from .image_similarity import find_similar_shots
from .parser import parse_srt
from .pdf_builder import convert_to_pdf, render_pdf_from_json
from .playlist import Playlist
from .process import cleanup_cache, delete_images, process_video
from .slides import convert_to_html, get_caption_texts, render_html_from_json


def _ensure_suffix(path: Path, suffix: str) -> Path:
    """Ensure path has the specified suffix."""
    return path.with_suffix(suffix) if path.suffix.lower() != suffix else path


def _sanitize_filename(filename: str) -> str:
    """Remove invalid filename characters."""
    return re.sub(r'[<>:"/\\|?*]', "_", filename)


def run(
    url: str | None,
    destination: str | None,
    verbose: bool,
    auto_cleanup: bool,
    detect_duplicates: bool,
    output_pdf: bool,
    compact: bool,
    slide_mode: bool,
    extract_json: bool = False,
    from_json: str | None = None,
) -> None:
    """Main entry point."""
    ffmpeg_log_level = "info" if verbose else "error"
    dest_path = Path(destination) if destination else Path.cwd()

    # Phase 2: Generate from JSON
    if from_json:
        generate_from_json(Path(from_json), dest_path, output_pdf, compact, slide_mode)
        return

    if not url:
        raise ValueError("URL is required unless using --from-json")

    # Handle playlists
    if Playlist.is_playlist(url):
        playlist = Playlist(url)
        print(f"Processing playlist: {url}", file=sys.stderr)
        for video_url in playlist:
            process_single_video(
                video_url, dest_path, ffmpeg_log_level, auto_cleanup,
                detect_duplicates, output_pdf, compact, slide_mode, extract_json,
            )
    else:
        process_single_video(
            url, dest_path, ffmpeg_log_level, auto_cleanup,
            detect_duplicates, output_pdf, compact, slide_mode, extract_json,
        )


def process_single_video(
    url: str,
    destination: Path,
    ffmpeg_log_level: str,
    auto_cleanup: bool,
    detect_duplicates: bool,
    output_pdf: bool,
    compact: bool,
    slide_mode: bool,
    extract_json: bool = False,
) -> None:
    """Process a single video."""
    dir_path, video, captions_path = process_video(url, ffmpeg_log_level)
    try:
        captions_text = captions_path.read_text(encoding="utf-8")
        parsed = parse_srt(captions_text)

        if destination.is_dir():
            output_path = destination / _sanitize_filename(video.title)
        else:
            output_path = destination

        if extract_json:
            # Phase 1: Extract to JSON
            caption_texts = get_caption_texts(parsed)
            duplicates = find_similar_shots(dir_path.glob("glancer-img*.jpg")) if detect_duplicates else set()
            content = extract_content(
                video.url, video.title, video.video_id,
                dir_path, caption_texts, duplicates,
            )
            dest = _ensure_suffix(output_path.expanduser(), ".json")
            dest.parent.mkdir(parents=True, exist_ok=True)
            print(f"Writing JSON to {dest}", file=sys.stderr)
            content.save(dest)
        elif output_pdf:
            dest = _ensure_suffix(output_path.expanduser(), ".pdf")
            dest.parent.mkdir(parents=True, exist_ok=True)
            print(f"Writing PDF to {dest}", file=sys.stderr)
            convert_to_pdf(video, dir_path, parsed, dest, detect_duplicates, compact, slide_mode)
        else:
            dest = _ensure_suffix(output_path.expanduser(), ".html")
            dest.parent.mkdir(parents=True, exist_ok=True)
            print(f"Writing HTML to {dest}", file=sys.stderr)
            html = convert_to_html(video, dir_path, parsed, detect_duplicates)
            dest.write_text(html, encoding="utf-8")
    finally:
        if auto_cleanup:
            cleanup_cache(dir_path)
        else:
            delete_images(dir_path)


def generate_from_json(
    json_path: Path,
    destination: Path,
    output_pdf: bool,
    compact: bool,
    slide_mode: bool,
) -> None:
    """Generate from JSON (Phase 2)."""
    content = ExtractedContent.load(json_path)
    print(f"Generating from: '{content.video.title}'", file=sys.stderr)

    if destination.is_dir():
        output_path = destination / _sanitize_filename(content.video.title)
    else:
        output_path = destination

    if output_pdf:
        dest = _ensure_suffix(output_path.expanduser(), ".pdf")
        dest.parent.mkdir(parents=True, exist_ok=True)
        print(f"Writing PDF to {dest}", file=sys.stderr)
        render_pdf_from_json(content.video.url, content.video.title, content.slides, dest, compact, slide_mode)
    else:
        dest = _ensure_suffix(output_path.expanduser(), ".html")
        dest.parent.mkdir(parents=True, exist_ok=True)
        print(f"Writing HTML to {dest}", file=sys.stderr)
        html = render_html_from_json(content.video.url, content.video.title, content.slides)
        dest.write_text(html, encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    """CLI entry point."""
    logging.basicConfig(
        level=logging.WARNING, format="%(levelname)s: %(message)s", stream=sys.stderr
    )

    parser = argparse.ArgumentParser(prog="glancer", description="Glancer")
    parser.add_argument(
        "url", nargs="?", default=None,
        help="YouTube URL or playlist URL (not required with --from-json)",
    )
    parser.add_argument(
        "destination", nargs="?", default=None,
        help="Output file or directory (default: current directory)",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    parser.add_argument("--auto-cleanup", action="store_true", help="Delete cached downloads")
    parser.add_argument("--no-detect-duplicates", action="store_true", help="Disable duplicate detection")
    parser.add_argument("--pdf", action="store_true", help="Output PDF (requires typst)")
    parser.add_argument("--compact-experimental", action="store_true", help="Compact PDF layout")
    parser.add_argument("--slide-experimental", action="store_true", help="One slide per page")
    parser.add_argument("--extract-json", action="store_true", help="Extract to JSON (Phase 1)")
    parser.add_argument("--from-json", metavar="PATH", help="Generate from JSON (Phase 2)")
    args = parser.parse_args(argv)

    # With --from-json, first positional arg is destination
    url = args.url
    destination = args.destination
    if args.from_json:
        if args.destination:
            parser.error("Cannot specify URL with --from-json")
        destination = args.url
        url = None

    if not args.from_json and not url:
        parser.error("URL is required unless using --from-json")
    if args.extract_json and args.from_json:
        parser.error("Cannot use --extract-json with --from-json")
    if args.extract_json and args.pdf:
        parser.error("Cannot use --extract-json with --pdf")

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    run(
        url, destination,
        verbose=args.verbose,
        auto_cleanup=args.auto_cleanup,
        detect_duplicates=not args.no_detect_duplicates,
        output_pdf=args.pdf,
        compact=args.compact_experimental,
        slide_mode=args.slide_experimental,
        extract_json=args.extract_json,
        from_json=args.from_json,
    )


if __name__ == "__main__":  # pragma: no cover
    main()
