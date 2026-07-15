import json
import os
import subprocess
from pathlib import Path

import pytest

from vka.qa_topology import build_qa_topology
from vka.store import AssetStore


def _complete_qa_asset(tmp_path: Path) -> AssetStore:
    asset = AssetStore.create(
        tmp_path / "assets", "asset-001", {"kind": "bilibili", "bvid": "BV1test"}
    )
    metadata = asset.root / "source" / "metadata.json"
    metadata.write_text('{"title":"Lesson"}\n', encoding="utf-8")
    records = asset.write_jsonl(
        "evidence/records.jsonl",
        [
            {
                "evidence_id": "ev-procedure",
                "origin": "video",
                "modality": "transcript",
                "content": "Transcript-only evidence wording must not appear in topology.",
                "spans": [{"start_ms": 1000, "end_ms": 2000}],
                "acquisition": "asr",
            },
            {
                "evidence_id": "ev-concept",
                "origin": "video",
                "modality": "transcript",
                "content": "Another transcript sentence.",
                "spans": [{"start_ms": 3000, "end_ms": 4000}],
                "acquisition": "asr",
            },
        ],
    )
    units = asset.write_jsonl(
        "knowledge/units.jsonl",
        [
            {
                "unit_id": "ku-concept",
                "type": "concept",
                "title": "Concept title must not be copied",
                "statement": "Knowledge prose must not be copied.",
                "epistemic_status": "video_explicit",
                "importance": "high",
                "tags": ["foundation", "model"],
                "evidence_refs": ["ev-concept"],
            },
            {
                "unit_id": "ku-procedure",
                "type": "procedure",
                "title": "Procedure title must not be copied",
                "statement": "Procedure prose must not be copied.",
                "epistemic_status": "agent_inference",
                "importance": "high",
                "tags": ["workflow"],
                "evidence_refs": ["ev-procedure"],
            },
            {
                "unit_id": "ku-external",
                "type": "limitation",
                "title": "External title",
                "statement": "External knowledge prose.",
                "epistemic_status": "external_enrichment",
                "importance": "low",
                "tags": ["parameter"],
                "evidence_refs": ["ev-concept"],
            },
        ],
    )
    relations = asset.write_jsonl(
        "knowledge/relations.jsonl",
        [
            {
                "relation_id": "rel-procedure-concept",
                "source_unit_id": "ku-procedure",
                "target_unit_id": "ku-concept",
                "relation_type": "supports",
                "evidence_refs": ["ev-procedure"],
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
        json.dumps({"sections": [{"text": "Course document-only prose must not appear."}]}),
        encoding="utf-8",
    )
    asset.complete_stage("source", [metadata])
    asset.complete_stage("evidence", [records])
    asset.complete_stage("knowledge", [units, relations, synthesis])
    return asset


def test_topology_is_deterministic_and_contains_only_canonical_references(tmp_path: Path) -> None:
    asset = _complete_qa_asset(tmp_path)

    first = build_qa_topology(asset)
    topology_path = asset.root / "index" / "qa-topology.json"
    first_bytes = topology_path.read_bytes()
    second = build_qa_topology(asset)

    assert second == first
    assert topology_path.read_bytes() == first_bytes
    assert first["asset_id"] == "asset-001"
    assert first["profile_id"] == "course-notes"
    assert first["qa_asset_fingerprint"]
    assert [facet["unit_id"] for facet in first["facets"]] == [
        "ku-concept",
        "ku-procedure",
    ]
    assert first["facets"][0]["inbound_relation_ids"] == ["rel-procedure-concept"]
    assert first["facets"][1]["outbound_relation_ids"] == ["rel-procedure-concept"]
    serialized = json.dumps(first, ensure_ascii=False)
    for prose in (
        "Course document-only prose must not appear.",
        "Transcript-only evidence wording must not appear in topology.",
        "Knowledge prose must not be copied.",
        "Procedure title must not be copied",
    ):
        assert prose not in serialized


def test_topology_capabilities_are_derived_from_actual_units(tmp_path: Path) -> None:
    asset = _complete_qa_asset(tmp_path)

    topology = build_qa_topology(asset)

    capabilities = topology["capabilities"]
    assert "type:procedure" in capabilities
    assert "tag:workflow" in capabilities
    assert "relation:supports" in capabilities
    assert "type:parameter" not in capabilities
    assert "parameter" not in json.dumps(topology, ensure_ascii=False)


def test_topology_rejects_profiles_other_than_course_notes(tmp_path: Path) -> None:
    asset = _complete_qa_asset(tmp_path)

    with pytest.raises(ValueError, match="course-notes"):
        build_qa_topology(asset, profile_id="enterprise-knowledge")


def test_topology_rejects_unknown_or_malformed_canonical_references(tmp_path: Path) -> None:
    asset = _complete_qa_asset(tmp_path)
    units_path = asset.root / "knowledge" / "units.jsonl"
    units = [json.loads(line) for line in units_path.read_text(encoding="utf-8").splitlines()]
    units[0]["evidence_refs"] = ["ev-missing"]
    units_path.write_text("".join(json.dumps(unit) + "\n" for unit in units), encoding="utf-8")
    asset.complete_stage(
        "knowledge",
        [
            units_path,
            asset.root / "knowledge" / "relations.jsonl",
            asset.root / "knowledge" / "synthesis.json",
        ],
    )

    with pytest.raises(ValueError, match="unknown evidence"):
        build_qa_topology(asset)

    asset = _complete_qa_asset(tmp_path / "relation")
    relations_path = asset.root / "knowledge" / "relations.jsonl"
    relations = [json.loads(line) for line in relations_path.read_text(encoding="utf-8").splitlines()]
    relations[0]["target_unit_id"] = "ku-missing"
    relations_path.write_text(
        "".join(json.dumps(relation) + "\n" for relation in relations), encoding="utf-8"
    )
    asset.complete_stage(
        "knowledge",
        [
            asset.root / "knowledge" / "units.jsonl",
            relations_path,
            asset.root / "knowledge" / "synthesis.json",
        ],
    )

    with pytest.raises(ValueError, match="unknown knowledge unit"):
        build_qa_topology(asset)


@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (lambda relation: relation.update({"evidence_refs": ["ev-missing"]}), "unknown evidence"),
        (lambda relation: relation.update({"evidence_refs": ["ev-unrelated"]}), "endpoint evidence"),
    ],
)
def test_topology_rejects_relation_evidence_outside_video_endpoint_support(
    tmp_path: Path, mutator: object, message: str
) -> None:
    asset = _complete_qa_asset(tmp_path)
    records_path = asset.root / "evidence" / "records.jsonl"
    records = [json.loads(line) for line in records_path.read_text(encoding="utf-8").splitlines()]
    records.append(
        {
            "evidence_id": "ev-unrelated",
            "origin": "video",
            "modality": "transcript",
            "content": "Unrelated video evidence.",
            "spans": [{"start_ms": 5_000, "end_ms": 6_000}],
            "acquisition": "asr",
        }
    )
    records_path.write_text(
        "".join(json.dumps(record) + "\n" for record in records), encoding="utf-8"
    )
    asset.complete_stage("evidence", [records_path])
    relation_path = asset.root / "knowledge" / "relations.jsonl"
    relations = [json.loads(line) for line in relation_path.read_text(encoding="utf-8").splitlines()]
    assert callable(mutator)
    mutator(relations[0])
    relation_path.write_text(
        "".join(json.dumps(relation) + "\n" for relation in relations), encoding="utf-8"
    )
    asset.complete_stage(
        "knowledge",
        [
            asset.root / "knowledge" / "units.jsonl",
            relation_path,
            asset.root / "knowledge" / "synthesis.json",
        ],
    )

    with pytest.raises(ValueError, match=message):
        build_qa_topology(asset)


def test_topology_rejects_non_video_relation_evidence(tmp_path: Path) -> None:
    asset = _complete_qa_asset(tmp_path)
    records_path = asset.root / "evidence" / "records.jsonl"
    records = [json.loads(line) for line in records_path.read_text(encoding="utf-8").splitlines()]
    records[0]["origin"] = "external"
    records[0]["spans"] = []
    records_path.write_text(
        "".join(json.dumps(record) + "\n" for record in records), encoding="utf-8"
    )
    asset.complete_stage("evidence", [records_path])

    with pytest.raises(ValueError, match="video evidence with source spans"):
        build_qa_topology(asset)


def test_topology_rebuilds_when_fingerprint_changes(tmp_path: Path) -> None:
    asset = _complete_qa_asset(tmp_path)
    first = build_qa_topology(asset)
    records = asset.write_jsonl(
        "evidence/records.jsonl",
        [
            {
                "evidence_id": "ev-procedure",
                "origin": "video",
                "modality": "transcript",
                "content": "Changed transcript content.",
                "spans": [{"start_ms": 1000, "end_ms": 2000}],
                "acquisition": "asr",
            },
            {
                "evidence_id": "ev-concept",
                "origin": "video",
                "modality": "transcript",
                "content": "Another transcript sentence.",
                "spans": [{"start_ms": 3000, "end_ms": 4000}],
                "acquisition": "asr",
            },
        ],
    )
    asset.complete_stage("evidence", [records])

    second = build_qa_topology(asset)

    assert second["qa_asset_fingerprint"] != first["qa_asset_fingerprint"]
    assert json.loads((asset.root / "index" / "qa-topology.json").read_text(encoding="utf-8")) == second


def test_topology_rebuilds_forged_or_malformed_matching_cache(tmp_path: Path) -> None:
    asset = _complete_qa_asset(tmp_path)
    expected = build_qa_topology(asset)
    topology_path = asset.root / "index" / "qa-topology.json"
    forged = json.loads(topology_path.read_text(encoding="utf-8"))
    forged["capabilities"].append("type:parameter")
    forged["facets"].append(
        {
            "unit_id": "ku-external",
            "type": "limitation",
            "epistemic_status": "external_enrichment",
            "tags": ["parameter"],
            "evidence_refs": ["ev-concept"],
            "inbound_relation_ids": [],
            "outbound_relation_ids": [],
            "capabilities": ["type:parameter"],
        }
    )
    topology_path.write_text(json.dumps(forged), encoding="utf-8")

    assert build_qa_topology(asset) == expected
    assert json.loads(topology_path.read_text(encoding="utf-8")) == expected

    topology_path.write_text('{"facets":"not a list"}', encoding="utf-8")

    assert build_qa_topology(asset) == expected
    assert json.loads(topology_path.read_text(encoding="utf-8")) == expected


@pytest.mark.parametrize(
    ("layer", "mutator", "expected_error"),
    [
        (
            "evidence",
            lambda records: records[0].pop("acquisition"),
            "evidence record 1 is invalid",
        ),
        (
            "evidence",
            lambda records: records[0].update({"origin": "unknown"}),
            "evidence record 1 is invalid",
        ),
        (
            "evidence",
            lambda records: records[0].update({"spans": []}),
            "evidence record 1 is invalid",
        ),
        (
            "knowledge",
            lambda units: units[0].update({"evidence_refs": []}),
            "knowledge record 1 is invalid",
        ),
        (
            "relation",
            lambda relations: relations[0].update({"relation_type": "uses"}),
            "relation record 1 is invalid",
        ),
    ],
)
def test_topology_rejects_malformed_canonical_record_schemas(
    tmp_path: Path, layer: str, mutator: object, expected_error: str
) -> None:
    asset = _complete_qa_asset(tmp_path)
    path = {
        "evidence": asset.root / "evidence" / "records.jsonl",
        "knowledge": asset.root / "knowledge" / "units.jsonl",
        "relation": asset.root / "knowledge" / "relations.jsonl",
    }[layer]
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert callable(mutator)
    mutator(records)
    path.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")
    if layer == "evidence":
        asset.complete_stage("evidence", [path])
    else:
        asset.complete_stage(
            "knowledge",
            [
                asset.root / "knowledge" / "units.jsonl",
                asset.root / "knowledge" / "relations.jsonl",
                asset.root / "knowledge" / "synthesis.json",
            ],
        )

    with pytest.raises(ValueError, match=expected_error):
        build_qa_topology(asset)


def test_topology_refuses_a_symlinked_destination(tmp_path: Path) -> None:
    asset = _complete_qa_asset(tmp_path)
    topology_path = asset.root / "index" / "qa-topology.json"
    outside = tmp_path / "outside.json"
    outside.write_text('{"preserve": true}', encoding="utf-8")
    try:
        topology_path.symlink_to(outside)
    except OSError as exc:
        if os.name != "nt":
            pytest.skip(f"file symlinks are unavailable: {exc}")
        outside_directory = tmp_path / "outside-directory"
        outside_directory.mkdir()
        junction = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(topology_path), str(outside_directory)],
            capture_output=True,
            text=True,
            check=False,
        )
        if junction.returncode != 0:
            pytest.skip(f"file symlinks and junctions unavailable: {exc}")

    with pytest.raises(ValueError, match="topology destination.*symlink"):
        build_qa_topology(asset)

    assert outside.read_text(encoding="utf-8") == '{"preserve": true}'
