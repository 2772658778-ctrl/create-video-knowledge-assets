"""Versioned, video-grounded knowledge revisions for P4 QA."""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from collections.abc import Mapping
from pathlib import Path

from pydantic import ValidationError

from vka.models import Evidence, KnowledgeRelation, KnowledgeUnit, Synthesis
from vka.qa_asset import qa_asset_fingerprint, validate_qa_asset
from vka.store import AssetStore


KNOWLEDGE_REVISION_SCHEMA_VERSION = "1.0"
_REVISION_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_REVISION_FILES = ("units.jsonl", "relations.jsonl", "synthesis.json")


def register_knowledge_revision(
    asset: AssetStore | Path | str, revision_id: str
) -> dict[str, object]:
    """Validate and register a new immutable-style knowledge revision.

    The caller supplies the three graph files under
    ``knowledge/revisions/<revision_id>``.  This function never modifies the
    legacy knowledge graph or its completed-stage record.
    """

    store = _as_store(asset)
    _validate_revision_id(revision_id)
    manifest = _manifest(store)
    registry = _registry_for_update(manifest)
    revisions = registry["revisions"]
    assert isinstance(revisions, dict)
    if revision_id in revisions:
        raise ValueError(f"knowledge revision is already registered: {revision_id}")
    revision_dir = _revision_dir(store, revision_id, create=True)
    readiness_errors = validate_qa_asset(store, profile_id="general-deep")
    if readiness_errors:
        raise ValueError("asset is not ready for knowledge revisions: " + "; ".join(readiness_errors))

    base_fingerprint = qa_asset_fingerprint(store)
    payload = _read_revision_payload(store, revision_id, revision_dir)
    document = _revision_document(revision_id, base_fingerprint, revision_dir)
    _atomic_write_json(store, revision_dir / "revision.json", document, "revision metadata")

    revisions[revision_id] = {
        "base_qa_asset_fingerprint": base_fingerprint,
        "files": {
            **_file_hashes(revision_dir),
        },
    }
    store._write_manifest(manifest)
    return {
        "revision_id": revision_id,
        "base_qa_asset_fingerprint": base_fingerprint,
        "units": payload["units"],
        "relations": payload["relations"],
        "synthesis": payload["synthesis"],
    }


def load_knowledge_revision(
    asset: AssetStore | Path | str, revision_id: str
) -> dict[str, object]:
    """Load a registered revision only when its base and files still match."""

    store = _as_store(asset)
    revision_dir = _revision_dir(store, revision_id)
    manifest = _manifest(store)
    registry_entry = _registry_entry(manifest, revision_id)
    current_fingerprint = qa_asset_fingerprint(store)
    expected_fingerprint = _fingerprint(
        registry_entry.get("base_qa_asset_fingerprint"), "revision registry"
    )
    if expected_fingerprint != current_fingerprint:
        raise ValueError("revision base QA asset fingerprint does not match the current asset")

    registry_files = _file_hash_mapping(registry_entry.get("files"), "revision registry")
    actual_hashes = _file_hashes(revision_dir)
    for name in (*_REVISION_FILES, "revision.json"):
        if registry_files[name] != actual_hashes[name]:
            raise ValueError(f"revision registry hash sha256 does not match {name}")

    document = _read_revision_document(revision_dir / "revision.json")
    if document["revision_id"] != revision_id:
        raise ValueError("revision metadata revision_id does not match its directory")
    if document["base_qa_asset_fingerprint"] != current_fingerprint:
        raise ValueError("revision base QA asset fingerprint does not match the current asset")
    for name, key in (
        ("units.jsonl", "units_sha256"),
        ("relations.jsonl", "relations_sha256"),
        ("synthesis.json", "synthesis_sha256"),
    ):
        if document[key] != actual_hashes[name]:
            raise ValueError(f"revision metadata hash does not match {name}")

    readiness_errors = validate_qa_asset(store, profile_id="general-deep")
    if readiness_errors:
        raise ValueError("asset is not ready for knowledge revisions: " + "; ".join(readiness_errors))
    payload = _read_revision_payload(store, revision_id, revision_dir)
    return {
        "revision_id": revision_id,
        "base_qa_asset_fingerprint": current_fingerprint,
        "units": payload["units"],
        "relations": payload["relations"],
        "synthesis": payload["synthesis"],
    }


def _as_store(asset: AssetStore | Path | str) -> AssetStore:
    store = asset if isinstance(asset, AssetStore) else AssetStore(Path(asset))
    if not store.root.is_dir() or _is_link(store.root):
        raise ValueError("asset root must be a real directory")
    return AssetStore(store.root.resolve())


def _revision_dir(store: AssetStore, revision_id: str, *, create: bool = False) -> Path:
    _validate_revision_id(revision_id)
    root = store.root.resolve()
    knowledge = root / "knowledge"
    _assert_safe_path(root, knowledge, "knowledge directory")
    if not knowledge.is_dir():
        raise ValueError("knowledge directory must exist")
    revisions = knowledge / "revisions"
    _assert_safe_path(root, revisions, "knowledge revisions directory")
    if create:
        revisions.mkdir(exist_ok=True)
    if not revisions.is_dir():
        raise ValueError("knowledge revisions directory must be a directory")
    _assert_safe_path(root, revisions, "knowledge revisions directory")
    revision = revisions / revision_id
    _assert_safe_path(root, revision, "revision directory")
    if create:
        revision.mkdir(exist_ok=True)
    if not revision.is_dir():
        raise ValueError("revision directory must be a directory")
    _assert_safe_path(root, revision, "revision directory")
    return revision


def _validate_revision_id(revision_id: object) -> None:
    if not isinstance(revision_id, str) or not _REVISION_ID.fullmatch(revision_id):
        raise ValueError("revision_id must be a single safe lowercase directory name")


def _read_revision_payload(
    store: AssetStore, revision_id: str, revision_dir: Path
) -> dict[str, object]:
    evidence = _read_evidence(_safe_asset_file(store, "records", "evidence/records.jsonl"))
    units = _read_units(_safe_file(store, revision_dir, "units", "units.jsonl"), evidence)
    relations = _read_relations(
        _safe_file(store, revision_dir, "relations", "relations.jsonl"), units, evidence
    )
    synthesis = _read_synthesis(
        _safe_file(store, revision_dir, "synthesis", "synthesis.json"), units, evidence
    )
    return {"units": units, "relations": relations, "synthesis": synthesis}


def _safe_file(store: AssetStore, revision_dir: Path, label: str, relative: str) -> Path:
    root = store.root.resolve()
    path = revision_dir / relative
    _assert_safe_path(root, path, f"{label} file")
    if not path.is_file():
        raise ValueError(f"{label} file is missing")
    return path


def _safe_asset_file(store: AssetStore, label: str, relative: str) -> Path:
    root = store.root.resolve()
    path = root / relative
    _assert_safe_path(root, path, f"{label} file")
    if not path.is_file():
        raise ValueError(f"{label} file is missing")
    return path


def _read_evidence(path: Path) -> dict[str, Evidence]:
    evidence: dict[str, Evidence] = {}
    for line_number, record in _jsonl_objects(path, "evidence"):
        parsed = _model(Evidence, record, f"evidence record {line_number}")
        _nonblank_id(parsed.evidence_id, f"evidence record {line_number} evidence_id")
        if parsed.evidence_id in evidence:
            raise ValueError(f"duplicate evidence_id: {parsed.evidence_id}")
        evidence[parsed.evidence_id] = parsed
    return evidence


def _read_units(path: Path, evidence: Mapping[str, Evidence]) -> list[dict[str, object]]:
    units: list[dict[str, object]] = []
    unit_ids: set[str] = set()
    for line_number, record in _jsonl_objects(path, "unit"):
        parsed = _model(KnowledgeUnit, record, f"unit record {line_number}")
        _nonblank_id(parsed.unit_id, f"unit record {line_number} unit_id")
        if parsed.unit_id in unit_ids:
            raise ValueError(f"duplicate unit_id: {parsed.unit_id}")
        if parsed.epistemic_status == "external_enrichment":
            raise ValueError(f"unit {parsed.unit_id} must not use external_enrichment")
        _video_refs(parsed.evidence_refs, evidence, f"unit {parsed.unit_id}")
        unit_ids.add(parsed.unit_id)
        units.append(parsed.model_dump(mode="json"))
    return units


def _read_relations(
    path: Path, units: list[dict[str, object]], evidence: Mapping[str, Evidence]
) -> list[dict[str, object]]:
    known_units = {str(unit["unit_id"]): unit for unit in units}
    relations: list[dict[str, object]] = []
    relation_ids: set[str] = set()
    for line_number, record in _jsonl_objects(path, "relation"):
        parsed = _model(KnowledgeRelation, record, f"relation record {line_number}")
        _nonblank_id(parsed.relation_id, f"relation record {line_number} relation_id")
        _nonblank_id(parsed.source_unit_id, f"relation {parsed.relation_id} source_unit_id")
        _nonblank_id(parsed.target_unit_id, f"relation {parsed.relation_id} target_unit_id")
        if parsed.relation_id in relation_ids:
            raise ValueError(f"duplicate relation_id: {parsed.relation_id}")
        missing = sorted({parsed.source_unit_id, parsed.target_unit_id} - set(known_units))
        if missing:
            raise ValueError("relation references unknown knowledge unit: " + ", ".join(missing))
        _video_refs(parsed.evidence_refs, evidence, f"relation {parsed.relation_id}")
        endpoint_refs = set(known_units[parsed.source_unit_id]["evidence_refs"]) | set(
            known_units[parsed.target_unit_id]["evidence_refs"]
        )
        if not set(parsed.evidence_refs).issubset(endpoint_refs):
            raise ValueError(f"relation {parsed.relation_id} evidence_refs must be endpoint evidence")
        relation_ids.add(parsed.relation_id)
        relations.append(parsed.model_dump(mode="json"))
    return relations


def _read_synthesis(
    path: Path, units: list[dict[str, object]], evidence: Mapping[str, Evidence]
) -> dict[str, object]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("synthesis file is not valid JSON") from exc
    if not isinstance(raw, Mapping):
        raise ValueError("synthesis file must be an object")
    parsed = _model(Synthesis, raw, "synthesis")
    known_units = {str(unit["unit_id"]) for unit in units}
    _unit_refs(parsed.video_summary_refs, known_units, "synthesis video_summary_refs")
    _unit_refs(parsed.agent_extension_refs, known_units, "synthesis agent_extension_refs")
    _video_refs(parsed.evidence_refs, evidence, "synthesis")
    return parsed.model_dump(mode="json")


def _model(model: type[Evidence] | type[KnowledgeUnit] | type[KnowledgeRelation] | type[Synthesis], value: object, label: str):
    try:
        return model.model_validate(value)
    except ValidationError as exc:
        raise ValueError(f"{label} does not match its schema: {exc}") from exc


def _video_refs(refs: list[str], evidence: Mapping[str, Evidence], label: str) -> None:
    _unique_nonblank_refs(refs, f"{label} evidence_refs")
    for reference in refs:
        record = evidence.get(reference)
        if record is None:
            raise ValueError(f"{label} references unknown evidence {reference}")
        if record.origin != "video" or not record.spans:
            raise ValueError(f"{label} must reference video evidence with source spans: {reference}")


def _unit_refs(refs: list[str], unit_ids: set[str], label: str) -> None:
    _unique_nonblank_refs(refs, label)
    missing = sorted(set(refs) - unit_ids)
    if missing:
        raise ValueError(f"{label} references unknown knowledge unit: " + ", ".join(missing))


def _unique_nonblank_refs(refs: list[str], label: str) -> None:
    if any(not isinstance(reference, str) or not reference.strip() for reference in refs):
        raise ValueError(f"{label} must contain non-empty strings")
    if len(set(refs)) != len(refs):
        raise ValueError(f"{label} must not contain duplicate evidence_refs")


def _nonblank_id(value: str, label: str) -> None:
    if not value.strip():
        raise ValueError(f"{label} must be a non-empty string")


def _jsonl_objects(path: Path, label: str) -> list[tuple[int, Mapping[str, object]]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        raise ValueError(f"{label} file is not valid JSONL") from exc
    values: list[tuple[int, Mapping[str, object]]] = []
    try:
        for line_number, line in enumerate(lines, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, Mapping):
                raise ValueError(f"{label} record {line_number} must be an object")
            values.append((line_number, value))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} file is not valid JSONL") from exc
    return values


def _revision_document(
    revision_id: str, base_fingerprint: dict[str, str], revision_dir: Path
) -> dict[str, object]:
    hashes = _file_hashes(revision_dir, include_metadata=False)
    return {
        "schema_version": KNOWLEDGE_REVISION_SCHEMA_VERSION,
        "revision_id": revision_id,
        "base_qa_asset_fingerprint": base_fingerprint,
        "units_sha256": hashes["units.jsonl"],
        "relations_sha256": hashes["relations.jsonl"],
        "synthesis_sha256": hashes["synthesis.json"],
    }


def _read_revision_document(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("revision metadata is not valid JSON") from exc
    if not isinstance(value, Mapping):
        raise ValueError("revision metadata must be an object")
    expected = {
        "schema_version",
        "revision_id",
        "base_qa_asset_fingerprint",
        "units_sha256",
        "relations_sha256",
        "synthesis_sha256",
    }
    if set(value) != expected or value.get("schema_version") != KNOWLEDGE_REVISION_SCHEMA_VERSION:
        raise ValueError("revision metadata has an invalid schema")
    _validate_revision_id(value.get("revision_id"))
    fingerprint = _fingerprint(value.get("base_qa_asset_fingerprint"), "revision metadata")
    document: dict[str, object] = dict(value)
    document["base_qa_asset_fingerprint"] = fingerprint
    for key in ("units_sha256", "relations_sha256", "synthesis_sha256"):
        if not isinstance(value.get(key), str) or not _SHA256.fullmatch(str(value[key])):
            raise ValueError(f"revision metadata {key} must be a sha256")
    return document


def _file_hashes(revision_dir: Path, *, include_metadata: bool = True) -> dict[str, str]:
    names = (*_REVISION_FILES, "revision.json") if include_metadata else _REVISION_FILES
    hashes: dict[str, str] = {}
    for name in names:
        path = revision_dir / name
        if not path.is_file() or _is_link(path):
            raise ValueError(f"revision file is missing or unsafe: {name}")
        hashes[name] = _sha256(path)
    return hashes


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest(store: AssetStore) -> dict[str, object]:
    try:
        manifest = store._read_manifest()
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("manifest cannot be read as JSON") from exc
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be an object")
    return manifest


def _registry_for_update(manifest: dict[str, object]) -> dict[str, object]:
    p4 = manifest.setdefault("p4", {})
    if not isinstance(p4, dict):
        raise ValueError("manifest p4 registry must be an object")
    registry = p4.setdefault(
        "knowledge_revisions",
        {"schema_version": KNOWLEDGE_REVISION_SCHEMA_VERSION, "revisions": {}},
    )
    if not isinstance(registry, dict):
        raise ValueError("manifest knowledge revision registry must be an object")
    if registry.get("schema_version") != KNOWLEDGE_REVISION_SCHEMA_VERSION:
        raise ValueError("manifest knowledge revision registry has an invalid schema_version")
    revisions = registry.get("revisions")
    if not isinstance(revisions, dict):
        raise ValueError("manifest knowledge revision registry revisions must be an object")
    return registry


def _registry_entry(manifest: dict[str, object], revision_id: str) -> Mapping[str, object]:
    p4 = manifest.get("p4")
    if not isinstance(p4, Mapping):
        raise ValueError("manifest has no P4 knowledge revision registry")
    registry = p4.get("knowledge_revisions")
    if not isinstance(registry, Mapping) or registry.get("schema_version") != KNOWLEDGE_REVISION_SCHEMA_VERSION:
        raise ValueError("manifest has an invalid P4 knowledge revision registry")
    revisions = registry.get("revisions")
    if not isinstance(revisions, Mapping):
        raise ValueError("manifest P4 knowledge revision registry revisions must be an object")
    entry = revisions.get(revision_id)
    if not isinstance(entry, Mapping):
        raise ValueError(f"knowledge revision is not registered: {revision_id}")
    return entry


def _fingerprint(value: object, label: str) -> dict[str, str]:
    if not isinstance(value, Mapping) or not value:
        raise ValueError(f"{label} base QA asset fingerprint must be a non-empty object")
    fingerprint: dict[str, str] = {}
    for path, sha256 in value.items():
        if not isinstance(path, str) or not path or not isinstance(sha256, str) or not _SHA256.fullmatch(sha256):
            raise ValueError(f"{label} base QA asset fingerprint is invalid")
        fingerprint[path] = sha256
    return {path: fingerprint[path] for path in sorted(fingerprint)}


def _file_hash_mapping(value: object, label: str) -> dict[str, str]:
    if not isinstance(value, Mapping) or set(value) != set((*_REVISION_FILES, "revision.json")):
        raise ValueError(f"{label} files must contain all revision hashes")
    hashes: dict[str, str] = {}
    for name in (*_REVISION_FILES, "revision.json"):
        sha256 = value[name]
        if not isinstance(sha256, str) or not _SHA256.fullmatch(sha256):
            raise ValueError(f"{label} hash for {name} must be a sha256")
        hashes[name] = sha256
    return hashes


def _atomic_write_json(store: AssetStore, destination: Path, value: Mapping[str, object], label: str) -> None:
    root = store.root.resolve()
    _assert_safe_path(root, destination, f"{label} destination")
    temporary: Path | None = None
    try:
        for _ in range(16):
            candidate = destination.parent / f".{destination.name}.{uuid.uuid4().hex}.tmp"
            _assert_safe_path(root, candidate, f"{label} temporary path")
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
            _assert_safe_path(root, temporary, f"{label} temporary path")
            _assert_safe_path(root, destination, f"{label} destination")
            os.replace(temporary, destination)
            temporary = None
            return
        raise OSError(f"could not allocate a {label} temporary file")
    finally:
        if temporary is not None and temporary.exists():
            _assert_safe_path(root, temporary, f"{label} temporary path")
            temporary.unlink()


def _is_link(path: Path) -> bool:
    is_junction = getattr(path, "is_junction", None)
    return path.is_symlink() or (callable(is_junction) and is_junction())


def _assert_safe_path(root: Path, path: Path, label: str) -> None:
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"{label} must stay within the asset root") from exc
    current = root
    for part in relative.parts:
        current = current / part
        if _is_link(current):
            raise ValueError(f"{label} must not be a symlink")
    try:
        path.resolve().relative_to(root)
    except ValueError as exc:
        raise ValueError(f"{label} must stay within the asset root") from exc
