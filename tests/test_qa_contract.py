import pytest
from pydantic import ValidationError

from vka.models import SourceSpan
from vka.qa_contract import (
    AnswerBlock,
    AnswerClaim,
    AnswerExtension,
    GroundedAnswer,
    aggregate_answer_status,
)


def _claim(status: str = "video_explicit") -> AnswerClaim:
    return AnswerClaim(
        text="The speaker defines the method.",
        status=status,
        knowledge_refs=["ku-1"],
        evidence_refs=["ev-1"],
        source_spans=[SourceSpan(start_ms=0, end_ms=1_000)],
    )


def _structured_claim(claim_id: str = "claim:001") -> AnswerClaim:
    return AnswerClaim(
        claim_id=claim_id,
        text="The speaker defines the method.",
        status="video_explicit",
        knowledge_refs=["ku-1"],
        evidence_refs=["ev-1"],
        source_spans=[SourceSpan(start_ms=0, end_ms=1_000)],
    )


def _answer(**overrides: object) -> GroundedAnswer:
    data: dict[str, object] = {
        "asset_id": "asset-1",
        "question": "What does the lesson define?",
        "answer": "It defines the method.",
        "mode": "video_plus_context",
        "answer_status": "video_explicit",
        "claims": [_claim()],
        "retrieval": {"strategy": "semantic"},
    }
    data.update(overrides)
    if data.get("schema_version") == "1.1":
        data.setdefault("knowledge_revision", "rev-test")
        data.setdefault("knowledge_revision_sha256", "a" * 64)
        plan = data.get("answer_plan")
        if isinstance(plan, dict):
            plan = dict(plan)
            plan.setdefault("knowledge_revision", data["knowledge_revision"])
            plan.setdefault("knowledge_revision_sha256", data["knowledge_revision_sha256"])
            data["answer_plan"] = plan
    return GroundedAnswer(**data)


def test_aggregate_answer_status_mixed_and_single_statuses() -> None:
    assert aggregate_answer_status(["video_explicit", "agent_inference"]) == "mixed"
    assert aggregate_answer_status(["video_explicit"]) == "video_explicit"
    assert aggregate_answer_status(["agent_inference"]) == "agent_inference"
    assert aggregate_answer_status(["insufficient_evidence"]) == "insufficient_evidence"
    assert aggregate_answer_status([]) == "insufficient_evidence"


def test_grounded_answer_constructs_with_source_spans() -> None:
    answer = _answer()

    assert answer.schema_version == "1.0"
    assert answer.claims[0].source_spans == [SourceSpan(start_ms=0, end_ms=1_000)]
    assert answer.knowledge_refs == []
    assert answer.evidence_refs == []
    assert answer.source_spans == []
    assert answer.extensions == []


def test_video_only_rejects_extensions() -> None:
    extension = AnswerExtension(
        kind="agent_background",
        text="This supplies background not stated in the video.",
        visible_label="\u975e\u89c6\u9891\u57fa\u7840\u8bf4\u660e",
    )

    with pytest.raises(ValidationError, match="video_only"):
        _answer(mode="video_only", extensions=[extension])


def test_out_of_scope_requires_no_claims_and_video_coverage_notice() -> None:
    with pytest.raises(ValidationError, match="out_of_scope"):
        _answer(answer_status="out_of_scope")

    answer = _answer(
        answer_status="out_of_scope",
        claims=[],
        answer="\u89c6\u9891\u8d44\u4ea7\u4e0d\u8986\u76d6\u8fd9\u4e2a\u95ee\u9898\u3002",
    )
    assert answer.claims == []


def test_background_content_in_claims_is_rejected() -> None:
    with pytest.raises(ValidationError, match="extensions must stay outside answer claims"):
        _answer(
            claims=[
                {
                    "kind": "agent_background",
                    "text": "This is background context.",
                    "visible_label": "\u975e\u89c6\u9891\u57fa\u7840\u8bf4\u660e",
                    "knowledge_refs": ["ku-1"],
                    "evidence_refs": ["ev-1"],
                }
            ]
        )


def test_claim_and_extension_require_non_empty_text_and_refs() -> None:
    with pytest.raises(ValidationError):
        AnswerClaim(
            text=" ",
            status="video_explicit",
            knowledge_refs=[],
            evidence_refs=[],
        )
    with pytest.raises(ValidationError):
        AnswerExtension(
            kind="exploration",
            text=" ",
            visible_label="\u53d1\u6563\u8ba8\u8bba\uff0c\u975e\u89c6\u9891\u7ed3\u8bba",
        )


def test_claim_refs_must_be_nonblank_and_video_claims_need_source_spans() -> None:
    with pytest.raises(ValidationError, match="references must not contain blank values"):
        AnswerClaim(
            text="The speaker defines the method.",
            status="agent_inference",
            knowledge_refs=[" "],
            evidence_refs=["ev-1"],
        )
    with pytest.raises(ValidationError, match="video_explicit claims require source_spans"):
        AnswerClaim(
            text="The speaker defines the method.",
            status="video_explicit",
            knowledge_refs=["ku-1"],
            evidence_refs=["ev-1"],
        )


def test_answer_status_must_equal_claim_aggregation_except_out_of_scope() -> None:
    with pytest.raises(ValidationError, match="answer_status must equal aggregated claim statuses"):
        _answer(answer_status="agent_inference")

    answer = _answer(claims=[], answer_status="insufficient_evidence")
    assert answer.answer_status == "insufficient_evidence"

    with pytest.raises(ValidationError, match="references must not contain blank values"):
        _answer(knowledge_refs=[" "])


def test_legacy_v1_answers_remain_valid_without_claim_ids_or_blocks() -> None:
    answer = _answer()

    assert answer.schema_version == "1.0"
    assert answer.claims[0].claim_id is None
    assert answer.blocks == []


def test_structured_v11_answer_requires_bound_claim_blocks_and_renders_answer() -> None:
    claim = _structured_claim()
    block = AnswerBlock(
        block_id="block:001",
        heading="Definition",
        purpose="answer selected facet",
        text="The speaker defines the method.",
        claim_refs=["claim:001"],
    )
    missing = AnswerBlock(
        block_id="block:002",
        kind="missing_facet",
        text="The video does not establish its limitations.",
        claim_refs=[],
    )

    answer = _answer(
        schema_version="1.1",
        claims=[claim],
        blocks=[block, missing],
        answer="The speaker defines the method.\n\nThe video does not establish its limitations.",
        answer_plan={
            "blocks": [
                {
                    "block_id": "block:001",
                    "authoring_purpose": "address_selected_facet",
                    "knowledge_refs": ["ku-1"],
                    "evidence_refs": ["ev-1"],
                    "source_spans": [{"start_ms": 0, "end_ms": 1_000}],
                    "evidence_window_ids": ["window:ku-1:001"],
                    "relation_refs": [],
                }
            ]
        },
    )

    assert answer.blocks == [block, missing]


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"claims": [_structured_claim("claim:001"), _structured_claim("claim:001")]}, "claim_id"),
        ({"blocks": [{"block_id": "block:001", "text": "Fact.", "claim_refs": ["claim:001"]}, {"block_id": "block:001", "text": "More.", "claim_refs": ["claim:001"]}]}, "block_id"),
        ({"blocks": [{"block_id": "block:001", "text": "Fact.", "claim_refs": ["claim:invented"]}]}, "unknown claim_id"),
        ({"blocks": [{"block_id": "block:001", "text": "Fact.", "claim_refs": []}]}, "factual blocks"),
        ({"blocks": [{"block_id": "block:001", "kind": "missing_facet", "text": "Missing.", "claim_refs": ["claim:001"]}]}, "missing_facet"),
    ],
)
def test_structured_v11_rejects_invalid_block_and_claim_ids(
    overrides: dict[str, object], message: str
) -> None:
    data: dict[str, object] = {
        "schema_version": "1.1",
        "claims": [_structured_claim()],
        "blocks": [
            AnswerBlock(
                block_id="block:001",
                text="The speaker defines the method.",
                claim_refs=["claim:001"],
            )
        ],
        "answer": "The speaker defines the method.",
    }
    data.update(overrides)

    with pytest.raises(ValidationError, match=message):
        _answer(**data)


def test_structured_v11_rejects_unreferenced_claim_and_answer_mismatch() -> None:
    claim = _structured_claim()
    block = AnswerBlock(block_id="block:001", text="Fact.", claim_refs=[claim.claim_id])

    with pytest.raises(ValidationError, match="every claim"):
        _answer(
            schema_version="1.1",
            claims=[claim, _structured_claim("claim:002")],
            blocks=[block],
            answer="Fact.",
        )
    with pytest.raises(ValidationError, match="derived from block text"):
        _answer(
            schema_version="1.1",
            claims=[claim],
            blocks=[block],
            answer="Hidden factual prose.",
        )


def test_structured_v11_blocks_cannot_contain_extensions_or_canonical_refs() -> None:
    with pytest.raises(ValidationError):
        _answer(
            schema_version="1.1",
            claims=[_structured_claim()],
            blocks=[
                {
                    "block_id": "block:001",
                    "text": "External background.",
                    "claim_refs": ["claim:001"],
                    "kind": "agent_background",
                    "knowledge_refs": ["ku-external"],
                }
            ],
            answer="External background.",
        )


def test_structured_v11_requires_a_nonempty_strict_reference_only_plan() -> None:
    claim = _structured_claim()
    block = AnswerBlock(
        block_id="block:001",
        text="The speaker defines the method.",
        claim_refs=["claim:001"],
    )
    data = {
        "schema_version": "1.1",
        "claims": [claim],
        "blocks": [block],
        "answer": block.text,
    }

    with pytest.raises(ValidationError, match="answer_plan"):
        _answer(**data)
    with pytest.raises(ValidationError, match="unknown properties"):
        _answer(
            **data,
            answer_plan={
                "blocks": [
                    {
                        "block_id": "block:001",
                        "authoring_purpose": "address_selected_facet",
                        "knowledge_refs": ["ku-1"],
                        "evidence_refs": ["ev-1"],
                        "source_spans": [{"start_ms": 0, "end_ms": 1_000}],
                        "evidence_window_ids": ["window:ku-1:001"],
                        "relation_refs": [],
                        "injected_fact": "not allowed",
                    }
                ]
            },
        )
    with pytest.raises(ValidationError, match="unknown properties"):
        _answer(**data, answer_plan={"blocks": [], "injected_fact": "not allowed"})
