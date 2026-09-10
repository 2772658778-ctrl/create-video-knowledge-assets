"""Deterministic, local lexical indexing for grounded QA knowledge units."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from vka.qa_asset import qa_asset_fingerprint, validate_qa_asset
from vka.qa_revision import load_knowledge_revision
from vka.store import AssetStore


INDEX_SCHEMA_VERSION = "1.0"
_SUPPORTED_PROFILE_ID = "course-notes"
_IDENTIFIER = re.compile(r"[a-z0-9]+")
_COMPACT_CJK_TEXT = re.compile(r"[^a-z0-9\u4e00-\u9fff]")
_CJK = re.compile(r"[\u4e00-\u9fff]")
_IMPORTANCE = {"low", "medium", "high"}
_EPISMIC_STATUSES = {
    "video_explicit",
    "agent_inference",
    "external_enrichment",
    "insufficient_evidence",
}
_SNAPSHOT_ATTEMPTS = 3


def lexical_terms(text: str) -> list[str]:
    """Return stable identifier terms plus mixed Chinese character bigrams.

    Identifiers retain useful model and product names while CJK bigrams make
    unsegmented Chinese queries retrievable. The compact sequence deliberately
    crosses script boundaries, so ``用 Colab`` contributes ``用c`` and ``co``.
    """
    if not isinstance(text, str):
        raise ValueError("lexical text must be a string")
    lowered = text.lower()
    terms = _IDENTIFIER.findall(lowered)
    compact = _COMPACT_CJK_TEXT.sub("", lowered)
    if _CJK.search(compact):
        terms.extend(compact[index : index + 2] for index in range(len(compact) - 1))
    return list(dict.fromkeys(term for term in terms if term))


def build_qa_index(
    asset: AssetStore | Path | str,
    *,
    profile_id: str = "course-notes",
    knowledge_revision: str | None = None,
) -> dict[str, object]:
    """Build (or reuse) a knowledge-only FTS5 index under ``asset/index``."""
    if profile_id != _SUPPORTED_PROFILE_ID:
        raise ValueError(f"P4.1 QA builders support only {_SUPPORTED_PROFILE_ID!r} profile_id")
    store = _as_store(asset)
    revision = _load_revision(store, knowledge_revision)
    readiness_errors = validate_qa_asset(store, profile_id=profile_id)
    if readiness_errors:
        raise ValueError("asset is not ready for QA: " + "; ".join(readiness_errors))

    manifest = _asset_manifest(store)
    asset_id = _required_string(manifest, "asset_id", "manifest")
    fingerprint = qa_asset_fingerprint(store)
    course_view_hash = _course_view_sha256(store, profile_id)
    revision_sha256 = _revision_sha256(revision) if revision is not None else None
    index_dir = _index_dir(store, knowledge_revision, create=knowledge_revision is not None)
    revision_root = store.root.resolve() if knowledge_revision is not None else None
    existing = _read_index_manifest(index_dir / "index-manifest.json")
    if _index_is_current(
        existing,
        asset_id=asset_id,
        profile_id=profile_id,
        fingerprint=fingerprint,
        course_view_hash=course_view_hash,
        knowledge_revision=knowledge_revision,
        revision_sha256=revision_sha256,
        index_dir=index_dir,
    ):
        return existing

    evidence = _read_evidence(store.root / "evidence" / "records.jsonl")
    locations = _course_locations(store.root, profile_id)
    if revision is None:
        chunks = _build_chunks(store.root / "knowledge" / "units.jsonl", evidence, locations)
    else:
        chunks = _build_chunks_records(_revision_units(revision), evidence, locations)

    chunks_path = index_dir / "chunks.jsonl"
    sqlite_path = index_dir / "lexical.sqlite"
    _atomic_write_text(chunks_path, _jsonl_text(chunks), root=revision_root)
    _write_sqlite(sqlite_path, chunks, root=revision_root)

    index_manifest: dict[str, object] = {
        "schema_version": INDEX_SCHEMA_VERSION,
        "asset_id": asset_id,
        "profile_id": profile_id,
        "qa_asset_fingerprint": fingerprint,
        "course_view_sha256": course_view_hash,
        "chunks_sha256": _sha256_file(chunks_path),
        "sqlite_sha256": _sha256_file(sqlite_path),
    }
    if knowledge_revision is not None:
        index_manifest["knowledge_revision"] = knowledge_revision
        index_manifest["knowledge_revision_sha256"] = revision_sha256
    _atomic_write_text(
        index_dir / "index-manifest.json",
        json.dumps(index_manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        root=revision_root,
    )
    return index_manifest


def read_chunks(path: Path | str) -> list[dict[str, object]]:
    """Read chunks JSONL without accepting non-object records."""
    try:
        return _chunks_from_bytes(_read_bytes(Path(path)))
    except OSError as exc:
        raise ValueError("chunks are not valid JSONL") from exc


def _chunks_from_bytes(content: bytes) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    try:
        text = content.decode("utf-8")
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, Mapping):
                raise ValueError(f"chunk {line_number} must be an object")
            records.append(dict(value))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("chunks are not valid JSONL") from exc
    return records


def read_qa_index(
    asset: AssetStore | Path | str,
    *,
    profile_id: str = "course-notes",
    knowledge_revision: str | None = None,
) -> dict[str, object]:
    """Load one published index generation after checking every declared hash.

    Consumers must use this boundary rather than opening the fixed index files
    independently. A writer publishes chunks and SQLite first, then publishes
    the manifest last; a manifest that cannot authenticate both files is never
    accepted as a usable generation. The caller must close the returned
    ``sqlite_connection`` after completing retrieval.
    """
    store = _as_store(asset)
    revision = _load_revision(store, knowledge_revision)
    readiness_errors = validate_qa_asset(store, profile_id=profile_id)
    if readiness_errors:
        raise ValueError("asset is not ready for QA: " + "; ".join(readiness_errors))
    revision_sha256 = _revision_sha256(revision) if revision is not None else None
    index_dir = _index_dir(store, knowledge_revision)
    for _ in range(_SNAPSHOT_ATTEMPTS):
        source_manifest_bytes = _read_bytes(store.root / "manifest.json")
        source_manifest = _mapping_from_json_bytes(source_manifest_bytes, "manifest")
        asset_id = _required_string(source_manifest, "asset_id", "manifest")
        fingerprint = qa_asset_fingerprint(store)
        course_view_hash = _course_view_sha256(store, profile_id)
        index_manifest_bytes = _read_bytes(index_dir / "index-manifest.json")
        index_manifest = _index_manifest_from_bytes(index_manifest_bytes)
        chunks_bytes = _read_bytes(index_dir / "chunks.jsonl")
        connection = _open_sqlite_snapshot(index_dir / "lexical.sqlite")
        accepted = False
        try:
            if not _snapshot_matches(
                index_manifest,
                asset_id=asset_id,
                profile_id=profile_id,
                fingerprint=fingerprint,
                course_view_hash=course_view_hash,
                knowledge_revision=knowledge_revision,
                revision_sha256=revision_sha256,
                chunks_bytes=chunks_bytes,
                connection=connection,
            ):
                continue

            final_index_manifest_bytes = _read_bytes(index_dir / "index-manifest.json")
            final_source_manifest_bytes = _read_bytes(store.root / "manifest.json")
            final_fingerprint = qa_asset_fingerprint(store)
            final_course_view_hash = _course_view_sha256(store, profile_id)
            if (
                final_index_manifest_bytes != index_manifest_bytes
                or final_source_manifest_bytes != source_manifest_bytes
                or final_fingerprint != fingerprint
                or final_course_view_hash != course_view_hash
            ):
                continue

            assert index_manifest is not None
            chunks = _chunks_from_bytes(chunks_bytes)
            accepted = True
            return {
                "manifest": index_manifest,
                "chunks": chunks,
                "sqlite_connection": connection,
            }
        finally:
            if not accepted:
                connection.close()
    raise ValueError("QA index generation is incomplete or mixed; rebuild the index")


def _as_store(asset: AssetStore | Path | str) -> AssetStore:
    return asset if isinstance(asset, AssetStore) else AssetStore(Path(asset))


def _asset_manifest(store: AssetStore) -> Mapping[str, object]:
    manifest = store._read_manifest()
    if not isinstance(manifest, Mapping):
        raise ValueError("manifest must be an object")
    return manifest


def _course_view_sha256(store: AssetStore, profile_id: str) -> str | None:
    if profile_id != "course-notes":
        return None
    return _sha256_file(store.root / "views" / "course-notes" / "document.json")


def _read_index_manifest(path: Path) -> dict[str, object] | None:
    try:
        return _index_manifest_from_bytes(_read_bytes(path))
    except OSError:
        return None


def _index_manifest_from_bytes(content: bytes) -> dict[str, object] | None:
    try:
        return dict(_mapping_from_json_bytes(content, "index manifest"))
    except ValueError:
        return None


def _mapping_from_json_bytes(content: bytes, label: str) -> Mapping[str, object]:
    try:
        value = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} is not valid JSON") from exc
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return value


def _index_is_current(
    existing: dict[str, object] | None,
    *,
    asset_id: str,
    profile_id: str,
    fingerprint: dict[str, str],
    course_view_hash: str | None,
    knowledge_revision: str | None,
    revision_sha256: str | None,
    index_dir: Path,
) -> bool:
    if existing is None:
        return False
    if (
        existing.get("schema_version") != INDEX_SCHEMA_VERSION
        or existing.get("asset_id") != asset_id
        or existing.get("profile_id") != profile_id
        or existing.get("qa_asset_fingerprint") != fingerprint
        or existing.get("course_view_sha256") != course_view_hash
        or existing.get("knowledge_revision") != knowledge_revision
    ):
        return False
    if knowledge_revision is not None and existing.get("knowledge_revision_sha256") != revision_sha256:
        return False
    for filename, key in (("chunks.jsonl", "chunks_sha256"), ("lexical.sqlite", "sqlite_sha256")):
        expected = existing.get(key)
        path = index_dir / filename
        if not isinstance(expected, str) or not path.is_file() or _sha256_file(path) != expected:
            return False
    return True


def _snapshot_matches(
    index_manifest: dict[str, object] | None,
    *,
    asset_id: str,
    profile_id: str,
    fingerprint: dict[str, str],
    course_view_hash: str | None,
    knowledge_revision: str | None,
    revision_sha256: str | None,
    chunks_bytes: bytes,
    connection: sqlite3.Connection,
) -> bool:
    if index_manifest is None:
        return False
    if (
        index_manifest.get("schema_version") != INDEX_SCHEMA_VERSION
        or index_manifest.get("asset_id") != asset_id
        or index_manifest.get("profile_id") != profile_id
        or index_manifest.get("qa_asset_fingerprint") != fingerprint
        or index_manifest.get("course_view_sha256") != course_view_hash
        or index_manifest.get("knowledge_revision") != knowledge_revision
    ):
        return False
    if knowledge_revision is not None and index_manifest.get("knowledge_revision_sha256") != revision_sha256:
        return False
    chunks_sha256 = index_manifest.get("chunks_sha256")
    sqlite_sha256 = index_manifest.get("sqlite_sha256")
    return (
        isinstance(chunks_sha256, str)
        and hashlib.sha256(chunks_bytes).hexdigest() == chunks_sha256
        and isinstance(sqlite_sha256, str)
        and hashlib.sha256(connection.serialize()).hexdigest() == sqlite_sha256
    )


def _open_sqlite_snapshot(path: Path) -> sqlite3.Connection:
    try:
        connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
        connection.execute("PRAGMA query_only = ON")
        connection.execute("BEGIN")
        return connection
    except (OSError, sqlite3.Error) as exc:
        raise ValueError("QA index generation is incomplete or mixed; rebuild the index") from exc


def _read_evidence(path: Path) -> dict[str, dict[str, object]]:
    records: dict[str, dict[str, object]] = {}
    for line_number, value in _jsonl_objects(path, "evidence"):
        evidence_id = _required_string(value, "evidence_id", f"evidence record {line_number}")
        if evidence_id in records:
            raise ValueError(f"duplicate evidence_id: {evidence_id}")
        origin = _required_string(value, "origin", f"evidence record {line_number}")
        if origin not in {"video", "external", "generated"}:
            raise ValueError(f"evidence record {line_number} has an invalid origin")
        spans = value.get("spans", [])
        if not isinstance(spans, list):
            raise ValueError(f"evidence record {line_number} spans must be a list")
        resolved_spans = _normalized_spans(spans, f"evidence record {line_number}")
        if origin == "video" and not resolved_spans:
            raise ValueError(f"video evidence {evidence_id} requires source spans")
        records[evidence_id] = {"origin": origin, "spans": resolved_spans}
    return records


def _build_chunks(
    path: Path,
    evidence: Mapping[str, Mapping[str, object]],
    locations: Mapping[str, list[dict[str, object]]],
) -> list[dict[str, object]]:
    return _build_chunks_records(
        [unit for _, unit in _jsonl_objects(path, "knowledge")], evidence, locations
    )


def _build_chunks_records(
    records: Sequence[Mapping[str, object]],
    evidence: Mapping[str, Mapping[str, object]],
    locations: Mapping[str, list[dict[str, object]]],
) -> list[dict[str, object]]:
    chunks: list[dict[str, object]] = []
    seen_units: set[str] = set()
    for line_number, unit in enumerate(records, start=1):
        unit_id = _required_string(unit, "unit_id", f"knowledge record {line_number}")
        if unit_id in seen_units:
            raise ValueError(f"duplicate unit_id: {unit_id}")
        seen_units.add(unit_id)
        status = _required_string(unit, "epistemic_status", f"knowledge record {line_number}")
        if status not in _EPISMIC_STATUSES:
            raise ValueError(f"knowledge record {line_number} has an invalid epistemic_status")
        if status == "external_enrichment":
            continue
        title = _required_string(unit, "title", f"knowledge record {line_number}")
        statement = _required_string(unit, "statement", f"knowledge record {line_number}")
        importance = _required_string(unit, "importance", f"knowledge record {line_number}")
        if importance not in _IMPORTANCE:
            raise ValueError(f"knowledge record {line_number} has an invalid importance")
        refs = _string_list(unit.get("evidence_refs"), f"knowledge record {line_number} evidence_refs")
        if not refs:
            raise ValueError(f"knowledge record {line_number} evidence_refs must not be empty")
        unknown = sorted(set(refs) - set(evidence))
        if unknown:
            raise ValueError(f"knowledge unit {unit_id} references unknown evidence: {', '.join(unknown)}")
        spans = [
            span
            for evidence_ref in refs
            if evidence[evidence_ref]["origin"] == "video"
            for span in evidence[evidence_ref]["spans"]  # type: ignore[index]
        ]
        payload: dict[str, object] = {
            "chunk_id": f"ku:{unit_id}",
            "title": title,
            "statement": statement,
            "terms": lexical_terms(" ".join((title, statement, *(_string_list(unit.get("tags", []), f"knowledge record {line_number} tags"))))),
            "epistemic_status": status,
            "importance": importance,
            "knowledge_refs": [unit_id],
            "evidence_refs": refs,
            "source_spans": _sorted_unique_spans(spans),
        }
        if unit_id in locations:
            payload["course_locations"] = locations[unit_id]
        chunks.append(payload)
    return sorted(chunks, key=lambda chunk: str(chunk["chunk_id"]))


def _load_revision(store: AssetStore, revision_id: str | None) -> dict[str, object] | None:
    if revision_id is None:
        return None
    return load_knowledge_revision(store, revision_id)


def _revision_units(revision: Mapping[str, object]) -> list[Mapping[str, object]]:
    units = revision.get("units")
    if not isinstance(units, list) or not all(isinstance(unit, Mapping) for unit in units):
        raise ValueError("loaded knowledge revision units are invalid")
    return list(units)


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


def _index_dir(
    store: AssetStore, revision_id: str | None, *, create: bool = False
) -> Path:
    if revision_id is None:
        return store.root / "index"

    root = store.root.resolve()
    if not root.is_dir() or _is_link(root):
        raise ValueError("asset root must be a real directory")
    index_dir = root / "index"
    revisions_dir = index_dir / "revisions"
    revision_dir = revisions_dir / revision_id
    for directory, label in (
        (index_dir, "index directory"),
        (revisions_dir, "revision index revisions directory"),
        (revision_dir, "revision index directory"),
    ):
        _assert_safe_path(root, directory, label)
        if create:
            directory.mkdir(exist_ok=True)
        if directory.exists() and not directory.is_dir():
            raise ValueError(f"{label} must be a directory")
        _assert_safe_path(root, directory, label)
    return revision_dir


def _course_locations(root: Path, profile_id: str) -> dict[str, list[dict[str, object]]]:
    if profile_id != "course-notes":
        return {}
    document_path = root / "views" / "course-notes" / "document.json"
    try:
        document = json.loads(document_path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("course-notes document is invalid") from exc
    if not isinstance(document, Mapping):
        raise ValueError("course-notes document must be an object")
    sections = document.get("sections")
    if not isinstance(sections, list):
        return {}
    result: dict[str, list[dict[str, object]]] = {}
    for section_index, section in enumerate(sections, start=1):
        if not isinstance(section, Mapping):
            raise ValueError(f"course section {section_index} must be an object")
        title = _required_string(section, "title", f"course section {section_index}")
        blocks = section.get("blocks", [])
        if not isinstance(blocks, list):
            raise ValueError(f"course section {section_index} blocks must be a list")
        location = {"section_index": section_index, "title": title}
        for block in blocks:
            if not isinstance(block, Mapping):
                raise ValueError(f"course section {section_index} block must be an object")
            for unit_id in _string_list(block.get("knowledge_refs", []), f"course section {section_index} knowledge_refs"):
                result.setdefault(unit_id, []).append(location)
    return result


def _write_sqlite(
    destination: Path,
    chunks: Sequence[Mapping[str, object]],
    *,
    root: Path | None = None,
) -> None:
    _assert_write_destination(root, destination)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".lexical-", suffix=".sqlite", dir=destination.parent)
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        connection = sqlite3.connect(temporary)
        try:
            connection.execute("CREATE TABLE chunks (chunk_id TEXT PRIMARY KEY, payload_json TEXT NOT NULL)")
            connection.execute(
                "CREATE VIRTUAL TABLE chunk_fts USING fts5(chunk_id UNINDEXED, terms, tokenize='unicode61')"
            )
            for chunk in chunks:
                chunk_id = str(chunk["chunk_id"])
                payload = json.dumps(chunk, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                terms = " ".join(_string_list(chunk.get("terms"), f"chunk {chunk_id} terms"))
                connection.execute("INSERT INTO chunks VALUES (?, ?)", (chunk_id, payload))
                connection.execute("INSERT INTO chunk_fts VALUES (?, ?)", (chunk_id, terms))
            connection.commit()
        finally:
            connection.close()
        _assert_write_destination(root, destination)
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()


def _jsonl_text(chunks: Sequence[Mapping[str, object]]) -> str:
    return "".join(
        json.dumps(chunk, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        for chunk in chunks
    )


def _atomic_write_text(
    destination: Path, content: str, *, root: Path | None = None
) -> None:
    _assert_write_destination(root, destination)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{destination.name}-", suffix=".tmp", dir=destination.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as file:
            file.write(content)
            file.flush()
            os.fsync(file.fileno())
        _assert_write_destination(root, destination)
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()


def _jsonl_objects(path: Path, label: str) -> list[tuple[int, dict[str, object]]]:
    records: list[tuple[int, dict[str, object]]] = []
    try:
        with path.open(encoding="utf-8") as file:
            for line_number, line in enumerate(file, start=1):
                if not line.strip():
                    continue
                value = json.loads(line)
                if not isinstance(value, Mapping):
                    raise ValueError(f"{label} record {line_number} must be an object")
                records.append((line_number, dict(value)))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} records are not valid JSONL") from exc
    return records


def _required_string(value: Mapping[str, object], key: str, label: str) -> str:
    field = value.get(key)
    if not isinstance(field, str) or not field.strip():
        raise ValueError(f"{label} {key} must be a non-empty string")
    return field


def _string_list(value: object, label: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise ValueError(f"{label} must be a list of non-empty strings")
    return list(value)


def _normalized_spans(value: list[object], label: str) -> list[dict[str, int]]:
    spans: list[dict[str, int]] = []
    for span in value:
        if not isinstance(span, Mapping):
            raise ValueError(f"{label} span must be an object")
        start_ms = span.get("start_ms")
        end_ms = span.get("end_ms")
        if (
            not isinstance(start_ms, int)
            or isinstance(start_ms, bool)
            or not isinstance(end_ms, int)
            or isinstance(end_ms, bool)
            or start_ms < 0
            or end_ms <= start_ms
        ):
            raise ValueError(f"{label} span must have increasing integer milliseconds")
        spans.append({"start_ms": start_ms, "end_ms": end_ms})
    return _sorted_unique_spans(spans)


def _sorted_unique_spans(spans: Sequence[Mapping[str, Any]]) -> list[dict[str, int]]:
    unique = {(int(span["start_ms"]), int(span["end_ms"])) for span in spans}
    return [{"start_ms": start, "end_ms": end} for start, end in sorted(unique)]


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_bytes(path: Path) -> bytes:
    with path.open("rb") as file:
        return file.read()


def _assert_write_destination(root: Path | None, destination: Path) -> None:
    if root is None:
        return
    _assert_safe_path(root, destination.parent, "revision index directory")
    _assert_safe_path(root, destination, "revision index destination")


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
