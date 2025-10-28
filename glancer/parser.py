from __future__ import annotations

from dataclasses import dataclass
from typing import List

import srt


@dataclass(frozen=True)
class Caption:
    start: float
    end: float
    text: str


def parse_srt(contents: str) -> List[Caption]:
    parsed = srt.parse(contents)
    captions: List[Caption] = []
    for subtitle in parsed:
        text = subtitle.content.replace("\r\n", "\n").replace("\r", "\n")
        captions.append(
            Caption(
                start=subtitle.start.total_seconds(),
                end=subtitle.end.total_seconds(),
                text=text,
            )
        )
    return captions
