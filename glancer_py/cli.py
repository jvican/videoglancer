from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .captions import convert_to_html
from .parser import parse_vtt
from .process import Url, process_url


def _ensure_html_suffix(path: Path) -> Path:
    if path.suffix.lower() == ".html":
        return path
    return path.with_suffix(".html")


def run(url: str, destination: str) -> None:
    print(f"Looking for video in {url}", file=sys.stderr)
    dir_path, video, captions_path = process_url(Url(url))

    captions_text = captions_path.read_text(encoding="utf-8")
    parsed = parse_vtt(captions_text)
    html = convert_to_html(video, dir_path, parsed)

    destination_path = _ensure_html_suffix(Path(destination).expanduser())
    destination_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Writing html to {destination_path}", file=sys.stderr)
    destination_path.write_text(html, encoding="utf-8")
    print(f"Data written to {destination_path}", file=sys.stderr)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="glancer", description="Glancer")
    parser.add_argument("url", help="Youtube URL")
    parser.add_argument(
        "filepath",
        help="HTML file name (don't add extension)",
    )
    args = parser.parse_args(argv)
    run(args.url, args.filepath)


if __name__ == "__main__":  # pragma: no cover
    main()
