import pytest

from vka.models import Evidence
from vka.transcript import parse_srt_as_evidence, whisper_command
from vka_cli import main


SRT = """1
00:00:01,000 --> 00:00:03,500
First sentence.

2
00:00:03,500 --> 00:00:05,000
Second sentence."""


def test_srt_becomes_timestamped_evidence() -> None:
    rows = parse_srt_as_evidence(SRT, acquisition="asr")
    assert [row["evidence_id"] for row in rows] == ["tr-000001", "tr-000002"]
    assert rows[0]["spans"] == [{"start_ms": 1000, "end_ms": 3500}]
    assert rows[1]["content"] == "Second sentence."


@pytest.mark.parametrize(
    "bad_srt",
    [
        """1
00:00:01,000 --> 00:00:01,000
Zero width.""",
        """1
00:00:02,000 --> 00:00:01,000
Inverted.""",
    ],
)
def test_invalid_subtitle_time_span_raises_value_error(bad_srt: str) -> None:
    with pytest.raises(ValueError, match="end_ms must be greater than start_ms|invalid subtitle time span"):
        parse_srt_as_evidence(bad_srt, acquisition="asr")


def test_multiline_and_repeated_whitespace_is_collapsed() -> None:
    rows = parse_srt_as_evidence(
        """1
00:00:01,000 --> 00:00:02,000
Alpha   beta
Gamma\t delta.""",
        acquisition="cc",
    )

    assert rows[0]["content"] == "Alpha beta Gamma delta."


def test_empty_subtitles_are_skipped_and_evidence_ids_remain_contiguous() -> None:
    rows = parse_srt_as_evidence(
        """1
00:00:01,000 --> 00:00:02,000


2
00:00:02,000 --> 00:00:03,000
Visible one.

3
00:00:03,000 --> 00:00:04,000
Visible two.""",
        acquisition="asr",
    )

    assert [row["evidence_id"] for row in rows] == ["tr-000001", "tr-000002"]
    assert [row["content"] for row in rows] == ["Visible one.", "Visible two."]


def test_whisper_command_matches_expected_arguments() -> None:
    assert whisper_command("source.wav", "out", model="small") == [
        "whisper",
        "source.wav",
        "--model",
        "small",
        "--language",
        "zh",
        "--output_format",
        "srt",
        "--output_dir",
        "out",
    ]


def test_generated_row_matches_evidence_contract() -> None:
    rows = parse_srt_as_evidence(SRT, acquisition="asr")

    Evidence.model_validate(rows[0])


def test_normalize_srt_reports_malformed_srt_without_traceback(tmp_path, capsys) -> None:
    input_path = tmp_path / "bad.srt"
    output_path = tmp_path / "timeline.jsonl"
    input_path.write_text("1\nnot a timestamp\nText", encoding="utf-8")

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "normalize-srt",
                "--input",
                str(input_path),
                "--output",
                str(output_path),
                "--acquisition",
                "asr",
            ]
        )

    captured = capsys.readouterr()
    assert exc_info.value.code == 1
    assert "error:" in captured.err
    assert "Traceback" not in captured.err
    assert not output_path.exists()


def test_normalize_srt_reports_missing_input_without_traceback(tmp_path, capsys) -> None:
    output_path = tmp_path / "timeline.jsonl"

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "normalize-srt",
                "--input",
                str(tmp_path / "missing.srt"),
                "--output",
                str(output_path),
                "--acquisition",
                "asr",
            ]
        )

    captured = capsys.readouterr()
    assert exc_info.value.code == 1
    assert "error:" in captured.err
    assert "Traceback" not in captured.err
    assert not output_path.exists()
