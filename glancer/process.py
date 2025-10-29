from __future__ import annotations

import math
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Video:
    url: str
    title: str
    video_id: str


def get_video_metadata(url: str) -> Video:
    title = _get_title(url)
    video_id = _get_id(url)
    return Video(url, title, video_id)


def prepare_cache_directory(video_id: str) -> Path:
    temp_root = Path(tempfile.gettempdir()) / "glancer"
    cache_dir = temp_root / video_id
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def download_video_and_captions(video: Video, cache_dir: Path) -> Path:
    video_path = cache_dir / f"{video.video_id}.mp4"
    captions_path = cache_dir / f"{video.video_id}.en.srt"
    if not (video_path.exists() and captions_path.exists()):
        print("Downloading video (this may take a while)", file=sys.stderr)
        _generate_video(video, cache_dir)
        print(
            f"Downloaded video to {cache_dir}/{video.video_id}(.mp4|en.srt)",
            file=sys.stderr,
        )
    else:
        print(f"Reusing cached video in {cache_dir}", file=sys.stderr)
    return captions_path


def generate_stills(cache_dir: Path, video_id: str, log_level: str) -> None:
    print("Generating still images (this may take a while)", file=sys.stderr)
    _generate_shots(cache_dir, video_id, log_level)
    print("Generated images", file=sys.stderr)


def process_video(
    url: str, ffmpeg_log_level: str = "error"
) -> tuple[Path, Video, Path]:
    video = get_video_metadata(url)
    print(f"Processing video: '{video.title}'", file=sys.stderr)
    cache_dir = prepare_cache_directory(video.video_id)
    captions_path = download_video_and_captions(video, cache_dir)
    generate_stills(cache_dir, video.video_id, ffmpeg_log_level)
    return cache_dir, video, captions_path


def _get_title(url: str) -> str:
    try:
        result = subprocess.run(
            [
                "yt-dlp",
                "-e",
                "--no-warnings",
                "--no-playlist",
                url,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"yt-dlp error getting title:\nstdout: {e.stdout}\nstderr: {e.stderr}", file=sys.stderr)
        raise


def _get_id(url: str) -> str:
    try:
        result = subprocess.run(
            [
                "yt-dlp",
                "--get-id",
                "--no-warnings",
                "--no-playlist",
                url,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"yt-dlp error getting ID:\nstdout: {e.stdout}\nstderr: {e.stderr}", file=sys.stderr)
        raise


def _generate_video(video: Video, directory: Path) -> None:
    output_template = directory / f"{video.video_id}.%(ext)s"
    args = [
        "yt-dlp",
        "-q",
        "--no-playlist",
        "-f",
        "bv*[height<=720][ext=mp4]+ba[ext=m4a]/b[height<=720][ext=mp4]/best[ext=mp4]",
        "-o",
        str(output_template),
        "--merge-output-format",
        "mp4",
        "--sub-langs",
        "en",
        "--write-auto-sub",
        "--write-sub",
        "--sub-format",
        "srt",
        "--no-warnings",
        "-k",
        "--no-cache-dir",
        video.url,
    ]
    try:
        subprocess.run(args, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        print(f"yt-dlp error downloading video:\nstdout: {e.stdout}\nstderr: {e.stderr}", file=sys.stderr)
        raise


def _ffmpeg_args(
    directory: Path,
    filename: str,
    selector: list[str],
    suffix: str,
    *,
    pre_input: list[str] | None = None,
    extra_args: list[str] | None = None,
    log_level: str = "error",
) -> list[str]:
    input_path = directory / f"{filename}.mp4"
    output_pattern = directory / f"glancer-img{suffix}.jpg"
    command = ["ffmpeg", "-y", "-hide_banner", "-loglevel", log_level]
    if pre_input:
        command.extend(pre_input)
    command.extend(["-i", str(input_path)])
    command.extend(selector)
    if extra_args:
        command.extend(extra_args)
    command.append(str(output_pattern))
    return command


def run_ffmpeg(cmd: list[str]) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ffmpeg error: {result.stderr}", file=sys.stderr)
        result.check_returncode()


def _generate_shots(directory: Path, filename: str, log_level: str) -> None:
    video_path = directory / f"{filename}.mp4"
    duration = get_video_duration(video_path)

    frame_selector = ["-vf", "fps=1/30", "-pix_fmt", "yuvj420p", "-q:v", JPEG_QUALITY]
    starts = (
        [0]
        if duration <= 0
        else list(range(0, duration, max(CHUNK_SECONDS, SECONDS_PER_SHOT)))
    )

    tasks = []
    for start in starts:
        length = max(0, min(CHUNK_SECONDS, duration - start))
        if length <= 0:
            continue

        pre_input = ["-ss", str(start)]
        pre_input.extend(["-t", str(length)])
        start_number = int(math.floor(start / SECONDS_PER_SHOT))
        extra = ["-start_number", str(start_number)]

        # For short chunks, use a higher frame rate to ensure we get at least one frame
        current_frame_selector = frame_selector
        if length < SECONDS_PER_SHOT:
            current_frame_selector = ["-vf", f"fps=1/{max(1, length)}", "-pix_fmt", "yuvj420p", "-q:v", JPEG_QUALITY]

        cmd = _ffmpeg_args(
            directory,
            filename,
            current_frame_selector,
            "%04d",
            pre_input=pre_input,
            extra_args=extra,
            log_level=log_level,
        )
        tasks.append(cmd)

    if tasks:
        with ThreadPoolExecutor(
            max_workers=max(1, min(len(tasks), (os.cpu_count() or 1) * 2))
        ) as executor:
            executor.map(run_ffmpeg, tasks)

    hero_selector = ["-pix_fmt", "yuvj420p", "-q:v", JPEG_QUALITY, "-vframes", "1"]
    hero_pre_input = ["-ss", "3"]
    hero_args = _ffmpeg_args(
        directory,
        filename,
        hero_selector,
        "0000",
        pre_input=hero_pre_input,
        log_level=log_level,
    )
    run_ffmpeg(hero_args)


def cleanup_cache(path: Path) -> None:
    if not path.exists():
        return
    for item in path.iterdir():
        if item.is_dir():
            cleanup_cache(item)
        else:
            try:
                item.unlink()
            except FileNotFoundError:
                continue
    try:
        path.rmdir()
    except OSError:
        pass


def delete_images(directory: Path) -> None:
    for img_path in directory.glob("glancer-img*.jpg"):
        try:
            img_path.unlink()
        except FileNotFoundError:
            continue


SECONDS_PER_SHOT = 30
CHUNK_SECONDS = 300
JPEG_QUALITY = "5"


def get_video_duration(video_path: Path) -> int:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    try:
        return int(float(result.stdout.strip()))
    except ValueError:
        return 0
