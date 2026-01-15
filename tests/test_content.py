"""Tests for content extraction and JSON serialization."""
from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest
from PIL import Image

from glancer.content import (
    SCHEMA_VERSION,
    ExtractedContent,
    SlideData,
    VideoInfo,
    extract_content,
)


def _create_test_image(path: Path, color: tuple[int, int, int]) -> None:
    """Create a simple test JPEG image."""
    image = Image.new("RGB", (64, 64), color=color)
    image.save(path, format="JPEG")


def _create_test_images(directory: Path, count: int = 3) -> None:
    """Create test images in the expected naming format."""
    colors = [(200, 100, 100), (100, 200, 100), (100, 100, 200)]
    for i in range(count):
        path = directory / f"glancer-img{i:04d}.jpg"
        _create_test_image(path, colors[i % len(colors)])


class TestExtractContent:
    def test_creates_content_from_processing(self, tmp_path: Path) -> None:
        _create_test_images(tmp_path, count=2)
        caption_texts = ["First slide caption", "Second slide caption"]
        duplicates = {1}  # Mark second as duplicate

        content = extract_content(
            video_url="http://example.com",
            video_title="Test Video",
            video_id="test123",
            image_dir=tmp_path,
            caption_texts=caption_texts,
            duplicate_indices=duplicates,
        )

        assert content.video.url == "http://example.com"
        assert content.video.title == "Test Video"
        assert content.video.id == "test123"
        assert len(content.slides) == 2
        assert content.slides[0].caption_text == "First slide caption"
        assert content.slides[0].is_duplicate is False
        assert content.slides[1].is_duplicate is True

    def test_encodes_images_as_base64(self, tmp_path: Path) -> None:
        _create_test_images(tmp_path, count=1)

        content = extract_content(
            video_url="http://example.com",
            video_title="Test",
            video_id="test",
            image_dir=tmp_path,
            caption_texts=[""],
            duplicate_indices=set(),
        )

        assert len(content.slides) == 1
        # Verify base64 is valid
        decoded = base64.b64decode(content.slides[0].image_base64)
        assert len(decoded) > 0
        # JPEG magic bytes
        assert decoded[:2] == b"\xff\xd8"

    def test_handles_missing_images(self, tmp_path: Path) -> None:
        # No images created
        content = extract_content(
            video_url="http://example.com",
            video_title="Test",
            video_id="test",
            image_dir=tmp_path,
            caption_texts=["caption"],
            duplicate_indices=set(),
        )

        assert content.slides == []


class TestExtractedContentSerialization:
    def test_to_dict_produces_correct_structure(self) -> None:
        content = ExtractedContent(
            video=VideoInfo(url="http://test", title="Test", id="t1"),
            slides=[
                SlideData(
                    index=0,
                    image_base64="abc123",
                    timestamp_seconds=0,
                    caption_text="Hello",
                    is_duplicate=False,
                )
            ],
            seconds_per_shot=30,
        )

        d = content.to_dict()

        assert d["schema_version"] == SCHEMA_VERSION
        assert d["video"]["url"] == "http://test"
        assert d["video"]["title"] == "Test"
        assert d["video"]["id"] == "t1"
        assert len(d["slides"]) == 1
        assert d["slides"][0]["index"] == 0
        assert d["slides"][0]["caption_text"] == "Hello"
        assert d["config"]["seconds_per_shot"] == 30

    def test_save_and_load_roundtrip(self, tmp_path: Path) -> None:
        original = ExtractedContent(
            video=VideoInfo(url="http://test", title="Test Video", id="vid123"),
            slides=[
                SlideData(
                    index=0,
                    image_base64="base64data",
                    timestamp_seconds=0,
                    caption_text="Caption",
                    is_duplicate=False,
                ),
                SlideData(
                    index=1,
                    image_base64="moredata",
                    timestamp_seconds=30,
                    caption_text="More",
                    is_duplicate=True,
                ),
            ],
            seconds_per_shot=30,
        )

        json_path = tmp_path / "content.json"
        original.save(json_path)
        assert json_path.exists()

        loaded = ExtractedContent.load(json_path)

        assert loaded.video.url == original.video.url
        assert loaded.video.title == original.video.title
        assert loaded.video.id == original.video.id
        assert len(loaded.slides) == len(original.slides)
        for orig, load in zip(original.slides, loaded.slides):
            assert load.index == orig.index
            assert load.image_base64 == orig.image_base64
            assert load.caption_text == orig.caption_text
            assert load.is_duplicate == orig.is_duplicate

    def test_load_rejects_unsupported_schema_version(self, tmp_path: Path) -> None:
        json_path = tmp_path / "future.json"
        json_path.write_text(
            json.dumps(
                {
                    "schema_version": SCHEMA_VERSION + 1,
                    "video": {"url": "x", "title": "x", "id": "x"},
                    "slides": [],
                    "config": {},
                }
            )
        )

        with pytest.raises(ValueError, match="not supported"):
            ExtractedContent.load(json_path)


class TestSlideData:
    def test_frozen_dataclass(self) -> None:
        slide = SlideData(
            index=0,
            image_base64="data",
            timestamp_seconds=0,
            caption_text="text",
            is_duplicate=False,
        )
        # Should not be modifiable
        with pytest.raises(AttributeError):
            slide.index = 1  # type: ignore


class TestVideoInfo:
    def test_frozen_dataclass(self) -> None:
        video = VideoInfo(url="http://x", title="X", id="x")
        with pytest.raises(AttributeError):
            video.url = "http://y"  # type: ignore
