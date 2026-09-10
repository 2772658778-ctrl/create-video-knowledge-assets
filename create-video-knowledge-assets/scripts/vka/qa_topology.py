"""Deterministic, reference-only topology for QA assets."""

from __future__ import annotations

import json
import os
import uuid
import hashlib
from collections.abc import Mapping
from pathlib import Path

from pydantic import ValidationError

from vka.models import Evidence, KnowledgeRelation, KnowledgeUnit
from vka.qa_asset import qa_asset_fingerprint, validate_qa_asset
from vka.qa_revision import load_knowledge_revision
from vka.store import AssetStore


TOPOLOGY_SCHEMA_VERSION = "1.0"
_SUPPORTED_PROFILE_ID = "course-notes"
_EPISTEMIC_STATUSES = frozenset(
    {
        "video_explicit",
        "agent_inference",
        "external_enrichment",
        "insufficient_evidence",
    }
)


def build_qa_topology(
    asset: AssetStore | Path | str,
    *,
    profile_id: str = "course-notes",
    knowledge_revision: str | None = None,
) -> dict[str, object]:
    """Build or reuse a fact-only QA topology in ``index/qa-topology.json``."""
    if profile_id != _SUPPORTED_PROFILE_ID:
        raise ValueError(f"P4.1 QA builders support only {_SUPPORTED_PROFILE_ID!r} profile_id")
    store = _as_store(asset)
    revision = _load_revision(store, knowledge_revision)
    readiness_errors = validate_qa_asset(store, profile_id=profile_id)
    if readiness_errors:
        raise ValueError("asset is not ready for QA: " + "; ".join(readiness_errors))

    asset_id = _asset_id(store)
    fingerprint = qa_asset_fingerprint(store)
    evidence = _read_evidence(store.root / "evidence" / "records.jsonl")
    if revision is None:
        units = _read_units(store.root / "knowledge" / "units.jsonl", evidence)
        relations = _read_relations(store.root / "knowledge" / "relations.jsonl", units, evidence)
    else:
        units = _read_units_records(_revision_records(revision, "units"), evidence)
        relations = _read_relations_records(_revision_records(revision, "relations"), units, evidence)
    topology = _topology(
        asset_id,
        profile_id,
        fingerprint,
        units,
        relations,
        evidence,
        knowledge_revision=knowledge_revision,
        revision_sha256=_revision_sha256(revision) if revision is not None else None,
    )
    topology_path = _topology_path(store, knowledge_revision)
    existing = _read_topology(topology_path)
    if existing == topology:
        return existing
    _atomic_write_json(store, topology, knowledge_revision)
    return topology


def _as_store(asset: AssetStore | Path | str) -> AssetStore:
    return asset if isinstance(asset, AssetStore) else AssetStore(Path(asset))


def _asset_id(store: AssetStore) -> str:
    try:
        manifest = store._read_manifest()
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("manifest cannot be read as JSON") from exc
    return _required_string(_mapping(manifest, "manifest"), "asset_id", "manifest")


def _read_evidence(path: Path) -> dict[str, Evidence]:
    evidence: dict[str, Evidence] = {}
    for line_number, record in _jsonl_objects(path, "evidence"):
        label = f"evidence record {line_number}"
        parsed = _validated_evidence(record, label)
        evidence_id = _required_string(record, "evidence_id", label)
        if evidence_id in evidence:
            raise ValueError(f"duplicate evidence_id: {evidence_id}")
        if parsed.evidence_id != evidence_id:
            raise ValueError(f"{label} evidence_id must be a non-empty string")
        evidence[evidence_id] = parsed
    return evidence


def _read_units(
    path: Path, evidence: Mapping[str, Evidence]
) -> dict[str, dict[str, object]]:
    return _read_units_records(
        [record for _, record in _jsonl_objects(path, "knowledge")], evidence
    )


def _read_units_records(
    records: list[Mapping[str, object]], evidence: Mapping[str, Evidence]
) -> dict[str, dict[str, object]]:
    units: dict[str, dict[str, object]] = {}
    for line_number, record in enumerate(records, start=1):
        label = f"knowledge record {line_number}"
        unit = _validated_unit(record, label)
        unit_id = _required_string(record, "unit_id", label)
        if unit_id in units:
            raise ValueError(f"duplicate unit_id: {unit_id}")
        status = _required_string(record, "epistemic_status", label)
        if status not in _EPISTEMIC_STATUSES:
            raise ValueError(f"{label} has an invalid epistemic_status")
        evidence_refs = _string_list(record.get("evidence_refs"), f"{label} evidence_refs")
        _require_known_ids(evidence_refs, set(evidence), "evidence")
        video_evidence_refs = [
            evidence_id
            for evidence_id in evidence_refs
            if evidence[evidence_id].origin == "video"
        ]
        source_spans = sorted(
            {
                (span.start_ms, span.end_ms)
                for evidence_id in video_evidence_refs
                for span in evidence[evidence_id].spans
            }
        )
        inspected_frame_refs = sorted(
            evidence_id
            for evidence_id in video_evidence_refs
            if evidence[evidence_id].modality == "frame"
            and evidence[evidence_id].quality.get("review") == "directly_inspected"
        )
        units[unit_id] = {
            "epistemic_status": status,
            "evidence_refs": sorted(video_evidence_refs),
            "source_spans": [
                {"start_ms": start_ms, "end_ms": end_ms}
                for start_ms, end_ms in source_spans
            ],
            "inspected_frame_refs": inspected_frame_refs,
        }
    return units


def _read_relations(
    path: Path,
    units: Mapping[str, Mapping[str, object]],
    evidence: Mapping[str, Evidence],
) -> list[dict[str, object]]:
    return _read_relations_records(
        [record for _, record in _jsonl_objects(path, "relation")], units, evidence
    )


def _read_relations_records(
    records: list[Mapping[str, object]],
    units: Mapping[str, Mapping[str, object]],
    evidence: Mapping[str, Evidence],
) -> list[dict[str, object]]:
    relations: list[dict[str, object]] = []
    relation_ids: set[str] = set()
    for line_number, record in enumerate(records, start=1):
        label = f"relation record {line_number}"
        relation = _validated_relation(record, label)
        relation_id = _required_string(record, "relation_id", label)
        if relation_id in relation_ids:
            raise ValueError(f"duplicate relation_id: {relation_id}")
        source = _required_string(record, "source_unit_id", label)
        target = _required_string(record, "target_unit_id", label)
        _require_known_ids([source, target], set(units), "knowledge unit")
        evidence_refs = _string_list(record.get("evidence_refs"), f"{label} evidence_refs")
        _require_known_ids(evidence_refs, set(evidence), "evidence")
        endpoint_evidence_refs = set(units[source]["evidence_refs"]) | set(
            units[target]["evidence_refs"]
        )
        if not set(evidence_refs).issubset(endpoint_evidence_refs):
            raise ValueError("relation evidence_refs must be endpoint evidence")
        for evidence_id in evidence_refs:
            record = evidence[evidence_id]
            if record.origin != "video" or not record.spans:
                raise ValueError("relation evidence_refs must be video evidence with source spans")
        relation_ids.add(relation_id)
        relations.append(
            {
                "relation_id": relation_id,
                "source_unit_id": source,
                "target_unit_id": target,
                "relation_type": relation.relation_type,
            }
        )
    return relations


def _topology(
    asset_id: str,
    profile_id: str,
    fingerprint: dict[str, str],
    units: Mapping[str, Mapping[str, object]],
    relations: list[Mapping[str, object]],
    evidence: Mapping[str, Evidence],
    *,
    knowledge_revision: str | None,
    revision_sha256: str | None,
) -> dict[str, object]:
    available_ids = {
        unit_id
        for unit_id, unit in units.items()
        if unit["epistemic_status"] != "external_enrichment" and unit["evidence_refs"]
    }
    inbound: dict[str, list[str]] = {unit_id: [] for unit_id in available_ids}
    outbound: dict[str, list[str]] = {unit_id: [] for unit_id in available_ids}
    for relation in relations:
        source = str(relation["source_unit_id"])
        target = str(relation["target_unit_id"])
        if source not in available_ids or target not in available_ids:
            continue
        relation_id = str(relation["relation_id"])
        outbound[source].append(relation_id)
        inbound[target].append(relation_id)

    facets: list[dict[str, object]] = []
    for unit_id in sorted(available_ids):
        unit = units[unit_id]
        facets.append(
            {
                "unit_id": unit_id,
                "evidence_refs": sorted(set(_as_string_list(unit["evidence_refs"]))),
                "source_spans": list(unit["source_spans"]),
                "inspected_frame_refs": list(unit["inspected_frame_refs"]),
                "inbound_relation_ids": sorted(inbound[unit_id]),
                "outbound_relation_ids": sorted(outbound[unit_id]),
            }
        )
    topology: dict[str, object] = {
        "schema_version": TOPOLOGY_SCHEMA_VERSION,
        "asset_id": asset_id,
        "profile_id": profile_id,
        "qa_asset_fingerprint": fingerprint,
        "facets": facets,
    }
    if knowledge_revision is not None:
        topology["knowledge_revision"] = knowledge_revision
        topology["knowledge_revision_sha256"] = revision_sha256
    return topology


def _read_topology(path: Path) -> dict[str, object] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return dict(value) if isinstance(value, Mapping) else None


def _topology_path(store: AssetStore, revision_id: str | None = None) -> Path:
    root = store.root
    if not root.is_dir() or _is_link(root):
        raise ValueError("asset root must be a real directory")
    root = root.resolve()
    index_dir = root / "index"
    _assert_safe_path(root, index_dir, "topology index directory")
    index_dir.mkdir(exist_ok=True)
    if not index_dir.is_dir():
        raise ValueError("topology index directory must be a directory")
    _assert_safe_path(root, index_dir, "topology index directory")
    if revision_id is not None:
        revisions_dir = index_dir / "revisions"
        _assert_safe_path(root, revisions_dir, "topology revisions directory")
        revisions_dir.mkdir(exist_ok=True)
        if not revisions_dir.is_dir():
            raise ValueError("topology revisions directory must be a directory")
        destination_dir = revisions_dir / revision_id
        _assert_safe_path(root, destination_dir, "topology revision directory")
        destination_dir.mkdir(exist_ok=True)
        if not destination_dir.is_dir():
            raise ValueError("topology revision directory must be a directory")
    else:
        destination_dir = index_dir
    destination = destination_dir / "qa-topology.json"
    if _is_link(destination):
        raise ValueError("topology destination must not be a symlink")
    _assert_safe_path(root, destination, "topology destination")
    return destination


def _atomic_write_json(
    store: AssetStore, value: Mapping[str, object], revision_id: str | None = None
) -> None:
    destination = _topology_path(store, revision_id)
    root = store.root.resolve()
    temporary: Path | None = None
    try:
        for _ in range(16):
            candidate = destination.parent / f".{destination.name}.{uuid.uuid4().hex}.tmp"
            _assert_safe_path(root, candidate, "topology temporary path")
            try:
                descriptor = os.open(candidate, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                continue
            temporary = candidate
            with os.fdopen(descriptor, "w", encoding="utf-8") as file:
                json.dump(value, file, ensure_ascii=False, sort_keys=True, indent=2)
                file.write("\n")
                file.flush()
                os.fsync(file.fileno())
            _assert_safe_path(root, temporary, "topology temporary path")
            _assert_safe_path(root, destination, "topology destination")
            os.replace(temporary, destination)
            temporary = None
            return
        raise OSError("could not allocate a unique topology temporary file")
    finally:
        if temporary is not None and temporary.exists():
            _assert_safe_path(root, temporary, "topology temporary path")
            temporary.unlink()


def _is_link(path: Path) -> bool:
    is_junction = getattr(path, "is_junction", None)
    return path.is_symlink() or (callable(is_junction) and is_junction())


def _assert_safe_path(root: Path, path: Path, label: str) -> None:
    if _is_link(path):
        raise ValueError(f"{label} must not be a symlink")
    try:
        path.resolve().relative_to(root)
    except ValueError as exc:
        raise ValueError(f"{label} must stay within the asset root") from exc


def _validated_evidence(record: Mapping[str, object], label: str) -> Evidence:
    try:
        return Evidence.model_validate(record)
    except ValidationError as exc:
        raise ValueError(f"{label} is invalid: {exc}") from exc


def _validated_unit(record: Mapping[str, object], label: str) -> KnowledgeUnit:
    try:
        return KnowledgeUnit.model_validate(record)
    except ValidationError as exc:
        raise ValueError(f"{label} is invalid: {exc}") from exc


def _validated_relation(record: Mapping[str, object], label: str) -> KnowledgeRelation:
    try:
        return KnowledgeRelation.model_validate(record)
    except ValidationError as exc:
        raise ValueError(f"{label} is invalid: {exc}") from exc


def _jsonl_objects(path: Path, label: str) -> list[tuple[int, Mapping[str, object]]]:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as exc:
        raise ValueError(f"{label} records are not valid JSONL") from exc
    records: list[tuple[int, Mapping[str, object]]] = []
    try:
        for line_number, line in enumerate(text.splitlines(), start=1):
            if line.strip():
                records.append((line_number, _mapping(json.loads(line), f"{label} record {line_number}")))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} records are not valid JSONL") from exc
    return records


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return value


def _required_string(record: Mapping[str, object], key: str, label: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} {key} must be a non-empty string")
    return value


def _string_list(value: object, label: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise ValueError(f"{label} must be a list of non-empty strings")
    if len(set(value)) != len(value):
        raise ValueError(f"{label} must not contain duplicate IDs")
    return list(value)


def _as_string_list(value: object) -> list[str]:
    assert isinstance(value, list)
    return [str(item) for item in value]


def _require_known_ids(ids: list[str], known_ids: set[str], label: str) -> None:
    missing = sorted(set(ids) - known_ids)
    if missing:
        raise ValueError(f"unknown {label} IDs: {', '.join(missing)}")


def _load_revision(store: AssetStore, revision_id: str | None) -> dict[str, object] | None:
    if revision_id is None:
        return None
    return load_knowledge_revision(store, revision_id)


def _revision_records(revision: Mapping[str, object], key: str) -> list[Mapping[str, object]]:
    records = revision.get(key)
    if not isinstance(records, list) or not all(isinstance(record, Mapping) for record in records):
        raise ValueError(f"loaded knowledge revision {key} are invalid")
    return list(records)


def _revision_sha256(revision: Mapping[str, object]) -> str:
    payload = {
        "revision_id": revision.get("revision_id"),
        "base_qa_asset_fingerprint": revision.get("base_qa_asset_fingerprint"),
        "units": revision.get("units"),
        "relations": revision.get("relations"),
        "synthesis": revision.get("synthesis"),
    }
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
