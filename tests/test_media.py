import subprocess

import pytest

from tiktok_ads import media


@pytest.fixture
def sample_video(tmp_path):
    path = tmp_path / "sample.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i",
         "testsrc=duration=2:size=128x128:rate=10", str(path)],
        capture_output=True, check=True,
    )
    return path


def test_has_ffmpeg_true():
    assert media.has_ffmpeg() is True


def test_video_duration(sample_video):
    assert media.video_duration(sample_video) == pytest.approx(2.0, abs=0.3)


def test_extract_keyframes_writes_files(sample_video, tmp_path):
    frames = media.extract_keyframes(sample_video, tmp_path / "frames")
    assert len(frames) >= 3
    for f in frames:
        assert f.endswith(".jpg")


def test_transcribe_degrades_without_whisper(sample_video, tmp_path, monkeypatch):
    import builtins
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name.startswith("faster_whisper"):
            raise ImportError("simulated missing whisper")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert media.transcribe(sample_video, tmp_path / "t.txt") is None
