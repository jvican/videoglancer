from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import imagehash
from PIL import Image


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
    unique_hashes: list[imagehash.ImageHash] = []

    for path in sorted(image_paths):
        shot_index = _shot_index(path.name)
        if shot_index is None:
            continue
        try:
            shot_hash = _phash(path, cfg.hash_size)
        except OSError:
            # Ignore images Pillow cannot handle; we leave the slide as non-duplicate.
            continue

        if _is_duplicate(shot_hash, unique_hashes, cfg.threshold):
            duplicates.add(shot_index)
        else:
            unique_hashes.append(shot_hash)

    return duplicates


def _is_duplicate(
    candidate: imagehash.ImageHash,
    unique_hashes: Sequence[imagehash.ImageHash],
    threshold: int,
) -> bool:
    return any((candidate - existing) <= threshold for existing in unique_hashes)


def _shot_index(filename: str) -> int | None:
    stem = filename.removesuffix(".jpg")
    if not stem.startswith("glancer-img"):
        return None
    try:
        number = int(stem.replace("glancer-img", ""))
    except ValueError:
        return None
    return number


def _phash(path: Path, hash_size: int) -> imagehash.ImageHash:
    """Compute a difference hash for the given image."""
    with Image.open(path) as image:
        return imagehash.dhash(image, hash_size=hash_size)
