import json

import pytest

from vka.transcript_repair import (
    apply_transcript_repairs,
    build_asr_repair_prompt,
    load_glossary,
    suggest_asr_repairs,
    to_simplified,
)
from vka_cli import main


ROWS = [
    {
        "evidence_id": "tr-000001",
        "origin": "video",
        "modality": "transcript",
        "spans": [{"start_ms": 10_000, "end_ms": 14_000}],
        "content": "但是你肯定听说过Chad GPT",
        "acquisition": "asr",
        "schema_version": "1.0",
    },
    {
        "evidence_id": "tr-000002",
        "origin": "video",
        "modality": "transcript",
        "spans": [{"start_ms": 14_000, "end_ms": 18_000}],
        "content": "只知道一个公式Q乘以K的转制，送进sulfmax会导致t度消失",
        "acquisition": "asr",
        "schema_version": "1.0",
    },
]


def test_build_asr_repair_prompt_preserves_ids_and_output_contract() -> None:
    prompt = build_asr_repair_prompt(ROWS, title="注意力机制")

    assert "不要改写讲者原意" in prompt
    assert "evidence_id" in prompt
    assert "repaired_content" in prompt
    assert "tr-000001" in prompt
    assert "00:00:10--00:00:14" in prompt


def test_suggest_asr_repairs_catches_common_technical_errors() -> None:
    repairs = suggest_asr_repairs(ROWS)

    assert repairs[0]["repaired_content"] == "但是你肯定听说过ChatGPT"
    assert "转置" in repairs[1]["repaired_content"]
    assert "softmax" in repairs[1]["repaired_content"]
    assert "梯度消失" in repairs[1]["repaired_content"]


def test_apply_transcript_repairs_keeps_original_and_marks_quality() -> None:
    repairs = [
        {
            "evidence_id": "tr-000001",
            "original_content": "但是你肯定听说过Chad GPT",
            "repaired_content": "但是你肯定听说过 ChatGPT",
            "confidence": "high",
            "reason": "英文专名",
            "uncertain": False,
        }
    ]

    repaired_rows = apply_transcript_repairs(ROWS, repairs)

    assert repaired_rows[0]["content"] == "但是你肯定听说过 ChatGPT"
    assert repaired_rows[0]["original_content"] == "但是你肯定听说过Chad GPT"
    assert repaired_rows[0]["quality"]["repair_status"] == "repaired"
    assert repaired_rows[1]["content"] == "只知道一个公式Q乘以K的转制，送进sulfmax会导致t度消失"


def test_cli_repair_roundtrip(tmp_path, capsys) -> None:
    timeline = tmp_path / "timeline.jsonl"
    repairs = tmp_path / "repairs.json"
    output = tmp_path / "timeline.repaired.jsonl"
    timeline.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in ROWS),
        encoding="utf-8",
    )

    assert main(["suggest-repairs", "--timeline", str(timeline), "--output", str(repairs)]) == 0
    assert main(
        [
            "apply-transcript-repairs",
            "--timeline",
            str(timeline),
            "--repairs",
            str(repairs),
            "--output",
            str(output),
        ]
    ) == 0
    captured = capsys.readouterr()

    assert "Traceback" not in captured.err
    assert "ChatGPT" in output.read_text(encoding="utf-8")


def test_unrepaired_rows_record_that_they_were_preserved() -> None:
    repaired_rows = apply_transcript_repairs(
        ROWS,
        {"repairs": [], "reviewed_ids": ["tr-000001", "tr-000002"]},
    )

    assert [row["quality"]["repair_status"] for row in repaired_rows] == [
        "raw_preserved",
        "raw_preserved",
    ]
    assert all("uncertain" not in row["quality"] for row in repaired_rows)


def test_rows_nobody_reviewed_are_labeled_unreviewed() -> None:
    repaired_rows = apply_transcript_repairs(ROWS, {"repairs": [], "reviewed_ids": ["tr-000001"]})

    assert repaired_rows[0]["quality"]["repair_status"] == "raw_preserved"
    assert repaired_rows[1]["quality"]["repair_status"] == "unreviewed"


def test_uncertain_ids_imply_the_row_was_reviewed() -> None:
    repaired_rows = apply_transcript_repairs(
        ROWS,
        {"repairs": [], "uncertain_ids": ["tr-000002"]},
    )

    assert repaired_rows[1]["quality"]["repair_status"] == "raw_preserved"
    assert repaired_rows[1]["quality"]["uncertain"] == "true"


def test_assume_reviewed_marks_every_remaining_row_as_read() -> None:
    repaired_rows = apply_transcript_repairs(
        ROWS,
        {"repairs": [], "uncertain_ids": ["tr-000002"]},
        assume_reviewed=True,
    )

    assert [row["quality"]["repair_status"] for row in repaired_rows] == [
        "raw_preserved",
        "raw_preserved",
    ]
    assert repaired_rows[1]["quality"]["uncertain"] == "true"


def test_uncertain_ids_flag_rows_without_rewriting_them() -> None:
    repaired_rows = apply_transcript_repairs(
        ROWS,
        {"repairs": [], "uncertain_ids": ["tr-000002"]},
    )

    assert repaired_rows[0]["quality"]["repair_status"] == "unreviewed"
    assert "uncertain" not in repaired_rows[0]["quality"]
    assert repaired_rows[1]["quality"]["uncertain"] == "true"
    assert repaired_rows[1]["content"] == ROWS[1]["content"]


def test_parent_prefix_turns_raw_ids_into_explicit_provenance() -> None:
    raw_rows = [
        {**ROWS[0], "evidence_id": "raw-tr-000001"},
        {**ROWS[1], "evidence_id": "raw-tr-000002"},
    ]
    repairs = [
        {
            "evidence_id": "raw-tr-000001",
            "original_content": ROWS[0]["content"],
            "repaired_content": "但是你肯定听说过ChatGPT",
            "confidence": "high",
            "reason": "英文专名",
            "uncertain": False,
        }
    ]

    repaired_rows = apply_transcript_repairs(raw_rows, repairs, parent_prefix="raw-")

    assert [row["evidence_id"] for row in repaired_rows] == ["tr-000001", "tr-000002"]
    assert [row["parent_ids"] for row in repaired_rows] == [
        ["raw-tr-000001"],
        ["raw-tr-000002"],
    ]
    assert repaired_rows[0]["quality"]["repair_status"] == "repaired"


def test_parent_prefix_rejects_ids_without_the_prefix() -> None:
    with pytest.raises(ValueError, match="does not start with parent prefix"):
        apply_transcript_repairs(ROWS, [], parent_prefix="raw-")


def test_glossary_repairs_domain_proper_nouns() -> None:
    rows = [
        {
            "evidence_id": "tr-000001",
            "origin": "video",
            "modality": "transcript",
            "spans": [{"start_ms": 0, "end_ms": 2_000}],
            "content": "王老奇两查和加多保的黄耀集团之争",
            "acquisition": "asr",
        }
    ]

    repairs = suggest_asr_repairs(
        rows,
        glossary={"王老奇": "王老吉", "两查": "凉茶", "加多保": "加多宝", "黄耀": "广药"},
    )

    assert repairs[0]["repaired_content"] == "王老吉凉茶和加多宝的广药集团之争"


def test_glossary_prefers_the_longest_key() -> None:
    rows = [
        {
            "evidence_id": "tr-000001",
            "origin": "video",
            "modality": "transcript",
            "spans": [{"start_ms": 0, "end_ms": 2_000}],
            "content": "王老奇两查很好喝",
            "acquisition": "asr",
        }
    ]

    repairs = suggest_asr_repairs(
        rows,
        glossary={"王老奇两查": "王老吉凉茶", "王老奇": "王老吉"},
    )

    assert repairs[0]["repaired_content"] == "王老吉凉茶很好喝"


def test_cli_suggest_repairs_accepts_a_glossary_file(tmp_path, capsys) -> None:
    timeline = tmp_path / "timeline.raw.jsonl"
    glossary = tmp_path / "glossary.json"
    output = tmp_path / "repairs.json"
    timeline.write_text(
        json.dumps(
            {
                "evidence_id": "raw-tr-000001",
                "origin": "video",
                "modality": "transcript",
                "spans": [{"start_ms": 0, "end_ms": 2_000}],
                "content": "王老奇的兩查",
                "acquisition": "asr",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    glossary.write_text(
        json.dumps({"王老奇": "王老吉", "兩查": "凉茶"}, ensure_ascii=False),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "suggest-repairs",
            "--timeline",
            str(timeline),
            "--glossary",
            str(glossary),
            "--output",
            str(output),
        ]
    )

    assert exit_code == 0
    repairs = json.loads(output.read_text(encoding="utf-8"))
    assert repairs[0]["repaired_content"] == "王老吉的凉茶"
    assert repairs[0]["evidence_id"] == "raw-tr-000001"


def test_load_glossary_rejects_invalid_entries() -> None:
    with pytest.raises(ValueError, match="glossary must be an object"):
        load_glossary(["not", "an", "object"])
    with pytest.raises(ValueError, match="must be a non-empty string"):
        load_glossary({"王老奇": ""})


def test_simplified_normalization_converts_traditional_rows(monkeypatch) -> None:
    rows = [
        {
            "evidence_id": "tr-000001",
            "origin": "video",
            "modality": "transcript",
            "spans": [{"start_ms": 0, "end_ms": 2_000}],
            "content": "從國民飲料到被年輕人抛棄",
            "acquisition": "asr",
        }
    ]
    fake = type("zhconv", (), {"convert": staticmethod(lambda value, target: value.replace("國", "国"))})
    monkeypatch.setitem(__import__("sys").modules, "zhconv", fake)

    repairs = suggest_asr_repairs(rows, simplified=True)

    assert repairs[0]["repaired_content"] == "從国民飲料到被年輕人抛棄"
    assert "繁体转简体" in repairs[0]["reason"]


def test_simplified_normalization_with_the_real_converter() -> None:
    pytest.importorskip("zhconv")
    rows = [
        {
            "evidence_id": "tr-000001",
            "origin": "video",
            "modality": "transcript",
            "spans": [{"start_ms": 0, "end_ms": 2_000}],
            "content": "從國民飲料到被年輕人抛棄",
            "acquisition": "asr",
        }
    ]

    repairs = suggest_asr_repairs(rows, simplified=True)

    assert repairs[0]["repaired_content"] == "从国民饮料到被年轻人抛弃"


def test_simplified_normalization_reports_a_missing_dependency(monkeypatch) -> None:
    monkeypatch.setitem(__import__("sys").modules, "zhconv", None)

    with pytest.raises(ValueError, match="zhconv is required"):
        to_simplified("繁體")


def test_glossary_and_simplified_normalization_converge(monkeypatch) -> None:
    """A Simplified key must still match after the Traditional text is converted."""
    rows = [
        {
            "evidence_id": "tr-000001",
            "origin": "video",
            "modality": "transcript",
            "spans": [{"start_ms": 0, "end_ms": 2_000}],
            "content": "改變中國引讓使的廣告語",  # Traditional "引讓使"
            "acquisition": "asr",
        }
    ]
    monkeypatch.setitem(
        __import__("sys").modules,
        "zhconv",
        type(
            "zhconv",
            (),
            {
                "convert": staticmethod(
                    lambda value, target: value.replace("讓", "让")
                    .replace("國", "国")
                    .replace("廣", "广")
                    .replace("語", "语")
                    .replace("變", "变")
                )
            },
        ),
    )

    repairs = suggest_asr_repairs(rows, glossary={"引让使": "饮料史"}, simplified=True)

    assert repairs[0]["repaired_content"] == "改变中国饮料史的广告语"
