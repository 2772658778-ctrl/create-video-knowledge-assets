import json
import os
import subprocess
import threading
import time
from dataclasses import FrozenInstanceError
from pathlib import Path
from copy import deepcopy

import pytest

import vka.profiles as profiles_module
from vka.profiles import (
    canonical_hash_tree,
    get_profile,
    reproject_profile_documents,
    route_profile,
    validate_profile_document,
    write_profile_document,
    write_profile_selection,
)
from vka.quality import validate_document_quality
from vka.store import AssetStore
from vka_cli import main


FIXTURES = Path(__file__).parent / "fixtures"


def _profile_fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _asset_with_canonical_profile_records(
    tmp_path: Path,
    document: dict[str, object],
    *,
    epistemic_status: str = "video_explicit",
    evidence_origin: str = "video",
    knowledge_statuses: dict[str, str] | None = None,
    evidence_records: dict[str, dict[str, object]] | None = None,
) -> AssetStore:
    asset = AssetStore.create(tmp_path / "assets", "asset-001", {"kind": "local_video"})
    knowledge_ids = sorted({
        reference
        for section in document["sections"]  # type: ignore[index]
        for block in section["blocks"]  # type: ignore[index]
        for reference in block["knowledge_refs"]
    })
    evidence_ids = sorted({
        reference
        for section in document["sections"]  # type: ignore[index]
        for block in section["blocks"]  # type: ignore[index]
        for reference in block["evidence_refs"]
    })
    evidence = asset.write_jsonl(
        "evidence/timeline.jsonl",
        [
            {
                "evidence_id": evidence_id,
                "origin": evidence_origin,
                **(evidence_records or {}).get(evidence_id, {}),
            }
            for evidence_id in evidence_ids
        ],
    )
    knowledge = asset.write_jsonl(
        "knowledge/units.jsonl",
        [
            {
                "unit_id": knowledge_id,
                "epistemic_status": (knowledge_statuses or {}).get(
                    knowledge_id, epistemic_status
                ),
            }
            for knowledge_id in knowledge_ids
        ],
    )
    asset.complete_stage("evidence", [evidence])
    asset.complete_stage("knowledge", [knowledge])
    return asset


def _completed_general_asset_for_reprojection(tmp_path: Path) -> AssetStore:
    """Create a completed canonical asset shared by multiple authored views."""
    creator = _profile_fixture("creator-article-document.json")
    research = _profile_fixture("research-brief-document.json")
    knowledge_ids = sorted({
        reference
        for document in (creator, research)
        for section in document["sections"]
        for block in section["blocks"]
        for reference in block["knowledge_refs"]
    })
    evidence_ids = sorted({
        reference
        for document in (creator, research)
        for section in document["sections"]
        for block in section["blocks"]
        for reference in block["evidence_refs"]
    })
    asset = AssetStore.create(tmp_path / "assets", "asset-001", {"kind": "local_video"})
    metadata = asset.root / "source" / "metadata.json"
    metadata.write_text('{"title":"completed general asset"}\n', encoding="utf-8")
    evidence = asset.write_jsonl(
        "evidence/timeline.jsonl",
        [
            {
                "evidence_id": evidence_id,
                "origin": "external" if evidence_id == "ext-user-001" else "video",
                **(
                    {
                        "provenance": "user_supplied",
                        "acquisition": "user_supplied",
                        "url": "https://example.test/user-background",
                        "author": "User",
                        "publication_date": "2026-01-01",
                        "accessed_at": "2026-01-02",
                        "supporting_snippet": "User-provided background only.",
                    }
                    if evidence_id == "ext-user-001"
                    else {}
                ),
            }
            for evidence_id in evidence_ids
        ],
    )
    statuses = {
        "ku-video": "video_explicit",
        "ku-inference": "agent_inference",
        "ku-external": "external_enrichment",
        "ku-limit": "insufficient_evidence",
    }
    knowledge = asset.write_jsonl(
        "knowledge/units.jsonl",
        [
            {"unit_id": knowledge_id, "epistemic_status": statuses.get(knowledge_id, "video_explicit")}
            for knowledge_id in knowledge_ids
        ],
    )
    asset.complete_stage("source", [metadata])
    asset.complete_stage("evidence", [evidence])
    asset.complete_stage("knowledge", [knowledge])
    return asset


def test_reproject_profile_documents_preserves_completed_general_asset_canonical_hash_tree(
    tmp_path: Path,
) -> None:
    asset = _completed_general_asset_for_reprojection(tmp_path)
    before = canonical_hash_tree(asset)

    outputs = reproject_profile_documents(
        asset,
        {
            "creator-article": _profile_fixture("creator-article-document.json"),
            "research-brief": _profile_fixture("research-brief-document.json"),
        },
    )

    assert set(before) == {"source/metadata.json", "evidence/timeline.jsonl", "knowledge/units.jsonl"}
    assert canonical_hash_tree(asset) == before
    assert outputs["creator-article"] == asset.root / "views" / "creator-article" / "document.json"
    assert outputs["creator-article"].is_file()
    assert outputs["research-brief"].is_file()


def test_reproject_research_brief_without_canonical_agent_inference_fails_before_mutation(
    tmp_path: Path,
) -> None:
    document = _profile_fixture("research-brief-document.json")
    asset = _asset_with_canonical_profile_records(
        tmp_path,
        document,
        evidence_records={
            "ext-user-001": {
                "origin": "external",
                "provenance": "user_supplied",
                "acquisition": "user_supplied",
                "url": "https://example.test/user-background",
                "author": "User",
                "publication_date": "2026-01-01",
                "accessed_at": "2026-01-02",
                "supporting_snippet": "User-provided background only.",
            }
        },
    )
    canonical_before = canonical_hash_tree(asset)
    manifest_before = (asset.root / "manifest.json").read_bytes()

    with pytest.raises(ValueError, match="canonical status 'video_explicit' in analysis_inference"):
        reproject_profile_documents(asset, {"research-brief": document})

    assert canonical_hash_tree(asset) == canonical_before
    assert (asset.root / "manifest.json").read_bytes() == manifest_before
    assert not (asset.root / "views" / "research-brief").exists()


def test_p3_projection_requires_a_reviewed_frame_to_be_rendered_when_available(tmp_path: Path) -> None:
    """A text mention of a checked frame is not a visual projection."""
    document = _profile_fixture("creator-article-document.json")
    asset = _asset_with_canonical_profile_records(
        tmp_path,
        document,
        evidence_records={
            "ev-4": {
                "modality": "frame",
                "artifact_ref": "source/frames/scene.jpg",
                "quality": {"review": "directly_inspected"},
            }
        },
    )

    with pytest.raises(ValueError, match="must include an image backed by a directly inspected frame"):
        reproject_profile_documents(asset, {"creator-article": document})

    visual = {
        "kind": "image",
        "path": "source/frames/scene.jpg",
        "caption": "The reviewed source frame shows the input, process, and output relationship.",
        "knowledge_refs": ["ku-evidence"],
        "evidence_refs": ["ev-4"],
        "source_spans": [{"start_ms": 15_000, "end_ms": 22_000}],
    }
    document["sections"][3]["blocks"].append(visual)  # type: ignore[index]
    document["sections"][2]["blocks"][0]["text"] *= 10  # type: ignore[index]
    document["sections"][4]["blocks"].append({  # type: ignore[index]
        "kind": "bullet_list",
        "items": [
            "Confirm the source-backed input before starting.",
            "Record the demonstrated process step by step.",
            "Check the output against the demonstrated boundary.",
        ],
        "knowledge_refs": ["ku-takeaway"],
        "evidence_refs": ["ev-5"],
        "source_spans": [{"start_ms": 22_000, "end_ms": 28_000}],
    })

    assert reproject_profile_documents(asset, {"creator-article": document})[
        "creator-article"
    ].is_file()


def test_reproject_batch_rolls_back_an_earlier_profile_when_a_later_document_fails(
    tmp_path: Path,
) -> None:
    creator = _profile_fixture("creator-article-document.json")
    enterprise = _profile_fixture("enterprise-knowledge-document.json")
    asset = _asset_with_canonical_profile_records(tmp_path, creator)
    # Supply the enterprise references to the canonical layer too; its profile
    # failure below is deliberate rather than an unrelated missing-ref error.
    asset.write_jsonl(
        "knowledge/units.jsonl",
        [
            {"unit_id": reference, "epistemic_status": "video_explicit"}
            for document in (creator, enterprise)
            for section in document["sections"]
            for block in section["blocks"]
            for reference in block["knowledge_refs"]
        ],
    )
    asset.write_jsonl(
        "evidence/timeline.jsonl",
        [
            {"evidence_id": reference, "origin": "video"}
            for document in (creator, enterprise)
            for section in document["sections"]
            for block in section["blocks"]
            for reference in block["evidence_refs"]
        ],
    )
    invalid_enterprise = deepcopy(enterprise)
    invalid_enterprise["sections"][0]["blocks"][0]["source_spans"] = []  # type: ignore[index]
    manifest_before = (asset.root / "manifest.json").read_bytes()
    canonical_before = canonical_hash_tree(asset)

    with pytest.raises(ValueError, match="canonical video evidence requires document source_spans"):
        reproject_profile_documents(
            asset,
            {"creator-article": creator, "enterprise-knowledge": invalid_enterprise},
        )

    assert canonical_hash_tree(asset) == canonical_before
    assert (asset.root / "manifest.json").read_bytes() == manifest_before
    assert not (asset.root / "views" / "creator-article").exists()
    assert not (asset.root / "views" / "enterprise-knowledge").exists()


@pytest.mark.parametrize("outline_payload", [None, {"sections": []}])
def test_course_profile_requires_a_valid_asset_teaching_outline_before_writing(
    tmp_path: Path, outline_payload: object | None
) -> None:
    document = _profile_fixture("creator-article-document.json")
    document["profile_id"] = "course-notes"
    document["teaching_outline_ref"] = "knowledge/teaching_outline.json"
    asset = _asset_with_canonical_profile_records(tmp_path, document)
    if outline_payload is not None:
        (asset.root / "knowledge" / "teaching_outline.json").write_text(
            json.dumps(outline_payload), encoding="utf-8"
        )
    canonical_before = canonical_hash_tree(asset)
    manifest_before = (asset.root / "manifest.json").read_bytes()

    with pytest.raises(ValueError, match="teaching outline"):
        write_profile_document(asset, profile_id="course-notes", document=document)

    assert canonical_hash_tree(asset) == canonical_before
    assert (asset.root / "manifest.json").read_bytes() == manifest_before
    assert not (asset.root / "views" / "course-notes").exists()


def test_profile_batch_serializes_concurrent_profile_writes(tmp_path: Path) -> None:
    creator = _profile_fixture("creator-article-document.json")
    enterprise = _profile_fixture("enterprise-knowledge-document.json")
    asset = _asset_with_canonical_profile_records(tmp_path, creator)
    asset.write_jsonl(
        "knowledge/units.jsonl",
        [
            {"unit_id": reference, "epistemic_status": "video_explicit"}
            for document in (creator, enterprise)
            for section in document["sections"]
            for block in section["blocks"]
            for reference in block["knowledge_refs"]
        ],
    )
    asset.write_jsonl(
        "evidence/timeline.jsonl",
        [
            {"evidence_id": reference, "origin": "video"}
            for document in (creator, enterprise)
            for section in document["sections"]
            for block in section["blocks"]
            for reference in block["evidence_refs"]
        ],
    )
    failures: list[BaseException] = []

    def project(profile_id: str, payload: dict[str, object]) -> None:
        try:
            reproject_profile_documents(asset, {profile_id: payload})
        except BaseException as exc:  # pragma: no cover - asserted below
            failures.append(exc)

    first = threading.Thread(target=project, args=("creator-article", creator))
    second = threading.Thread(target=project, args=("enterprise-knowledge", enterprise))
    first.start()
    second.start()
    first.join(timeout=10)
    second.join(timeout=10)

    assert not first.is_alive() and not second.is_alive()
    assert failures == []
    manifest = json.loads((asset.root / "manifest.json").read_text(encoding="utf-8"))
    assert {"views/creator-article", "views/enterprise-knowledge"} <= set(manifest["stages"])
    assert {"creator-article", "enterprise-knowledge"} <= set(manifest["profile_selections"])


def test_explicit_profile_wins_over_a_recognized_intent_label() -> None:
    selection = route_profile(
        explicit_profile="enterprise-knowledge",
        intent="写成公众号长文",
    )

    assert selection.profile_id == "enterprise-knowledge"
    assert selection.selection_source == "explicit_profile"


def test_no_profile_or_intent_defaults_to_general_deep() -> None:
    selection = route_profile(None, None)

    assert selection.profile_id == "general-deep"
    assert selection.selection_source == "default"
    assert selection.requested_formats == ()
    assert selection.formats == ("pdf",)


def test_new_profile_specs_are_registered_with_approved_contracts() -> None:
    deep_summary = get_profile("deep-summary")
    assert deep_summary.required_sections == (
        "overview",
        "logical_body",
        "limitations",
        "source_navigation",
    )
    assert deep_summary.reference_path == "references/profile-general-deep.md"

    deep_article = get_profile("deep-article")
    assert deep_article.required_sections == (
        "reader_promise",
        "core_point",
        "narrative",
        "video_evidence",
        "actionable_takeaway",
        "limitations_sources",
    )
    assert deep_article.reference_path == "references/profile-creator-article.md"

    short_script = get_profile("short-video-script")
    assert short_script.required_sections == (
        "hook",
        "context",
        "core_point",
        "evidence",
        "payoff",
        "closing",
    )
    assert short_script.formats == ("pdf",)
    assert short_script.reference_path == "references/profile-short-video-script.md"
    assert short_script.renderer_options == {"source_navigation": False}
    errors = short_script.validator({"sections": []})
    assert errors[:6] == [
        "short-video-script needs hook",
        "short-video-script needs context",
        "short-video-script needs core point",
        "short-video-script needs evidence",
        "short-video-script needs payoff",
        "short-video-script needs closing",
    ]
    assert "short-video-script sections must follow the required hook-to-closing order" in errors
    assert "short-video-script prose is too abstract; add concrete script beats" in errors


def test_new_profile_fixtures_stay_valid() -> None:
    assert validate_document_quality(_profile_fixture("deep-article-document.json")) == []
    assert validate_document_quality(
        _profile_fixture("short-video-script-document.json")
    ) == []


@pytest.mark.parametrize("intent", ["短视频脚本", "写成短视频脚本"])
def test_short_video_script_intent_labels_route_to_short_video_script(intent: str) -> None:
    selection = route_profile(None, intent)

    assert selection.profile_id == "short-video-script"
    assert selection.selection_source == "intent_label"


def test_legacy_profiles_remain_registered_and_compatible() -> None:
    assert get_profile("general-deep").profile_id == "general-deep"
    assert get_profile("creator-article").profile_id == "creator-article"
    assert route_profile(None, None).profile_id == "general-deep"
    assert route_profile(None, "写成公众号长文").profile_id == "creator-article"


def test_unknown_explicit_profile_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown profile"):
        route_profile(explicit_profile="meeting-minutes", intent=None)


def test_registered_intent_label_is_auditable_without_free_text_inference() -> None:
    selection = route_profile(None, "写成公众号长文")

    assert selection.profile_id == "creator-article"
    assert selection.selection_source == "intent_label"
    assert selection.requested == {"explicit_profile": None, "intent": "写成公众号长文"}


def test_profile_selection_writes_view_and_asset_manifests(tmp_path) -> None:
    asset = AssetStore.create(
        tmp_path / "assets",
        "asset-001",
        {"kind": "bilibili", "bvid": "BV1test"},
    )

    selection = write_profile_selection(
        asset,
        explicit_profile=None,
        intent="研究简报",
        requested_formats=("pdf",),
    )

    view_manifest = json.loads(
        (asset.root / "views" / "research-brief" / "view-manifest.json").read_text(
            encoding="utf-8"
        )
    )
    asset_manifest = json.loads((asset.root / "manifest.json").read_text(encoding="utf-8"))
    assert view_manifest["profile_id"] == "research-brief"
    assert view_manifest["selection"] == selection.model_dump(mode="json")
    assert view_manifest["requested_formats"] == ["pdf"]
    assert view_manifest["formats"] == ["pdf"]
    assert asset_manifest["profile_selection"] == selection.model_dump(mode="json")
    assert asset_manifest["requested_formats"] == ["pdf"]
    assert asset_manifest["formats"] == ["pdf"]
    # Routing is an authoring decision, not completion of the eventual view.
    # The authoring stage later hashes both this manifest and document.json.
    assert "views/research-brief" not in asset_manifest["stages"]


def test_profile_specs_keep_formats_immutable() -> None:
    profile = get_profile("general-deep")

    assert profile.formats == ("pdf",)
    with pytest.raises(FrozenInstanceError):
        profile.formats = ()  # type: ignore[misc]


@pytest.mark.parametrize(
    ("profile_id", "section_kinds"),
    [
        (
            "creator-article",
            (
                "reader_promise",
                "core_point",
                "narrative",
                "video_evidence",
                "actionable_takeaway",
                "limitations_sources",
            ),
        ),
        (
            "enterprise-knowledge",
            (
                "purpose_scope",
                "terminology",
                "process_practice",
                "roles_inputs_outputs",
                "risks",
                "limitations_sources",
            ),
        ),
        (
            "research-brief",
            (
                "video_evidence",
                "analysis_inference",
                "external_enrichment",
                "limitations_questions",
                "source_navigation",
            ),
        ),
    ],
)
def test_registered_non_p1_profiles_enforce_required_sections(
    profile_id: str, section_kinds: tuple[str, ...]
) -> None:
    document = {
        "profile_id": profile_id,
        "title": "Decision record",
        "sections": [
            {
                "kind": section_kind,
                "title": section_kind.replace("_", " ").title(),
                "blocks": [
                    {
                        "kind": "paragraph",
                        "text": "The source establishes the operating constraint.",
                        "knowledge_refs": ["ku-1"],
                        "evidence_refs": ["ev-1"],
                        "source_spans": [{"start_ms": 0, "end_ms": 1_000}],
                    }
                ],
            }
            for section_kind in section_kinds
        ],
    }

    if profile_id == "research-brief":
        for section in document["sections"]:
            block = section["blocks"][0]
            block["data"] = {
                "claim_status": "video_explicit",
                "source_category": "video_explicit",
                "visible_label": "视频明确指出",
                "structured_refs": [{
                    "knowledge_id": "ku-1",
                    "evidence_id": "ev-1",
                    "source_category": "video_explicit",
                }],
            }
        document["sections"][1]["blocks"][0]["data"].update({
            "claim_status": "agent_inference",
            "source_category": "agent_inference",
            "visible_label": "分析与推断",
        })
        document["sections"][2]["blocks"][0]["data"].update({
            "claim_status": "external_enrichment",
            "source_category": "external_enrichment",
            "visible_label": "用户提供资料",
        })
        document["sections"][3]["blocks"][0]["data"].update({
            "claim_status": "insufficient_evidence",
            "source_category": "insufficient_evidence",
            "visible_label": "争议、限制、待验证问题",
        })
        for index in range(1, 4):
            data = document["sections"][index]["blocks"][0]["data"]
            data["structured_refs"][0]["source_category"] = data["source_category"]
        document["sections"][4]["blocks"][0]["data"].update({
            "claim_status": "source_navigation",
            "source_category": "source_navigation",
            "visible_label": "来源导航",
        })
        document["sections"][4]["blocks"][0]["data"]["structured_refs"] = [
            {
                "knowledge_id": "ku-1",
                "evidence_id": "ev-1",
                "source_category": category,
            }
            for category in (
                "video_explicit",
                "agent_inference",
                "external_enrichment",
                "insufficient_evidence",
            )
        ]

    assert validate_document_quality(document) == []


def _research_fixture() -> dict[str, object]:
    return _profile_fixture("research-brief-document.json")


def _research_asset(tmp_path: Path, document: dict[str, object]) -> AssetStore:
    return _asset_with_canonical_profile_records(
        tmp_path,
        document,
        knowledge_statuses={
            "ku-video": "video_explicit",
            "ku-inference": "agent_inference",
            "ku-external": "external_enrichment",
            "ku-limit": "insufficient_evidence",
            "ku-source": "video_explicit",
        },
        evidence_records={
            "ext-user-001": {
                "origin": "external",
                "provenance": "user_supplied",
                "acquisition": "user_supplied",
                "url": "https://example.test/user-material",
                "institution": "Example Research Group",
                "publication_date": "2026-07-01",
                "accessed_at": "2026-07-12T10:00:00Z",
                "supporting_snippet": "The supplied material provides background only.",
            }
        },
    )


def test_research_rejects_inference_labelled_as_video_claim() -> None:
    document = _research_fixture()
    claim = document["sections"][1]["blocks"][0]  # type: ignore[index]
    claim["data"]["visible_label"] = "视频明确指出"

    assert validate_profile_document("research-brief", document) == [
        "research-brief claim ku-inference labels agent inference as video evidence"
    ]


@pytest.mark.parametrize(
    "wording",
    [
        "视频表明",
        "视频中的讲者认为",
        "视频里讲者认为",
        "根据视频可知",
        "从视频中可以看出",
        "从视频里得知",
        "视频讲解",
        "视频介绍",
        "视频讨论",
        "视频展示",
        "视频演示",
        "视频说明",
        "视频呈现",
        "视频讲了",
        "视频讲述",
        "录像显示",
        "录屏说明",
        "录制内容表明",
        "video explicitly states",
        "the presenter in the video argues",
        "according to the video",
        "the video shows",
        "from the video we can see",
        "the video demonstrates",
        "the recording shows",
        "the recording points out",
        "the recording pointed out",
        "the footage will explain",
        "the clip points out",
        "片段说明",
        "the videos claim",
        "recordings explain",
        "影片说明",
        "影像显示",
        "the lecture argues",
        "the talk shows",
        "the webinar says",
        "the tutorial demonstrates",
        "讲座说明",
        "演讲表明",
        "教程讲解",
        "在视频中，讲者强调",
        "讲者将该流程定义为",
        "视频没有讨论",
        "the speaker frames the issue as",
        "in the video, the method is",
    ],
)
def test_research_rejects_inference_worded_as_a_video_claim(wording: str) -> None:
    document = _research_fixture()
    claim = document["sections"][1]["blocks"][0]  # type: ignore[index]
    claim["text"] = f"{wording}: 该流程可降低遗漏输入和未复核输出的风险。"

    assert validate_profile_document("research-brief", document) == [
        "research-brief claim ku-inference labels agent inference as video evidence"
    ]


@pytest.mark.parametrize(
    "wording",
    [
        "从视频中可以看出",
        "在视频中，讲者强调",
        "the video demonstrates",
        "the speaker frames the issue as",
        "the recording points out",
        "the recording pointed out",
        "the clip points out",
        "recordings explain",
        "the tutorial demonstrates",
    ],
)
def test_research_writer_rejects_inference_worded_as_video_evidence(
    tmp_path: Path, wording: str
) -> None:
    document = _research_fixture()
    document["sections"][1]["blocks"][0]["text"] = f"{wording}: this is reliable."  # type: ignore[index]
    asset = _research_asset(tmp_path, document)

    with pytest.raises(ValueError, match="ku-inference labels agent inference as video evidence"):
        write_profile_document(asset, profile_id="research-brief", document=document)


def test_research_does_not_treat_neutral_source_navigation_as_an_inference_claim() -> None:
    document = _research_fixture()
    navigation = document["sections"][4]["blocks"][0]  # type: ignore[index]
    navigation["text"] = "根据视频可知，来源导航保留了每类主张的结构化引用。"

    assert validate_profile_document("research-brief", document) == []


def test_research_allows_neutral_inference_without_video_attribution() -> None:
    document = _research_fixture()
    document["sections"][1]["blocks"][0]["text"] = (
        "分析与推断：将输入确认和输出复核分开，有助于减少遗漏风险。"
    )  # type: ignore[index]

    assert validate_profile_document("research-brief", document) == []


@pytest.mark.parametrize("title", ["视频明确指出 X", "The webinar explains X"])
def test_research_rejects_video_attribution_in_analysis_section_title(title: str) -> None:
    document = _research_fixture()
    document["sections"][1]["title"] = title  # type: ignore[index]

    assert validate_profile_document("research-brief", document) == [
        "research-brief claim ku-inference labels agent inference as video evidence"
    ]


def test_research_writer_rejects_video_attribution_in_analysis_section_title(tmp_path: Path) -> None:
    document = _research_fixture()
    document["sections"][1]["title"] = "The recording points out X"  # type: ignore[index]
    asset = _research_asset(tmp_path, document)

    with pytest.raises(ValueError, match="ku-inference labels agent inference as video evidence"):
        write_profile_document(asset, profile_id="research-brief", document=document)


def test_research_allows_a_neutral_analysis_section_title() -> None:
    document = _research_fixture()
    document["sections"][1]["title"] = "分析与推断"

    assert validate_profile_document("research-brief", document) == []


@pytest.mark.parametrize(
    "text",
    [
        "This analysis goes beyond the video.",
        "本分析超出视频范围。",
    ],
)
def test_research_allows_a_narrow_beyond_video_limitation(text: str) -> None:
    document = _research_fixture()
    document["sections"][1]["blocks"][0]["text"] = text  # type: ignore[index]

    assert validate_profile_document("research-brief", document) == []


@pytest.mark.parametrize(
    "text",
    [
        "This analysis goes beyond the video, but the recording shows a fixed process.",
        "本分析超出视频范围，但录像说明了固定流程。",
    ],
)
def test_research_rejects_a_composite_limitation_and_media_claim(text: str) -> None:
    document = _research_fixture()
    document["sections"][1]["blocks"][0]["text"] = text  # type: ignore[index]

    assert validate_profile_document("research-brief", document) == [
        "research-brief claim ku-inference labels agent inference as video evidence"
    ]


def test_research_rejects_structured_ref_with_a_mismatched_source_category() -> None:
    document = _research_fixture()
    inference = document["sections"][1]["blocks"][0]  # type: ignore[index]
    inference["data"]["structured_refs"][0]["source_category"] = "video_explicit"

    assert "research-brief claims must preserve matching structured refs" in (
        validate_profile_document("research-brief", document)
    )


def test_research_writer_rejects_a_structured_pair_not_linked_by_canonical_knowledge(
    tmp_path: Path,
) -> None:
    document = _research_fixture()
    inference = document["sections"][1]["blocks"][0]  # type: ignore[index]
    inference["evidence_refs"] = ["ev-video"]
    inference["data"]["structured_refs"][0]["evidence_id"] = "ev-video"
    asset = _research_asset(tmp_path, document)
    units_path = asset.root / "knowledge" / "units.jsonl"
    units = [json.loads(line) for line in units_path.read_text(encoding="utf-8").splitlines()]
    next(unit for unit in units if unit["unit_id"] == "ku-inference")["evidence_refs"] = [
        "ev-inference"
    ]
    units_path.write_text("".join(json.dumps(unit) + "\n" for unit in units), encoding="utf-8")

    with pytest.raises(ValueError, match="ku-inference/ev-video is not canonical"):
        write_profile_document(asset, profile_id="research-brief", document=document)


def test_research_source_navigation_covers_each_represented_source_category() -> None:
    document = _research_fixture()
    navigation = document["sections"][4]["blocks"][0]  # type: ignore[index]
    navigation["data"]["structured_refs"] = [
        item
        for item in navigation["data"]["structured_refs"]
        if item["source_category"] not in {"agent_inference", "external_enrichment"}
    ]

    assert (
        "research-brief source navigation is missing categories: agent_inference, external_enrichment"
        in validate_profile_document("research-brief", document)
    )


def test_research_accepts_existing_user_supplied_external_evidence(tmp_path: Path) -> None:
    document = _research_fixture()
    asset = _research_asset(tmp_path, document)

    assert validate_profile_document("research-brief", document) == []
    assert write_profile_document(asset, profile_id="research-brief", document=document).is_file()


def test_research_writer_accepts_an_explicit_not_used_external_section(tmp_path: Path) -> None:
    document = _research_fixture()
    external = document["sections"][2]["blocks"][0]  # type: ignore[index]
    external["text"] = "未使用外部资料：本简报未引入视频以外的事实。"
    external["knowledge_refs"] = ["ku-limit"]
    external["evidence_refs"] = ["ev-limit"]
    external["source_spans"] = [{"start_ms": 9000, "end_ms": 12000}]
    external["data"] = {
        "claim_status": "not_used",
        "source_category": "not_used",
        "visible_label": "未使用外部资料",
        "structured_refs": [{
            "knowledge_id": "ku-limit",
            "evidence_id": "ev-limit",
            "source_category": "not_used",
        }],
    }
    document["evidence_origins"].pop("ext-user-001")  # type: ignore[index]
    navigation = document["sections"][4]["blocks"][0]  # type: ignore[index]
    navigation["knowledge_refs"] = ["ku-video", "ku-inference", "ku-limit"]
    navigation["evidence_refs"] = ["ev-video", "ev-inference", "ev-limit"]
    navigation["data"]["structured_refs"] = [
        item
        for item in navigation["data"]["structured_refs"]
        if item["source_category"] != "external_enrichment"
    ]
    asset = _research_asset(tmp_path, document)

    assert write_profile_document(asset, profile_id="research-brief", document=document).is_file()


def test_research_writer_rejects_external_evidence_without_required_user_material_metadata(
    tmp_path: Path,
) -> None:
    document = _research_fixture()
    asset = _asset_with_canonical_profile_records(
        tmp_path,
        document,
        knowledge_statuses={
            "ku-video": "video_explicit",
            "ku-inference": "agent_inference",
            "ku-external": "external_enrichment",
            "ku-limit": "insufficient_evidence",
            "ku-source": "video_explicit",
        },
        evidence_records={
            "ext-user-001": {
                "origin": "external",
                "provenance": "user_supplied",
                "acquisition": "user_supplied",
            }
        },
    )

    with pytest.raises(ValueError, match="ext-user-001 lacks required user-material metadata"):
        write_profile_document(asset, profile_id="research-brief", document=document)


@pytest.mark.parametrize("acquisition", ["web-search", "web search", "web_search_via"])
def test_research_writer_rejects_non_user_supplied_external_acquisition(
    tmp_path: Path, acquisition: str
) -> None:
    document = _research_fixture()
    asset = _research_asset(tmp_path, document)
    timeline = asset.root / "evidence" / "timeline.jsonl"
    records = [json.loads(line) for line in timeline.read_text(encoding="utf-8").splitlines()]
    next(record for record in records if record["evidence_id"] == "ext-user-001")["acquisition"] = acquisition
    timeline.write_text(
        "".join(json.dumps(record) + "\n" for record in records), encoding="utf-8"
    )

    with pytest.raises(ValueError, match="must use an explicit user-supplied acquisition"):
        write_profile_document(asset, profile_id="research-brief", document=document)


def test_research_writer_rejects_external_evidence_in_video_viewpoint(tmp_path: Path) -> None:
    document = _research_fixture()
    video_claim = document["sections"][0]["blocks"][0]  # type: ignore[index]
    video_claim["knowledge_refs"] = ["ku-external"]
    video_claim["evidence_refs"] = ["ext-user-001"]
    video_claim["source_spans"] = []
    video_claim["data"]["structured_refs"] = [{  # type: ignore[index]
        "knowledge_id": "ku-external",
        "evidence_id": "ext-user-001",
        "source_category": "video_explicit",
    }]
    asset = _research_asset(tmp_path, document)

    with pytest.raises(ValueError, match="ku-external has canonical status 'external_enrichment' in video_evidence"):
        write_profile_document(asset, profile_id="research-brief", document=document)


def test_research_requires_explicit_not_used_external_section_and_source_navigation() -> None:
    document = _research_fixture()
    document["sections"] = document["sections"][:-1]  # type: ignore[index]
    document["sections"][2]["blocks"][0]["data"]["claim_status"] = "not_used"  # type: ignore[index]
    document["sections"][2]["blocks"][0]["data"]["source_category"] = "not_used"  # type: ignore[index]
    document["sections"][2]["blocks"][0]["data"]["visible_label"] = "未使用外部资料"  # type: ignore[index]

    errors = validate_profile_document("research-brief", document)

    assert "research-brief needs source navigation" in errors
    assert "research-brief sections must follow the required evidence-separated order" in errors


def test_creator_article_fixture_meets_reader_and_source_policy() -> None:
    document = _profile_fixture("creator-article-document.json")

    assert validate_document_quality(document) == []


def test_creator_article_rejects_invented_author_experience_or_business_outcome() -> None:
    document = deepcopy(_profile_fixture("creator-article-document.json"))
    document["sections"][2]["blocks"][0]["text"] = "我亲自用这套方法赚到十万。"  # type: ignore[index]

    assert "creator-article must not invent author experience or outcome" in (
        validate_document_quality(document)
    )


@pytest.mark.parametrize("mutation", ["reversed", "empty"])
def test_creator_article_requires_exact_section_order_and_nonempty_content(mutation: str) -> None:
    document = deepcopy(_profile_fixture("creator-article-document.json"))
    if mutation == "reversed":
        document["sections"] = list(reversed(document["sections"]))  # type: ignore[index]
        expected = "creator-article sections must follow the required semantic order"
    else:
        document["sections"][1]["blocks"] = []  # type: ignore[index]
        expected = "creator-article section 'core_point' must contain non-empty content blocks"

    assert expected in validate_document_quality(document)


def test_creator_article_rejects_a_data_only_required_section() -> None:
    document = deepcopy(_profile_fixture("creator-article-document.json"))
    document["sections"][1]["blocks"] = [{  # type: ignore[index]
        "kind": "paragraph",
        "data": {"internal_hint": "not visible to readers"},
        "knowledge_refs": ["ku-core"],
        "evidence_refs": ["ev-2"],
        "source_spans": [{"start_ms": 4000, "end_ms": 9000}],
    }]

    assert "creator-article section 'core_point' must contain non-empty content blocks" in (
        validate_document_quality(document)
    )


def test_creator_article_quality_allows_a_grounded_quote_for_writer_provenance_check() -> None:
    document = deepcopy(_profile_fixture("creator-article-document.json"))
    document["sections"][3]["blocks"][0]["kind"] = "quote"  # type: ignore[index]

    assert validate_document_quality(document) == []


def test_enterprise_knowledge_fixture_meets_operational_policy() -> None:
    document = _profile_fixture("enterprise-knowledge-document.json")

    assert validate_document_quality(document) == []


def test_enterprise_knowledge_rejects_unsourced_decision_or_action_item() -> None:
    document = deepcopy(_profile_fixture("enterprise-knowledge-document.json"))
    document["sections"] = [  # type: ignore[index]
        section
        for section in document["sections"]  # type: ignore[index]
        if section["kind"] != "purpose_scope"
    ]
    document["sections"][2]["blocks"][0]["text"] = "下周必须上线。"  # type: ignore[index]

    errors = validate_document_quality(document)

    assert "enterprise-knowledge needs purpose/scope and applicability" in errors
    assert "enterprise-knowledge cannot present unsourced decisions/action items" in errors


def test_enterprise_action_requires_insufficient_marker_on_the_same_content_block() -> None:
    document = deepcopy(_profile_fixture("enterprise-knowledge-document.json"))
    document["sections"][2]["blocks"][0]["text"] = "下周必须上线。"  # type: ignore[index]
    document["sections"][-1]["blocks"][0]["text"] += "证据不足。"  # type: ignore[index]

    assert "enterprise-knowledge cannot present unsourced decisions/action items" in (
        validate_document_quality(document)
    )


def test_enterprise_action_requires_insufficient_marker_on_the_same_sentence() -> None:
    document = deepcopy(_profile_fixture("enterprise-knowledge-document.json"))
    document["sections"][2]["blocks"][0]["text"] = "下周必须上线。视频未说明，需要确认。"  # type: ignore[index]

    assert "enterprise-knowledge cannot present unsourced decisions/action items" in (
        validate_document_quality(document)
    )


def test_enterprise_action_allows_an_explicit_same_sentence_insufficient_marker() -> None:
    document = deepcopy(_profile_fixture("enterprise-knowledge-document.json"))
    document["sections"][2]["blocks"][0]["text"] = "下周必须上线，但视频未说明，需要确认。"  # type: ignore[index]

    assert validate_document_quality(document) == []


def test_enterprise_action_rejects_a_block_status_waiver_without_same_sentence_evidence() -> None:
    document = deepcopy(_profile_fixture("enterprise-knowledge-document.json"))
    block = document["sections"][2]["blocks"][0]  # type: ignore[index]
    block["text"] = "下周必须上线。"
    block["data"] = {"epistemic_status": "insufficient_evidence"}

    assert "enterprise-knowledge cannot present unsourced decisions/action items" in (
        validate_document_quality(document)
    )


@pytest.mark.parametrize(
    ("profile_id", "fixture_name"),
    [
        ("creator-article", "creator-article-document.json"),
        ("enterprise-knowledge", "enterprise-knowledge-document.json"),
    ],
)
def test_profile_writer_projects_validated_document_without_mutating_canonical_records(
    tmp_path: Path, profile_id: str, fixture_name: str
) -> None:
    document = _profile_fixture(fixture_name)
    asset = _asset_with_canonical_profile_records(tmp_path, document)
    canonical_before = {
        path.relative_to(asset.root).as_posix(): path.read_bytes()
        for directory in ("evidence", "knowledge")
        for path in (asset.root / directory).rglob("*")
        if path.is_file()
    }

    output = write_profile_document(asset, profile_id=profile_id, document=document)

    assert output == asset.root / "views" / profile_id / "document.json"
    assert json.loads(output.read_text(encoding="utf-8")) == document
    assert (output.parent / "view-manifest.json").is_file()
    assert asset.verify_stage(f"views/{profile_id}", schema_version="1.1") == []
    manifest = json.loads((asset.root / "manifest.json").read_text(encoding="utf-8"))
    assert {entry["path"] for entry in manifest["stages"][f"views/{profile_id}"]["outputs"]} == {
        f"views/{profile_id}/view-manifest.json",
        f"views/{profile_id}/document.json",
    }
    canonical_after = {
        path.relative_to(asset.root).as_posix(): path.read_bytes()
        for directory in ("evidence", "knowledge")
        for path in (asset.root / directory).rglob("*")
        if path.is_file()
    }
    assert canonical_after == canonical_before


def test_profile_writer_preserves_an_existing_selected_profile_route_and_formats(tmp_path: Path) -> None:
    document = _profile_fixture("creator-article-document.json")
    asset = _asset_with_canonical_profile_records(tmp_path, document)
    selected = write_profile_selection(
        asset,
        explicit_profile=None,
        intent="公众号长文",
        requested_formats=("pdf",),
    )

    write_profile_document(asset, profile_id="creator-article", document=document)

    view_manifest = json.loads(
        (asset.root / "views" / "creator-article" / "view-manifest.json").read_text(
            encoding="utf-8"
        )
    )
    asset_manifest = json.loads((asset.root / "manifest.json").read_text(encoding="utf-8"))
    assert view_manifest["selection"] == selected.model_dump(mode="json")
    assert view_manifest["requested_formats"] == ["pdf"]
    assert view_manifest["formats"] == ["pdf"]
    assert asset_manifest["profile_selections"]["creator-article"] == selected.model_dump(
        mode="json"
    )


def test_profile_writer_rejects_inconsistent_existing_selection_manifests(tmp_path: Path) -> None:
    document = _profile_fixture("creator-article-document.json")
    asset = _asset_with_canonical_profile_records(tmp_path, document)
    write_profile_selection(asset, explicit_profile="creator-article", intent=None)
    view_path = asset.root / "views" / "creator-article" / "view-manifest.json"
    view_manifest = json.loads(view_path.read_text(encoding="utf-8"))
    view_manifest["selection"]["reason"] = "tampered"
    view_path.write_text(json.dumps(view_manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="profile selection manifests disagree"):
        write_profile_document(asset, profile_id="creator-article", document=document)


@pytest.mark.parametrize(
    ("reference_field", "missing_id", "expected_error"),
    [
        ("knowledge_refs", "ku-absent", "unknown canonical knowledge IDs: ku-absent"),
        ("evidence_refs", "ev-absent", "unknown canonical evidence IDs: ev-absent"),
    ],
)
def test_profile_writer_rejects_unknown_canonical_references_without_mutation(
    tmp_path: Path, reference_field: str, missing_id: str, expected_error: str
) -> None:
    document = _profile_fixture("creator-article-document.json")
    asset = _asset_with_canonical_profile_records(tmp_path, document)
    invalid = deepcopy(document)
    invalid["sections"][0]["blocks"][0][reference_field] = [missing_id]  # type: ignore[index]
    canonical_before = {
        path.relative_to(asset.root).as_posix(): path.read_bytes()
        for directory in ("evidence", "knowledge")
        for path in (asset.root / directory).rglob("*")
        if path.is_file()
    }

    with pytest.raises(ValueError, match=expected_error):
        write_profile_document(asset, profile_id="creator-article", document=invalid)

    assert not (asset.root / "views" / "creator-article" / "document.json").exists()
    canonical_after = {
        path.relative_to(asset.root).as_posix(): path.read_bytes()
        for directory in ("evidence", "knowledge")
        for path in (asset.root / directory).rglob("*")
        if path.is_file()
    }
    assert canonical_after == canonical_before


def test_profile_writer_allows_quote_backed_by_video_explicit_canonical_knowledge(tmp_path: Path) -> None:
    document = deepcopy(_profile_fixture("creator-article-document.json"))
    document["sections"][3]["blocks"][0]["kind"] = "quote"  # type: ignore[index]
    asset = _asset_with_canonical_profile_records(tmp_path, document)

    assert write_profile_document(asset, profile_id="creator-article", document=document).is_file()


def test_profile_writer_rejects_quote_with_nonvideo_canonical_evidence_even_if_document_claims_video(
    tmp_path: Path,
) -> None:
    document = deepcopy(_profile_fixture("creator-article-document.json"))
    document["sections"][3]["blocks"][0]["kind"] = "quote"  # type: ignore[index]
    document["evidence_origins"] = {"ev-4": "video"}
    asset = _asset_with_canonical_profile_records(
        tmp_path, document, evidence_origin="external"
    )

    with pytest.raises(ValueError, match="creator-article quotes require canonical video evidence"):
        write_profile_document(asset, profile_id="creator-article", document=document)


@pytest.mark.parametrize("case", ["unsourced", "nonexplicit"])
def test_profile_writer_rejects_quote_without_video_explicit_canonical_provenance(
    tmp_path: Path, case: str
) -> None:
    document = deepcopy(_profile_fixture("creator-article-document.json"))
    quote = document["sections"][3]["blocks"][0]  # type: ignore[index]
    quote["kind"] = "quote"
    if case == "unsourced":
        quote["evidence_refs"] = []
        asset = _asset_with_canonical_profile_records(tmp_path, document)
        expected = "document blocks must preserve evidence_refs"
    else:
        asset = _asset_with_canonical_profile_records(
            tmp_path, document, epistemic_status="agent_inference"
        )
        expected = "creator-article quotes require video_explicit canonical knowledge"

    with pytest.raises(ValueError, match=expected):
        write_profile_document(asset, profile_id="creator-article", document=document)


def test_profile_writer_rejects_enterprise_external_canonical_evidence_even_if_document_catalog_says_video(
    tmp_path: Path,
) -> None:
    document = _profile_fixture("enterprise-knowledge-document.json")
    document["evidence_origins"] = {"ev-3": "video"}
    asset = _asset_with_canonical_profile_records(
        tmp_path, document, evidence_origin="external"
    )

    with pytest.raises(
        ValueError, match="enterprise-knowledge must ground operational content in canonical video evidence"
    ):
        write_profile_document(asset, profile_id="enterprise-knowledge", document=document)


def test_profile_writer_rejects_creator_video_evidence_forged_as_external_without_source_span(
    tmp_path: Path,
) -> None:
    document = deepcopy(_profile_fixture("creator-article-document.json"))
    core_point = document["sections"][1]["blocks"][0]  # type: ignore[index]
    core_point["source_spans"] = []
    document["evidence_origins"] = {"ev-2": "external"}
    asset = _asset_with_canonical_profile_records(tmp_path, document, evidence_origin="video")

    with pytest.raises(ValueError, match="canonical video evidence requires document source_spans"):
        write_profile_document(asset, profile_id="creator-article", document=document)


def test_profile_writer_allows_genuine_canonical_external_creator_evidence_without_source_span(
    tmp_path: Path,
) -> None:
    document = deepcopy(_profile_fixture("creator-article-document.json"))
    core_point = document["sections"][1]["blocks"][0]  # type: ignore[index]
    core_point["source_spans"] = []
    document["evidence_origins"] = {"ev-2": "external"}
    asset = _asset_with_canonical_profile_records(tmp_path, document, evidence_origin="external")

    assert write_profile_document(asset, profile_id="creator-article", document=document).is_file()


def test_profile_writer_rejects_creator_document_catalog_origin_mismatch(tmp_path: Path) -> None:
    document = deepcopy(_profile_fixture("creator-article-document.json"))
    document["evidence_origins"] = {"ev-2": "video"}
    asset = _asset_with_canonical_profile_records(
        tmp_path, document, evidence_origin="external"
    )

    with pytest.raises(ValueError, match="document evidence_origins does not match canonical origin for ev-2"):
        write_profile_document(asset, profile_id="creator-article", document=document)


def test_profile_writer_rejects_unknown_document_evidence_origin_catalog_entry(tmp_path: Path) -> None:
    document = deepcopy(_profile_fixture("creator-article-document.json"))
    document["evidence_origins"] = {"ev-unknown": "external"}
    asset = _asset_with_canonical_profile_records(tmp_path, document)

    with pytest.raises(ValueError, match="unknown canonical evidence ID: ev-unknown"):
        write_profile_document(asset, profile_id="creator-article", document=document)


@pytest.mark.parametrize("failure_point", ["view", "document", "manifest"])
def test_profile_writer_rolls_back_every_path_when_commit_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure_point: str
) -> None:
    document = _profile_fixture("creator-article-document.json")
    asset = _asset_with_canonical_profile_records(tmp_path, document)
    paths = {
        asset.root / "views" / "creator-article" / "view-manifest.json": None,
        asset.root / "views" / "creator-article" / "document.json": None,
        asset.root / "manifest.json": (asset.root / "manifest.json").read_bytes(),
    }
    original_write = profiles_module._write_text_atomic
    original_manifest_write = AssetStore._write_manifest
    calls = {"count": 0}

    def fail_view_or_document(path: Path, text: str) -> None:
        calls["count"] += 1
        if (failure_point == "view" and calls["count"] == 1) or (
            failure_point == "document" and calls["count"] == 2
        ):
            raise OSError(f"{failure_point} write failed")
        original_write(path, text)

    def fail_manifest(self: AssetStore, manifest: dict[str, object]) -> None:
        if failure_point == "manifest":
            raise OSError("manifest write failed")
        original_manifest_write(self, manifest)

    monkeypatch.setattr(profiles_module, "_write_text_atomic", fail_view_or_document)
    monkeypatch.setattr(AssetStore, "_write_manifest", fail_manifest)

    with pytest.raises(OSError, match=f"{failure_point} write failed"):
        write_profile_document(asset, profile_id="creator-article", document=document)

    for path, before in paths.items():
        assert (path.read_bytes() if path.exists() else None) == before
    assert not (asset.root / "views" / "creator-article").exists()
    manifest = json.loads((asset.root / "manifest.json").read_text(encoding="utf-8"))
    assert "views/creator-article" not in manifest["stages"]
    assert not (asset.root / ".profile-write.lock").exists()


def test_registered_non_p1_profiles_reject_a_generic_paragraph_document() -> None:
    document = {
        "profile_id": "enterprise-knowledge",
        "title": "Decision record",
        "blocks": [{
            "kind": "paragraph",
            "text": "The source establishes the operating constraint.",
            "knowledge_refs": ["ku-1"],
            "evidence_refs": ["ev-1"],
            "source_spans": [{"start_ms": 0, "end_ms": 1_000}],
        }],
    }

    assert "enterprise-knowledge document must declare semantic sections" in (
        validate_document_quality(document)
    )


def test_select_profile_cli_writes_an_auditable_selection(tmp_path, capsys) -> None:
    asset = AssetStore.create(tmp_path / "assets", "asset-001", {"kind": "local_video"})

    assert main([
        "select-profile", "--asset", str(asset.root), "--intent", "课程笔记",
        "--format", "pdf",
    ]) == 0

    reported = json.loads(capsys.readouterr().out)
    assert reported["profile_id"] == "course-notes"
    assert reported["selection_source"] == "intent_label"
    assert reported["requested_formats"] == ["pdf"]
    assert reported["formats"] == ["pdf"]


@pytest.mark.parametrize(
    ("args", "expected_profile_id", "expected_selection_source"),
    [
        (
            ["select-profile", "--profile", "deep-summary"],
            "deep-summary",
            "explicit_profile",
        ),
        (
            ["select-profile", "--intent", "短视频脚本"],
            "short-video-script",
            "intent_label",
        ),
    ],
)
def test_select_profile_cli_routes_new_profiles(
    tmp_path: Path,
    capsys,
    args: list[str],
    expected_profile_id: str,
    expected_selection_source: str,
) -> None:
    asset = AssetStore.create(tmp_path / "assets", "asset-001", {"kind": "local_video"})

    assert main([*args, "--asset", str(asset.root)]) == 0

    reported = json.loads(capsys.readouterr().out)
    assert reported["profile_id"] == expected_profile_id
    assert reported["selection_source"] == expected_selection_source


def test_reproject_profile_cli_accepts_only_a_supplied_authored_document(tmp_path, capsys) -> None:
    document = _profile_fixture("creator-article-document.json")
    asset = _asset_with_canonical_profile_records(tmp_path, document)
    document_path = tmp_path / "creator.json"
    document_path.write_text(json.dumps(document), encoding="utf-8")

    assert main([
        "reproject-profile", "--asset", str(asset.root),
        "--profile", "creator-article", "--document", str(document_path),
    ]) == 0

    reported = json.loads(capsys.readouterr().out)
    assert reported["profile_id"] == "creator-article"
    assert reported["document_path"] == str(asset.root / "views" / "creator-article" / "document.json")
    assert canonical_hash_tree(asset)


def test_profile_selection_rejects_an_escaping_profile_symlink(tmp_path: Path) -> None:
    asset = AssetStore.create(tmp_path / "assets", "asset-001", {"kind": "local_video"})
    outside = tmp_path / "outside"
    outside.mkdir()
    profile_dir = asset.root / "views" / "general-deep"
    try:
        profile_dir.symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        if os.name != "nt":
            pytest.skip(f"directory symlinks unavailable: {exc}")
        junction = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(profile_dir), str(outside)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if junction.returncode != 0:
            pytest.skip(f"directory symlinks and junctions unavailable: {exc}")

    with pytest.raises(ValueError, match="symlink|within the asset root"):
        write_profile_selection(asset, explicit_profile=None, intent=None)

    assert not (outside / "view-manifest.json").exists()


def test_profile_selection_rejects_an_internal_evidence_junction(tmp_path: Path) -> None:
    asset = AssetStore.create(tmp_path / "assets", "asset-001", {"kind": "local_video"})
    profile_dir = asset.root / "views" / "general-deep"
    target = asset.root / "evidence"
    if os.name != "nt":
        pytest.skip("Windows junction test")
    junction = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(profile_dir), str(target)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if junction.returncode != 0:
        pytest.skip("junctions unavailable")
    manifest_before = (asset.root / "manifest.json").read_bytes()
    evidence_before = {
        path.relative_to(asset.root).as_posix(): path.read_bytes()
        for path in target.rglob("*")
        if path.is_file()
    }

    with pytest.raises(ValueError, match="reparse point"):
        write_profile_selection(asset, explicit_profile=None, intent=None)

    assert (asset.root / "manifest.json").read_bytes() == manifest_before
    assert {
        path.relative_to(asset.root).as_posix(): path.read_bytes()
        for path in target.rglob("*")
        if path.is_file()
    } == evidence_before


def test_completed_profile_view_only_allows_an_exact_idempotent_selection(tmp_path: Path) -> None:
    asset = AssetStore.create(tmp_path / "assets", "asset-001", {"kind": "local_video"})
    selection = write_profile_selection(asset, explicit_profile=None, intent=None)
    view_manifest = asset.root / "views" / selection.profile_id / "view-manifest.json"
    asset.complete_stage(f"views/{selection.profile_id}", [view_manifest])
    manifest_before = (asset.root / "manifest.json").read_bytes()
    view_before = view_manifest.read_bytes()

    assert write_profile_selection(asset, explicit_profile=None, intent=None) == selection
    assert (asset.root / "manifest.json").read_bytes() == manifest_before
    assert view_manifest.read_bytes() == view_before

    with pytest.raises(ValueError, match="completed profile view"):
        write_profile_selection(
            asset,
            explicit_profile="general-deep",
            intent=None,
            requested_formats=("pdf",),
        )

    assert (asset.root / "manifest.json").read_bytes() == manifest_before
    assert view_manifest.read_bytes() == view_before


def test_profile_selection_refuses_legacy_manifest_before_writing(tmp_path: Path) -> None:
    asset = AssetStore.create(tmp_path / "assets", "asset-001", {"kind": "local_video"})
    manifest_path = asset.root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["schema_version"] = "1.0"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="only 1.1 manifests"):
        write_profile_selection(asset, explicit_profile=None, intent=None)

    assert not (asset.root / "views" / "general-deep" / "view-manifest.json").exists()


def test_profile_selection_rejects_a_legacy_manifest_tmp_link_without_touching_outside(
    tmp_path: Path,
) -> None:
    asset = AssetStore.create(tmp_path / "assets", "asset-001", {"kind": "local_video"})
    outside = tmp_path / "outside.json"
    outside.write_text('{"sentinel":"outside"}\n', encoding="utf-8")
    legacy_tmp = asset.root / "manifest.json.tmp"
    try:
        legacy_tmp.symlink_to(outside)
    except OSError as exc:
        if os.name != "nt":
            pytest.skip(f"file symlinks unavailable: {exc}")
        outside_directory = tmp_path / "outside-directory"
        outside_directory.mkdir()
        junction = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(legacy_tmp), str(outside_directory)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if junction.returncode != 0:
            pytest.skip(f"file symlinks and junctions unavailable: {exc}")

    outside_before = outside.read_bytes()
    with pytest.raises(ValueError, match="manifest temporary path.*symlink|manifest temporary path.*asset root"):
        write_profile_selection(asset, explicit_profile=None, intent=None)

    assert outside.read_bytes() == outside_before
