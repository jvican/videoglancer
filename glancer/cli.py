from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from .captions import convert_to_html
from .parser import parse_srt
from .playlist import Playlist
from .process import cleanup_cache, delete_images, process_video


def _ensure_html_suffix(path: Path) -> Path:
    return path.with_suffix(".html") if path.suffix.lower() != ".html" else path


def _sanitize_filename(filename: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "_", filename)


def run(
    url: str,
    destination: str,
    ffmpeg_verbose: bool,
    auto_cleanup: bool,
) -> None:
    ffmpeg_log_level = "info" if ffmpeg_verbose else "error"
    if Playlist.is_playlist(url):
        playlist = Playlist(url)
        print(f"Processing playlist: {url}", file=sys.stderr)
        for video_url in playlist:
            process_and_save_video(
                video_url,
                Path(destination),
                ffmpeg_log_level,
                auto_cleanup,
            )
    else:
        process_and_save_video(
            url,
            Path(destination),
            ffmpeg_log_level,
            auto_cleanup,
        )


def process_and_save_video(
    url: str,
    destination: Path,
    ffmpeg_log_level: str,
    auto_cleanup: bool,
) -> None:
    dir_path, video, captions_path = process_video(url, ffmpeg_log_level)
    try:
        captions_text = captions_path.read_text(encoding="utf-8")
        parsed = parse_srt(captions_text)
        html = convert_to_html(video, dir_path, parsed)

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
    parser = argparse.ArgumentParser(prog="glancer", description="Glancer")
    parser.add_argument("url", help="YouTube URL or playlist URL")
    parser.add_argument(
        "destination",
        help="HTML file name or directory for playlists",
    )
    parser.add_argument(
        "--ffmpeg-verbose",
        action="store_true",
        help="Show ffmpeg logs",
    )
    parser.add_argument(
        "--auto-cleanup",
        action="store_true",
        help="Delete cached downloads after HTML generation",
    )
    args = parser.parse_args(argv)
    run(
        args.url,
        args.destination,
        ffmpeg_verbose=args.ffmpeg_verbose,
        auto_cleanup=args.auto_cleanup,
    )


if __name__ == "__main__":  # pragma: no cover
    main()
