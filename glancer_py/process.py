from __future__ import annotations

import random
import string
import subprocess
import sys
import tempfile
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
) -> list[str]:
    dir_path = directory.value
    input_path = dir_path / f"{filename.value}.mp4"
    output_pattern = dir_path / f"glancer-img{suffix}.jpg"
    return [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(input_path),
        *selector,
        str(output_pattern),
    ]


def generate_shots(directory: Dir, filename: Filename) -> None:
    quality_args = ["-q:v", "2"]
    frame_filter = ["-vf", "fps=1/30,scale=640:-1"]
    shot_args = _ffmpeg_args(directory, filename, frame_filter + quality_args, "%04d")
    _run_command(shot_args)

    hero_selector = ["-ss", "3", "-vframes", "1", "-vf", "scale=640:-1", *quality_args]
    hero_args = _ffmpeg_args(directory, filename, hero_selector, "0000")
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


def process_url(url: Url) -> tuple[Dir, Video, Path]:
    dir_path = Dir(Path(tempfile.gettempdir()))
    video_name = Filename(_random_filename())
    title = get_title(url)
    print(
        f"The video is titled '{title.value.strip()}'",
        file=sys.stderr,
    )
    video_id = get_id(url)
    full_url = youtube_url(video_id)
    print(f"Seems like the video is in {full_url.value}", file=sys.stderr)
    video = Video(full_url, title, video_name)
    print("Downloading video (this may take a while)", file=sys.stderr)
    generate_video(video, dir_path)
    dir_str = str(dir_path.value)
    download_message = f"Downloaded video to {dir_str}{video_name.value}(.mp4|en.vtt)"
    print(download_message, file=sys.stderr)
    print(
        "Generating still images from video (this may take a while)",
        file=sys.stderr,
    )
    generate_shots(dir_path, video_name)
    print("Generated images", file=sys.stderr)
    delete_video(dir_path, video_name)
    captions_path = dir_path.value / f"{video_name.value}.en.vtt"
    return dir_path, video, captions_path
