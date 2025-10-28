from __future__ import annotations

from dataclasses import dataclass
from io import StringIO
from typing import List

import webvtt


@dataclass(frozen=True)
class Caption:
    start: float
    end: float
    text: str


def _to_seconds(timestamp: str) -> float:
    hours, minutes, rest = timestamp.split(":")
    seconds, milliseconds = rest.split(".")
    return (
        int(hours) * 3600
        + int(minutes) * 60
        + int(seconds)
        + int(milliseconds) / 1000.0
    )


def parse_vtt(contents: str) -> List[Caption]:
    buffer = StringIO(contents)
    parsed = webvtt.read_buffer(buffer)
    captions: List[Caption] = []
    for raw in parsed:
        text = raw.text.replace("\r\n", "\n").replace("\r", "\n")
        captions.append(
            Caption(
                start=_to_seconds(raw.start),
                end=_to_seconds(raw.end),
                text=text,
            )
        )
    return captions
