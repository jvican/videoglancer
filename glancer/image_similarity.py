from __future__ import annotations

import base64
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from PIL import Image, ImageOps


@dataclass(frozen=True)
class ShotSimilarityConfig:
    hash_size: int = 8
    threshold: int = 5


def find_similar_shots(
    image_paths: Iterable[Path],
    config: ShotSimilarityConfig | None = None,
) -> set[int]:
    """Return the zero-based shot indexes whose imagery matches earlier shots."""
    cfg = config or ShotSimilarityConfig()
    duplicates: set[int] = set()
    unique_hashes: list[int] = []

    for path in sorted(image_paths):
        shot_index = _shot_index(path.name)
        if shot_index is None:
            continue
        try:
            shot_hash = _dhash(path, cfg.hash_size)
        except OSError:
            # Ignore images Pillow cannot handle; we leave the slide as non-duplicate.
            continue

        if _is_duplicate(shot_hash, unique_hashes, cfg.threshold):
            duplicates.add(shot_index)
        else:
            unique_hashes.append(shot_hash)

    return duplicates


def _is_duplicate(candidate: int, unique_hashes: Sequence[int], threshold: int) -> bool:
    return any(
        _hamming_distance(candidate, existing) <= threshold
        for existing in unique_hashes
    )


def _shot_index(filename: str) -> int | None:
    stem = filename.removesuffix(".jpg")
    if not stem.startswith("glancer-img"):
        return None
    try:
        number = int(stem.replace("glancer-img", ""))
    except ValueError:
        return None
    return number


def _dhash(path: Path, hash_size: int) -> int:
    """Compute a perceptual difference hash for the given image."""
    with Image.open(path) as image:
        grayscale = ImageOps.grayscale(image)
        resized = grayscale.resize(
            (hash_size + 1, hash_size),
            getattr(Image.Resampling, "LANCZOS", Image.LANCZOS),
        )
        pixels = list(resized.getdata())

    bits = []
    row_stride = hash_size + 1
    for row in range(hash_size):
        offset = row * row_stride
        row_pixels = pixels[offset : offset + row_stride]
        for col in range(hash_size):
            left = row_pixels[col]
            right = row_pixels[col + 1]
            bits.append(1 if left < right else 0)

    result = 0
    for bit_index, bit in enumerate(bits):
        if bit:
            result |= 1 << bit_index
    return result


def _hamming_distance(left: int, right: int) -> int:
    return (left ^ right).bit_count()


def find_similar_shots_from_data(
    image_data: dict[int, str],
    config: ShotSimilarityConfig | None = None,
) -> set[int]:
    """Return shot indexes whose imagery matches earlier shots, using base64 data.

    This function works with pre-extracted image data from JSON, avoiding
    the need to read images from disk.

    Args:
        image_data: Dict mapping shot index to base64-encoded JPEG data
        config: Similarity detection configuration

    Returns:
        Set of shot indices that are duplicates of earlier shots
    """
    cfg = config or ShotSimilarityConfig()
    duplicates: set[int] = set()
    unique_hashes: list[int] = []

    for shot_index in sorted(image_data.keys()):
        try:
            shot_hash = _dhash_from_data(image_data[shot_index], cfg.hash_size)
        except OSError:
            # Ignore images Pillow cannot handle; we leave the slide as non-duplicate.
            continue

        if _is_duplicate(shot_hash, unique_hashes, cfg.threshold):
            duplicates.add(shot_index)
        else:
            unique_hashes.append(shot_hash)

    return duplicates


def _dhash_from_data(data_base64: str, hash_size: int) -> int:
    """Compute a perceptual difference hash from base64-encoded image data."""
    image_bytes = base64.b64decode(data_base64)
    with Image.open(io.BytesIO(image_bytes)) as image:
        grayscale = ImageOps.grayscale(image)
        resized = grayscale.resize(
            (hash_size + 1, hash_size),
            getattr(Image.Resampling, "LANCZOS", Image.LANCZOS),
        )
        pixels = list(resized.getdata())

    bits = []
    row_stride = hash_size + 1
    for row in range(hash_size):
        offset = row * row_stride
        row_pixels = pixels[offset : offset + row_stride]
        for col in range(hash_size):
            left = row_pixels[col]
            right = row_pixels[col + 1]
            bits.append(1 if left < right else 0)

    result = 0
    for bit_index, bit in enumerate(bits):
        if bit:
            result |= 1 << bit_index
    return result
