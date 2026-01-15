"""JSON Intermediate Representation for extracted video content.

This module defines the JSON IR that bridges Phase 1 (extraction) and Phase 2 (rendering).

## JSON IR Specification (v1)

The JSON file contains all data needed to render HTML or PDF without re-processing:

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
    },
    ...
  ],
  "config": {
    "seconds_per_shot": 30
  }
}
```

### Fields:
- schema_version: Integer version for compatibility checking
- video: Source video metadata
- slides: Pre-processed slides ready for rendering
  - index: Slide number (0-based)
  - image_base64: JPEG image encoded as base64 string
  - timestamp_seconds: Video timestamp for this slide
  - caption_text: Combined, cleaned caption text (empty string if none)
  - is_duplicate: True if slide is visually similar to an earlier slide
- config: Processing parameters used during extraction
"""
from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1


@dataclass(frozen=True)
class VideoInfo:
    """Video metadata."""
    url: str
    title: str
    id: str


@dataclass(frozen=True)
class SlideData:
    """A single slide ready for rendering."""
    index: int
    image_base64: str
    timestamp_seconds: int
    caption_text: str
    is_duplicate: bool


@dataclass
class ExtractedContent:
    """Complete extracted content, serializable to JSON."""
    video: VideoInfo
    slides: list[SlideData]
    seconds_per_shot: int = 30

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "schema_version": SCHEMA_VERSION,
            "video": {
                "url": self.video.url,
                "title": self.video.title,
                "id": self.video.id,
            },
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
            "config": {
                "seconds_per_shot": self.seconds_per_shot,
            },
        }

    def save(self, path: Path) -> None:
        """Save to JSON file."""
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "ExtractedContent":
        """Load from JSON file."""
        data = json.loads(path.read_text(encoding="utf-8"))

        version = data.get("schema_version", 1)
        if version > SCHEMA_VERSION:
            raise ValueError(
                f"JSON schema version {version} not supported. "
                f"Maximum supported: {SCHEMA_VERSION}"
            )

        video = VideoInfo(
            url=data["video"]["url"],
            title=data["video"]["title"],
            id=data["video"]["id"],
        )

        slides = [
            SlideData(
                index=s["index"],
                image_base64=s["image_base64"],
                timestamp_seconds=s["timestamp_seconds"],
                caption_text=s["caption_text"],
                is_duplicate=s["is_duplicate"],
            )
            for s in data["slides"]
        ]

        return cls(
            video=video,
            slides=slides,
            seconds_per_shot=data.get("config", {}).get("seconds_per_shot", 30),
        )


def extract_content(
    video_url: str,
    video_title: str,
    video_id: str,
    image_dir: Path,
    caption_texts: list[str],
    duplicate_indices: set[int],
    seconds_per_shot: int = 30,
) -> ExtractedContent:
    """Create ExtractedContent from processing results.

    Args:
        video_url: Source video URL
        video_title: Video title
        video_id: Video ID
        image_dir: Directory containing glancer-img*.jpg files
        caption_texts: List of caption text per slide (index-aligned)
        duplicate_indices: Set of slide indices that are duplicates
        seconds_per_shot: Seconds between each frame

    Returns:
        ExtractedContent ready for serialization
    """
    video = VideoInfo(url=video_url, title=video_title, id=video_id)
    slides: list[SlideData] = []

    # Load images and create slides
    for img_path in sorted(image_dir.glob("glancer-img*.jpg")):
        try:
            index = int(img_path.stem.replace("glancer-img", ""))
        except ValueError:
            continue

        try:
            image_data = base64.b64encode(img_path.read_bytes()).decode("ascii")
        except OSError as e:
            logger.warning(f"Failed to read image {img_path}: {e}")
            continue

        caption_text = caption_texts[index] if index < len(caption_texts) else ""

        slides.append(
            SlideData(
                index=index,
                image_base64=image_data,
                timestamp_seconds=index * seconds_per_shot,
                caption_text=caption_text,
                is_duplicate=index in duplicate_indices,
            )
        )

    return ExtractedContent(video=video, slides=slides, seconds_per_shot=seconds_per_shot)
