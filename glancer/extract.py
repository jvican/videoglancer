#!/usr/bin/env python3
"""glancer-extract: Extract video content to JSON.

This tool downloads a YouTube video, extracts frames and captions,
and outputs a self-contained JSON file for later rendering.

Usage:
    glancer-extract URL [OUTPUT]
    glancer-extract https://youtube.com/watch?v=... output.json
"""
from __future__ import annotations

import argparse
import base64
import html
import logging
import math
import os
import re
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Iterable, Sequence

import srt
from PIL import Image, ImageOps

from .schema import ExtractedContent, SlideData, VideoMeta

logger = logging.getLogger(__name__)

SECONDS_PER_SHOT = 30
CHUNK_SECONDS = 300
JPEG_QUALITY = "5"


# === Video download ===


@dataclass(frozen=True)
class Video:
    url: str
    title: str
    video_id: str


def download_video(url: str, ffmpeg_log_level: str = "error") -> tuple[Path, Video, Path]:
    """Download video and captions, extract frames."""
    video = _get_video_metadata(url)
    print(f"Processing: '{video.title}'", file=sys.stderr)

    cache_dir = Path(tempfile.gettempdir()) / "glancer" / video.video_id
    cache_dir.mkdir(parents=True, exist_ok=True)

    captions_path = _download_video_and_captions(video, cache_dir)
    _extract_frames(cache_dir, video.video_id, ffmpeg_log_level)

    return cache_dir, video, captions_path


def _get_video_metadata(url: str) -> Video:
    title = subprocess.run(
        ["yt-dlp", "-e", "--no-warnings", "--no-playlist", url],
        check=True, capture_output=True, text=True,
    ).stdout.strip()

    video_id = subprocess.run(
        ["yt-dlp", "--get-id", "--no-warnings", "--no-playlist", url],
        check=True, capture_output=True, text=True,
    ).stdout.strip()

    return Video(url=url, title=title, video_id=video_id)


def _download_video_and_captions(video: Video, cache_dir: Path) -> Path:
    video_path = cache_dir / f"{video.video_id}.mp4"
    captions_path = cache_dir / f"{video.video_id}.en.srt"

    if video_path.exists() and captions_path.exists():
        print(f"Using cached video in {cache_dir}", file=sys.stderr)
        return captions_path

    print("Downloading video...", file=sys.stderr)
    subprocess.run([
        "yt-dlp", "-q", "--no-playlist",
        "-f", "bv*[height<=720][ext=mp4]+ba[ext=m4a]/b[height<=720][ext=mp4]/best[ext=mp4]",
        "-o", str(cache_dir / f"{video.video_id}.%(ext)s"),
        "--merge-output-format", "mp4",
        "--sub-langs", "en", "--write-auto-sub", "--write-sub",
        "--sub-format", "srt", "--no-warnings", "-k", "--no-cache-dir",
        video.url,
    ], check=True, capture_output=True, text=True)

    return captions_path


def _extract_frames(cache_dir: Path, video_id: str, log_level: str) -> None:
    print("Extracting frames...", file=sys.stderr)
    video_path = cache_dir / f"{video_id}.mp4"

    duration = int(float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(video_path)],
        check=True, capture_output=True, text=True,
    ).stdout.strip() or "0"))

    starts = [0] if duration <= 0 else list(range(0, duration, max(CHUNK_SECONDS, SECONDS_PER_SHOT)))
    tasks = []

    for start in starts:
        length = max(0, min(CHUNK_SECONDS, duration - start))
        if length <= 0:
            continue
        start_number = int(math.floor(start / SECONDS_PER_SHOT))
        tasks.append(_build_ffmpeg_cmd(cache_dir, video_id, start, length, start_number, log_level))

    if tasks:
        with ThreadPoolExecutor(max_workers=max(1, min(len(tasks), (os.cpu_count() or 1) * 2))) as ex:
            ex.map(_run_ffmpeg, tasks)

    # First frame at 3 seconds
    _run_ffmpeg([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", log_level,
        "-ss", "3", "-i", str(video_path),
        "-pix_fmt", "yuvj420p", "-q:v", JPEG_QUALITY, "-vframes", "1",
        str(cache_dir / "glancer-img0000.jpg"),
    ])


def _build_ffmpeg_cmd(cache_dir: Path, video_id: str, start: int, length: int, start_number: int, log_level: str) -> list[str]:
    return [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", log_level,
        "-ss", str(start), "-t", str(length),
        "-i", str(cache_dir / f"{video_id}.mp4"),
        "-vf", "fps=1/30", "-pix_fmt", "yuvj420p", "-q:v", JPEG_QUALITY,
        "-start_number", str(start_number),
        str(cache_dir / "glancer-img%04d.jpg"),
    ]


def _run_ffmpeg(cmd: list[str]) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.warning(f"ffmpeg error: {result.stderr}")


# === Caption processing ===


@dataclass(frozen=True)
class Caption:
    start: float
    end: float
    text: str


def parse_captions(path: Path) -> list[Caption]:
    """Parse SRT file into Caption objects."""
    contents = path.read_text(encoding="utf-8")
    return [
        Caption(
            start=sub.start.total_seconds(),
            end=sub.end.total_seconds(),
            text=sub.content.replace("\r\n", "\n").replace("\r", "\n"),
        )
        for sub in srt.parse(contents)
    ]


def get_caption_texts(captions: list[Caption]) -> list[str]:
    """Get combined caption text for each slide."""
    cleaned = [_clean_caption(c) for c in captions if _clean_caption(c).text]
    if not cleaned:
        return []

    total_shots = max(1, int(math.floor(cleaned[-1].end / SECONDS_PER_SHOT)))
    texts = []

    for shot_idx in range(total_shots):
        shot_start = shot_idx * SECONDS_PER_SHOT
        shot_end = cleaned[-1].end if shot_idx == total_shots - 1 else shot_start + SECONDS_PER_SHOT

        overlapping = [c for c in cleaned if c.start <= shot_end and c.end >= shot_start]
        combined = " ".join(" ".join(c.text.strip().replace("\n", " ").split()) for c in overlapping)
        texts.append(" ".join(combined.split()))

    return texts


TAG_RE = re.compile(r"<[^>]+>")


def _clean_caption(caption: Caption) -> Caption:
    text = html.unescape(caption.text)
    text = TAG_RE.sub("", text)
    text = text.replace("\u00a0", " ").strip()
    return replace(caption, text=text)


# === Duplicate detection ===


def find_duplicates(image_dir: Path, threshold: int = 5) -> set[int]:
    """Find duplicate slides using perceptual hashing."""
    duplicates: set[int] = set()
    unique_hashes: list[int] = []

    for path in sorted(image_dir.glob("glancer-img*.jpg")):
        try:
            idx = int(path.stem.replace("glancer-img", ""))
            img_hash = _dhash(path)
        except (ValueError, OSError):
            continue

        if any(_hamming(img_hash, h) <= threshold for h in unique_hashes):
            duplicates.add(idx)
        else:
            unique_hashes.append(img_hash)

    return duplicates


def _dhash(path: Path, size: int = 8) -> int:
    with Image.open(path) as img:
        gray = ImageOps.grayscale(img)
        resized = gray.resize((size + 1, size), getattr(Image.Resampling, "LANCZOS", Image.LANCZOS))
        pixels = list(resized.getdata())

    bits = []
    for row in range(size):
        offset = row * (size + 1)
        for col in range(size):
            bits.append(1 if pixels[offset + col] < pixels[offset + col + 1] else 0)

    result = 0
    for i, bit in enumerate(bits):
        if bit:
            result |= 1 << i
    return result


def _hamming(a: int, b: int) -> int:
    return (a ^ b).bit_count()


# === Content extraction ===


def extract(video: Video, image_dir: Path, caption_texts: list[str], duplicates: set[int]) -> ExtractedContent:
    """Create ExtractedContent from processed video data."""
    slides: list[SlideData] = []

    for img_path in sorted(image_dir.glob("glancer-img*.jpg")):
        try:
            idx = int(img_path.stem.replace("glancer-img", ""))
            img_b64 = base64.b64encode(img_path.read_bytes()).decode("ascii")
        except (ValueError, OSError):
            continue

        slides.append(SlideData(
            index=idx,
            image_base64=img_b64,
            timestamp_seconds=idx * SECONDS_PER_SHOT,
            caption_text=caption_texts[idx] if idx < len(caption_texts) else "",
            is_duplicate=idx in duplicates,
        ))

    return ExtractedContent(
        video=VideoMeta(url=video.url, title=video.title, id=video.video_id),
        slides=slides,
        seconds_per_shot=SECONDS_PER_SHOT,
    )


# === CLI ===


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="glancer-extract",
        description="Extract YouTube video content to JSON",
    )
    parser.add_argument("url", help="YouTube video URL")
    parser.add_argument("output", nargs="?", help="Output JSON file (default: VIDEO_TITLE.json)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--no-detect-duplicates", action="store_true", help="Skip duplicate detection")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s: %(message)s",
        stream=sys.stderr,
    )

    # Download and process
    cache_dir, video, captions_path = download_video(
        args.url,
        ffmpeg_log_level="info" if args.verbose else "error",
    )

    # Parse captions
    captions = parse_captions(captions_path)
    caption_texts = get_caption_texts(captions)

    # Detect duplicates
    duplicates = set() if args.no_detect_duplicates else find_duplicates(cache_dir)

    # Extract content
    content = extract(video, cache_dir, caption_texts, duplicates)

    # Output
    if args.output:
        output_path = Path(args.output)
    else:
        safe_title = re.sub(r'[<>:"/\\|?*]', '_', video.title)
        output_path = Path(f"{safe_title}.json")
    content.save(output_path)
    print(f"Saved: {output_path}", file=sys.stderr)
    print(f"  {len(content.slides)} slides, {len([s for s in content.slides if not s.is_duplicate])} unique", file=sys.stderr)


if __name__ == "__main__":
    main()
