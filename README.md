# Videoglancer :movie: :detective:

Videoglancer is a tool to convert videos to slides of screenshots with
transcripts on the side to quickly glance through a video! Supports yt-dlp
videos and outputs standalone html documents that are easy to distribute.

Unlike fully watching a video, videoglancer creates a distributable document to
quickly process the video images, read the transcription, look for search terms,
and speed-watch videos for exactly the content you want. It's extremely handy
for studying purposes (recalling contents of a video, searching for a memorable
sentence) and it's a time-saver for all mortals.

## Usage

```bash
glancer URL [DESTINATION] [OPTIONS]
```

**Arguments:**
- `URL`: YouTube URL or playlist URL to process
- `DESTINATION` (optional): Output HTML file or directory
  - If omitted, uses current directory with video title as filename
  - For playlists, specify a directory to save all videos

**Options:**
- `--verbose`: Show detailed ffmpeg logs during processing
- `--auto-cleanup`: Delete cached video files after HTML generation
- `--no-detect-duplicates`: Disable duplicate slide detection (enabled by default)

**Examples:**
```bash
# Basic usage - saves to current directory with video title
glancer https://youtube.com/watch?v=VIDEO_ID

# Specify output file
glancer https://youtube.com/watch?v=VIDEO_ID output.html

# Verbose output with cleanup
glancer https://youtube.com/watch?v=VIDEO_ID --verbose --auto-cleanup

# Disable duplicate slide detection
glancer https://youtube.com/watch?v=VIDEO_ID --no-detect-duplicates

# Process entire playlist to directory
glancer https://youtube.com/playlist?list=PLAYLIST_ID videos/
```

## Requirements

The Python port requires the following executables on your `$PATH`:

- `yt-dlp` - Downloads video and English subtitles (SRT format)
- `ffmpeg` - Extracts JPEG frames every 30 seconds

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
glancer URL [DESTINATION] [OPTIONS]
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
glancer URL [DESTINATION]
```

Or directly with Python:

```bash
python -m glancer.cli URL [DESTINATION]
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

## Acknowledgements

The main idea for this tool has been borrowed from the original
[glancer](https://github.com/rberenguel/glancer) tool. Nonetheless, it's been
rewritten in Python, improved with tests and bugfixes, and has yt-dlp playlist
support so you can glance all videos in a playlist.
