import json

import pytest

from vka.qa_planning import build_answer_plan


def _pack(*, question: str = "How do I configure the runner?") -> dict[str, object]:
    return {
        "question": question,
        "mode": "video_only",
        "candidates": [
            {
                "knowledge_id": "ku-setup",
                "knowledge_refs": ["ku-setup"],
                "evidence_refs": ["ev-setup"],
                "title": "Setup title must not leak",
                "statement": "The hidden setup fact must not leak.",
                "source_spans": [{"start_ms": 1_000, "end_ms": 2_000}],
                "related_units": [
                    {
                        "knowledge_id": "ku-concept",
                        "relation_id": "rel-setup-concept",
                        "relation_type": "supports",
                        "direction": "outgoing",
                    }
                ],
            },
            {
                "knowledge_id": "ku-concept",
                "knowledge_refs": ["ku-concept"],
                "evidence_refs": ["ev-concept"],
                "title": "Concept title must not leak",
                "statement": "The hidden concept fact must not leak.",
                "source_spans": [{"start_ms": 3_000, "end_ms": 4_000}],
                "related_units": [],
            },
        ],
        "topology": {
            "facets": [
                {
                    "unit_id": "ku-setup",
                    "capabilities": ["tag:setup", "type:procedure"],
                    "inbound_relation_ids": [],
                    "outbound_relation_ids": ["rel-setup-concept"],
                },
                {
                    "unit_id": "ku-concept",
                    "capabilities": ["tag:foundation", "type:concept"],
                    "inbound_relation_ids": ["rel-setup-concept"],
                    "outbound_relation_ids": [],
                },
            ],
            "capabilities": [
                "tag:foundation",
                "tag:setup",
                "type:concept",
                "type:procedure",
            ],
        },
        "evidence_windows": [
            {
                "window_id": "window:ku-setup:001",
                "knowledge_id": "ku-setup",
                "evidence_refs": ["ev-setup"],
                "source_spans": [{"start_ms": 1_000, "end_ms": 2_000}],
                "evidence": [{"content": "Evidence prose must not leak."}],
            },
            {
                "window_id": "window:ku-concept:001",
                "knowledge_id": "ku-concept",
                "evidence_refs": ["ev-concept"],
                "source_spans": [{"start_ms": 3_000, "end_ms": 4_000}],
                "evidence": [{"content": "More evidence prose must not leak."}],
            },
        ],
        "empty_reason": None,
    }


def test_build_answer_plan_uses_procedure_capability_and_ranked_candidates() -> None:
    plan = build_answer_plan(_pack())

    assert plan["schema_version"] == "1.0"
    assert plan["question"] == "How do I configure the runner?"
    assert plan["mode"] == "video_only"
    assert plan["inferred_intent"] == {
        "question": "How do I configure the runner?",
        "strategy": "selected_video_facets_only",
    }
    assert plan["selected_facets"] == [
        {"knowledge_id": "ku-setup"},
        {"knowledge_id": "ku-concept"},
    ]
    assert plan["missing_facets"] == []
    assert [block["knowledge_refs"] for block in plan["blocks"]] == [
        ["ku-setup"],
        ["ku-concept"],
    ]
    assert plan["blocks"][0] == {
        "block_id": "block:001",
        "authoring_purpose": "address_selected_facet",
        "expected_claim_ids": ["claim:001"],
        "knowledge_refs": ["ku-setup"],
        "evidence_refs": ["ev-setup"],
        "source_spans": [{"start_ms": 1_000, "end_ms": 2_000}],
        "evidence_window_ids": ["window:ku-setup:001"],
        "relation_refs": ["rel-setup-concept"],
    }


def test_concept_only_plan_does_not_force_procedure_or_parameter_blocks() -> None:
    pack = _pack(question="What is the runner concept?")
    pack["candidates"] = [pack["candidates"][1]]
    pack["topology"] = {
        "facets": [pack["topology"]["facets"][1]],
        "capabilities": ["tag:foundation", "type:concept"],
    }
    pack["evidence_windows"] = [pack["evidence_windows"][1]]

    plan = build_answer_plan(pack)

    assert plan["inferred_intent"]["strategy"] == "selected_video_facets_only"
    assert "supported_capabilities" not in plan["inferred_intent"]
    assert len(plan["blocks"]) == 1
    assert plan["blocks"][0]["knowledge_refs"] == ["ku-concept"]
    assert "type:procedure" not in json.dumps(plan)
    assert "parameter" not in json.dumps(plan)


def test_no_hit_produces_missing_only_plan_without_claim_slots() -> None:
    pack = _pack(question="What parameters tune the unknown system?")
    pack["candidates"] = []
    pack["topology"] = {"facets": [], "capabilities": []}
    pack["evidence_windows"] = []
    pack["empty_reason"] = "no indexed video knowledge matched the question"

    plan = build_answer_plan(pack)

    assert plan["selected_facets"] == []
    assert plan["blocks"] == []
    assert plan["missing_facets"] == ["question_relevant_coverage"]
    assert plan["limitations"] == ["no_grounded_candidates"]


def test_plan_uses_only_selected_references_and_is_deterministic() -> None:
    pack = _pack()
    pack["topology"]["facets"].append(
        {"unit_id": "ku-unselected", "capabilities": ["type:parameter"]}
    )
    pack["topology"]["capabilities"].append("type:parameter")

    with pytest.raises(ValueError, match="unselected"):
        build_answer_plan(pack)

    selected_pack = _pack()
    first = build_answer_plan(selected_pack)
    second = build_answer_plan(selected_pack)
    assert second == first
    assert "ku-unselected" not in json.dumps(first)


def test_plan_never_copies_candidate_or_evidence_prose() -> None:
    plan = build_answer_plan(_pack())
    serialized = json.dumps(plan)

    for prose in (
        "Setup title must not leak",
        "The hidden setup fact must not leak.",
        "Evidence prose must not leak.",
    ):
        assert prose not in serialized


@pytest.mark.parametrize(
    "candidate_refs,window_refs",
    [
        (["ev-invented"], ["ev-setup"]),
        (["ev-setup"], ["ev-other"]),
    ],
)
def test_plan_rejects_candidate_evidence_not_covered_by_its_selected_windows(
    candidate_refs: list[str], window_refs: list[str]
) -> None:
    pack = _pack()
    pack["candidates"][0]["evidence_refs"] = candidate_refs
    pack["evidence_windows"][0]["evidence_refs"] = window_refs

    with pytest.raises(ValueError, match="candidate evidence_refs"):
        build_answer_plan(pack)


def test_plan_rejects_candidate_relation_not_in_selected_topology() -> None:
    pack = _pack()
    pack["candidates"][0]["related_units"][0]["relation_id"] = "rel-invented"

    with pytest.raises(ValueError, match="relation"):
        build_answer_plan(pack)


def test_plan_rejects_one_sided_selected_relation_topology() -> None:
    pack = _pack()
    pack["topology"]["facets"][1]["inbound_relation_ids"] = []

    with pytest.raises(ValueError, match="reciprocal"):
        build_answer_plan(pack)


def test_plan_rejects_candidate_spans_not_covered_by_selected_windows() -> None:
    pack = _pack()
    pack["candidates"][0]["source_spans"] = [{"start_ms": 5_000, "end_ms": 6_000}]

    with pytest.raises(ValueError, match="source_spans"):
        build_answer_plan(pack)


@pytest.mark.parametrize(
    "pack",
    [
        {},
        {"question": "What?", "mode": "video_only", "answer": "not allowed"},
        {
            "question": "What?",
            "mode": "video_only",
            "candidates": [],
            "topology": {
                "facets": [
                    {
                        "unit_id": "ku-unselected",
                        "inbound_relation_ids": [],
                        "outbound_relation_ids": [],
                    }
                ],
                "capabilities": [],
            },
            "evidence_windows": [],
        },
    ],
)
def test_plan_rejects_malformed_or_answer_bearing_packs(pack: object) -> None:
    with pytest.raises(ValueError):
        build_answer_plan(pack)
