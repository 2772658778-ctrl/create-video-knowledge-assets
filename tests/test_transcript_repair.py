import json

import pytest

from vka.transcript_repair import (
    apply_reviewed_transcript,
    build_asr_review_prompt,
    parse_reviewed_transcript,
)
from vka_cli import main


ROWS = [
    {
        "evidence_id": "raw-tr-000001",
        "origin": "video",
        "modality": "transcript",
        "spans": [{"start_ms": 10_000, "end_ms": 14_000}],
        "content": "但是你肯定听说过Chad GPT",
        "acquisition": "asr",
        "schema_version": "1.0",
    },
    {
        "evidence_id": "raw-tr-000002",
        "origin": "video",
        "modality": "transcript",
        "spans": [{"start_ms": 14_000, "end_ms": 18_000}],
        "content": "只知道一个公式Q乘以K的转制，送进sulfmax会导致t度消失",
        "acquisition": "asr",
        "schema_version": "1.0",
    },
    {
        "evidence_id": "raw-tr-000003",
        "origin": "video",
        "modality": "transcript",
        "spans": [{"start_ms": 18_000, "end_ms": 20_000}],
        "content": "聽不清的一句",
        "acquisition": "asr",
        "schema_version": "1.0",
    },
]


def test_review_prompt_numbers_rows_without_timestamps_or_json() -> None:
    prompt = build_asr_review_prompt(ROWS, title="注意力机制")

    assert "视频标题：注意力机制" in prompt
    assert "1|但是你肯定听说过Chad GPT" in prompt
    assert "2|只知道一个公式Q乘以K的转制，送进sulfmax会导致t度消失" in prompt
    assert "00:00:10" not in prompt
    assert "evidence_id" not in prompt


def test_review_prompt_rejects_an_empty_timeline() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        build_asr_review_prompt([])


def test_parse_reviewed_transcript_reads_text_comments_and_uncertainty() -> None:
    reviewed = parse_reviewed_transcript(
        """
        # 审校结果
        1|但是你肯定听说过ChatGPT

        3|?
        """
    )

    assert reviewed == {1: "但是你肯定听说过ChatGPT", 3: None}


@pytest.mark.parametrize(
    "text",
    ["1 没有分隔符", "1|", "0|文本", "1|a\n1|b", "no rows here"],
)
def test_parse_reviewed_transcript_rejects_malformed_sheets(text: str) -> None:
    with pytest.raises(ValueError):
        parse_reviewed_transcript(text)


def test_reviewed_rows_are_labeled_repaired_preserved_or_unreviewed() -> None:
    reviewed = parse_reviewed_transcript("1|但是你肯定听说过ChatGPT\n3|?")

    rows = apply_reviewed_transcript(ROWS, reviewed, parent_prefix="raw-")

    assert [row["evidence_id"] for row in rows] == ["tr-000001", "tr-000002", "tr-000003"]
    assert [row["parent_ids"] for row in rows] == [
        ["raw-tr-000001"],
        ["raw-tr-000002"],
        ["raw-tr-000003"],
    ]
    assert rows[0]["content"] == "但是你肯定听说过ChatGPT"
    assert rows[0]["original_content"] == "但是你肯定听说过Chad GPT"
    assert rows[0]["quality"]["repair_status"] == "repaired"
    assert rows[1]["quality"]["repair_status"] == "unreviewed"
    assert "original_content" not in rows[1]
    assert rows[2]["quality"] == {"repair_status": "raw_preserved", "uncertain": "true"}
    assert rows[2]["content"] == "聽不清的一句"


def test_a_row_the_reviewer_left_unchanged_is_raw_preserved() -> None:
    rows = apply_reviewed_transcript(ROWS, {2: ROWS[1]["content"]})

    assert rows[1]["quality"] == {"repair_status": "raw_preserved"}
    assert "original_content" not in rows[1]


def test_apply_rejects_a_sheet_row_beyond_the_timeline() -> None:
    with pytest.raises(ValueError, match="references row 9"):
        apply_reviewed_transcript(ROWS, {9: "文本"})


def test_apply_rejects_ids_without_the_parent_prefix() -> None:
    unprefixed = [{**ROWS[0], "evidence_id": "tr-000001"}]

    with pytest.raises(ValueError, match="does not start with parent prefix"):
        apply_reviewed_transcript(unprefixed, {1: "文本"}, parent_prefix="raw-")


def test_cli_review_roundtrip(tmp_path, capsys) -> None:
    timeline = tmp_path / "timeline.raw.jsonl"
    prompt_path = tmp_path / "review-prompt.md"
    reviewed = tmp_path / "reviewed.txt"
    output = tmp_path / "timeline.jsonl"
    timeline.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in ROWS),
        encoding="utf-8",
    )

    assert (
        main(
            [
                "build-repair-prompt",
                "--timeline",
                str(timeline),
                "--output",
                str(prompt_path),
                "--title",
                "注意力机制",
            ]
        )
        == 0
    )
    assert "1|但是你肯定听说过Chad GPT" in prompt_path.read_text(encoding="utf-8")

    reviewed.write_text("1|但是你肯定听说过ChatGPT\n3|?\n", encoding="utf-8")
    assert (
        main(
            [
                "apply-reviewed-transcript",
                "--timeline",
                str(timeline),
                "--reviewed",
                str(reviewed),
                "--parent-prefix",
                "raw-",
                "--output",
                str(output),
            ]
        )
        == 0
    )

    assert "Traceback" not in capsys.readouterr().err
    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["content"] == "但是你肯定听说过ChatGPT"
    assert rows[0]["evidence_id"] == "tr-000001"


def test_cli_reports_a_malformed_sheet_without_a_traceback(tmp_path, capsys) -> None:
    timeline = tmp_path / "timeline.raw.jsonl"
    reviewed = tmp_path / "reviewed.txt"
    timeline.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in ROWS),
        encoding="utf-8",
    )
    reviewed.write_text("这不是一个合法的审校文件\n", encoding="utf-8")

    exit_code = main(
        [
            "apply-reviewed-transcript",
            "--timeline",
            str(timeline),
            "--reviewed",
            str(reviewed),
            "--output",
            str(tmp_path / "out.jsonl"),
        ]
    )

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "failed to apply the reviewed transcript" in captured.err
    assert "Traceback" not in captured.err
