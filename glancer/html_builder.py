from __future__ import annotations

from jinja2 import Environment, FileSystemLoader
from .process import Video


def embody(video: Video, body: str) -> str:
    env = Environment(loader=FileSystemLoader("glancer/templates"))
    template = env.get_template("template.html")
    return template.render(video=video, slides_html=body)
