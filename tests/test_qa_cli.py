import json

import vka_cli


def _grounding_pack() -> dict[str, object]:
    return {
        "question": "How is the model fine tuned?",
        "mode": "video_only",
        "candidates": [],
        "topology": {"facets": [], "capabilities": []},
        "evidence_windows": [],
        "empty_reason": "no indexed video knowledge matched the question",
    }


def test_build_qa_topology_prints_course_notes_topology(monkeypatch, capsys) -> None:
    expected = {"asset_id": "asset-001", "profile_id": "course-notes", "facets": []}
    calls: list[tuple[object, str]] = []

    def build(asset: object, *, profile_id: str) -> dict[str, object]:
        calls.append((asset, profile_id))
        return expected

    monkeypatch.setattr(vka_cli, "build_qa_topology", build)

    result = vka_cli.main(
        ["build-qa-topology", "--asset", "asset-root", "--profile", "course-notes"]
    )

    assert result == 0
    assert json.loads(capsys.readouterr().out) == expected
    assert calls[0][1] == "course-notes"


def test_retrieve_qa_prints_grounding_candidates_without_an_answer(
    monkeypatch, capsys
) -> None:
    expected_pack = {
        "question": "How is the model fine tuned?",
        "mode": "video_only",
        "candidates": [{"knowledge_id": "ku-platform", "evidence_refs": ["ev-1"]}],
        "topology": {"facets": [], "capabilities": []},
        "evidence_windows": [],
        "course_locations": [],
        "empty_reason": None,
    }
    monkeypatch.setattr(vka_cli, "retrieve_question", lambda *args, **kwargs: expected_pack)

    result = vka_cli.main(
        [
            "retrieve-qa",
            "--asset",
            "asset-root",
            "--question",
            "How is the model fine tuned?",
            "--mode",
            "video_only",
            "--limit",
            "8",
        ]
    )

    output = json.loads(capsys.readouterr().out)
    assert result == 0
    assert output == expected_pack
    assert output["candidates"][0]["knowledge_id"] == "ku-platform"
    assert "topology" in output
    assert "evidence_windows" in output
    assert "answer" not in output


def test_plan_qa_prints_reference_only_plan(monkeypatch, tmp_path, capsys) -> None:
    grounding_path = tmp_path / "grounding-pack.json"
    grounding_path.write_text(json.dumps(_grounding_pack()), encoding="utf-8")
    expected_plan = {
        "schema_version": "1.0",
        "question": "How is the model fine tuned?",
        "blocks": [],
        "limitations": ["no_grounded_candidates"],
    }
    monkeypatch.setattr(vka_cli, "build_answer_plan", lambda pack: expected_plan)

    result = vka_cli.main(["plan-qa", "--input", str(grounding_path)])

    output = json.loads(capsys.readouterr().out)
    assert result == 0
    assert output == expected_plan
    assert "answer" not in output
    assert "claims" not in output


def test_plan_qa_rejects_malformed_or_answer_bearing_pack_without_echoing_contents(
    tmp_path, capsys
) -> None:
    grounding_path = tmp_path / "grounding-pack.json"
    submitted_answer = "sensitive answer text must not be reflected"
    for payload in (
        json.dumps({"answer": submitted_answer}),
        "{malformed: " + submitted_answer + "}",
    ):
        grounding_path.write_text(payload, encoding="utf-8")

        result = vka_cli.main(["plan-qa", "--input", str(grounding_path)])

        error = capsys.readouterr().err
        assert result == 1
        assert "grounding pack failed validation" in error
        assert submitted_answer not in error


def test_validate_answer_reports_invalid_contract_without_echoing_answer(
    tmp_path, capsys
) -> None:
    answer_path = tmp_path / "answer.json"
    answer_path.write_text(
        json.dumps(
            {
                "asset_id": "asset-001",
                "question": "question",
                "answer": "sensitive answer text must not be reflected",
            }
        ),
        encoding="utf-8",
    )

    result = vka_cli.main(
        ["validate-answer", "--asset", str(tmp_path / "asset"), "--input", str(answer_path)]
    )

    error = capsys.readouterr().err
    assert result == 1
    assert "answer failed validation" in error
    assert "sensitive answer text must not be reflected" not in error


def test_validate_answer_accepts_v11_blocks_and_plan(monkeypatch, tmp_path, capsys) -> None:
    answer_path = tmp_path / "answer.json"
    answer_path.write_text(
        json.dumps(
            {
                "schema_version": "1.1",
                "asset_id": "asset-001",
                "question": "What is covered?",
                "answer": "The video covers the procedure.",
                "mode": "video_only",
                "answer_status": "video_explicit",
                "claims": [
                    {
                        "claim_id": "claim:001",
                        "text": "The video covers the procedure.",
                        "status": "video_explicit",
                        "knowledge_refs": ["ku-procedure"],
                        "evidence_refs": ["ev-procedure"],
                        "source_spans": [{"start_ms": 1000, "end_ms": 2000}],
                    }
                ],
                "blocks": [
                    {
                        "block_id": "block:001",
                        "text": "The video covers the procedure.",
                        "claim_refs": ["claim:001"],
                    }
                ],
                "answer_plan": {
                    "mode": "video_only",
                    "blocks": [
                        {
                            "block_id": "block:001",
                            "expected_claim_ids": ["claim:001"],
                            "knowledge_refs": ["ku-procedure"],
                            "evidence_refs": ["ev-procedure"],
                            "source_spans": [{"start_ms": 1000, "end_ms": 2000}],
                            "evidence_window_ids": ["window:ku-procedure:001"],
                            "relation_refs": [],
                        }
                    ]
                },
                "knowledge_refs": ["ku-procedure"],
                "evidence_refs": ["ev-procedure"],
                "source_spans": [{"start_ms": 1000, "end_ms": 2000}],
                "retrieval": {"mode": "video_only"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(vka_cli, "validate_grounded_answer", lambda *args: [])

    result = vka_cli.main(
        ["validate-answer", "--asset", "asset-root", "--input", str(answer_path)]
    )

    assert result == 0
    assert capsys.readouterr().out == "answer passed validation\n"
