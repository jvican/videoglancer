"""Tests for glancer-render CLI."""
from __future__ import annotations

import base64
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image

from glancer.render import (
    _escape_typst,
    _format_time,
    render_html,
)
from glancer.schema import ExtractedContent, SlideData, VideoMeta


def _create_base64_jpeg() -> str:
    """Create a minimal base64-encoded JPEG."""
    from io import BytesIO

    img = Image.new("RGB", (64, 64), color=(100, 100, 100))
    buffer = BytesIO()
    img.save(buffer, format="JPEG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


class TestRenderHtml:
    def test_produces_valid_html(self) -> None:
        content = ExtractedContent(
            video=VideoMeta(url="http://example.com", title="Test Video", id="test"),
            slides=[
                SlideData(
                    index=0,
                    image_base64=_create_base64_jpeg(),
                    timestamp_seconds=0,
                    caption_text="First caption",
                    is_duplicate=False,
                ),
            ],
            seconds_per_shot=30,
        )

        html = render_html(content)

        assert "<!DOCTYPE html>" in html
        assert "Test Video" in html
        assert "First caption" in html
        assert "data:image/jpeg;base64" in html
        assert "slide-block" in html

    def test_marks_duplicates_with_class(self) -> None:
        content = ExtractedContent(
            video=VideoMeta(url="http://example.com", title="Test", id="test"),
            slides=[
                SlideData(
                    index=0,
                    image_base64=_create_base64_jpeg(),
                    timestamp_seconds=0,
                    caption_text="",
                    is_duplicate=True,
                ),
            ],
            seconds_per_shot=30,
        )

        html = render_html(content)

        assert "slide-block duplicate" in html


class TestFormatTime:
    def test_formats_seconds_only(self) -> None:
        assert _format_time(45) == "0:45"

    def test_formats_minutes_and_seconds(self) -> None:
        assert _format_time(125) == "2:05"

    def test_formats_hours(self) -> None:
        assert _format_time(3665) == "1:01:05"


class TestEscapeTypst:
    def test_escapes_special_chars(self) -> None:
        assert _escape_typst("#$*_<>@[]") == "\\#\\$\\*\\_\\<\\>\\@\\[\\]"

    def test_escapes_backslash(self) -> None:
        assert _escape_typst("\\") == "\\\\"

    def test_leaves_normal_text(self) -> None:
        assert _escape_typst("Hello world") == "Hello world"
