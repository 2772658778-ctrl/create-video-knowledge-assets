import json
from pathlib import Path

import pytest
import vka.qa_retrieval as qa_retrieval
from vka.qa_index import build_qa_index
from vka.qa_retrieval import retrieve_question
from vka.store import AssetStore


def _indexed_asset(tmp_path: Path, *, include_external: bool = False) -> AssetStore:
    asset = AssetStore.create(
        tmp_path / "assets", "asset-001", {"kind": "bilibili", "bvid": "BV1test"}
    )
    metadata = asset.root / "source" / "metadata.json"
    metadata.write_text('{"title":"Lesson"}\n', encoding="utf-8")
    records = asset.write_jsonl(
        "evidence/records.jsonl",
        [
            {
                "evidence_id": "ev-platform",
                "origin": "video",
                "modality": "transcript",
                "spans": [{"start_ms": 1000, "end_ms": 2000}],
                "content": "Use Colab to fine tune DeepSeek-R1.",
                "artifact_ref": "source/asr/audio.srt",
                "acquisition": "asr",
            },
            {
                "evidence_id": "ev-external",
                "origin": "external",
                "modality": "document",
                "spans": [],
                "content": "Background platform information.",
                "acquisition": "user_supplied",
            },
        ],
    )
    units = asset.write_jsonl(
        "knowledge/units.jsonl",
        [
            {
                "unit_id": "ku-platform",
                "type": "procedure",
                "title": "Platform fine tuning",
                "statement": "Use Colab to fine tune DeepSeek-R1.",
                "evidence_refs": ["ev-platform"],
                "epistemic_status": "video_explicit",
                "importance": "high",
            },
            *(
                [
                    {
                        "unit_id": "ku-external",
                        "type": "concept",
                        "title": "Platform background",
                        "statement": "Background platform information.",
                        "evidence_refs": ["ev-external"],
                        "epistemic_status": "external_enrichment",
                        "importance": "high",
                    }
                ]
                if include_external
                else []
            ),
        ],
    )
    relations = asset.write_jsonl(
        "knowledge/relations.jsonl",
        [
            {
                "relation_id": "rel-platform",
                "source_unit_id": "ku-platform",
                "target_unit_id": "ku-platform",
                "relation_type": "explains",
                "evidence_refs": ["ev-platform"],
            }
        ],
    )
    synthesis = asset.root / "knowledge" / "synthesis.json"
    synthesis.write_text('{"video_summary":"Lesson"}\n', encoding="utf-8")
    outline = asset.root / "knowledge" / "teaching_outline.json"
    outline.write_text('{"sections": []}\n', encoding="utf-8")
    document = asset.root / "views" / "course-notes" / "document.json"
    document.parent.mkdir(parents=True, exist_ok=True)
    document.write_text(
        json.dumps(
            {
                "sections": [
                    {"title": "Introduction", "blocks": []},
                    {
                        "title": "Platform fine tuning",
                        "blocks": [{"knowledge_refs": ["ku-platform"]}],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    asset.complete_stage("source", [metadata])
    asset.complete_stage("evidence", [records])
    asset.complete_stage("knowledge", [units, relations, synthesis])
    build_qa_index(asset, profile_id="course-notes")
    return asset


def test_retrieve_returns_evidence_and_course_location(tmp_path: Path) -> None:
    asset = _indexed_asset(tmp_path)

    pack = retrieve_question(asset, "How does the platform fine tune a model?")

    candidate = pack["candidates"][0]
    assert "answer" not in pack
    assert candidate["knowledge_id"] == "ku-platform"
    assert candidate["evidence_refs"] == ["ev-platform"]
    assert "evidence" not in candidate
    assert candidate["course_locations"] == [
        {"section_index": 2, "title": "Platform fine tuning"}
    ]
    assert len(pack["evidence_windows"]) == 1
    evidence_window = pack["evidence_windows"][0]
    assert evidence_window["knowledge_id"] == "ku-platform"
    assert evidence_window["evidence_refs"] == ["ev-platform"]
    assert len(evidence_window["evidence"]) <= 12
    assert sum(
        len(item["content"].encode("utf-8")) for item in evidence_window["evidence"]
    ) <= 12_000
    assert "statement" not in evidence_window
    assert "title" not in evidence_window


def test_retrieve_excludes_external_enrichment_in_mvp(tmp_path: Path) -> None:
    asset = _indexed_asset(tmp_path, include_external=True)

    pack = retrieve_question(asset, "platform background")

    assert all(
        item["epistemic_status"] != "external_enrichment"
        for item in pack["candidates"]
    )
    assert pack["excluded_external_enrichment_count"] == 1


def test_retrieve_applies_limit_after_global_deterministic_ranking(tmp_path: Path) -> None:
    asset = _indexed_asset(tmp_path)
    units_path = asset.root / "knowledge" / "units.jsonl"
    units = [json.loads(line) for line in units_path.read_text(encoding="utf-8").splitlines()]
    units.extend(
        [
            {
                "unit_id": "ku-aaa",
                "type": "concept",
                "title": "Platform alpha",
                "statement": "Platform explanation.",
                "evidence_refs": ["ev-platform"],
                "epistemic_status": "video_explicit",
                "importance": "low",
            },
            {
                "unit_id": "ku-zzz",
                "type": "concept",
                "title": "Platform zeta",
                "statement": "Platform explanation.",
                "evidence_refs": ["ev-platform"],
                "epistemic_status": "video_explicit",
                "importance": "high",
            },
        ]
    )
    units_path.write_text(
        "".join(json.dumps(unit) + "\n" for unit in units), encoding="utf-8"
    )
    asset.complete_stage(
        "knowledge",
        [
            units_path,
            asset.root / "knowledge" / "relations.jsonl",
            asset.root / "knowledge" / "synthesis.json",
        ],
    )
    build_qa_index(asset, profile_id="course-notes")

    pack = retrieve_question(asset, "platform", limit=1)

    assert pack["candidates"][0]["knowledge_id"] == "ku-zzz"


def test_retrieve_builds_windows_for_only_post_limit_candidates_and_filters_topology(
    tmp_path: Path, monkeypatch
) -> None:
    asset = _indexed_asset(tmp_path)
    units_path = asset.root / "knowledge" / "units.jsonl"
    units = [json.loads(line) for line in units_path.read_text(encoding="utf-8").splitlines()]
    units.append(
        {
            "unit_id": "ku-other",
            "type": "concept",
            "title": "Platform configuration",
            "statement": "Platform configuration is demonstrated.",
            "evidence_refs": ["ev-platform"],
            "epistemic_status": "video_explicit",
            "importance": "low",
        }
    )
    units_path.write_text(
        "".join(json.dumps(unit) + "\n" for unit in units), encoding="utf-8"
    )
    asset.complete_stage(
        "knowledge",
        [
            units_path,
            asset.root / "knowledge" / "relations.jsonl",
            asset.root / "knowledge" / "synthesis.json",
        ],
    )
    build_qa_index(asset, profile_id="course-notes")

    selected_calls: list[list[str]] = []
    def fake_windows(_asset, selected_knowledge_ids, *, profile_id):
        selected_calls.append(list(selected_knowledge_ids))
        return {
            "windows": [
                {
                    "window_id": f"window:{selected_knowledge_ids[0]}:001",
                    "knowledge_id": selected_knowledge_ids[0],
                    "evidence_refs": ["ev-platform"],
                    "evidence": [
                        {
                            "evidence_id": "ev-platform",
                            "origin": "video",
                            "modality": "transcript",
                            "content": "Use Colab to fine tune DeepSeek-R1.",
                        }
                    ],
                }
            ]
        }

    def fake_topology(_asset, *, profile_id):
        return {
            "facets": [
                {
                    "unit_id": "ku-platform",
                    "evidence_refs": ["ev-platform"],
                    "capabilities": ["type:procedure", "tag:finetuning"],
                },
                {
                    "unit_id": "ku-other",
                    "evidence_refs": ["ev-platform"],
                    "capabilities": ["type:concept", "tag:unselected"],
                },
            ],
            "capabilities": ["tag:finetuning", "tag:unselected", "type:concept", "type:procedure"],
        }

    monkeypatch.setattr(qa_retrieval, "build_evidence_windows", fake_windows)
    monkeypatch.setattr(qa_retrieval, "build_qa_topology", fake_topology)

    pack = retrieve_question(asset, "platform", limit=1)

    selected_ids = [candidate["knowledge_id"] for candidate in pack["candidates"]]
    assert selected_calls == [selected_ids]
    assert pack["evidence_windows"][0]["knowledge_id"] == selected_ids[0]
    selected_facet = next(
        facet
        for facet in fake_topology(asset, profile_id="course-notes")["facets"]
        if facet["unit_id"] == selected_ids[0]
    )
    assert pack["topology"] == {
        "facets": [selected_facet],
        "capabilities": sorted(selected_facet["capabilities"]),
    }
    assert "answer" not in pack


def test_retrieve_no_hit_builds_empty_windows_and_topology(
    tmp_path: Path, monkeypatch
) -> None:
    asset = _indexed_asset(tmp_path)
    selected_calls: list[list[str]] = []

    def fake_windows(_asset, selected_knowledge_ids, *, profile_id):
        selected_calls.append(list(selected_knowledge_ids))
        return {"windows": []}

    monkeypatch.setattr(qa_retrieval, "build_evidence_windows", fake_windows)
    monkeypatch.setattr(
        qa_retrieval,
        "build_qa_topology",
        lambda _asset, *, profile_id: {"facets": [], "capabilities": []},
    )

    pack = retrieve_question(asset, "unrelated zygomorphic question")

    assert pack["candidates"] == []
    assert selected_calls == [[]]
    assert pack["evidence_windows"] == []
    assert pack["topology"] == {"facets": [], "capabilities": []}
    assert "answer" not in pack


def test_retrieve_excludes_candidate_with_any_unsafe_canonical_evidence(
    tmp_path: Path, monkeypatch
) -> None:
    asset = _indexed_asset(tmp_path)
    records_path = asset.root / "evidence" / "records.jsonl"
    records = [
        json.loads(line) for line in records_path.read_text(encoding="utf-8").splitlines()
    ]
    records.extend(
        [
            {
                "evidence_id": "ev-generated",
                "origin": "generated",
                "modality": "transcript",
                "spans": [],
                "content": "Generated unsafe detail.",
                "acquisition": "agent",
            },
            {
                "evidence_id": "ev-video-document",
                "origin": "video",
                "modality": "document",
                "spans": [{"start_ms": 3000, "end_ms": 4000}],
                "content": "Video document unsafe detail.",
                "acquisition": "download",
            },
        ]
    )
    records_path.write_text(
        "".join(json.dumps(record) + "\n" for record in records), encoding="utf-8"
    )
    units_path = asset.root / "knowledge" / "units.jsonl"
    units = [json.loads(line) for line in units_path.read_text(encoding="utf-8").splitlines()]
    units.append(
        {
            "unit_id": "ku-unsafe",
            "type": "concept",
            "title": "Unsafe canonical evidence",
            "statement": "Unsafe evidence is present.",
            "evidence_refs": [
                "ev-platform",
                "ev-external",
                "ev-generated",
                "ev-video-document",
            ],
            "epistemic_status": "video_explicit",
            "importance": "high",
        }
    )
    units_path.write_text(
        "".join(json.dumps(unit) + "\n" for unit in units), encoding="utf-8"
    )
    asset.complete_stage("evidence", [records_path])
    asset.complete_stage(
        "knowledge",
        [
            units_path,
            asset.root / "knowledge" / "relations.jsonl",
            asset.root / "knowledge" / "synthesis.json",
        ],
    )
    build_qa_index(asset, profile_id="course-notes")
    monkeypatch.setattr(
        qa_retrieval,
        "build_evidence_windows",
        lambda _asset, selected_knowledge_ids, *, profile_id: {"windows": []},
    )
    monkeypatch.setattr(
        qa_retrieval,
        "build_qa_topology",
        lambda _asset, *, profile_id: {"facets": [], "capabilities": []},
    )

    pack = retrieve_question(asset, "unsafe canonical evidence")

    assert pack["candidates"] == []
    assert pack["excluded_unsafe_evidence_count"] == 1
    assert pack["evidence_windows"] == []


def test_retrieve_candidates_keep_large_evidence_sets_as_references_only(
    tmp_path: Path,
) -> None:
    asset = _indexed_asset(tmp_path)
    records_path = asset.root / "evidence" / "records.jsonl"
    records = [
        json.loads(line) for line in records_path.read_text(encoding="utf-8").splitlines()
    ]
    evidence_refs = []
    for index in range(16):
        evidence_id = f"ev-many-{index:02d}"
        evidence_refs.append(evidence_id)
        records.append(
            {
                "evidence_id": evidence_id,
                "origin": "video",
                "modality": "transcript",
                "spans": [{"start_ms": 3_000 + index * 1_000, "end_ms": 3_500 + index * 1_000}],
                "content": "x" * 10_000,
                "acquisition": "asr",
            }
        )
    records_path.write_text(
        "".join(json.dumps(record) + "\n" for record in records), encoding="utf-8"
    )
    units_path = asset.root / "knowledge" / "units.jsonl"
    units = [json.loads(line) for line in units_path.read_text(encoding="utf-8").splitlines()]
    units.append(
        {
            "unit_id": "ku-many",
            "type": "concept",
            "title": "Large evidence set",
            "statement": "Large evidence remains bounded.",
            "evidence_refs": evidence_refs,
            "epistemic_status": "video_explicit",
            "importance": "high",
        }
    )
    units_path.write_text(
        "".join(json.dumps(unit) + "\n" for unit in units), encoding="utf-8"
    )
    asset.complete_stage("evidence", [records_path])
    asset.complete_stage(
        "knowledge",
        [
            units_path,
            asset.root / "knowledge" / "relations.jsonl",
            asset.root / "knowledge" / "synthesis.json",
        ],
    )
    build_qa_index(asset, profile_id="course-notes")

    pack = retrieve_question(asset, "large evidence set")

    candidate = next(
        item for item in pack["candidates"] if item["knowledge_id"] == "ku-many"
    )
    assert candidate["evidence_refs"] == evidence_refs
    assert "evidence" not in candidate
    windows = [
        window
        for window in pack["evidence_windows"]
        if window["knowledge_id"] == "ku-many"
    ]
    assert len(windows) == len(evidence_refs)
    assert all(len(window["evidence"]) <= 12 for window in windows)
    assert all(
        sum(len(item["content"].encode("utf-8")) for item in window["evidence"])
        <= 12_000
        for window in windows
    )


@pytest.mark.parametrize(
    ("published", "expected_message"),
    [
        ({"windows": [{"window_id": "window:a", "knowledge_id": "a"}]}, "missing selected knowledge"),
        (
            {"windows": [{"window_id": "window:c", "knowledge_id": "c"}]},
            "references unselected knowledge",
        ),
        (
            {
                "windows": [
                    {"window_id": "window:duplicate", "knowledge_id": "a"},
                    {"window_id": "window:duplicate", "knowledge_id": "b"},
                ]
            },
            "duplicate evidence window_id",
        ),
        (
            {
                "windows": [
                    {"window_id": "window:a", "knowledge_id": "a"},
                    {"window_id": "window:b", "knowledge_id": "a"},
                ]
            },
            "duplicate evidence window knowledge_id",
        ),
    ],
)
def test_selected_evidence_windows_must_cover_each_selected_candidate_once(
    published, expected_message
) -> None:
    with pytest.raises(ValueError, match=expected_message):
        qa_retrieval._selected_evidence_windows(published, ["a", "b"])
