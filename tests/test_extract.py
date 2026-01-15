"""Tests for glancer-extract CLI."""
from __future__ import annotations

import base64
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image

from glancer.extract import (
    Caption,
    Video,
    extract,
    find_duplicates,
    get_caption_texts,
    parse_captions,
)


def _create_test_image(path: Path, color: tuple[int, int, int]) -> None:
    """Create a simple test JPEG image."""
    img = Image.new("RGB", (64, 64), color=color)
    img.save(path, format="JPEG")


class TestParseCaptions:
    def test_parses_srt_file(self, tmp_path: Path) -> None:
        srt_content = """1
00:00:00,000 --> 00:00:05,000
Hello world

2
00:00:05,000 --> 00:00:10,000
Second caption
"""
        srt_path = tmp_path / "test.srt"
        srt_path.write_text(srt_content)

        captions = parse_captions(srt_path)

        assert len(captions) == 2
        assert captions[0].text == "Hello world"
        assert captions[0].start == 0.0
        assert captions[0].end == 5.0
        assert captions[1].text == "Second caption"


class TestGetCaptionTexts:
    def test_combines_captions_per_shot(self) -> None:
        # Captions spanning 60+ seconds to create 2 shots
        captions = [
            Caption(start=0.0, end=5.0, text="First"),
            Caption(start=25.0, end=30.0, text="Second"),
            Caption(start=35.0, end=65.0, text="Third"),
        ]

        texts = get_caption_texts(captions)

        # floor(65/30) = 2 shots
        assert len(texts) == 2
        assert "First" in texts[0]
        assert "Second" in texts[0]
        assert "Third" in texts[1]

    def test_empty_captions_returns_empty(self) -> None:
        assert get_caption_texts([]) == []


def _create_patterned_image(path: Path, pattern: str) -> None:
    """Create an image with a distinct pattern for unique perceptual hash."""
    img = Image.new("RGB", (64, 64))
    pixels = img.load()
    for y in range(64):
        for x in range(64):
            if pattern == "checkerboard":
                val = 255 if (x // 8 + y // 8) % 2 == 0 else 0
            elif pattern == "vertical_stripes":
                val = 255 if (x // 8) % 2 == 0 else 0
            elif pattern == "diagonal":
                val = 255 if x > y else 0
            else:
                val = 128
            pixels[x, y] = (val, val, val)
    img.save(path, format="JPEG")


class TestFindDuplicates:
    def test_marks_identical_images_as_duplicates(self, tmp_path: Path) -> None:
        # Create identical images (solid color has same dhash)
        for i in range(3):
            _create_test_image(tmp_path / f"glancer-img{i:04d}.jpg", (100, 100, 100))

        duplicates = find_duplicates(tmp_path)

        # First image is not a duplicate, subsequent ones are
        assert 0 not in duplicates
        assert 1 in duplicates
        assert 2 in duplicates

    def test_different_patterns_not_duplicates(self, tmp_path: Path) -> None:
        # Create images with distinct patterns for different dhash values
        _create_patterned_image(tmp_path / "glancer-img0000.jpg", "checkerboard")
        _create_patterned_image(tmp_path / "glancer-img0001.jpg", "vertical_stripes")
        _create_patterned_image(tmp_path / "glancer-img0002.jpg", "diagonal")

        duplicates = find_duplicates(tmp_path)

        assert len(duplicates) == 0


class TestExtract:
    def test_creates_extracted_content(self, tmp_path: Path) -> None:
        # Create test images
        for i in range(2):
            _create_test_image(tmp_path / f"glancer-img{i:04d}.jpg", (100, 100, 100))

        video = Video(url="http://example.com", title="Test", video_id="test123")
        caption_texts = ["First caption", "Second caption"]
        duplicates = {1}

        content = extract(video, tmp_path, caption_texts, duplicates)

        assert content.video.url == "http://example.com"
        assert content.video.title == "Test"
        assert content.video.id == "test123"
        assert len(content.slides) == 2
        assert content.slides[0].caption_text == "First caption"
        assert content.slides[0].is_duplicate is False
        assert content.slides[1].is_duplicate is True

    def test_encodes_images_as_base64(self, tmp_path: Path) -> None:
        _create_test_image(tmp_path / "glancer-img0000.jpg", (100, 100, 100))

        video = Video(url="http://example.com", title="Test", video_id="test")
        content = extract(video, tmp_path, [""], set())

        # Verify base64 is valid JPEG
        decoded = base64.b64decode(content.slides[0].image_base64)
        assert decoded[:2] == b"\xff\xd8"  # JPEG magic bytes
