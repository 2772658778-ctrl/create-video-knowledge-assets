import json
from pathlib import Path

import pytest

from vka.qa_revision import load_knowledge_revision, register_knowledge_revision
from vka.qa_index import build_qa_index, read_chunks
from vka.qa_topology import build_qa_topology
from vka.qa_windows import build_evidence_windows
from vka.qa_retrieval import retrieve_question
from vka.qa_planning import build_answer_plan
from vka.qa_contract import AnswerBlock, AnswerClaim, GroundedAnswer
from vka.qa_validation import validate_grounded_answer
from vka.models import SourceSpan
from vka.store import AssetStore


def _asset(tmp_path: Path) -> AssetStore:
    asset = AssetStore.create(
        tmp_path / "assets", "asset-001", {"kind": "bilibili", "bvid": "BV1test"}
    )
    metadata = asset.root / "source" / "metadata.json"
    metadata.write_text('{"title":"Lesson"}\n', encoding="utf-8")
    evidence = asset.write_jsonl(
        "evidence/records.jsonl",
        [
            {
                "evidence_id": "ev-video",
                "origin": "video",
                "modality": "transcript",
                "spans": [{"start_ms": 1_000, "end_ms": 2_000}],
                "content": "The speaker gives a procedure.",
                "acquisition": "asr",
            },
            {
                "evidence_id": "ev-external",
                "origin": "external",
                "modality": "document",
                "content": "Outside material.",
                "acquisition": "user",
            },
        ],
    )
    units = asset.write_jsonl(
        "knowledge/units.jsonl",
        [
            {
                "unit_id": "legacy-unit",
                "type": "concept",
                "title": "Legacy",
                "statement": "Legacy knowledge remains immutable.",
                "evidence_refs": ["ev-video"],
                "epistemic_status": "video_explicit",
                "importance": "high",
            }
        ],
    )
    relations = asset.write_jsonl("knowledge/relations.jsonl", [])
    synthesis = asset.root / "knowledge" / "synthesis.json"
    synthesis.write_text('{"legacy":true}\n', encoding="utf-8")
    outline = asset.root / "knowledge" / "teaching_outline.json"
    outline.write_text('{"sections":[]}\n', encoding="utf-8")
    document = asset.root / "views" / "course-notes" / "document.json"
    document.parent.mkdir(parents=True, exist_ok=True)
    document.write_text('{"sections":[]}\n', encoding="utf-8")
    asset.complete_stage("source", [metadata])
    asset.complete_stage("evidence", [evidence])
    asset.complete_stage("knowledge", [units, relations, synthesis])
    return asset


def _write_revision(asset: AssetStore, revision_id: str = "rev-001") -> Path:
    revision = asset.root / "knowledge" / "revisions" / revision_id
    revision.mkdir(parents=True)
    (revision / "units.jsonl").write_text(
        json.dumps(
            {
                "unit_id": "revision-unit",
                "type": "procedure",
                "title": "Procedure",
                "statement": "The speaker gives a procedure.",
                "evidence_refs": ["ev-video"],
                "epistemic_status": "video_explicit",
                "importance": "high",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (revision / "relations.jsonl").write_text(
        json.dumps(
            {
                "relation_id": "revision-rel",
                "source_unit_id": "revision-unit",
                "target_unit_id": "revision-unit",
                "relation_type": "explains",
                "evidence_refs": ["ev-video"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (revision / "synthesis.json").write_text(
        json.dumps(
            {
                "video_summary": "The video gives a procedure.",
                "video_summary_refs": ["revision-unit"],
                "agent_extensions": [],
                "agent_extension_refs": ["revision-unit"],
                "evidence_refs": ["ev-video"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return revision


def test_register_and_load_revision_preserves_legacy_knowledge(tmp_path: Path) -> None:
    asset = _asset(tmp_path)
    legacy = {
        path: (asset.root / path).read_bytes()
        for path in ("knowledge/units.jsonl", "knowledge/relations.jsonl", "knowledge/synthesis.json")
    }
    _write_revision(asset)

    registered = register_knowledge_revision(asset, "rev-001")
    loaded = load_knowledge_revision(asset, "rev-001")

    assert registered["revision_id"] == "rev-001"
    assert loaded["units"][0]["unit_id"] == "revision-unit"
    assert loaded["relations"][0]["relation_id"] == "revision-rel"
    assert loaded["synthesis"]["video_summary_refs"] == ["revision-unit"]
    assert (asset.root / "knowledge" / "revisions" / "rev-001" / "revision.json").is_file()
    assert {
        path: (asset.root / path).read_bytes() for path in legacy
    } == legacy
    manifest = json.loads((asset.root / "manifest.json").read_text(encoding="utf-8"))
    assert "rev-001" in manifest["p4"]["knowledge_revisions"]["revisions"]


def test_qa_builders_use_registered_revision_in_isolated_artifacts(tmp_path: Path) -> None:
    asset = _asset(tmp_path)
    _write_revision(asset)
    register_knowledge_revision(asset, "rev-001")

    index = build_qa_index(asset, knowledge_revision="rev-001")
    topology = build_qa_topology(asset, knowledge_revision="rev-001")
    windows = build_evidence_windows(
        asset, ["revision-unit"], knowledge_revision="rev-001"
    )

    revision_index = asset.root / "index" / "revisions" / "rev-001"
    assert revision_index.is_dir()
    assert not (asset.root / "index" / "index-manifest.json").exists()
    assert [chunk["chunk_id"] for chunk in read_chunks(revision_index / "chunks.jsonl")] == [
        "ku:revision-unit"
    ]
    for manifest in (index, topology, windows):
        assert manifest["knowledge_revision"] == "rev-001"
        assert isinstance(manifest["knowledge_revision_sha256"], str)
    assert [facet["unit_id"] for facet in topology["facets"]] == ["revision-unit"]
    assert [window["knowledge_id"] for window in windows["windows"]] == ["revision-unit"]


def test_qa_builders_reject_unknown_or_tampered_revision(tmp_path: Path) -> None:
    asset = _asset(tmp_path)
    _write_revision(asset)
    register_knowledge_revision(asset, "rev-001")

    with pytest.raises(ValueError, match="revision directory"):
        build_qa_index(asset, knowledge_revision="unknown")

    revision_units = asset.root / "knowledge" / "revisions" / "rev-001" / "units.jsonl"
    revision_units.write_text(revision_units.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="sha256"):
        build_qa_topology(asset, knowledge_revision="rev-001")
    with pytest.raises(ValueError, match="sha256"):
        build_evidence_windows(asset, ["revision-unit"], knowledge_revision="rev-001")


def test_revision_indexes_do_not_reuse_another_revision_cache(tmp_path: Path) -> None:
    asset = _asset(tmp_path)
    _write_revision(asset, "rev-001")
    register_knowledge_revision(asset, "rev-001")
    second_revision = _write_revision(asset, "rev-002")
    for path in (
        second_revision / "units.jsonl",
        second_revision / "relations.jsonl",
        second_revision / "synthesis.json",
    ):
        path.write_text(
            path.read_text(encoding="utf-8").replace("revision-unit", "revision-unit-two"),
            encoding="utf-8",
        )
    register_knowledge_revision(asset, "rev-002")

    first = build_qa_index(asset, knowledge_revision="rev-001")
    second = build_qa_index(asset, knowledge_revision="rev-002")

    assert first["knowledge_revision"] == "rev-001"
    assert second["knowledge_revision"] == "rev-002"
    assert read_chunks(asset.root / "index" / "revisions" / "rev-001" / "chunks.jsonl")[0][
        "knowledge_refs"
    ] == ["revision-unit"]
    assert read_chunks(asset.root / "index" / "revisions" / "rev-002" / "chunks.jsonl")[0][
        "knowledge_refs"
    ] == ["revision-unit-two"]


def test_register_rejects_an_already_registered_revision_id(tmp_path: Path) -> None:
    asset = _asset(tmp_path)
    _write_revision(asset)
    register_knowledge_revision(asset, "rev-001")

    with pytest.raises(ValueError, match="already registered"):
        register_knowledge_revision(asset, "rev-001")


def test_register_rejects_mutated_content_under_an_registered_revision_id(
    tmp_path: Path,
) -> None:
    asset = _asset(tmp_path)
    revision = _write_revision(asset)
    register_knowledge_revision(asset, "rev-001")
    units_path = revision / "units.jsonl"
    units_path.write_text(
        units_path.read_text(encoding="utf-8").replace("Procedure", "Changed procedure"),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="already registered"):
        register_knowledge_revision(asset, "rev-001")


@pytest.mark.parametrize("revision_id", ["", ".", "..", "../escape", "a/b", "a\\b", "UPPER"])
def test_revision_ids_are_single_safe_lowercase_names(
    tmp_path: Path, revision_id: str
) -> None:
    asset = _asset(tmp_path)

    with pytest.raises(ValueError, match="revision_id"):
        register_knowledge_revision(asset, revision_id)
    with pytest.raises(ValueError, match="revision_id"):
        load_knowledge_revision(asset, revision_id)


def test_register_rejects_revision_symlink(tmp_path: Path) -> None:
    asset = _asset(tmp_path)
    revisions = asset.root / "knowledge" / "revisions"
    revisions.mkdir()
    target = tmp_path / "outside"
    target.mkdir()
    try:
        (revisions / "rev-001").symlink_to(target, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlinks are unavailable: {exc}")

    with pytest.raises(ValueError, match="revision directory must not be a symlink"):
        register_knowledge_revision(asset, "rev-001")


@pytest.mark.parametrize(
    ("filename", "mutator", "error"),
    [
        ("units.jsonl", lambda value: value.replace("revision-unit", "tampered-unit"), "sha256"),
        ("revision.json", lambda value: value.replace("rev-001", "rev-002"), "sha256"),
    ],
)
def test_load_rejects_tampered_revision_files(
    tmp_path: Path, filename: str, mutator: object, error: str
) -> None:
    asset = _asset(tmp_path)
    revision = _write_revision(asset)
    register_knowledge_revision(asset, "rev-001")
    path = revision / filename
    assert callable(mutator)
    path.write_text(mutator(path.read_text(encoding="utf-8")), encoding="utf-8")

    with pytest.raises(ValueError, match=error):
        load_knowledge_revision(asset, "rev-001")


def test_load_rejects_tampered_manifest_hash_and_base_fingerprint(tmp_path: Path) -> None:
    asset = _asset(tmp_path)
    _write_revision(asset)
    register_knowledge_revision(asset, "rev-001")
    manifest_path = asset.root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["p4"]["knowledge_revisions"]["revisions"]["rev-001"]["files"]["units.jsonl"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="registry hash"):
        load_knowledge_revision(asset, "rev-001")

    _write_revision(asset, "rev-002")
    register_knowledge_revision(asset, "rev-002")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["stages"]["evidence"]["outputs"][0]["sha256"] = "f" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="base QA asset fingerprint"):
        load_knowledge_revision(asset, "rev-002")


@pytest.mark.parametrize(
    ("record", "error"),
    [
        ({"evidence_refs": ["ev-external"]}, "must reference video evidence"),
        ({"evidence_refs": ["missing"]}, "unknown evidence"),
        ({"epistemic_status": "external_enrichment"}, "external_enrichment"),
        ({"evidence_refs": ["ev-video", "ev-video"]}, "duplicate evidence_refs"),
    ],
)
def test_register_rejects_noncanonical_or_external_unit_evidence(
    tmp_path: Path, record: dict[str, object], error: str
) -> None:
    asset = _asset(tmp_path)
    revision = _write_revision(asset)
    unit = json.loads((revision / "units.jsonl").read_text(encoding="utf-8"))
    unit.update(record)
    (revision / "units.jsonl").write_text(json.dumps(unit) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match=error):
        register_knowledge_revision(asset, "rev-001")


def test_register_rejects_duplicate_and_unknown_graph_references(tmp_path: Path) -> None:
    asset = _asset(tmp_path)
    revision = _write_revision(asset)
    duplicate = json.loads((revision / "units.jsonl").read_text(encoding="utf-8"))
    (revision / "units.jsonl").write_text(
        json.dumps(duplicate) + "\n" + json.dumps(duplicate) + "\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="duplicate unit_id"):
        register_knowledge_revision(asset, "rev-001")

    _write_revision(asset, "rev-002")
    relation_path = asset.root / "knowledge" / "revisions" / "rev-002" / "relations.jsonl"
    relation = json.loads(relation_path.read_text(encoding="utf-8"))
    relation["target_unit_id"] = "unknown-unit"
    relation_path.write_text(json.dumps(relation) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="unknown knowledge unit"):
        register_knowledge_revision(asset, "rev-002")


def test_register_rejects_nonvideo_relation_and_unknown_synthesis_refs(
    tmp_path: Path,
) -> None:
    asset = _asset(tmp_path)
    revision = _write_revision(asset)
    relation = json.loads((revision / "relations.jsonl").read_text(encoding="utf-8"))
    relation["evidence_refs"] = ["ev-external"]
    (revision / "relations.jsonl").write_text(
        json.dumps(relation) + "\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="must reference video evidence"):
        register_knowledge_revision(asset, "rev-001")

    revision = _write_revision(asset, "rev-002")
    synthesis = json.loads((revision / "synthesis.json").read_text(encoding="utf-8"))
    synthesis["video_summary_refs"] = ["unknown-unit"]
    (revision / "synthesis.json").write_text(
        json.dumps(synthesis) + "\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="unknown knowledge unit"):
        register_knowledge_revision(asset, "rev-002")


def test_revision_retrieval_plan_and_v11_answer_use_one_immutable_graph(
    tmp_path: Path,
) -> None:
    asset = _asset(tmp_path)
    _write_revision(asset)
    register_knowledge_revision(asset, "rev-001")
    build_qa_index(asset, knowledge_revision="rev-001")

    pack = retrieve_question(
        asset, "What procedure does the speaker give?", knowledge_revision="rev-001"
    )
    plan = build_answer_plan(pack)

    assert [candidate["knowledge_id"] for candidate in pack["candidates"]] == [
        "revision-unit"
    ]
    assert pack["knowledge_revision"] == "rev-001"
    assert plan["knowledge_revision"] == "rev-001"
    assert plan["knowledge_revision_sha256"] == pack["knowledge_revision_sha256"]

    claim = AnswerClaim(
        claim_id="claim:001",
        text="The speaker gives a procedure.",
        status="video_explicit",
        knowledge_refs=["revision-unit"],
        evidence_refs=["ev-video"],
        source_spans=[SourceSpan(start_ms=1_000, end_ms=2_000)],
    )
    block = AnswerBlock(
        block_id="block:001", text=claim.text, claim_refs=["claim:001"]
    )
    answer = GroundedAnswer(
        schema_version="1.1",
        asset_id="asset-001",
        question=pack["question"],
        answer=block.text,
        mode="video_only",
        answer_status="video_explicit",
        claims=[claim],
        blocks=[block],
        answer_plan=plan,
        knowledge_revision=pack["knowledge_revision"],
        knowledge_revision_sha256=pack["knowledge_revision_sha256"],
        knowledge_refs=["revision-unit"],
        evidence_refs=["ev-video"],
        source_spans=[SourceSpan(start_ms=1_000, end_ms=2_000)],
        retrieval={"strategy": "lexical"},
    )

    assert validate_grounded_answer(asset, answer) == []


def test_v11_revision_identity_rejects_missing_mismatched_and_legacy_refs(
    tmp_path: Path,
) -> None:
    asset = _asset(tmp_path)
    _write_revision(asset)
    register_knowledge_revision(asset, "rev-001")
    build_qa_index(asset, knowledge_revision="rev-001")
    pack = retrieve_question(asset, "procedure", knowledge_revision="rev-001")
    plan = build_answer_plan(pack)
    base = {
        "schema_version": "1.1",
        "asset_id": "asset-001",
        "question": "procedure",
        "answer": "The speaker gives a procedure.",
        "mode": "video_only",
        "answer_status": "video_explicit",
        "claims": [{"claim_id": "claim:001", "text": "The speaker gives a procedure.", "status": "video_explicit", "knowledge_refs": ["revision-unit"], "evidence_refs": ["ev-video"], "source_spans": [{"start_ms": 1000, "end_ms": 2000}]}],
        "blocks": [{"block_id": "block:001", "text": "The speaker gives a procedure.", "claim_refs": ["claim:001"]}],
        "answer_plan": plan,
        "knowledge_refs": ["revision-unit"],
        "evidence_refs": ["ev-video"],
        "source_spans": [{"start_ms": 1000, "end_ms": 2000}],
        "retrieval": {"strategy": "lexical"},
    }
    with pytest.raises(Exception, match="knowledge_revision"):
        GroundedAnswer(**base)
    with pytest.raises(Exception, match="revision identity"):
        GroundedAnswer(
            **base,
            knowledge_revision="rev-001",
            knowledge_revision_sha256="0" * 64,
        )

    valid = GroundedAnswer(
        **base,
        knowledge_revision=pack["knowledge_revision"],
        knowledge_revision_sha256=pack["knowledge_revision_sha256"],
    )
    legacy_claim = valid.model_copy(
        update={
            "claims": [
                valid.claims[0].model_copy(update={"knowledge_refs": ["legacy-unit"]})
            ],
            "knowledge_refs": ["legacy-unit"],
        }
    )
    assert "claim 1 references unknown knowledge legacy-unit" in validate_grounded_answer(
        asset, legacy_claim
    )


def test_revision_answer_rejects_tampered_revision_and_cross_revision_windows(
    tmp_path: Path,
) -> None:
    asset = _asset(tmp_path)
    _write_revision(asset, "rev-001")
    register_knowledge_revision(asset, "rev-001")
    build_qa_index(asset, knowledge_revision="rev-001")
    pack = retrieve_question(asset, "procedure", knowledge_revision="rev-001")
    plan = build_answer_plan(pack)
    answer = GroundedAnswer(
        schema_version="1.1",
        asset_id="asset-001",
        question="procedure",
        answer="The speaker gives a procedure.",
        mode="video_only",
        answer_status="video_explicit",
        claims=[AnswerClaim(claim_id="claim:001", text="The speaker gives a procedure.", status="video_explicit", knowledge_refs=["revision-unit"], evidence_refs=["ev-video"], source_spans=[SourceSpan(start_ms=1_000, end_ms=2_000)])],
        blocks=[AnswerBlock(block_id="block:001", text="The speaker gives a procedure.", claim_refs=["claim:001"])],
        answer_plan=plan,
        knowledge_revision=pack["knowledge_revision"],
        knowledge_revision_sha256=pack["knowledge_revision_sha256"],
        knowledge_refs=["revision-unit"],
        evidence_refs=["ev-video"],
        source_spans=[SourceSpan(start_ms=1_000, end_ms=2_000)],
        retrieval={"strategy": "lexical"},
    )

    _write_revision(asset, "rev-002")
    revision_two = asset.root / "knowledge" / "revisions" / "rev-002"
    for path in (revision_two / "units.jsonl", revision_two / "relations.jsonl", revision_two / "synthesis.json"):
        path.write_text(path.read_text(encoding="utf-8").replace("revision-unit", "revision-unit-two"), encoding="utf-8")
    register_knowledge_revision(asset, "rev-002")
    build_qa_index(asset, knowledge_revision="rev-002")
    retrieve_question(asset, "procedure", knowledge_revision="rev-002")
    first_windows = asset.root / "index" / "revisions" / "rev-001" / "evidence-windows.jsonl"
    second_windows = asset.root / "index" / "revisions" / "rev-002" / "evidence-windows.jsonl"
    first_windows.write_text(second_windows.read_text(encoding="utf-8"), encoding="utf-8")

    assert any(
        "revision identity does not match the answer" in error
        for error in validate_grounded_answer(asset, answer)
    )

    revision_units = asset.root / "knowledge" / "revisions" / "rev-001" / "units.jsonl"
    revision_units.write_text(revision_units.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    assert any(
        error.startswith("knowledge revision cannot be loaded:")
        for error in validate_grounded_answer(asset, answer)
    )
