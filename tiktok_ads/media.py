"""Turn a downloaded ad video into AI-readable inputs.

Keyframes (via ffmpeg) let Claude see the creative, including burned-in
on-screen text. A spoken transcript (via the optional faster-whisper package)
captures the voiceover. Transcription degrades to None when faster-whisper is
not installed, so the pipeline keeps working on frames alone.
"""

import shutil
import subprocess
from pathlib import Path


def has_ffmpeg():
    """True when ffmpeg is available on PATH."""
    return shutil.which("ffmpeg") is not None


def video_duration(video_path):
    """Return the video duration in seconds, or 0.0 if it cannot be read."""
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(video_path)],
        capture_output=True, text=True,
    )
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 0.0


def extract_keyframes(video_path, frames_dir, fractions=(0.05, 0.25, 0.5, 0.75, 0.95)):
    """Extract one frame at each fraction of the duration. Returns file paths."""
    out_dir = Path(frames_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    duration = video_duration(video_path)
    paths = []
    for index, fraction in enumerate(fractions):
        timestamp = duration * fraction if duration else float(index)
        dest = out_dir / f"frame_{index:02d}.jpg"
        subprocess.run(
            ["ffmpeg", "-y", "-ss", str(timestamp), "-i", str(video_path),
             "-frames:v", "1", "-q:v", "3", str(dest)],
            capture_output=True,
        )
        if dest.exists() and dest.stat().st_size > 0:
            paths.append(str(dest))
    return paths


def transcribe(video_path, transcript_path):
    """Transcribe audio with faster-whisper. None when it is not installed."""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return None
    model = WhisperModel("base", device="cpu", compute_type="int8")
    segments, _ = model.transcribe(str(video_path))
    text = " ".join(segment.text.strip() for segment in segments).strip()
    dest = Path(transcript_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")
    return text


def process_video(video_path, frames_dir, transcript_path):
    """Extract keyframes and (when available) a transcript for one video."""
    frames = extract_keyframes(video_path, frames_dir) if has_ffmpeg() else []
    transcript = transcribe(video_path, transcript_path)
    return {"frames": frames, "transcript": transcript}
