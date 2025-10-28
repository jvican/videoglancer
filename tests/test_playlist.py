from __future__ import annotations

from unittest.mock import MagicMock, patch

from glancer.playlist import Playlist


@patch("subprocess.run")
def test_playlist_iteration(mock_run: MagicMock) -> None:
    mock_run.return_value.stdout = "video1\nvideo2\nvideo3"
    playlist = Playlist("http://playlist.test")
    urls = list(playlist)
    assert urls == [
        "https://www.youtube.com/watch?v=video1",
        "https://www.youtube.com/watch?v=video2",
        "https://www.youtube.com/watch?v=video3",
    ]
    mock_run.assert_called_once_with(
        ["yt-dlp", "--flat-playlist", "-i", "--get-id", "http://playlist.test"],
        check=True,
        capture_output=True,
        text=True,
    )

def test_is_playlist() -> None:
    assert Playlist.is_playlist("https://www.youtube.com/playlist?list=123")
    assert not Playlist.is_playlist("https://www.youtube.com/watch?v=123")
