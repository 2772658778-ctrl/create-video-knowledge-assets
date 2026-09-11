from pathlib import Path

from vka.models import KnowledgeUnit
from vka.render_latex import render_course_tex
from vka.transcript import parse_srt_as_evidence
from vka.validate import validate_knowledge_evidence_refs


def test_fixture_keeps_provenance_traceable_from_srt_to_course_tex() -> None:
    source = (Path(__file__).parent / "fixtures" / "sample.srt").read_text(encoding="utf-8")
    evidence = parse_srt_as_evidence(source, acquisition="asr")
    evidence_by_id = {row["evidence_id"]: row for row in evidence}
    knowledge_unit = KnowledgeUnit.model_validate(
        {
            "unit_id": "ku-translation-example",
            "type": "example",
            "title": "翻译例子",
            "statement": "我们接下来用一个翻译例子说明它。",
            "evidence_refs": ["tr-000002"],
            "epistemic_status": "video_explicit",
            "importance": "high",
        }
    )

    assert evidence[0]["content"] == "注意力机制用于建立序列元素之间的关系。"
    assert evidence_by_id[knowledge_unit.evidence_refs[0]]["content"] == "我们接下来用一个翻译例子说明它。"
    assert validate_knowledge_evidence_refs(
        set(evidence_by_id), [knowledge_unit.model_dump()]
    ) == []
    source_spans = [
        span
        for evidence_id in knowledge_unit.evidence_refs
        for span in evidence_by_id[evidence_id]["spans"]
    ]
    assert knowledge_unit.evidence_refs == ["tr-000002"]
    assert source_spans == [{"start_ms": 3000, "end_ms": 6000}]

    tex = render_course_tex(
        "注意力机制",
        [
            {
                "title": "机制",
                "blocks": [
                    {
                        "kind": "paragraph",
                        "text": knowledge_unit.statement,
                        "source_spans": source_spans,
                    }
                ],
            }
        ],
    )
    assert "00:00:03--00:00:06" in tex
    assert r"\footnote{00:00:03--00:00:06}" in tex
