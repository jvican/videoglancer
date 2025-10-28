from __future__ import annotations

import logging
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from .process import Video

logger = logging.getLogger(__name__)


def embody(video: Video, body: str) -> str:
    template_dir = Path(__file__).parent / "templates"
    env = Environment(loader=FileSystemLoader(str(template_dir)))
    template = env.get_template("template.html")
    return template.render(video=video, slides_html=body)
