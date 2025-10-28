from __future__ import annotations

import textwrap

from glancer.parser import parse_vtt
from glancer.captions import (
    captions_per_slide,
    deduplicate_slides,
    normalize_caption_text,
)


SAMPLE_VTT = textwrap.dedent(
    """\
    WEBVTT
    Kind: captions
    Language: en

    00:00:00.000 --> 00:00:00.180
    Practical Deep Learning for Coders, Lesson 6

    00:00:00.180 --> 00:00:06.840
    OK, so welcome back to lesson 6… not welcome&nbsp;
    back to, welcome to lesson 6 — first time we've&nbsp;&nbsp;

    00:00:06.840 --> 00:00:15.780
    been in lesson 6! Welcome back to Practical Deep&nbsp;
    Learning for Coders. We just started looking at&nbsp;&nbsp;

    00:00:16.680 --> 00:00:27.180
    tabular data last time, and for those of&nbsp;
    you who've forgotten what we did was: We&nbsp;&nbsp;

    00:00:28.860 --> 00:00:36.780
    were looking at the Titanic data set and&nbsp;
    we were looking at creating binary splits&nbsp;&nbsp;

    00:00:37.500 --> 00:00:46.320
    by looking at categorical variables&nbsp;
    or binary variables like sex and&nbsp;&nbsp;

    00:00:47.820 --> 00:00:52.020
    continuous variables, like the&nbsp;
    log of the fare that they paid,&nbsp;&nbsp;

    00:00:53.400 --> 00:01:02.700
    and using those. You know, we also kind of&nbsp;
    came up with a score which was basically: How&nbsp;&nbsp;

    00:01:04.200 --> 00:01:10.620
    good a job did that split do of grouping the&nbsp;
    survival characteristics into two groups,&nbsp;&nbsp;

    00:01:10.620 --> 00:01:14.040
    you know, all of, nearly all of one of&nbsp;
    whom survived, nearly all of whom the&nbsp;&nbsp;

    00:01:14.040 --> 00:01:17.400
    other didn't survive so they had like&nbsp;
    small standard deviation in each group.

    00:01:20.100 --> 00:01:23.940
    And so then we created the world's simplest&nbsp;
    little UI to allow us to fiddle around and&nbsp;&nbsp;

    00:01:23.940 --> 00:01:33.900
    try to find a good binary split. And we did…&nbsp;
    we did come up with a very good binary split,&nbsp;&nbsp;
    """
).strip()


EXPECTED_FIRST_SLIDE_TEXT = (
    "Practical Deep Learning for Coders, Lesson 6 OK, so welcome back to "
    "lesson 6… not welcome back to, welcome to lesson 6 — first time we've "
    "been in lesson 6! Welcome back to Practical Deep Learning for Coders. "
    "We just started looking at tabular data last time, and for those of you "
    "who've forgotten what we did was: We were looking at the Titanic data "
    "set and we were looking at creating binary splits"
)


def test_first_slide_contains_full_caption_sequence() -> None:
    captions = parse_vtt(SAMPLE_VTT)
    slides = captions_per_slide(captions)

    assert slides, "Expected at least one slide of captions"

    first_slide_combined = " ".join(
        normalize_caption_text(caption.text) for caption in slides[0]
    )
    assert first_slide_combined.startswith("Practical Deep Learning")
    assert EXPECTED_FIRST_SLIDE_TEXT in first_slide_combined


def test_deduplicate_slides_removes_repeated_lines_across_windows() -> None:
    captions = parse_vtt(SAMPLE_VTT)
    slides = captions_per_slide(captions)
    deduped = deduplicate_slides(slides)

    flat_texts = [caption.text for slide in deduped for caption in slide]
    assert len(flat_texts) == len(set(flat_texts)), "Expected all captions to be unique"

    # First slide should contain intro text
    assert deduped[0]
    first_slide_text = " ".join(
        normalize_caption_text(caption.text) for caption in deduped[0]
    )
    assert first_slide_text.startswith("Practical Deep Learning")

    # Second slide should not repeat the intro
    assert deduped[1]
    second_slide_text = " ".join(
        normalize_caption_text(caption.text) for caption in deduped[1]
    )
    assert not second_slide_text.startswith("Practical Deep Learning")
