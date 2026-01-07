from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path

from .content import ExtractedContent
from .slides import convert_to_html, convert_to_html_from_content
from .pdf_builder import convert_to_pdf, convert_to_pdf_from_content
from .parser import parse_srt
from .playlist import Playlist
from .process import cleanup_cache, delete_images, process_video


def _ensure_html_suffix(path: Path) -> Path:
    return path.with_suffix(".html") if path.suffix.lower() != ".html" else path


def _ensure_pdf_suffix(path: Path) -> Path:
    return path.with_suffix(".pdf") if path.suffix.lower() != ".pdf" else path


def _ensure_json_suffix(path: Path) -> Path:
    return path.with_suffix(".json") if path.suffix.lower() != ".json" else path


def _sanitize_filename(filename: str) -> str:
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
    ffmpeg_log_level = "info" if verbose else "error"

    # Use current directory if no destination provided, we'll create a new file with the video name
    dest_path = Path(destination) if destination else Path.cwd()

    # Phase 2 only: Generate artifact from existing JSON
    if from_json:
        generate_from_json(
            from_json,
            dest_path,
            detect_duplicates,
            output_pdf,
            compact,
            slide_mode,
        )
        return

    # URL is required if not using --from-json
    if not url:
        raise ValueError("URL is required unless using --from-json")

    if Playlist.is_playlist(url):
        playlist = Playlist(url)
        print(f"Processing playlist: {url}", file=sys.stderr)
        for video_url in playlist:
            process_and_save_video(
                video_url,
                dest_path,
                ffmpeg_log_level,
                auto_cleanup,
                detect_duplicates,
                output_pdf,
                compact,
                slide_mode,
                extract_json,
            )
    else:
        process_and_save_video(
            url,
            dest_path,
            ffmpeg_log_level,
            auto_cleanup,
            detect_duplicates,
            output_pdf,
            compact,
            slide_mode,
            extract_json,
        )


def process_and_save_video(
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
    dir_path, video, captions_path = process_video(url, ffmpeg_log_level)
    try:
        captions_text = captions_path.read_text(encoding="utf-8")
        parsed = parse_srt(captions_text)

        if destination.is_dir():
            output_path = destination / _sanitize_filename(video.title)
        else:
            output_path = destination

        # Phase 1 only: Extract content to JSON and exit
        if extract_json:
            content = ExtractedContent.from_processing(video, parsed, dir_path)
            destination_path = _ensure_json_suffix(output_path.expanduser())
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            print(f"Writing JSON to {destination_path}", file=sys.stderr)
            content.save(destination_path)
            return

        # Full workflow or Phase 2: Generate artifact
        if output_pdf:
            destination_path = _ensure_pdf_suffix(output_path.expanduser())
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            print(f"Writing PDF to {destination_path}", file=sys.stderr)
            convert_to_pdf(
                video,
                dir_path,
                parsed,
                destination_path,
                detect_duplicates,
                compact,
                slide_mode,
            )
        else:
            html = convert_to_html(video, dir_path, parsed, detect_duplicates)
            destination_path = _ensure_html_suffix(output_path.expanduser())
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            print(f"Writing HTML to {destination_path}", file=sys.stderr)
            destination_path.write_text(html, encoding="utf-8")

    finally:
        if auto_cleanup:
            cleanup_cache(dir_path)
        else:
            delete_images(dir_path)


def generate_from_json(
    json_path: str,
    destination: Path,
    detect_duplicates: bool,
    output_pdf: bool,
    compact: bool,
    slide_mode: bool,
) -> None:
    """Generate HTML or PDF output from previously extracted JSON content.

    This is Phase 2 of the two-phase workflow, allowing artifact generation
    without re-downloading or re-processing the video.
    """
    content = ExtractedContent.load(Path(json_path))
    video = content.get_video()

    print(f"Generating from extracted content: '{video.title}'", file=sys.stderr)

    if destination.is_dir():
        output_path = destination / _sanitize_filename(video.title)
    else:
        output_path = destination

    if output_pdf:
        destination_path = _ensure_pdf_suffix(output_path.expanduser())
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"Writing PDF to {destination_path}", file=sys.stderr)
        convert_to_pdf_from_content(
            content,
            destination_path,
            detect_duplicates,
            compact,
            slide_mode,
        )
    else:
        html = convert_to_html_from_content(content, detect_duplicates)
        destination_path = _ensure_html_suffix(output_path.expanduser())
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"Writing HTML to {destination_path}", file=sys.stderr)
        destination_path.write_text(html, encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(
        level=logging.WARNING, format="%(levelname)s: %(message)s", stream=sys.stderr
    )

    parser = argparse.ArgumentParser(prog="glancer", description="Glancer")
    parser.add_argument(
        "url",
        nargs="?",
        default=None,
        help="YouTube URL or playlist URL (not required with --from-json)",
    )
    parser.add_argument(
        "destination",
        nargs="?",
        default=None,
        help="Output file name or directory (default: current directory with video title)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging and show verbose ffmpeg logs",
    )
    parser.add_argument(
        "--auto-cleanup",
        action="store_true",
        help="Delete cached downloads after HTML generation",
    )
    parser.add_argument(
        "--no-detect-duplicates",
        action="store_true",
        help="Disable duplicate slide detection",
    )
    parser.add_argument(
        "--pdf",
        action="store_true",
        help="Output as PDF instead of HTML (requires typst CLI)",
    )
    parser.add_argument(
        "--compact-experimental",
        action="store_true",
        help="Use compact side-by-side layout for PDF (experimental)",
    )
    parser.add_argument(
        "--slide-experimental",
        action="store_true",
        help="One slide per page for easy arrow-key navigation (experimental)",
    )
    parser.add_argument(
        "--extract-json",
        action="store_true",
        help="Extract content to JSON instead of generating HTML/PDF (Phase 1)",
    )
    parser.add_argument(
        "--from-json",
        metavar="PATH",
        help="Generate HTML/PDF from previously extracted JSON file (Phase 2)",
    )
    args = parser.parse_args(argv)

    # Handle argument interpretation for --from-json mode
    # When --from-json is provided, any positional argument is the destination (not URL)
    url = args.url
    destination = args.destination
    if args.from_json:
        if args.destination:
            # Both positional args provided with --from-json is an error
            parser.error("Cannot specify URL with --from-json")
        # With --from-json, first positional arg (url) is actually the destination
        destination = args.url
        url = None

    # Validate arguments
    if not args.from_json and not url:
        parser.error("URL is required unless using --from-json")
    if args.extract_json and args.from_json:
        parser.error("Cannot use --extract-json with --from-json")
    if args.extract_json and args.pdf:
        parser.error("Cannot use --extract-json with --pdf (JSON extraction doesn't generate PDF)")

    log_level = logging.DEBUG if args.verbose else logging.WARNING
    logging.getLogger().setLevel(log_level)

    run(
        url,
        destination,
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
