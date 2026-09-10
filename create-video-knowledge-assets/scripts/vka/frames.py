from __future__ import annotations

from pathlib import Path


def plan_candidate_timestamps(start_ms: int, end_ms: int, interval_ms: int) -> list[int]:
    if interval_ms <= 0:
        raise ValueError("interval_ms must be positive")
    if end_ms <= start_ms:
        return [start_ms]
    timestamps = list(range(start_ms, end_ms, interval_ms))
    if timestamps[-1] != end_ms:
        timestamps.append(end_ms)
    return timestamps


def ffmpeg_frame_command(video: Path, timestamp_ms: int, output: Path) -> list[str]:
    return [
        "ffmpeg",
        "-y",
        "-ss",
        f"{timestamp_ms / 1000:.3f}",
        "-i",
        str(video),
        "-frames:v",
        "1",
        str(output),
    ]
