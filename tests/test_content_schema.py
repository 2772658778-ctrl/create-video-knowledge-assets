import pytest

from vka.models import ContentUnit, SourceSpan


def test_content_unit_validates_required_refs_and_adaptation() -> None:
    unit = ContentUnit(
        content_unit_id="cu-001",
        kind="thesis",
        title="核心判断",
        editorial_text="This is the distilled editorial phrasing.",
        knowledge_refs=["ku-001"],
        evidence_refs=["tr-001"],
        epistemic_status="video_explicit",
        standalone_level="standalone",
        adaptation={"tone": "concise"},
    )

    assert unit.knowledge_refs == ["ku-001"]
    assert unit.evidence_refs == ["tr-001"]
    assert unit.adaptation == {"tone": "concise"}


def test_content_unit_rejects_missing_required_refs() -> None:
    with pytest.raises(ValueError):
        ContentUnit(
            content_unit_id="cu-002",
            kind="example",
            title="Example",
            editorial_text="Example text.",
            evidence_refs=["tr-001"],
            epistemic_status="video_explicit",
            standalone_level="needs_intro",
        )

    with pytest.raises(ValueError):
        ContentUnit(
            content_unit_id="cu-003",
            kind="example",
            title="Example",
            editorial_text="Example text.",
            knowledge_refs=["ku-001"],
            epistemic_status="video_explicit",
            standalone_level="needs_intro",
        )


def test_content_unit_accepts_source_spans() -> None:
    unit = ContentUnit(
        content_unit_id="cu-004",
        kind="scene",
        title="Scene",
        editorial_text="A short scene description.",
        knowledge_refs=["ku-001"],
        evidence_refs=["tr-001"],
        epistemic_status="video_explicit",
        standalone_level="needs_intro",
        source_spans=[SourceSpan(start_ms=1000, end_ms=2000)],
    )

    assert unit.source_spans[0].start_ms == 1000
