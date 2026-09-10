from pathlib import Path

from vka.frames import ffmpeg_frame_command, plan_candidate_timestamps


def test_candidate_plan_covers_interval_and_endpoints() -> None:
    assert plan_candidate_timestamps(10_000, 16_000, 2_000) == [
        10_000,
        12_000,
        14_000,
        16_000,
    ]


def test_candidate_plan_keeps_a_single_zero_width_point() -> None:
    assert plan_candidate_timestamps(8_000, 8_000, 2_000) == [8_000]


def test_ffmpeg_frame_command_extracts_single_candidate_frame() -> None:
    assert ffmpeg_frame_command(Path("video.mp4"), 12_345, Path("frame.jpg")) == [
        "ffmpeg",
        "-y",
        "-ss",
        "12.345",
        "-i",
        "video.mp4",
        "-frames:v",
        "1",
        "frame.jpg",
    ]
