from pathlib import Path

from vka.models import SourceSpan
from vka.qa_contract import AnswerBlock, AnswerClaim, GroundedAnswer
from vka.qa_topology import build_qa_topology
from vka.qa_validation import validate_grounded_answer
from vka.qa_windows import build_evidence_windows
from vka.store import AssetStore


def _asset(tmp_path: Path) -> AssetStore:
    asset = AssetStore.create(
        tmp_path / "assets", "asset-001", {"kind": "bilibili", "bvid": "BV1test"}
    )
    metadata = asset.root / "source" / "metadata.json"
    metadata.write_text('{"title":"Lesson"}\n', encoding="utf-8")
    records = asset.write_jsonl(
        "evidence/records.jsonl",
        [
            {
                "evidence_id": "ev-video",
                "origin": "video",
                "modality": "transcript",
                "spans": [{"start_ms": 1_000, "end_ms": 2_000}],
                "content": "The speaker states the procedure.",
                "acquisition": "asr",
            },
            {
                "evidence_id": "ev-external",
                "origin": "external",
                "modality": "document",
                "spans": [],
                "content": "External background.",
                "acquisition": "user_supplied",
            },
        ],
    )
    units = asset.write_jsonl(
        "knowledge/units.jsonl",
        [
            {
                "unit_id": "ku-video",
                "type": "concept",
                "title": "Procedure",
                "statement": "The speaker states the procedure.",
                "evidence_refs": ["ev-video"],
                "epistemic_status": "video_explicit",
                "importance": "high",
            },
            {
                "unit_id": "ku-inference",
                "type": "mechanism",
                "title": "Inference",
                "statement": "This is an inference from the procedure.",
                "evidence_refs": ["ev-video"],
                "epistemic_status": "agent_inference",
                "importance": "medium",
            },
            {
                "unit_id": "ku-limitation",
                "type": "limitation",
                "title": "Limitation",
                "statement": "The video does not establish the result.",
                "evidence_refs": ["ev-video"],
                "epistemic_status": "insufficient_evidence",
                "importance": "medium",
            },
            {
                "unit_id": "ku-external",
                "type": "concept",
                "title": "External background",
                "statement": "This is external background only.",
                "evidence_refs": ["ev-external"],
                "epistemic_status": "external_enrichment",
                "importance": "low",
            },
        ],
    )
    relations = asset.write_jsonl(
        "knowledge/relations.jsonl",
        [
            {
                "relation_id": "rel-1",
                "source_unit_id": "ku-video",
                "target_unit_id": "ku-inference",
                "relation_type": "supports",
                "evidence_refs": ["ev-video"],
            }
        ],
    )
    synthesis = asset.root / "knowledge" / "synthesis.json"
    synthesis.write_text('{"video_summary":"Lesson"}\n', encoding="utf-8")
    outline = asset.root / "knowledge" / "teaching_outline.json"
    outline.write_text('{"sections": []}\n', encoding="utf-8")
    document = asset.root / "views" / "course-notes" / "document.json"
    document.parent.mkdir(parents=True, exist_ok=True)
    document.write_text('{"sections": []}\n', encoding="utf-8")
    asset.complete_stage("source", [metadata])
    asset.complete_stage("evidence", [records])
    asset.complete_stage("knowledge", [units, relations, synthesis])
    return asset


def _claim(
    *,
    knowledge_ref: str = "ku-video",
    evidence_ref: str = "ev-video",
    status: str = "video_explicit",
    span: SourceSpan | None = None,
) -> AnswerClaim:
    return AnswerClaim(
        text="The answer claim.",
        status=status,
        knowledge_refs=[knowledge_ref],
        evidence_refs=[evidence_ref],
        source_spans=[span or SourceSpan(start_ms=1_000, end_ms=2_000)],
    )


def _answer(**overrides: object) -> GroundedAnswer:
    claim = _claim()
    data: dict[str, object] = {
        "asset_id": "asset-001",
        "question": "What does the video establish?",
        "answer": "It states the procedure.",
        "mode": "video_only",
        "answer_status": "video_explicit",
        "claims": [claim],
        "knowledge_refs": list(claim.knowledge_refs),
        "evidence_refs": list(claim.evidence_refs),
        "source_spans": list(claim.source_spans),
        "retrieval": {"strategy": "lexical"},
    }
    data.update(overrides)
    plan = data.get("answer_plan")
    if isinstance(plan, dict):
        plan = dict(plan)
        plan.setdefault("mode", data["mode"])
        data["answer_plan"] = plan
    return GroundedAnswer(**data)


def test_video_explicit_rejects_inference_knowledge(tmp_path: Path) -> None:
    asset = _asset(tmp_path)
    claim = _claim(knowledge_ref="ku-inference")
    answer = _answer(claims=[claim])

    errors = validate_grounded_answer(asset, answer)

    assert "claim 1 video_explicit references non-video-explicit knowledge ku-inference" in errors


def test_claim_source_spans_must_match_resolved_video_evidence(tmp_path: Path) -> None:
    asset = _asset(tmp_path)
    claim = _claim(span=SourceSpan(start_ms=2_000, end_ms=3_000))
    answer = _answer(claims=[claim], source_spans=list(claim.source_spans))

    errors = validate_grounded_answer(asset, answer)

    assert "claim 1 source_spans must equal resolved video evidence spans" in errors


def test_top_level_refs_and_spans_must_equal_claim_union(tmp_path: Path) -> None:
    asset = _asset(tmp_path)
    answer = _answer(knowledge_refs=[], evidence_refs=[], source_spans=[])

    errors = validate_grounded_answer(asset, answer)

    assert "top-level knowledge_refs must equal the union of claim knowledge_refs" in errors
    assert "top-level evidence_refs must equal the union of claim evidence_refs" in errors
    assert "top-level source_spans must equal the union of claim source_spans" in errors


def test_video_explicit_rejects_external_evidence(tmp_path: Path) -> None:
    asset = _asset(tmp_path)
    claim = _claim(evidence_ref="ev-external")
    answer = _answer(claims=[claim], evidence_refs=["ev-external"])

    errors = validate_grounded_answer(asset, answer)

    assert "claim 1 video_explicit references non-video evidence ev-external" in errors
    assert "claim 1 evidence ev-external is not a canonical evidence_ref for its knowledge_refs" in errors


def test_agent_inference_requires_labelled_limitations(tmp_path: Path) -> None:
    asset = _asset(tmp_path)
    claim = _claim(knowledge_ref="ku-inference", status="agent_inference")
    answer = _answer(
        mode="video_only",
        answer_status="agent_inference",
        claims=[claim],
        knowledge_refs=["ku-inference"],
        limitations=[],
    )

    errors = validate_grounded_answer(asset, answer)

    assert "agent_inference answers require limitations containing 推断 or 未由视频直接证明" in errors


def test_agent_inference_rejects_external_knowledge_and_evidence(tmp_path: Path) -> None:
    asset = _asset(tmp_path)
    claim = AnswerClaim(
        text="An inference with external background.",
        status="agent_inference",
        knowledge_refs=["ku-inference", "ku-external"],
        evidence_refs=["ev-video", "ev-external"],
        source_spans=[SourceSpan(start_ms=1_000, end_ms=2_000)],
    )
    answer = _answer(
        mode="video_only",
        answer_status="agent_inference",
        claims=[claim],
        knowledge_refs=sorted(claim.knowledge_refs),
        evidence_refs=sorted(claim.evidence_refs),
        source_spans=list(claim.source_spans),
        limitations=["这是基于视频证据的推断。"],
    )

    errors = validate_grounded_answer(asset, answer)

    assert "claim 1 references external_enrichment knowledge ku-external" in errors
    assert "claim 1 references external evidence ev-external" in errors


def test_agent_inference_allows_video_explicit_premise_with_inference_unit(
    tmp_path: Path,
) -> None:
    asset = _asset(tmp_path)
    claim = AnswerClaim(
        text="An inference grounded in the stated procedure.",
        status="agent_inference",
        knowledge_refs=["ku-video", "ku-inference"],
        evidence_refs=["ev-video"],
        source_spans=[SourceSpan(start_ms=1_000, end_ms=2_000)],
    )
    answer = _answer(
        mode="video_only",
        answer_status="agent_inference",
        claims=[claim],
        knowledge_refs=sorted(claim.knowledge_refs),
        evidence_refs=list(claim.evidence_refs),
        source_spans=list(claim.source_spans),
        limitations=["这是基于视频证据的推断。"],
    )

    assert validate_grounded_answer(asset, answer) == []


def test_out_of_scope_answer_has_no_grounding_errors(tmp_path: Path) -> None:
    asset = _asset(tmp_path)
    answer = _answer(
        answer="The video does not cover this question.",
        answer_status="out_of_scope",
        claims=[],
        knowledge_refs=[],
        evidence_refs=[],
        source_spans=[],
    )

    assert validate_grounded_answer(asset, answer) == []


def test_rejects_asset_with_tampered_canonical_output(tmp_path: Path) -> None:
    asset = _asset(tmp_path)
    records_path = asset.root / "evidence" / "records.jsonl"
    records_path.write_text(records_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    errors = validate_grounded_answer(asset, _answer())

    assert "asset integrity error: evidence/records.jsonl sha256 does not match manifest" in errors


def test_rejects_incomplete_qa_asset_before_answer_reconciliation(tmp_path: Path) -> None:
    asset = _asset(tmp_path)
    (asset.root / "knowledge" / "synthesis.json").unlink()

    errors = validate_grounded_answer(asset, _answer())

    assert "asset QA error: required QA file is missing: knowledge/synthesis.json" in errors


def test_rejects_retained_records_that_fail_full_evidence_and_knowledge_schema(
    tmp_path: Path,
) -> None:
    asset = _asset(tmp_path)
    records = asset.write_jsonl(
        "evidence/records.jsonl",
        [
            {
                "evidence_id": "ev-video",
                "origin": "video",
                "modality": "transcript",
                "spans": [],
                "content": "The speaker states the procedure.",
                "acquisition": "asr",
            },
            {
                "evidence_id": "ev-external",
                "origin": "external",
                "modality": "document",
                "spans": [],
                "content": "External background.",
                "acquisition": "user_supplied",
            },
        ],
    )
    units = asset.write_jsonl(
        "knowledge/units.jsonl",
        [
            {
                "unit_id": "ku-video",
                "type": "concept",
                "statement": "The speaker states the procedure.",
                "evidence_refs": ["ev-video"],
                "epistemic_status": "video_explicit",
                "importance": "high",
            }
        ],
    )
    asset.complete_stage("evidence", [records])
    asset.complete_stage(
        "knowledge",
        [
            units,
            asset.root / "knowledge" / "relations.jsonl",
            asset.root / "knowledge" / "synthesis.json",
        ],
    )

    errors = validate_grounded_answer(asset, _answer())

    assert any(
        error.startswith("evidence record 1 schema error")
        and "video evidence requires a source span" in error
        for error in errors
    )
    assert "knowledge record 1 schema error at title: Field required" in errors


def test_structured_v11_blocks_validate_against_claims_and_plan_slots(
    tmp_path: Path,
) -> None:
    asset = _asset(tmp_path)
    published = build_evidence_windows(asset, ["ku-video"])
    build_qa_topology(asset)
    claim = AnswerClaim(
        claim_id="claim:procedure",
        text="The video states the procedure.",
        status="video_explicit",
        knowledge_refs=["ku-video"],
        evidence_refs=["ev-video"],
        source_spans=[SourceSpan(start_ms=1_000, end_ms=2_000)],
    )
    block = AnswerBlock(
        block_id="block:001",
        text="The video states the procedure.",
        claim_refs=["claim:procedure"],
    )
    answer = _answer(
        schema_version="1.1",
        claims=[claim],
        blocks=[block],
        answer=block.text,
        knowledge_refs=["ku-video"],
        evidence_refs=["ev-video"],
        source_spans=[SourceSpan(start_ms=1_000, end_ms=2_000)],
        answer_plan={
            "blocks": [
                {
                    "block_id": "block:001",
                    "expected_claim_ids": ["claim:procedure"],
                    "knowledge_refs": ["ku-video"],
                    "evidence_refs": ["ev-video"],
                    "source_spans": [{"start_ms": 1_000, "end_ms": 2_000}],
                    "evidence_window_ids": ["window:ku-video:001"],
                    "relation_refs": [],
                }
            ]
        },
    )

    assert validate_grounded_answer(asset, answer) == []

    bypassed_plan = answer.model_copy(update={"answer_plan": None})
    bypass_errors = validate_grounded_answer(asset, bypassed_plan)
    assert any("1.1 answers require a non-empty answer_plan" in error for error in bypass_errors)

    window = published["windows"][0]
    assert isinstance(window, dict)
    injected_plan = {
        "mode": "video_only",
        "blocks": [
            {
                **answer.answer_plan["blocks"][0],  # type: ignore[index]
                "source_spans": [
                    {"start_ms": 1_000, "end_ms": 2_000, "injected": True}
                ],
            }
        ]
    }
    plan_span_errors = validate_grounded_answer(
        asset, answer.model_copy(update={"answer_plan": injected_plan})
    )
    assert "answer_plan block block:001 source_spans must be a list of valid spans" in plan_span_errors

    injected_window_span = dict(window)
    injected_window_span["source_spans"] = [
        {"start_ms": 1_000, "end_ms": 2_000, "injected": True}
    ]
    asset.write_jsonl("index/evidence-windows.jsonl", [injected_window_span])
    window_span_errors = validate_grounded_answer(asset, answer)
    assert "retained evidence window 1 source_spans must be a list of valid spans" in window_span_errors

    injected = dict(window)
    injected["window_id"] = "window:ku-inference:001"
    injected["knowledge_id"] = "ku-inference"
    injected["injected_fact"] = "not allowed"
    asset.write_jsonl("index/evidence-windows.jsonl", [window, injected])

    errors = validate_grounded_answer(asset, answer)

    assert "retained evidence window 2 has unknown or missing properties" in errors


def test_structured_v11_rejects_plan_slot_with_unknown_or_external_refs(
    tmp_path: Path,
) -> None:
    asset = _asset(tmp_path)
    build_evidence_windows(asset, ["ku-video"])
    build_qa_topology(asset)
    claim = AnswerClaim(
        claim_id="claim:procedure",
        text="The video states the procedure.",
        status="video_explicit",
        knowledge_refs=["ku-video"],
        evidence_refs=["ev-video"],
        source_spans=[SourceSpan(start_ms=1_000, end_ms=2_000)],
    )
    block = AnswerBlock(
        block_id="block:001",
        text="The video states the procedure.",
        claim_refs=["claim:procedure"],
    )
    answer = _answer(
        schema_version="1.1",
        claims=[claim],
        blocks=[block],
        answer=block.text,
        knowledge_refs=["ku-video"],
        evidence_refs=["ev-video"],
        source_spans=[SourceSpan(start_ms=1_000, end_ms=2_000)],
        answer_plan={
            "blocks": [
                {
                    "block_id": "block:001",
                    "expected_claim_ids": ["claim:procedure"],
                    "knowledge_refs": ["ku-external", "ku-invented"],
                    "evidence_refs": ["ev-external", "ev-invented"],
                    "source_spans": [],
                    "evidence_window_ids": [],
                    "relation_refs": [],
                }
            ]
        },
    )

    errors = validate_grounded_answer(asset, answer)

    assert "answer_plan block block:001 references external_enrichment knowledge ku-external" in errors
    assert "answer_plan block block:001 references unknown knowledge ku-invented" in errors
    assert "answer_plan block block:001 references external evidence ev-external" in errors
    assert "answer_plan block block:001 references unknown evidence ev-invented" in errors


def test_structured_v11_rejects_forged_missing_and_unselected_plan_ids(
    tmp_path: Path,
) -> None:
    asset = _asset(tmp_path)
    build_evidence_windows(asset, ["ku-video"])
    build_qa_topology(asset)
    claim = AnswerClaim(
        claim_id="claim:procedure",
        text="The video states the procedure.",
        status="video_explicit",
        knowledge_refs=["ku-video"],
        evidence_refs=["ev-video"],
        source_spans=[SourceSpan(start_ms=1_000, end_ms=2_000)],
    )
    block = AnswerBlock(
        block_id="block:001",
        text="The video states the procedure.",
        claim_refs=["claim:procedure"],
    )
    answer = _answer(
        schema_version="1.1",
        claims=[claim],
        blocks=[block],
        answer=block.text,
        knowledge_refs=["ku-video"],
        evidence_refs=["ev-video"],
        source_spans=[SourceSpan(start_ms=1_000, end_ms=2_000)],
        answer_plan={
            "blocks": [
                {
                    "block_id": "block:001",
                    "expected_claim_ids": ["claim:procedure"],
                    "knowledge_refs": ["ku-video"],
                    "evidence_refs": ["ev-video"],
                    "source_spans": [{"start_ms": 1_000, "end_ms": 2_000}],
                    "evidence_window_ids": ["window:ku-video:999"],
                    "relation_refs": ["rel-1"],
                }
            ]
        },
    )

    errors = validate_grounded_answer(asset, answer)

    assert "answer_plan block block:001 evidence_window_ids do not match retained windows for ku-video" in errors
    assert "answer_plan block block:001 relation rel-1 reaches unselected knowledge ku-inference" in errors


def test_structured_v11_rejects_non_partitioned_retained_plan_windows(
    tmp_path: Path,
) -> None:
    asset = _asset(tmp_path)
    published = build_evidence_windows(asset, ["ku-video"])
    build_qa_topology(asset)
    window = published["windows"][0]
    assert isinstance(window, dict)
    forged = dict(window)
    forged["window_id"] = "window:ku-video:002"
    asset.write_jsonl("index/evidence-windows.jsonl", [forged])

    claim = AnswerClaim(
        claim_id="claim:procedure",
        text="The video states the procedure.",
        status="video_explicit",
        knowledge_refs=["ku-video"],
        evidence_refs=["ev-video"],
        source_spans=[SourceSpan(start_ms=1_000, end_ms=2_000)],
    )
    block = AnswerBlock(
        block_id="block:001",
        text="The video states the procedure.",
        claim_refs=["claim:procedure"],
    )
    answer = _answer(
        schema_version="1.1",
        claims=[claim],
        blocks=[block],
        answer=block.text,
        knowledge_refs=["ku-video"],
        evidence_refs=["ev-video"],
        source_spans=[SourceSpan(start_ms=1_000, end_ms=2_000)],
        answer_plan={
            "blocks": [
                {
                    "block_id": "block:001",
                    "expected_claim_ids": ["claim:procedure"],
                    "knowledge_refs": ["ku-video"],
                    "evidence_refs": ["ev-video"],
                    "source_spans": [{"start_ms": 1_000, "end_ms": 2_000}],
                    "evidence_window_ids": ["window:ku-video:002"],
                    "relation_refs": [],
                }
            ]
        },
    )

    errors = validate_grounded_answer(asset, answer)

    assert "retained evidence windows have an invalid partition for knowledge ku-video" in errors


def test_structured_v11_rejects_selected_facets_that_do_not_match_plan_slots(
    tmp_path: Path,
) -> None:
    asset = _asset(tmp_path)
    build_evidence_windows(asset, ["ku-video"])
    build_qa_topology(asset)
    claim = AnswerClaim(
        claim_id="claim:procedure",
        text="The video states the procedure.",
        status="video_explicit",
        knowledge_refs=["ku-video"],
        evidence_refs=["ev-video"],
        source_spans=[SourceSpan(start_ms=1_000, end_ms=2_000)],
    )
    block = AnswerBlock(
        block_id="block:001",
        text="The video states the procedure.",
        claim_refs=["claim:procedure"],
    )
    answer = _answer(
        schema_version="1.1",
        claims=[claim],
        blocks=[block],
        answer=block.text,
        knowledge_refs=["ku-video"],
        evidence_refs=["ev-video"],
        source_spans=[SourceSpan(start_ms=1_000, end_ms=2_000)],
        answer_plan={
            "selected_facets": [],
            "blocks": [
                {
                    "block_id": "block:001",
                    "expected_claim_ids": ["claim:procedure"],
                    "knowledge_refs": ["ku-video"],
                    "evidence_refs": ["ev-video"],
                    "source_spans": [{"start_ms": 1_000, "end_ms": 2_000}],
                    "evidence_window_ids": ["window:ku-video:001"],
                    "relation_refs": [],
                }
            ],
        },
    )

    errors = validate_grounded_answer(asset, answer)

    assert "answer_plan selected_facets must equal block knowledge_refs" in errors


def test_structured_v11_rejects_empty_or_forged_retained_window_payload(
    tmp_path: Path,
) -> None:
    asset = _asset(tmp_path)
    published = build_evidence_windows(asset, ["ku-video"])
    window = published["windows"][0]
    assert isinstance(window, dict)
    forged = dict(window)
    forged["evidence_refs"] = []
    forged["anchor_evidence_refs"] = []
    forged["source_spans"] = []
    forged["evidence"] = []
    asset.write_jsonl("index/evidence-windows.jsonl", [forged])

    claim = AnswerClaim(
        claim_id="claim:procedure",
        text="The video states the procedure.",
        status="video_explicit",
        knowledge_refs=["ku-video"],
        evidence_refs=["ev-video"],
        source_spans=[SourceSpan(start_ms=1_000, end_ms=2_000)],
    )
    block = AnswerBlock(
        block_id="block:001",
        text="The video states the procedure.",
        claim_refs=["claim:procedure"],
    )
    answer = _answer(
        schema_version="1.1",
        claims=[claim],
        blocks=[block],
        answer=block.text,
        knowledge_refs=["ku-video"],
        evidence_refs=["ev-video"],
        source_spans=[SourceSpan(start_ms=1_000, end_ms=2_000)],
        answer_plan={
            "blocks": [
                {
                    "block_id": "block:001",
                    "expected_claim_ids": ["claim:procedure"],
                    "knowledge_refs": ["ku-video"],
                    "evidence_refs": ["ev-video"],
                    "source_spans": [{"start_ms": 1_000, "end_ms": 2_000}],
                    "evidence_window_ids": ["window:ku-video:001"],
                    "relation_refs": [],
                }
            ]
        },
    )

    errors = validate_grounded_answer(asset, answer)

    assert "retained evidence window 1 must contain evidence_refs" in errors
    assert "answer_plan block block:001 evidence_refs are not covered by declared evidence windows" in errors
    assert "answer_plan block block:001 source_spans are not covered by declared evidence windows" in errors


def test_relation_reconciliation_rejects_unknown_canonical_evidence_ref(
    tmp_path: Path,
) -> None:
    asset = _asset(tmp_path)
    relations = asset.write_jsonl(
        "knowledge/relations.jsonl",
        [
            {
                "relation_id": "rel-1",
                "source_unit_id": "ku-video",
                "target_unit_id": "ku-inference",
                "relation_type": "supports",
                "evidence_refs": ["ev-invented"],
            }
        ],
    )
    asset.complete_stage(
        "knowledge",
        [
            asset.root / "knowledge" / "units.jsonl",
            relations,
            asset.root / "knowledge" / "synthesis.json",
        ],
    )
    build_evidence_windows(asset, ["ku-video"])
    claim = AnswerClaim(
        claim_id="claim:procedure",
        text="The video states the procedure.",
        status="video_explicit",
        knowledge_refs=["ku-video"],
        evidence_refs=["ev-video"],
        source_spans=[SourceSpan(start_ms=1_000, end_ms=2_000)],
    )
    block = AnswerBlock(
        block_id="block:001",
        text="The video states the procedure.",
        claim_refs=["claim:procedure"],
    )
    answer = _answer(
        schema_version="1.1",
        claims=[claim],
        blocks=[block],
        answer=block.text,
        knowledge_refs=["ku-video"],
        evidence_refs=["ev-video"],
        source_spans=[SourceSpan(start_ms=1_000, end_ms=2_000)],
        answer_plan={
            "blocks": [
                {
                    "block_id": "block:001",
                    "expected_claim_ids": ["claim:procedure"],
                    "knowledge_refs": ["ku-video"],
                    "evidence_refs": ["ev-video"],
                    "source_spans": [{"start_ms": 1_000, "end_ms": 2_000}],
                    "evidence_window_ids": ["window:ku-video:001"],
                    "relation_refs": [],
                }
            ]
        },
    )

    errors = validate_grounded_answer(asset, answer)

    assert "relation rel-1 references unknown evidence ev-invented" in errors
