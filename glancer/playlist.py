from __future__ import annotations

import subprocess
from dataclasses import dataclass


@dataclass
class Playlist:
    url: str

    def __post_init__(self) -> None:
        self._video_ids: list[str] | None = None
        self._index = 0

    def __iter__(self) -> "Playlist":
        self._video_ids = self._get_video_ids()
        self._index = 0
        return self

    def __next__(self) -> str:
        if self._video_ids is None:
            self._video_ids = self._get_video_ids()
        if self._index < len(self._video_ids):
            video_id = self._video_ids[self._index]
            self._index += 1
            return f"https://www.youtube.com/watch?v={video_id}"
        raise StopIteration

    def _get_video_ids(self) -> list[str]:
        result = subprocess.run(
            [
                "yt-dlp",
                "--flat-playlist",
                "-i",
                "--get-id",
                self.url,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip().split("\n")

    @staticmethod
    def is_playlist(url: str) -> bool:
        return "list=" in url
