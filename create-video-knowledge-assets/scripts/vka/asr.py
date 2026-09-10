"""Speech recognition that produces the SRT the rest of the pipeline consumes.

The pipeline's ASR of record is `faster-whisper` on CPU: it is the backend a
real run could actually finish, and its output is still a raw SRT that must go
through the repair workflow before it becomes canonical evidence.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any


DEFAULT_MODEL = "base"
DEFAULT_DEVICE = "cpu"
DEFAULT_COMPUTE_TYPE = "int8"
DEFAULT_LANGUAGE = "zh"
DEFAULT_CPU_THREADS = 4
DEFAULT_BEAM_SIZE = 1


def transcribe_to_srt(
    audio_path: Path | str,
    output_path: Path | str,
    *,
    model_name: str = DEFAULT_MODEL,
    device: str = DEFAULT_DEVICE,
    compute_type: str = DEFAULT_COMPUTE_TYPE,
    language: str = DEFAULT_LANGUAGE,
    cpu_threads: int = DEFAULT_CPU_THREADS,
    beam_size: int = DEFAULT_BEAM_SIZE,
    download_root: Path | str | None = None,
) -> dict[str, Any]:
    """Transcribe audio with faster-whisper and write a raw SRT."""
    audio = Path(audio_path)
    if not audio.is_file():
        raise ValueError(f"audio file does not exist: {audio}")
    if cpu_threads <= 0:
        raise ValueError("cpu_threads must be a positive integer")
    if beam_size <= 0:
        raise ValueError("beam_size must be a positive integer")

    try:
        from faster_whisper import WhisperModel  # noqa: PLC0415 - optional dependency
    except ImportError as exc:  # pragma: no cover - depends on the environment
        raise ValueError(
            "faster-whisper is not installed; install it in the workspace environment"
        ) from exc

    model = WhisperModel(
        model_name,
        device=device,
        compute_type=compute_type,
        cpu_threads=cpu_threads,
        download_root=str(download_root) if download_root else None,
    )
    segments, info = model.transcribe(
        str(audio),
        language=language,
        beam_size=beam_size,
        vad_filter=True,
        condition_on_previous_text=False,
    )
    srt_text, segment_count = build_srt(segments)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(srt_text, encoding="utf-8")
    return {
        "backend": "faster-whisper",
        "model": model_name,
        "device": device,
        "compute_type": compute_type,
        "language": getattr(info, "language", language),
        "duration_seconds": getattr(info, "duration", None),
        "segments": segment_count,
        "output": str(output),
    }


def build_srt(segments: Iterable[object]) -> tuple[str, int]:
    """Serialize faster-whisper segments into SRT text."""
    blocks: list[str] = []
    count = 0
    for segment in segments:
        text = str(_segment_value(segment, "text")).strip()
        if not text:
            continue
        count += 1
        start = _timestamp(_segment_value(segment, "start"))
        end = _timestamp(_segment_value(segment, "end"))
        blocks.append(f"{count}\n{start} --> {end}\n{text}\n")
    if not blocks:
        raise ValueError("transcription produced no usable segments")
    return "\n".join(blocks), count


def _segment_value(segment: object, field: str) -> Any:
    if isinstance(segment, Mapping):
        return segment.get(field)
    return getattr(segment, field, None)


def _timestamp(seconds: object) -> str:
    if not isinstance(seconds, (int, float)) or isinstance(seconds, bool) or seconds < 0:
        raise ValueError("segment timestamps must be non-negative numbers")
    total_milliseconds = round(float(seconds) * 1000)
    milliseconds = total_milliseconds % 1000
    total_seconds = total_milliseconds // 1000
    seconds_part = total_seconds % 60
    minutes = (total_seconds // 60) % 60
    hours = total_seconds // 3600
    return f"{hours:02d}:{minutes:02d}:{seconds_part:02d},{milliseconds:03d}"
