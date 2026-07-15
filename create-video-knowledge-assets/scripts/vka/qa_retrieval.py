"""Evidence-only lexical retrieval for grounded video QA."""

from __future__ import annotations

import json
import sqlite3
import hashlib
from collections.abc import Mapping, Sequence
from pathlib import Path

from vka.qa_index import lexical_terms, read_qa_index
from vka.qa_topology import build_qa_topology
from vka.qa_windows import build_evidence_windows
from vka.qa_revision import load_knowledge_revision
from vka.store import AssetStore


_IMPORTANCE_RANK = {"high": 0, "medium": 1, "low": 2}
_MODES = {"video_only", "video_plus_context", "explore"}


def retrieve_question(
    asset: AssetStore | Path | str,
    question: str,
    *,
    profile_id: str = "course-notes",
    mode: str = "video_only",
    limit: int = 8,
    knowledge_revision: str | None = None,
) -> dict[str, object]:
    """Return a deterministic grounding pack, never an answer fragment."""
    if not isinstance(question, str) or not question.strip():
        raise ValueError("question must be a non-empty string")
    if mode not in _MODES:
        raise ValueError("mode must be video_only, video_plus_context, or explore")
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        raise ValueError("limit must be a positive integer")

    store = _as_store(asset)
    revision = _load_revision(store, knowledge_revision)
    snapshot = read_qa_index(
        store, profile_id=profile_id, knowledge_revision=knowledge_revision
    )
    connection = snapshot["sqlite_connection"]
    if not isinstance(connection, sqlite3.Connection):
        raise ValueError("QA index did not provide a SQLite snapshot")

    try:
        manifest = _mapping(snapshot.get("manifest"), "index manifest")
        chunks = _chunk_map(snapshot.get("chunks"))
        evidence = _read_evidence(store.root / "evidence" / "records.jsonl")
        if revision is None:
            units = _read_units(store.root / "knowledge" / "units.jsonl")
            relations = _read_relations(store.root / "knowledge" / "relations.jsonl")
        else:
            units = _read_units_records(_revision_records(revision, "units"))
            relations = _read_relations_records(_revision_records(revision, "relations"))
        terms = lexical_terms(question)
        external_count = _excluded_external_count(units, terms)
        hits = _fts_hits(connection, terms)
        candidates, unsafe_evidence_count = _candidates(
            hits, chunks, evidence, units, relations
        )
        candidates = candidates[:limit]
        selected_knowledge_ids = [
            _required_string(candidate, "knowledge_id", "candidate")
            for candidate in candidates
        ]
        window_kwargs: dict[str, object] = {"profile_id": profile_id}
        topology_kwargs: dict[str, object] = {"profile_id": profile_id}
        if knowledge_revision is not None:
            window_kwargs["knowledge_revision"] = knowledge_revision
            topology_kwargs["knowledge_revision"] = knowledge_revision
        evidence_windows = _selected_evidence_windows(
            build_evidence_windows(store, selected_knowledge_ids, **window_kwargs),
            selected_knowledge_ids,
        )
        topology = _selected_topology(
            build_qa_topology(store, **topology_kwargs), selected_knowledge_ids
        )
        course_locations = _course_locations(candidates)
        pack: dict[str, object] = {
            "question": question,
            "mode": mode,
            "index_fingerprint": manifest.get("qa_asset_fingerprint"),
            "candidates": candidates,
            "topology": topology,
            "evidence_windows": evidence_windows,
            "course_locations": course_locations,
            "excluded_external_enrichment_count": external_count,
            "excluded_unsafe_evidence_count": unsafe_evidence_count,
            "empty_reason": _empty_reason(terms, candidates),
        }
        if knowledge_revision is not None:
            pack["knowledge_revision"] = knowledge_revision
            pack["knowledge_revision_sha256"] = _revision_sha256(revision)
        return pack
    finally:
        connection.close()


def _selected_evidence_windows(
    published: object, selected_knowledge_ids: Sequence[str]
) -> list[object]:
    windows = _mapping(published, "evidence windows").get("windows")
    if not isinstance(windows, list):
        raise ValueError("evidence windows must contain a windows list")
    selected_ids = set(selected_knowledge_ids)
    if len(selected_ids) != len(selected_knowledge_ids):
        raise ValueError("selected knowledge IDs must not contain duplicates")
    window_ids: set[str] = set()
    window_ids_by_knowledge_id: dict[str, list[str]] = {}
    for index, window in enumerate(windows, start=1):
        record = _mapping(window, f"evidence window {index}")
        window_id = _required_string(record, "window_id", f"evidence window {index}")
        if window_id in window_ids:
            raise ValueError(f"duplicate evidence window_id: {window_id}")
        window_ids.add(window_id)
        knowledge_id = _required_string(
            record,
            "knowledge_id",
            f"evidence window {index}",
        )
        if knowledge_id not in selected_ids:
            raise ValueError("evidence window references unselected knowledge")
        window_ids_by_knowledge_id.setdefault(knowledge_id, []).append(window_id)
    for knowledge_id, knowledge_window_ids in window_ids_by_knowledge_id.items():
        if len(knowledge_window_ids) > 1 and not _is_window_partition(
            knowledge_id, knowledge_window_ids
        ):
            raise ValueError(f"duplicate evidence window knowledge_id: {knowledge_id}")
    missing_ids = sorted(selected_ids - set(window_ids_by_knowledge_id))
    if missing_ids:
        raise ValueError(
            "evidence windows missing selected knowledge IDs: " + ", ".join(missing_ids)
        )
    return list(windows)


def _is_window_partition(knowledge_id: str, window_ids: Sequence[str]) -> bool:
    return sorted(window_ids) == [
        f"window:{knowledge_id}:{sequence:03d}"
        for sequence in range(1, len(window_ids) + 1)
    ]


def _selected_topology(
    published: object, selected_knowledge_ids: Sequence[str]
) -> dict[str, object]:
    topology = _mapping(published, "QA topology")
    facets = topology.get("facets")
    if not isinstance(facets, list):
        raise ValueError("QA topology facets must be a list")

    selected_ids = set(selected_knowledge_ids)
    selected_facets: list[dict[str, object]] = []
    found_ids: set[str] = set()
    for index, value in enumerate(facets, start=1):
        facet = _mapping(value, f"QA topology facet {index}")
        knowledge_id = _required_string(
            facet, "unit_id", f"QA topology facet {index}"
        )
        if knowledge_id not in selected_ids:
            continue
        selected_facets.append(dict(facet))
        found_ids.add(knowledge_id)

    missing_ids = sorted(selected_ids - found_ids)
    if missing_ids:
        raise ValueError(
            "QA topology does not include selected knowledge IDs: " + ", ".join(missing_ids)
        )
    result: dict[str, object] = {"facets": selected_facets}
    for key in ("knowledge_revision", "knowledge_revision_sha256"):
        if key in topology:
            result[key] = topology[key]
    return result


def _as_store(asset: AssetStore | Path | str) -> AssetStore:
    return asset if isinstance(asset, AssetStore) else AssetStore(Path(asset))


def _load_revision(
    store: AssetStore, revision_id: str | None
) -> dict[str, object] | None:
    return None if revision_id is None else load_knowledge_revision(store, revision_id)


def _revision_records(
    revision: Mapping[str, object], key: str
) -> list[Mapping[str, object]]:
    records = revision.get(key)
    if not isinstance(records, list) or not all(isinstance(record, Mapping) for record in records):
        raise ValueError(f"loaded knowledge revision {key} are invalid")
    return list(records)


def _revision_sha256(revision: Mapping[str, object] | None) -> str:
    if revision is None:
        raise ValueError("knowledge revision is required")
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


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return value


def _chunk_map(value: object) -> dict[str, Mapping[str, object]]:
    if not isinstance(value, list):
        raise ValueError("index chunks must be a list")
    chunks: dict[str, Mapping[str, object]] = {}
    for index, chunk in enumerate(value, start=1):
        record = _mapping(chunk, f"index chunk {index}")
        chunk_id = _required_string(record, "chunk_id", f"index chunk {index}")
        if chunk_id in chunks:
            raise ValueError(f"duplicate index chunk_id: {chunk_id}")
        chunks[chunk_id] = record
    return chunks


def _read_evidence(path: Path) -> dict[str, Mapping[str, object]]:
    records: dict[str, Mapping[str, object]] = {}
    for line_number, record in _jsonl_records(path, "evidence"):
        evidence_id = _required_string(record, "evidence_id", f"evidence record {line_number}")
        if evidence_id in records:
            raise ValueError(f"duplicate evidence_id: {evidence_id}")
        origin = _required_string(record, "origin", f"evidence record {line_number}")
        if origin not in {"video", "external", "generated"}:
            raise ValueError(f"evidence record {line_number} has an invalid origin")
        _required_string(record, "content", f"evidence record {line_number}")
        _spans(record.get("spans", []), f"evidence record {line_number}")
        artifact_ref = record.get("artifact_ref")
        if artifact_ref is not None and (
            not isinstance(artifact_ref, str) or not artifact_ref.strip()
        ):
            raise ValueError(f"evidence record {line_number} artifact_ref must be a string")
        records[evidence_id] = record
    return records


def _read_units(path: Path) -> dict[str, Mapping[str, object]]:
    return _read_units_records([record for _, record in _jsonl_records(path, "knowledge")])


def _read_units_records(records: Sequence[Mapping[str, object]]) -> dict[str, Mapping[str, object]]:
    units: dict[str, Mapping[str, object]] = {}
    for line_number, record in enumerate(records, start=1):
        unit_id = _required_string(record, "unit_id", f"knowledge record {line_number}")
        if unit_id in units:
            raise ValueError(f"duplicate unit_id: {unit_id}")
        _required_string(record, "title", f"knowledge record {line_number}")
        _required_string(record, "statement", f"knowledge record {line_number}")
        status = _required_string(record, "epistemic_status", f"knowledge record {line_number}")
        if status not in {
            "video_explicit",
            "agent_inference",
            "external_enrichment",
            "insufficient_evidence",
        }:
            raise ValueError(f"knowledge record {line_number} has an invalid epistemic_status")
        _string_list(record.get("evidence_refs"), f"knowledge record {line_number} evidence_refs")
        units[unit_id] = record
    return units


def _read_relations(path: Path) -> list[Mapping[str, object]]:
    return _read_relations_records([record for _, record in _jsonl_records(path, "relation")])


def _read_relations_records(records: Sequence[Mapping[str, object]]) -> list[Mapping[str, object]]:
    relations: list[Mapping[str, object]] = []
    for record in records:
        # Relation metadata is optional retrieval context, never candidate evidence.
        if all(
            isinstance(record.get(field), str) and record[field].strip()
            for field in ("relation_id", "source_unit_id", "target_unit_id", "relation_type")
        ):
            relations.append(record)
    return relations


def _jsonl_records(path: Path, label: str) -> list[tuple[int, Mapping[str, object]]]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ValueError(f"{label} records are not valid JSONL") from exc
    records: list[tuple[int, Mapping[str, object]]] = []
    try:
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            records.append((line_number, _mapping(json.loads(line), f"{label} record {line_number}")))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} records are not valid JSONL") from exc
    return records


def _fts_hits(connection: sqlite3.Connection, terms: Sequence[str]) -> list[tuple[str, float]]:
    if not terms:
        return []
    query = " OR ".join(terms)
    try:
        rows = connection.execute(
            "SELECT chunk_id, bm25(chunk_fts) AS score "
            "FROM chunk_fts WHERE chunk_fts MATCH ?",
            (query,),
        ).fetchall()
    except sqlite3.Error as exc:
        raise ValueError("QA index lexical query failed") from exc
    return [(str(chunk_id), float(score)) for chunk_id, score in rows]


def _candidates(
    hits: Sequence[tuple[str, float]],
    chunks: Mapping[str, Mapping[str, object]],
    evidence: Mapping[str, Mapping[str, object]],
    units: Mapping[str, Mapping[str, object]],
    relations: Sequence[Mapping[str, object]],
) -> tuple[list[dict[str, object]], int]:
    ranked: list[tuple[float, int, str, Mapping[str, object]]] = []
    for chunk_id, score in hits:
        chunk = chunks.get(chunk_id)
        if chunk is None:
            raise ValueError(f"SQLite result references missing chunk: {chunk_id}")
        importance = _required_string(chunk, "importance", f"chunk {chunk_id}")
        if importance not in _IMPORTANCE_RANK:
            raise ValueError(f"chunk {chunk_id} has an invalid importance")
        ranked.append((score, _IMPORTANCE_RANK[importance], chunk_id, chunk))

    result: list[dict[str, object]] = []
    unsafe_evidence_count = 0
    for _, _, chunk_id, chunk in sorted(ranked, key=lambda item: item[:3]):
        knowledge_refs = _string_list(chunk.get("knowledge_refs"), f"chunk {chunk_id} knowledge_refs")
        if len(knowledge_refs) != 1:
            raise ValueError(f"chunk {chunk_id} must reference exactly one knowledge unit")
        knowledge_id = knowledge_refs[0]
        unit = units.get(knowledge_id)
        if unit is None:
            raise ValueError(f"chunk {chunk_id} references unknown knowledge unit: {knowledge_id}")
        if unit.get("epistemic_status") == "external_enrichment":
            continue
        evidence_refs = _string_list(chunk.get("evidence_refs"), f"chunk {chunk_id} evidence_refs")
        if evidence_refs != _string_list(unit.get("evidence_refs"), f"knowledge unit {knowledge_id} evidence_refs"):
            raise ValueError(f"chunk {chunk_id} evidence refs do not match canonical knowledge refs")
        safe_evidence_refs, safe_span_keys = _safe_candidate_evidence(
            evidence, evidence_refs
        )
        if not safe_evidence_refs:
            unsafe_evidence_count += 1
            continue
        source_spans = [
            span
            for span in _spans(chunk.get("source_spans", []), f"chunk {chunk_id}")
            if (span["start_ms"], span["end_ms"]) in safe_span_keys
        ]
        if not source_spans:
            unsafe_evidence_count += 1
            continue
        result.append(
            {
                "knowledge_id": knowledge_id,
                "knowledge_refs": knowledge_refs,
                "evidence_refs": safe_evidence_refs,
                "title": _required_string(chunk, "title", f"chunk {chunk_id}"),
                "statement": _required_string(chunk, "statement", f"chunk {chunk_id}"),
                "epistemic_status": _required_string(chunk, "epistemic_status", f"chunk {chunk_id}"),
                "importance": _required_string(chunk, "importance", f"chunk {chunk_id}"),
                "source_spans": source_spans,
                "course_locations": _locations(chunk.get("course_locations", []), f"chunk {chunk_id}"),
                "related_units": _related_units(knowledge_id, relations, units),
            }
        )
    return result, unsafe_evidence_count


def _safe_candidate_evidence(
    evidence: Mapping[str, Mapping[str, object]], evidence_refs: Sequence[str]
) -> tuple[list[str], set[tuple[int, int]]]:
    safe_refs: list[str] = []
    safe_span_keys: set[tuple[int, int]] = set()
    for evidence_id in evidence_refs:
        record = evidence.get(evidence_id)
        if record is None:
            raise ValueError(f"knowledge references unknown evidence: {evidence_id}")
        if not _is_usable_candidate_evidence(record):
            continue
        spans = _spans(record.get("spans", []), f"evidence {evidence_id}")
        if not spans:
            continue
        safe_refs.append(evidence_id)
        safe_span_keys.update((span["start_ms"], span["end_ms"]) for span in spans)
    return safe_refs, safe_span_keys


def _is_usable_candidate_evidence(record: Mapping[str, object]) -> bool:
    if record.get("origin") != "video":
        return False
    if record.get("modality") == "transcript":
        return True
    quality = record.get("quality")
    return (
        record.get("modality") == "frame"
        and isinstance(quality, Mapping)
        and quality.get("review") == "directly_inspected"
    )


def _related_units(
    knowledge_id: str,
    relations: Sequence[Mapping[str, object]],
    units: Mapping[str, Mapping[str, object]],
) -> list[dict[str, str]]:
    related: list[dict[str, str]] = []
    for relation in relations:
        source = _required_string(relation, "source_unit_id", "relation")
        target = _required_string(relation, "target_unit_id", "relation")
        if source == knowledge_id:
            other, direction = target, "outgoing"
        elif target == knowledge_id:
            other, direction = source, "incoming"
        else:
            continue
        if other == knowledge_id or other not in units:
            continue
        if units[other].get("epistemic_status") == "external_enrichment":
            continue
        related.append(
            {
                "knowledge_id": other,
                "relation_id": _required_string(relation, "relation_id", "relation"),
                "relation_type": _required_string(relation, "relation_type", "relation"),
                "direction": direction,
            }
        )
    return sorted(related, key=lambda item: (item["knowledge_id"], item["relation_id"]))


def _excluded_external_count(units: Mapping[str, Mapping[str, object]], terms: Sequence[str]) -> int:
    if not terms:
        return 0
    return sum(
        unit.get("epistemic_status") == "external_enrichment"
        and bool(set(terms) & set(lexical_terms(_unit_text(unit))))
        for unit in units.values()
    )


def _unit_text(unit: Mapping[str, object]) -> str:
    return " ".join(
        (
            _required_string(unit, "title", "knowledge unit"),
            _required_string(unit, "statement", "knowledge unit"),
            *(_string_list(unit.get("tags", []), "knowledge unit tags") if "tags" in unit else []),
        )
    )


def _course_locations(candidates: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for candidate in candidates:
        knowledge_id = _required_string(candidate, "knowledge_id", "candidate")
        for location in _locations(candidate.get("course_locations", []), "candidate"):
            result.append({"knowledge_id": knowledge_id, **location})
    return result


def _empty_reason(terms: Sequence[str], candidates: Sequence[object]) -> str | None:
    if not terms:
        return "question has no retrievable lexical terms"
    if not candidates:
        return "no indexed video knowledge matched the question"
    return None


def _required_string(record: Mapping[str, object], key: str, label: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} {key} must be a non-empty string")
    return value


def _string_list(value: object, label: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise ValueError(f"{label} must be a list of non-empty strings")
    return list(value)


def _spans(value: object, label: str) -> list[dict[str, int]]:
    if not isinstance(value, list):
        raise ValueError(f"{label} spans must be a list")
    spans: list[dict[str, int]] = []
    for span in value:
        record = _mapping(span, f"{label} span")
        start = record.get("start_ms")
        end = record.get("end_ms")
        if (
            not isinstance(start, int)
            or isinstance(start, bool)
            or not isinstance(end, int)
            or isinstance(end, bool)
            or start < 0
            or end <= start
        ):
            raise ValueError(f"{label} span must have increasing integer milliseconds")
        spans.append({"start_ms": start, "end_ms": end})
    unique = sorted({(span["start_ms"], span["end_ms"]) for span in spans})
    return [
        {"start_ms": start, "end_ms": end}
        for start, end in unique
    ]


def _locations(value: object, label: str) -> list[dict[str, object]]:
    if not isinstance(value, list):
        raise ValueError(f"{label} course_locations must be a list")
    locations: list[dict[str, object]] = []
    for location in value:
        record = _mapping(location, f"{label} course location")
        section_index = record.get("section_index")
        title = record.get("title")
        if not isinstance(section_index, int) or isinstance(section_index, bool) or section_index < 1:
            raise ValueError(f"{label} course location section_index must be a positive integer")
        if not isinstance(title, str) or not title.strip():
            raise ValueError(f"{label} course location title must be a non-empty string")
        locations.append({"section_index": section_index, "title": title})
    return sorted(locations, key=lambda item: (int(item["section_index"]), str(item["title"])))
