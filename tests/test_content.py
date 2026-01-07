"""Tests for content extraction and JSON serialization."""
from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from glancer.content import CONTENT_SCHEMA_VERSION, ExtractedContent
from glancer.parser import Caption
from glancer.process import Video


def _create_test_image(path: Path, color: tuple[int, int, int]) -> None:
    """Create a simple test JPEG image."""
    image = Image.new("RGB", (64, 64), color=color)
    draw = ImageDraw.Draw(image)
    draw.rectangle((10, 10, 54, 54), fill=(color[0] // 2, color[1] // 2, color[2] // 2))
    image.save(path, format="JPEG")


def _create_test_images(directory: Path, count: int = 3) -> None:
    """Create multiple test images in the expected naming format."""
    colors = [(200, 100, 100), (100, 200, 100), (100, 100, 200)]
    for i in range(count):
        path = directory / f"glancer-img{i:04d}.jpg"
        _create_test_image(path, colors[i % len(colors)])


@pytest.fixture
def sample_video() -> Video:
    return Video(
        url="https://www.youtube.com/watch?v=test123",
        title="Test Video Title",
        video_id="test123",
    )


@pytest.fixture
def sample_captions() -> list[Caption]:
    return [
        Caption(start=0.0, end=10.0, text="First caption"),
        Caption(start=10.0, end=25.0, text="Second caption"),
        Caption(start=30.0, end=45.0, text="Third caption"),
    ]


class TestExtractedContentFromProcessing:
    def test_creates_content_from_video_and_captions(
        self, tmp_path: Path, sample_video: Video, sample_captions: list[Caption]
    ) -> None:
        _create_test_images(tmp_path)

        content = ExtractedContent.from_processing(
            sample_video, sample_captions, tmp_path
        )

        assert content.schema_version == CONTENT_SCHEMA_VERSION
        assert content.video_url == sample_video.url
        assert content.video_title == sample_video.title
        assert content.video_id == sample_video.video_id
        assert len(content.captions) == 3
        assert len(content.images) == 3

    def test_encodes_images_as_base64(
        self, tmp_path: Path, sample_video: Video, sample_captions: list[Caption]
    ) -> None:
        _create_test_images(tmp_path, count=1)

        content = ExtractedContent.from_processing(
            sample_video, sample_captions, tmp_path
        )

        assert len(content.images) == 1
        img_data = content.images[0]
        assert img_data["index"] == 0
        assert img_data["timestamp_seconds"] == 0
        # Verify base64 is valid by decoding
        decoded = base64.b64decode(img_data["data_base64"])
        assert len(decoded) > 0

    def test_handles_empty_captions(
        self, tmp_path: Path, sample_video: Video
    ) -> None:
        _create_test_images(tmp_path)

        content = ExtractedContent.from_processing(sample_video, [], tmp_path)

        assert content.captions == []
        assert len(content.images) == 3

    def test_handles_missing_images(
        self, tmp_path: Path, sample_video: Video, sample_captions: list[Caption]
    ) -> None:
        # No images created

        content = ExtractedContent.from_processing(
            sample_video, sample_captions, tmp_path
        )

        assert content.images == []
        assert len(content.captions) == 3


class TestExtractedContentSerialization:
    def test_to_json_produces_valid_json(
        self, tmp_path: Path, sample_video: Video, sample_captions: list[Caption]
    ) -> None:
        _create_test_images(tmp_path)
        content = ExtractedContent.from_processing(
            sample_video, sample_captions, tmp_path
        )

        json_str = content.to_json()
        parsed = json.loads(json_str)

        assert parsed["schema_version"] == CONTENT_SCHEMA_VERSION
        assert parsed["video_url"] == sample_video.url
        assert parsed["video_title"] == sample_video.title
        assert len(parsed["captions"]) == 3
        assert len(parsed["images"]) == 3

    def test_save_and_load_roundtrip(
        self, tmp_path: Path, sample_video: Video, sample_captions: list[Caption]
    ) -> None:
        # Create images in a subdirectory
        img_dir = tmp_path / "images"
        img_dir.mkdir()
        _create_test_images(img_dir)

        content = ExtractedContent.from_processing(
            sample_video, sample_captions, img_dir
        )

        # Save to file
        json_path = tmp_path / "content.json"
        content.save(json_path)
        assert json_path.exists()

        # Load from file
        loaded = ExtractedContent.load(json_path)

        assert loaded.schema_version == content.schema_version
        assert loaded.video_url == content.video_url
        assert loaded.video_title == content.video_title
        assert loaded.video_id == content.video_id
        assert loaded.captions == content.captions
        assert len(loaded.images) == len(content.images)
        for orig, loaded_img in zip(content.images, loaded.images):
            assert orig["index"] == loaded_img["index"]
            assert orig["data_base64"] == loaded_img["data_base64"]

    def test_load_rejects_unsupported_schema_version(self, tmp_path: Path) -> None:
        json_path = tmp_path / "future_content.json"
        json_path.write_text(
            json.dumps(
                {
                    "schema_version": CONTENT_SCHEMA_VERSION + 1,
                    "video_url": "http://test",
                    "video_title": "Test",
                    "video_id": "test",
                    "captions": [],
                    "images": [],
                    "seconds_per_shot": 30,
                }
            )
        )

        with pytest.raises(ValueError, match="Unsupported schema version"):
            ExtractedContent.load(json_path)


class TestExtractedContentHelpers:
    def test_get_video_reconstructs_video_object(
        self, tmp_path: Path, sample_video: Video, sample_captions: list[Caption]
    ) -> None:
        _create_test_images(tmp_path)
        content = ExtractedContent.from_processing(
            sample_video, sample_captions, tmp_path
        )

        video = content.get_video()

        assert video.url == sample_video.url
        assert video.title == sample_video.title
        assert video.video_id == sample_video.video_id

    def test_get_captions_reconstructs_caption_objects(
        self, tmp_path: Path, sample_video: Video, sample_captions: list[Caption]
    ) -> None:
        _create_test_images(tmp_path)
        content = ExtractedContent.from_processing(
            sample_video, sample_captions, tmp_path
        )

        captions = content.get_captions()

        assert len(captions) == len(sample_captions)
        for orig, loaded in zip(sample_captions, captions):
            assert orig.start == loaded.start
            assert orig.end == loaded.end
            assert orig.text == loaded.text

    def test_get_image_data_returns_decoded_bytes(
        self, tmp_path: Path, sample_video: Video, sample_captions: list[Caption]
    ) -> None:
        _create_test_images(tmp_path, count=1)
        content = ExtractedContent.from_processing(
            sample_video, sample_captions, tmp_path
        )

        data = content.get_image_data(0)

        assert data is not None
        assert len(data) > 0
        # Verify it's valid JPEG by checking magic bytes
        assert data[:2] == b"\xff\xd8"

    def test_get_image_data_returns_none_for_missing(
        self, tmp_path: Path, sample_video: Video, sample_captions: list[Caption]
    ) -> None:
        _create_test_images(tmp_path, count=1)
        content = ExtractedContent.from_processing(
            sample_video, sample_captions, tmp_path
        )

        data = content.get_image_data(999)

        assert data is None

    def test_get_image_indices_returns_sorted_list(
        self, tmp_path: Path, sample_video: Video, sample_captions: list[Caption]
    ) -> None:
        _create_test_images(tmp_path, count=3)
        content = ExtractedContent.from_processing(
            sample_video, sample_captions, tmp_path
        )

        indices = content.get_image_indices()

        assert indices == [0, 1, 2]
