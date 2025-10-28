from __future__ import annotations

import html
from typing import List

from .process import Video


heading = """<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {
            font-family: Arial, sans-serif;
            background: #fdfdfd;
            color: #0a0a0a;
        }

        #container {
            padding: 2.5%;
            margin: auto;
            max-width: 1200px;
        }

        h1 {
            text-align: center;
            margin-bottom: 0;
        }

        h3 {
            float: right;
            font-size: 80%;
        }

        a {
            color: darkgreen;
            text-decoration: none;
        }

        a:hover {
            text-decoration: underline;
        }

        .slide-block {
            margin-top: 1%;
            border: 1px solid #222;
            border-radius: 4px;
            display: flex;
            gap: 2%;
            padding: 1.5%;
            background: #fff;
        }

        .img {
            flex: 2;
        }

        .img img {
            max-width: 100%;
            border-radius: 2px;
        }

        .txt {
            flex: 1;
            line-height: 1.5;
            font-size: 18px;
        }

        .to-video {
            font-size: 30px;
            align-self: flex-end;
            margin-left: auto;
        }
    </style>
</head>
"""


def embody(video: Video, body: str) -> str:
    url = html.escape(video.url.value, quote=True)
    title = html.escape(video.title.value)
    parts: List[str] = [
        "<body>",
        "\t<div id='container'>",
        f"\t\t<h1><a href='{url}'>{title}</a></h1>",
        "\t\t<h3>Created with <a href='https://github.com/rberenguel/glancer'>glancer</a></h3>",
        body,
        "\t</div>",
        "</body>",
        "</html>",
    ]
    return "\n".join(parts)
