"""Tests for the shared JSON schema module."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from glancer.schema import (
    SCHEMA_VERSION,
    ExtractedContent,
    SlideData,
    VideoMeta,
)


class TestVideoMeta:
    def test_frozen_dataclass(self) -> None:
        video = VideoMeta(url="http://x", title="X", id="x")
        with pytest.raises(AttributeError):
            video.url = "http://y"  # type: ignore


class TestSlideData:
    def test_frozen_dataclass(self) -> None:
        slide = SlideData(
            index=0,
            image_base64="data",
            timestamp_seconds=0,
            caption_text="text",
            is_duplicate=False,
        )
        with pytest.raises(AttributeError):
            slide.index = 1  # type: ignore


class TestExtractedContent:
    def test_to_dict_produces_correct_structure(self) -> None:
        content = ExtractedContent(
            video=VideoMeta(url="http://test", title="Test", id="t1"),
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
            video=VideoMeta(url="http://test", title="Test Video", id="vid123"),
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
