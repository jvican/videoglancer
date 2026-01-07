"""Module for extracting and serializing video content to JSON.

This module provides functionality to split the video processing workflow into two phases:
1. Content Extraction: Download video, extract frames, parse captions, output JSON
2. Artifact Generation: Read JSON, generate HTML/PDF output

The JSON intermediate format enables caching of the expensive extraction phase
and allows experimentation with different output formats.
"""
from __future__ import annotations

import base64
import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .parser import Caption
from .process import Video

logger = logging.getLogger(__name__)

# Schema version for backwards compatibility
CONTENT_SCHEMA_VERSION = 1


@dataclass
class ExtractedImage:
    """A single extracted frame from the video."""

    index: int  # Frame index (0-based)
    data_base64: str  # Base64-encoded JPEG data
    timestamp_seconds: int  # Timestamp in seconds when this frame was captured


@dataclass
class ExtractedContent:
    """Complete extracted content from a video, serializable to JSON.

    This structure contains all data needed to generate HTML or PDF output
    without requiring access to the original video or intermediate files.
    """

    # Schema version for forward/backward compatibility
    schema_version: int

    # Video metadata
    video_url: str
    video_title: str
    video_id: str

    # Captions list
    captions: list[dict[str, Any]]  # List of {start, end, text}

    # Extracted images
    images: list[dict[str, Any]]  # List of {index, data_base64, timestamp_seconds}

    # Processing configuration
    seconds_per_shot: int

    @classmethod
    def from_processing(
        cls,
        video: Video,
        captions: list[Caption],
        directory: Path,
        seconds_per_shot: int = 30,
    ) -> "ExtractedContent":
        """Create ExtractedContent from video processing results.

        Args:
            video: Video metadata
            captions: Parsed captions from SRT
            directory: Directory containing extracted JPEG frames
            seconds_per_shot: Seconds between each frame (default 30)

        Returns:
            ExtractedContent ready for serialization
        """
        # Convert captions to dict format
        caption_dicts = [
            {"start": c.start, "end": c.end, "text": c.text} for c in captions
        ]

        # Load and encode images
        images: list[dict[str, Any]] = []
        for img_path in sorted(directory.glob("glancer-img*.jpg")):
            try:
                # Extract index from filename (glancer-img0001.jpg -> 1)
                index = int(img_path.stem.replace("glancer-img", ""))
                data = img_path.read_bytes()
                data_base64 = base64.b64encode(data).decode("ascii")
                images.append(
                    {
                        "index": index,
                        "data_base64": data_base64,
                        "timestamp_seconds": index * seconds_per_shot,
                    }
                )
            except (ValueError, OSError) as e:
                logger.warning(f"Failed to process image {img_path}: {e}")
                continue

        logger.info(f"Extracted {len(images)} images and {len(caption_dicts)} captions")

        return cls(
            schema_version=CONTENT_SCHEMA_VERSION,
            video_url=video.url,
            video_title=video.title,
            video_id=video.video_id,
            captions=caption_dicts,
            images=images,
            seconds_per_shot=seconds_per_shot,
        )

    def to_json(self, indent: int | None = 2) -> str:
        """Serialize to JSON string.

        Args:
            indent: JSON indentation level (None for compact)

        Returns:
            JSON string representation
        """
        return json.dumps(asdict(self), indent=indent)

    def save(self, path: Path) -> None:
        """Save to a JSON file.

        Args:
            path: Output file path
        """
        path.write_text(self.to_json(), encoding="utf-8")
        logger.info(f"Saved extracted content to {path}")

    @classmethod
    def load(cls, path: Path) -> "ExtractedContent":
        """Load from a JSON file.

        Args:
            path: Input file path

        Returns:
            ExtractedContent instance

        Raises:
            ValueError: If schema version is unsupported
        """
        data = json.loads(path.read_text(encoding="utf-8"))

        schema_version = data.get("schema_version", 1)
        if schema_version > CONTENT_SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported schema version {schema_version}. "
                f"Maximum supported version is {CONTENT_SCHEMA_VERSION}"
            )

        return cls(
            schema_version=schema_version,
            video_url=data["video_url"],
            video_title=data["video_title"],
            video_id=data["video_id"],
            captions=data["captions"],
            images=data["images"],
            seconds_per_shot=data.get("seconds_per_shot", 30),
        )

    def get_video(self) -> Video:
        """Reconstruct Video object from extracted content."""
        return Video(
            url=self.video_url,
            title=self.video_title,
            video_id=self.video_id,
        )

    def get_captions(self) -> list[Caption]:
        """Reconstruct Caption objects from extracted content."""
        return [
            Caption(start=c["start"], end=c["end"], text=c["text"])
            for c in self.captions
        ]

    def get_image_data(self, index: int) -> bytes | None:
        """Get decoded image data for a specific index.

        Args:
            index: Frame index

        Returns:
            Decoded JPEG bytes or None if not found
        """
        for img in self.images:
            if img["index"] == index:
                return base64.b64decode(img["data_base64"])
        return None

    def get_image_indices(self) -> list[int]:
        """Get sorted list of available image indices."""
        return sorted(img["index"] for img in self.images)
