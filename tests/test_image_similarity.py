from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from glancer.image_similarity import ShotSimilarityConfig, find_similar_shots


def _write_image(
    path: Path, color: tuple[int, int, int], variant: str | None = None
) -> None:
    image = Image.new("RGB", (128, 128), color=color)
    draw = ImageDraw.Draw(image)
    if variant == "horizontal":
        draw.rectangle(
            (0, 60, 127, 68), fill=(color[0] // 2, color[1] // 2, color[2] // 2)
        )
    elif variant == "vertical":
        draw.rectangle(
            (60, 0, 68, 127), fill=(color[0] // 2, color[1] // 2, color[2] // 2)
        )
    elif variant == "diagonal":
        for offset in range(-10, 11):
            draw.line(
                (0, 64 + offset, 127, 64 - offset),
                fill=(color[0] // 3, color[1] // 3, color[2] // 3),
                width=3,
            )
    image.save(path, format="JPEG")


def test_find_similar_shots_marks_second_identical_frame(tmp_path) -> None:
    first = tmp_path / "glancer-img0000.jpg"
    duplicate = tmp_path / "glancer-img0001.jpg"
    third = tmp_path / "glancer-img0002.jpg"

    _write_image(first, (200, 200, 200), variant="horizontal")
    _write_image(duplicate, (200, 200, 200), variant="horizontal")
    _write_image(third, (120, 80, 200), variant="diagonal")

    duplicates = find_similar_shots(tmp_path.glob("glancer-img*.jpg"))

    assert 1 in duplicates
    assert 0 not in duplicates
    assert 2 not in duplicates


def test_find_similar_shots_detects_near_duplicates(tmp_path) -> None:
    base = tmp_path / "glancer-img0000.jpg"
    near_duplicate = tmp_path / "glancer-img0001.jpg"
    distinct = tmp_path / "glancer-img0002.jpg"

    _write_image(base, (30, 60, 90), variant="horizontal")
    _write_image(distinct, (200, 10, 10), variant="vertical")

    # Create a near duplicate by drawing tiny noise on top of the base image
    with Image.open(base) as original:
        modified = original.copy()
    draw = ImageDraw.Draw(modified)
    draw.rectangle((0, 0, 4, 4), fill=(28, 58, 88))
    modified.save(near_duplicate, format="JPEG")
    modified.close()

    duplicates = find_similar_shots(
        tmp_path.glob("glancer-img*.jpg"),
        ShotSimilarityConfig(hash_size=8, threshold=6),
    )

    assert 1 in duplicates
    assert 2 not in duplicates
