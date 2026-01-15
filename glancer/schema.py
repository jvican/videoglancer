"""JSON schema for extracted video content.

This is the ONLY shared code between glancer-extract and glancer-render.

## Schema v1

```json
{
  "schema_version": 1,
  "video": {
    "url": "https://youtube.com/watch?v=...",
    "title": "Video Title",
    "id": "video_id"
  },
  "slides": [
    {
      "index": 0,
      "image_base64": "...",
      "timestamp_seconds": 0,
      "caption_text": "Combined caption text for this slide",
      "is_duplicate": false
    }
  ],
  "config": {
    "seconds_per_shot": 30
  }
}
```
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1


@dataclass(frozen=True)
class VideoMeta:
    url: str
    title: str
    id: str


@dataclass(frozen=True)
class SlideData:
    index: int
    image_base64: str
    timestamp_seconds: int
    caption_text: str
    is_duplicate: bool


@dataclass
class ExtractedContent:
    video: VideoMeta
    slides: list[SlideData]
    seconds_per_shot: int = 30

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "video": {"url": self.video.url, "title": self.video.title, "id": self.video.id},
            "slides": [
                {
                    "index": s.index,
                    "image_base64": s.image_base64,
                    "timestamp_seconds": s.timestamp_seconds,
                    "caption_text": s.caption_text,
                    "is_duplicate": s.is_duplicate,
                }
                for s in self.slides
            ],
            "config": {"seconds_per_shot": self.seconds_per_shot},
        }

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "ExtractedContent":
        data = json.loads(path.read_text(encoding="utf-8"))
        version = data.get("schema_version", 1)
        if version > SCHEMA_VERSION:
            raise ValueError(f"Schema version {version} not supported (max: {SCHEMA_VERSION})")

        return cls(
            video=VideoMeta(
                url=data["video"]["url"],
                title=data["video"]["title"],
                id=data["video"]["id"],
            ),
            slides=[
                SlideData(
                    index=s["index"],
                    image_base64=s["image_base64"],
                    timestamp_seconds=s["timestamp_seconds"],
                    caption_text=s["caption_text"],
                    is_duplicate=s["is_duplicate"],
                )
                for s in data["slides"]
            ],
            seconds_per_shot=data.get("config", {}).get("seconds_per_shot", 30),
        )
