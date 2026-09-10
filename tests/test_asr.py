import json
from pathlib import Path

import pytest

from vka.asr import build_srt, transcribe_to_srt
from vka_cli import main


class _Segment:
    def __init__(self, start: float, end: float, text: str) -> None:
        self.start = start
        self.end = end
        self.text = text


def test_build_srt_numbers_segments_and_formats_timestamps() -> None:
    srt, count = build_srt(
        [
            _Segment(0.0, 2.5, " 第一句 "),
            _Segment(2.5, 64.04, "第二句"),
        ]
    )

    assert count == 2
    assert "1\n00:00:00,000 --> 00:00:02,500\n第一句" in srt
    assert "2\n00:00:02,500 --> 00:01:04,040\n第二句" in srt


def test_build_srt_skips_empty_segments_and_rejects_empty_output() -> None:
    srt, count = build_srt([_Segment(0.0, 1.0, "  "), _Segment(1.0, 2.0, "有效")])

    assert count == 1
    assert "有效" in srt
    with pytest.raises(ValueError, match="no usable segments"):
        build_srt([_Segment(0.0, 1.0, "   ")])


def test_build_srt_rejects_invalid_timestamps() -> None:
    with pytest.raises(ValueError, match="non-negative numbers"):
        build_srt([{"start": -1.0, "end": 2.0, "text": "x"}])


def test_transcribe_rejects_a_missing_audio_file(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="audio file does not exist"):
        transcribe_to_srt(tmp_path / "missing.wav", tmp_path / "out.srt")


def test_cli_transcribe_asr_reports_failure_without_a_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = main(
        [
            "transcribe-asr",
            "--audio",
            str(tmp_path / "missing.wav"),
            "--output",
            str(tmp_path / "out.srt"),
        ]
    )

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "transcription failed" in captured.err
    assert "Traceback" not in captured.err
    assert not (tmp_path / "out.srt").exists()


def test_transcribe_writes_srt_through_the_injected_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"fake")
    captured: dict[str, object] = {}

    class _Info:
        language = "zh"
        duration = 3.0

    class _Model:
        def __init__(self, name: str, **options: object) -> None:
            captured["name"] = name
            captured["options"] = options

        def transcribe(self, path: str, **options: object):
            captured["path"] = path
            captured["transcribe_options"] = options
            return [_Segment(0.0, 3.0, "转录结果")], _Info()

    fake_module = type("faster_whisper", (), {"WhisperModel": _Model})
    monkeypatch.setitem(__import__("sys").modules, "faster_whisper", fake_module)

    report = transcribe_to_srt(
        audio,
        tmp_path / "audio-faster-base.srt",
        download_root=tmp_path / "cache",
    )

    assert report["model"] == "base"
    assert report["compute_type"] == "int8"
    assert report["segments"] == 1
    assert captured["transcribe_options"]["language"] == "zh"
    assert captured["transcribe_options"]["beam_size"] == 1
    assert captured["options"]["download_root"] == str(tmp_path / "cache")
    assert "转录结果" in (tmp_path / "audio-faster-base.srt").read_text(encoding="utf-8")
    assert json.loads(json.dumps(report))["backend"] == "faster-whisper"
