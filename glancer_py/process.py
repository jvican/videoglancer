from __future__ import annotations

import random
import string
import subprocess
import sys
import tempfile
import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import override


@dataclass(frozen=True)
class Url:
    value: str

    @override
    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class Title:
    value: str

    @override
    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class Dir:
    value: Path

    @override
    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True)
class Filename:
    value: str

    @override
    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class Video:
    url: Url
    title: Title
    file: Filename


def _run_command(args: list[str]) -> None:
    subprocess.run(args, check=True)


def get_title(url: Url) -> Title:
    result = subprocess.run(
        [
            "yt-dlp",
            "-e",
            "--no-warnings",
            "--no-playlist",
            str(url),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return Title(result.stdout.strip())


def get_id(url: Url) -> str:
    result = subprocess.run(
        [
            "yt-dlp",
            "--get-id",
            "--no-warnings",
            "--no-playlist",
            str(url),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def youtube_url(video_id: str) -> Url:
    return Url(f"https://www.youtube.com/watch?v={video_id}")


def generate_video(video: Video, directory: Dir) -> None:
    dir_path = directory.value
    video_name = video.file.value
    output_template = dir_path / f"{video_name}.%(ext)s"
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
        str(video.url),
    ]
    _run_command(args)


def _ffmpeg_args(
    directory: Dir,
    filename: Filename,
    selector: list[str],
    suffix: str,
    *,
    pre_input: list[str] | None = None,
    extra_args: list[str] | None = None,
    log_level: str = "error",
) -> list[str]:
    dir_path = directory.value
    input_path = dir_path / f"{filename.value}.mp4"
    output_pattern = dir_path / f"glancer-img{suffix}.jpg"
    command = ["ffmpeg", "-y", "-hide_banner", "-loglevel", log_level]
    if pre_input:
        command.extend(pre_input)
    command.extend(["-i", str(input_path)])
    command.extend(selector)
    if extra_args:
        command.extend(extra_args)
    command.append(str(output_pattern))
    return command


async def _run_ffmpeg_commands(commands: list[list[str]], max_parallel: int) -> None:
    semaphore = asyncio.Semaphore(max_parallel)

    async def worker(cmd: list[str]) -> None:
        async with semaphore:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                raise subprocess.CalledProcessError(
                    proc.returncode,
                    cmd,
                    output=stdout,
                    stderr=stderr,
                )

    await asyncio.gather(*(worker(cmd) for cmd in commands))


def generate_shots(directory: Dir, filename: Filename, log_level: str) -> None:
    dir_path = directory.value
    video_path = dir_path / f"{filename.value}.mp4"
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

    import math
    import os

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

    max_workers = min(len(tasks), (os.cpu_count() or 1)) if tasks else 1
    if max_workers < 1:
        max_workers = 1
    if tasks:
        asyncio.run(_run_ffmpeg_commands(tasks, max_workers))

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
    _run_command(hero_args)


def delete_video(directory: Dir, filename: Filename) -> None:
    video_path = directory.value / f"{filename.value}.mp4"
    try:
        video_path.unlink()
    except FileNotFoundError:
        pass


def delete_images(directory: Dir) -> None:
    for img_path in directory.value.glob("glancer-img*.jpg"):
        try:
            img_path.unlink()
        except FileNotFoundError:
            continue


def _random_filename(length: int = 10) -> str:
    return "".join(random.choice(string.ascii_lowercase) for _ in range(length))


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


def process_url(url: Url, ffmpeg_log_level: str = "error") -> tuple[Dir, Video, Path]:
    temp_root = Path(tempfile.gettempdir()) / "glancer"
    temp_root.mkdir(parents=True, exist_ok=True)
    title = get_title(url)
    print(
        f"The video is titled '{title.value.strip()}'",
        file=sys.stderr,
    )
    video_id = get_id(url)
    full_url = youtube_url(video_id)
    print(f"Seems like the video is in {full_url.value}", file=sys.stderr)
    cache_dir = temp_root / video_id
    cache_dir.mkdir(parents=True, exist_ok=True)
    dir_path = Dir(cache_dir)
    video_name = Filename(video_id)
    video = Video(full_url, title, video_name)

    video_path = cache_dir / f"{video_name.value}.mp4"
    captions_path = cache_dir / f"{video_name.value}.en.vtt"
    if video_path.exists() and captions_path.exists():
        print(
            f"Reusing cached video and subtitles in {cache_dir}",
            file=sys.stderr,
        )
    else:
        print("Downloading video (this may take a while)", file=sys.stderr)
        generate_video(video, dir_path)
        dir_str = str(cache_dir)
        download_message = f"Downloaded video to {dir_str}{video_name.value}(.mp4|en.vtt)"
        print(download_message, file=sys.stderr)

    print(
        "Generating still images from video (this may take a while)",
        file=sys.stderr,
    )
    generate_shots(dir_path, video_name, ffmpeg_log_level)
    print("Generated images", file=sys.stderr)
    return dir_path, video, captions_path
