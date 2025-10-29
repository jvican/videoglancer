from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path

from .slides import convert_to_html
from .parser import parse_srt
from .playlist import Playlist
from .process import cleanup_cache, delete_images, process_video


def _ensure_html_suffix(path: Path) -> Path:
    return path.with_suffix(".html") if path.suffix.lower() != ".html" else path


def _sanitize_filename(filename: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "_", filename)


def run(
    url: str,
    destination: str | None,
    verbose: bool,
    auto_cleanup: bool,
    detect_duplicates: bool,
) -> None:
    ffmpeg_log_level = "info" if verbose else "error"

    # Use current directory if no destination provided, we'll create a new file with the video name
    dest_path = Path(destination) if destination else Path.cwd()

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
            )
    else:
        process_and_save_video(
            url,
            dest_path,
            ffmpeg_log_level,
            auto_cleanup,
            detect_duplicates,
        )


def process_and_save_video(
    url: str,
    destination: Path,
    ffmpeg_log_level: str,
    auto_cleanup: bool,
    detect_duplicates: bool,
) -> None:
    dir_path, video, captions_path = process_video(url, ffmpeg_log_level)
    try:
        captions_text = captions_path.read_text(encoding="utf-8")
        parsed = parse_srt(captions_text)
        html = convert_to_html(video, dir_path, parsed, detect_duplicates)

        if destination.is_dir():
            output_path = destination / _sanitize_filename(video.title)
        else:
            output_path = destination
        destination_path = _ensure_html_suffix(output_path.expanduser())
        destination_path.parent.mkdir(parents=True, exist_ok=True)

        print(f"Writing HTML to {destination_path}", file=sys.stderr)
        destination_path.write_text(html, encoding="utf-8")

    finally:
        if auto_cleanup:
            cleanup_cache(dir_path)
        else:
            delete_images(dir_path)


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(
        level=logging.WARNING, format="%(levelname)s: %(message)s", stream=sys.stderr
    )

    parser = argparse.ArgumentParser(prog="glancer", description="Glancer")
    parser.add_argument("url", help="YouTube URL or playlist URL")
    parser.add_argument(
        "destination",
        nargs="?",
        default=None,
        help="HTML file name or directory (default: current directory with video title)",
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
    args = parser.parse_args(argv)

    log_level = logging.DEBUG if args.verbose else logging.WARNING
    logging.getLogger().setLevel(log_level)

    run(
        args.url,
        args.destination,
        verbose=args.verbose,
        auto_cleanup=args.auto_cleanup,
        detect_duplicates=not args.no_detect_duplicates,
    )


if __name__ == "__main__":  # pragma: no cover
    main()
