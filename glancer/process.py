from __future__ import annotations

import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import math
import os


@dataclass(frozen=True)
class Video:
    url: str
    title: str
    file: str


def get_title(url: str) -> str:
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


def get_id(url: str) -> str:
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


def youtube_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def generate_video(video: Video, directory: Path) -> None:
    video_name = video.file
    output_template = directory / f"{video_name}.%(ext)s"
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
        "--no-warnings",
        "-k",
        "--no-cache-dir",
        video.url,
    ]
    subprocess.run(args, check=True)


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


def generate_shots(directory: Path, filename: str, log_level: str) -> None:
    video_path = directory / f"{filename}.mp4"
    duration = get_video_duration(video_path)

    frame_selector = [
        "-vf",
        "fps=1/30",
        "-q:v",
        JPEG_QUALITY,
    ]
    starts: list[int] = []
    if duration <= 0:
        starts = [0]
    else:
        chunk = max(CHUNK_SECONDS, SECONDS_PER_SHOT)
        current = 0
        while current < duration:
            starts.append(int(current))
            current += chunk

    tasks: list[list[str]] = []
    for start in starts:
        length = max(0, min(CHUNK_SECONDS, duration - start))
        pre_input = ["-ss", str(start)]
        if length > 0:
            pre_input.extend(["-t", str(length)])
        start_number = int(math.floor(start / SECONDS_PER_SHOT))
        extra = ["-start_number", str(start_number)]
        cmd = _ffmpeg_args(
            directory,
            filename,
            frame_selector,
            "%04d",
            pre_input=pre_input,
            extra_args=extra,
            log_level=log_level,
        )
        tasks.append(cmd)

    if tasks:
        cpu_count = os.cpu_count() or 1
        target = max(4, cpu_count * 2)
        max_workers = max(1, min(len(tasks), target))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            executor.map(lambda cmd: subprocess.run(cmd, check=True), tasks)

    hero_selector = [
        "-q:v",
        JPEG_QUALITY,
        "-vframes",
        "1",
    ]
    hero_pre_input = ["-ss", "3"]
    hero_args = _ffmpeg_args(
        directory,
        filename,
        hero_selector,
        "0000",
        pre_input=hero_pre_input,
        log_level=log_level,
    )
    subprocess.run(hero_args, check=True)


def delete_video(directory: Path, filename: str) -> None:
    video_path = directory / f"{filename}.mp4"
    try:
        video_path.unlink()
    except FileNotFoundError:
        pass


def delete_images(directory: Path) -> None:
    for img_path in directory.glob("glancer-img*.jpg"):
        try:
            img_path.unlink()
        except FileNotFoundError:
            continue


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


SECONDS_PER_SHOT = 30
CHUNK_SECONDS = 5 * 60  # 5 minutes per ffmpeg chunk for parallel extraction.
JPEG_QUALITY = "2"


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


def process_url(url: str, ffmpeg_log_level: str = "error") -> tuple[Path, Video, Path]:
    temp_root = Path(tempfile.gettempdir()) / "glancer"
    temp_root.mkdir(parents=True, exist_ok=True)
    title = get_title(url)
    print(
        f"The video is titled '{title.strip()}'",
        file=sys.stderr,
    )
    video_id = get_id(url)
    full_url = youtube_url(video_id)
    print(f"Seems like the video is in {full_url}", file=sys.stderr)
    cache_dir = temp_root / video_id
    cache_dir.mkdir(parents=True, exist_ok=True)
    dir_path = cache_dir
    video_name = video_id
    video = Video(full_url, title, video_name)

    video_path = cache_dir / f"{video_name}.mp4"
    captions_path = cache_dir / f"{video_name}.en.vtt"
    if video_path.exists() and captions_path.exists():
        print(
            f"Reusing cached video and subtitles in {cache_dir}",
            file=sys.stderr,
        )
    else:
        print("Downloading video (this may take a while)", file=sys.stderr)
        generate_video(video, dir_path)
        dir_str = str(cache_dir)
        download_message = (
            f"Downloaded video to {dir_str}{video_name}(.mp4|en.vtt)"
        )
        print(download_message, file=sys.stderr)

    print(
        "Generating still images from video (this may take a while)",
        file=sys.stderr,
    )
    generate_shots(dir_path, video_name, ffmpeg_log_level)
    print("Generated images", file=sys.stderr)
    return dir_path, video, captions_path
