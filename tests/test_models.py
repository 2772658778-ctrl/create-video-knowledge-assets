import pytest

from vka.models import (
    DocumentBlock,
    DocumentView,
    Evidence,
    KnowledgeRelation,
    KnowledgeUnit,
    SourceSpan,
    Synthesis,
)


def test_video_evidence_requires_increasing_time_span() -> None:
    evidence = Evidence(
        evidence_id="tr-000001",
        origin="video",
        modality="transcript",
        spans=[SourceSpan(start_ms=1000, end_ms=2500)],
        content="注意力机制用于建立序列关系。",
        acquisition="asr",
    )
    assert evidence.spans[0].end_ms == 2500


def test_source_span_rejects_non_increasing_time_span() -> None:
    with pytest.raises(ValueError, match="greater than start_ms"):
        SourceSpan(start_ms=2500, end_ms=2500)


def test_video_evidence_rejects_missing_span() -> None:
    with pytest.raises(ValueError, match="source span"):
        Evidence(
            evidence_id="bad",
            origin="video",
            modality="frame",
            content="画面",
            acquisition="ffmpeg",
        )


def test_knowledge_unit_preserves_epistemic_status() -> None:
    unit = KnowledgeUnit(
        unit_id="ku-001",
        type="mechanism",
        title="注意力机制",
        statement="模型按相关性聚合序列信息。",
        evidence_refs=["tr-000001"],
        epistemic_status="agent_inference",
        importance="high",
    )
    assert unit.epistemic_status == "agent_inference"


def test_knowledge_unit_rejects_empty_evidence_refs() -> None:
    with pytest.raises(ValueError):
        KnowledgeUnit(
            unit_id="ku-002",
            type="claim",
            title="Attention mechanism",
            statement="The model aggregates sequence information.",
            evidence_refs=[],
            epistemic_status="agent_inference",
            importance="medium",
        )


def test_document_block_keeps_grounding_refs() -> None:
    block = DocumentBlock.model_validate(
        {
            "kind": "paragraph",
            "text": "The core mechanism has two steps.",
            "knowledge_refs": ["ku-1"],
            "evidence_refs": ["tr-2"],
            "source_spans": [{"start_ms": 2000, "end_ms": 8000}],
        }
    )

    assert block.evidence_refs == ["tr-2"]


def test_document_view_requires_profile_and_block_provenance() -> None:
    with pytest.raises(ValueError):
        DocumentView.model_validate(
            {
                "title": "A document",
                "blocks": [{"kind": "paragraph", "text": "Ungrounded prose."}],
            }
        )


def test_knowledge_relation_and_synthesis_keep_their_grounding() -> None:
    relation = KnowledgeRelation(
        relation_id="rel-1",
        source_unit_id="ku-1",
        target_unit_id="ku-2",
        relation_type="supports",
        evidence_refs=["tr-2"],
    )
    synthesis = Synthesis(
        video_summary="The video explains the two steps.",
        video_summary_refs=["ku-1"],
        agent_extensions=["The steps can be compared to a feedback loop."],
        agent_extension_refs=["ku-2"],
        evidence_refs=["tr-2"],
    )

    assert relation.relation_type == "supports"
    assert synthesis.agent_extensions == ["The steps can be compared to a feedback loop."]
    assert synthesis.video_summary_refs == ["ku-1"]
    assert synthesis.agent_extension_refs == ["ku-2"]


def test_knowledge_relation_uses_part_of_not_composes() -> None:
    relation = KnowledgeRelation(
        relation_id="rel-part",
        source_unit_id="ku-1",
        target_unit_id="ku-2",
        relation_type="part_of",
        evidence_refs=["tr-2"],
    )

    assert relation.relation_type == "part_of"

    with pytest.raises(ValueError):
        KnowledgeRelation(
            relation_id="rel-composes",
            source_unit_id="ku-1",
            target_unit_id="ku-2",
            relation_type="composes",
            evidence_refs=["tr-2"],
        )


def test_synthesis_rejects_blank_agent_extensions() -> None:
    with pytest.raises(ValueError, match="agent_extensions"):
        Synthesis(
            video_summary="The video explains the two steps.",
            video_summary_refs=["ku-1"],
            agent_extensions=["  "],
            agent_extension_refs=["ku-2"],
            evidence_refs=["tr-2"],
        )
