# Python Glancer

This folder contains a Python reimplementation of the original [glancer](https://github.com/rberenguel/glancer) tool.
It exposes the same command line interface:

```
glancer URL FILEPATH
```

- `URL`: YouTube URL to fetch.
- `FILEPATH`: Base name for the generated HTML (omit the `.html` extension).

The Python port requires the following executables on your `$PATH`:

- `yt-dlp`
- `ffmpeg`

Both commands are used exactly like in the Haskell version: `yt-dlp` downloads
the video and English subtitles, while `ffmpeg` extracts frames every 30 seconds.

## Installation

Install using [uv](https://docs.astral.sh/uv/):

```bash
uv tool install git+https://github.com/jvican/videoglancer.git
```

Or clone and install locally:

```bash
git clone https://github.com/jvican/videoglancer.git
cd videoglancer
uv tool install .
```

After installation, the `glancer` command will be available globally:

```bash
glancer <URL> <FILEPATH>
```

## Development

For contributors who want to hack on the tool, install in editable mode:

```bash
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e .
```

With editable mode (`-e`), your code changes take effect immediately without reinstalling. You can run the tool as:

```bash
glancer <URL> <FILEPATH>
```

Or directly with Python:

```bash
python -m glancer_py.cli <URL> <FILEPATH>
```

Run tests with:

```bash
uv pip install -e ".[dev]"
pytest
```

---

The generated HTML mirrors the original layout. Each slide combines an embedded
base64 JPEG frame with the captions that overlap that 30-second window, and
links let you jump back to the corresponding point in YouTube.
