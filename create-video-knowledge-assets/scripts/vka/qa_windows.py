"""Bounded, evidence-only authoring windows for grounded video QA."""

from __future__ import annotations

import json
import os
import uuid
import hashlib
from collections.abc import Mapping, Sequence
from pathlib import Path

from pydantic import ValidationError

from vka.models import Evidence, KnowledgeUnit
from vka.qa_asset import qa_asset_fingerprint, validate_qa_asset
from vka.qa_revision import load_knowledge_revision
from vka.store import AssetStore


WINDOWS_SCHEMA_VERSION = "1.0"
CONTEXT_MS = 5_000
MAX_TRANSCRIPT_ITEMS = 8
MAX_TOTAL_ITEMS = 12
MAX_CONTENT_BYTES = 12_000
_SUPPORTED_PROFILE_ID = "course-notes"


def build_evidence_windows(
    asset: AssetStore | Path | str,
    selected_knowledge_ids: Sequence[str],
    *,
    profile_id: str = _SUPPORTED_PROFILE_ID,
    context_ms: int = CONTEXT_MS,
    max_transcript_items: int = MAX_TRANSCRIPT_ITEMS,
    max_total_items: int = MAX_TOTAL_ITEMS,
    max_content_bytes: int = MAX_CONTENT_BYTES,
    knowledge_revision: str | None = None,
) -> dict[str, object]:
    """Publish bounded windows only for explicitly retrieved knowledge units.

    The published JSONL contains no knowledge or document prose.  It is derived
    solely from direct, canonical video evidence and nearby canonical transcript
    records, so it can be handed to an answer author without becoming a second
    unrestricted transcript index.
    """
    _validate_profile(profile_id)
    _validate_limits(context_ms, max_transcript_items, max_total_items, max_content_bytes)
    selected_ids = _validate_selected_knowledge_ids(selected_knowledge_ids)
    store = _as_store(asset)
    revision = _load_revision(store, knowledge_revision)
    readiness_errors = validate_qa_asset(store, profile_id=profile_id)
    if readiness_errors:
        raise ValueError("asset is not ready for QA: " + "; ".join(readiness_errors))

    fingerprint = qa_asset_fingerprint(store)
    evidence = _read_evidence(store.root / "evidence" / "records.jsonl")
    if revision is None:
        units = _read_units(store.root / "knowledge" / "units.jsonl", set(evidence))
    else:
        units = _read_units_records(_revision_units(revision), set(evidence))
    selected_units = _select_units(units, selected_ids)
    windows = _build_windows(
        evidence,
        selected_units,
        context_ms,
        max_transcript_items,
        max_total_items,
        max_content_bytes,
    )
    published = {
        "schema_version": WINDOWS_SCHEMA_VERSION,
        "profile_id": profile_id,
        "qa_asset_fingerprint": fingerprint,
        "windows": [
            {
                "schema_version": WINDOWS_SCHEMA_VERSION,
                "profile_id": profile_id,
                "qa_asset_fingerprint": fingerprint,
                **window,
            }
            for window in windows
        ],
    }
    if knowledge_revision is not None:
        revision_sha256 = _revision_sha256(revision)
        published["knowledge_revision"] = knowledge_revision
        published["knowledge_revision_sha256"] = revision_sha256
        for window in published["windows"]:
            window["knowledge_revision"] = knowledge_revision
            window["knowledge_revision_sha256"] = revision_sha256

    destination = _windows_path(store, knowledge_revision)
    if _read_windows(destination) == published["windows"]:
        return published
    _atomic_write_jsonl(store, published["windows"], knowledge_revision)
    return published


def _validate_profile(profile_id: str) -> None:
    if profile_id != _SUPPORTED_PROFILE_ID:
        raise ValueError(f"P4.1 QA builders support only {_SUPPORTED_PROFILE_ID!r} profile_id")


def _validate_selected_knowledge_ids(selected_knowledge_ids: Sequence[str]) -> list[str]:
    if isinstance(selected_knowledge_ids, (str, bytes)) or not isinstance(
        selected_knowledge_ids, Sequence
    ):
        raise ValueError("selected knowledge IDs must be a sequence of strings")
    if not all(
        isinstance(unit_id, str) and unit_id.strip() for unit_id in selected_knowledge_ids
    ):
        raise ValueError("selected knowledge IDs must be a sequence of strings")
    if len(set(selected_knowledge_ids)) != len(selected_knowledge_ids):
        raise ValueError("selected knowledge IDs must not contain duplicates")
    return sorted(selected_knowledge_ids)


def _validate_limits(
    context_ms: int,
    max_transcript_items: int,
    max_total_items: int,
    max_content_bytes: int,
) -> None:
    if not isinstance(context_ms, int) or isinstance(context_ms, bool) or context_ms < 0:
        raise ValueError("context_ms must be a non-negative integer")
    if (
        not isinstance(max_transcript_items, int)
        or isinstance(max_transcript_items, bool)
        or max_transcript_items < 1
    ):
        raise ValueError("max_transcript_items must be a positive integer")
    if (
        not isinstance(max_total_items, int)
        or isinstance(max_total_items, bool)
        or max_total_items < 1
    ):
        raise ValueError("max_total_items must be a positive integer")
    if (
        not isinstance(max_content_bytes, int)
        or isinstance(max_content_bytes, bool)
        or max_content_bytes < 1
    ):
        raise ValueError("max_content_bytes must be a positive integer")


def _as_store(asset: AssetStore | Path | str) -> AssetStore:
    return asset if isinstance(asset, AssetStore) else AssetStore(Path(asset))


def _read_evidence(path: Path) -> dict[str, Evidence]:
    result: dict[str, Evidence] = {}
    for line_number, record in _jsonl_objects(path, "evidence"):
        label = f"evidence record {line_number}"
        parsed = _validated_evidence(record, label)
        if parsed.evidence_id in result:
            raise ValueError(f"duplicate evidence_id: {parsed.evidence_id}")
        result[parsed.evidence_id] = parsed
    return result


def _read_units(path: Path, evidence_ids: set[str]) -> dict[str, KnowledgeUnit]:
    return _read_units_records(
        [record for _, record in _jsonl_objects(path, "knowledge")], evidence_ids
    )


def _read_units_records(
    records: list[Mapping[str, object]], evidence_ids: set[str]
) -> dict[str, KnowledgeUnit]:
    result: dict[str, KnowledgeUnit] = {}
    seen: set[str] = set()
    for line_number, record in enumerate(records, start=1):
        label = f"knowledge record {line_number}"
        parsed = _validated_unit(record, label)
        if parsed.unit_id in seen:
            raise ValueError(f"duplicate unit_id: {parsed.unit_id}")
        if len(set(parsed.evidence_refs)) != len(parsed.evidence_refs):
            raise ValueError(f"{label} evidence_refs must not contain duplicate IDs")
        missing = sorted(set(parsed.evidence_refs) - evidence_ids)
        if missing:
            raise ValueError(f"unknown evidence IDs: {', '.join(missing)}")
        seen.add(parsed.unit_id)
        result[parsed.unit_id] = parsed
    return result


def _select_units(
    units: Mapping[str, KnowledgeUnit], selected_ids: Sequence[str]
) -> list[KnowledgeUnit]:
    missing = sorted(set(selected_ids) - set(units))
    if missing:
        raise ValueError("unknown selected knowledge IDs: " + ", ".join(missing))
    selected = [units[unit_id] for unit_id in selected_ids]
    unavailable = [
        unit.unit_id for unit in selected if unit.epistemic_status == "external_enrichment"
    ]
    if unavailable:
        raise ValueError(
            "selected knowledge IDs are not video-grounded: " + ", ".join(unavailable)
        )
    return selected


def _build_windows(
    evidence: Mapping[str, Evidence],
    units: Sequence[KnowledgeUnit],
    context_ms: int,
    max_transcript_items: int,
    max_total_items: int,
    max_content_bytes: int,
) -> list[dict[str, object]]:
    transcript_candidates = sorted(
        (
            record
            for record in evidence.values()
            if record.origin == "video" and record.modality == "transcript"
        ),
        key=_evidence_time_key,
    )
    windows: list[dict[str, object]] = []
    for unit in units:
        direct = sorted(
            (
                evidence[reference]
                for reference in unit.evidence_refs
                if _is_usable_direct_evidence(evidence[reference])
            ),
            key=_evidence_time_key,
        )
        if not direct:
            raise ValueError(
                f"knowledge unit {unit.unit_id} has no usable transcript or directly inspected frame evidence"
            )

        # A checked frame can ground every unit that cites it. Keep it in each
        # bounded window rather than leaving an anchor without its record.
        materialized_direct = direct
        shared_frames: list[Evidence] = []
        groups = _partition_direct_evidence(
            materialized_direct,
            max_transcript_items,
            max_total_items,
            max_content_bytes,
        )
        if not groups:
            groups = [[]]
        for sequence, group in enumerate(groups, start=1):
            anchors = sorted(group, key=_evidence_time_key)
            context_anchors = anchors if sequence > 1 else sorted(
                [*anchors, *shared_frames], key=_evidence_time_key
            )
            selected = _select_neighbors(
                context_anchors,
                transcript_candidates,
                context_ms,
                max_transcript_items - _transcript_count(context_anchors),
                max_transcript_items,
                max_total_items,
                max_content_bytes,
            )
            records = sorted([*anchors, *selected], key=_evidence_time_key)
            windows.append(
                {
                    "window_id": f"window:{unit.unit_id}:{sequence:03d}",
                    "knowledge_id": unit.unit_id,
                    "anchor_evidence_refs": [
                        record.evidence_id for record in context_anchors
                    ],
                    "evidence_refs": [record.evidence_id for record in records],
                    "source_spans": _source_spans(records),
                    "evidence": [_evidence_item(record) for record in records],
                }
            )
    return windows


def _deduplicate_direct_frames(
    direct: Sequence[Evidence], emitted_frame_ids: set[str]
) -> tuple[list[Evidence], list[Evidence]]:
    materialized: list[Evidence] = []
    shared: list[Evidence] = []
    for record in direct:
        if record.modality == "frame" and record.evidence_id in emitted_frame_ids:
            shared.append(record)
            continue
        materialized.append(record)
        if record.modality == "frame":
            emitted_frame_ids.add(record.evidence_id)
    return materialized, shared


def _is_usable_direct_evidence(record: Evidence) -> bool:
    if record.origin != "video":
        return False
    if record.modality == "transcript":
        return True
    return record.modality == "frame" and record.quality.get("review") == "directly_inspected"


def _partition_direct_evidence(
    records: Sequence[Evidence],
    max_transcript_items: int,
    max_total_items: int,
    max_content_bytes: int,
) -> list[list[Evidence]]:
    groups: list[list[Evidence]] = []
    current: list[Evidence] = []
    for record in records:
        if not _can_add(
            current, record, max_transcript_items, max_total_items, max_content_bytes
        ):
            if not current:
                raise ValueError(
                    f"direct evidence {record.evidence_id} cannot fit within max_content_bytes"
                )
            groups.append(current)
            current = []
            if not _can_add(
                current, record, max_transcript_items, max_total_items, max_content_bytes
            ):
                raise ValueError(
                    f"direct evidence {record.evidence_id} cannot fit within configured window caps"
                )
        current.append(record)
    if current:
        groups.append(current)
    return groups


def _select_neighbors(
    anchors: Sequence[Evidence],
    candidates: Sequence[Evidence],
    context_ms: int,
    transcript_limit: int,
    max_transcript_items: int,
    max_total_items: int,
    max_content_bytes: int,
) -> list[Evidence]:
    if transcript_limit == 0 or len(anchors) >= max_total_items:
        return []
    anchor_ids = {record.evidence_id for record in anchors}
    anchor_spans = _source_spans(anchors)
    available = [
        record
        for record in candidates
        if record.evidence_id not in anchor_ids
        and any(_overlaps_expanded(_source_spans([record]), span, context_ms) for span in anchor_spans)
    ]
    nearest = sorted(
        available,
        key=lambda record: (_distance_to_anchors(record, anchor_spans), *_evidence_time_key(record)),
    )
    selected: list[Evidence] = []
    for record in nearest:
        if len(selected) >= transcript_limit:
            break
        if _can_add(
            [*anchors, *selected],
            record,
            max_transcript_items,
            max_total_items,
            max_content_bytes,
        ):
            selected.append(record)
    return sorted(selected, key=_evidence_time_key)


def _transcript_count(records: Sequence[Evidence]) -> int:
    return sum(record.modality == "transcript" for record in records)


def _content_bytes(records: Sequence[Evidence]) -> int:
    return sum(len(record.content.encode("utf-8")) for record in records)


def _can_add(
    records: Sequence[Evidence],
    record: Evidence,
    max_transcript_items: int,
    max_total_items: int,
    max_content_bytes: int,
) -> bool:
    return (
        len(records) + 1 <= max_total_items
        and _transcript_count(records) + (record.modality == "transcript") <= max_transcript_items
        and _content_bytes(records) + len(record.content.encode("utf-8")) <= max_content_bytes
    )


def _overlaps_expanded(candidate: Sequence[dict[str, int]], anchor: Mapping[str, int], context_ms: int) -> bool:
    start = max(0, int(anchor["start_ms"]) - context_ms)
    end = int(anchor["end_ms"]) + context_ms
    return any(int(span["start_ms"]) < end and int(span["end_ms"]) > start for span in candidate)


def _distance_to_anchors(record: Evidence, anchors: Sequence[Mapping[str, int]]) -> int:
    distances = []
    for span in _source_spans([record]):
        for anchor in anchors:
            if int(span["end_ms"]) < int(anchor["start_ms"]):
                distances.append(int(anchor["start_ms"]) - int(span["end_ms"]))
            elif int(span["start_ms"]) > int(anchor["end_ms"]):
                distances.append(int(span["start_ms"]) - int(anchor["end_ms"]))
            else:
                distances.append(0)
    return min(distances, default=0)


def _evidence_time_key(record: Evidence) -> tuple[int, int, str]:
    spans = _source_spans([record])
    if not spans:
        return (2**63 - 1, 2**63 - 1, record.evidence_id)
    return (spans[0]["start_ms"], spans[0]["end_ms"], record.evidence_id)


def _source_spans(records: Sequence[Evidence]) -> list[dict[str, int]]:
    spans = {
        (span.start_ms, span.end_ms)
        for record in records
        for span in record.spans
    }
    return [{"start_ms": start, "end_ms": end} for start, end in sorted(spans)]


def _evidence_item(record: Evidence) -> dict[str, object]:
    return {
        "evidence_id": record.evidence_id,
        "origin": record.origin,
        "modality": record.modality,
        "content": record.content,
        "artifact_ref": record.artifact_ref,
        "spans": _source_spans([record]),
    }


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


def _jsonl_objects(path: Path, label: str) -> list[tuple[int, Mapping[str, object]]]:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as exc:
        raise ValueError(f"{label} records are not valid JSONL") from exc
    records: list[tuple[int, Mapping[str, object]]] = []
    try:
        for line_number, line in enumerate(text.splitlines(), start=1):
            if line.strip():
                value = json.loads(line)
                if not isinstance(value, Mapping):
                    raise ValueError(f"{label} record {line_number} must be an object")
                records.append((line_number, value))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} records are not valid JSONL") from exc
    return records


def _read_windows(path: Path) -> list[dict[str, object]] | None:
    try:
        records = _jsonl_objects(path, "windows")
    except ValueError:
        return None
    return [dict(record) for _, record in records]


def _windows_path(store: AssetStore, revision_id: str | None = None) -> Path:
    root = store.root
    if not root.is_dir() or _is_link(root):
        raise ValueError("asset root must be a real directory")
    root = root.resolve()
    index = root / "index"
    _assert_safe_path(root, index, "windows index directory")
    index.mkdir(exist_ok=True)
    if not index.is_dir():
        raise ValueError("windows index directory must be a directory")
    _assert_safe_path(root, index, "windows index directory")
    if revision_id is not None:
        revisions = index / "revisions"
        _assert_safe_path(root, revisions, "windows revisions directory")
        revisions.mkdir(exist_ok=True)
        if not revisions.is_dir():
            raise ValueError("windows revisions directory must be a directory")
        destination_dir = revisions / revision_id
        _assert_safe_path(root, destination_dir, "windows revision directory")
        destination_dir.mkdir(exist_ok=True)
        if not destination_dir.is_dir():
            raise ValueError("windows revision directory must be a directory")
    else:
        destination_dir = index
    destination = destination_dir / "evidence-windows.jsonl"
    _assert_safe_path(root, destination, "windows destination")
    return destination


def _atomic_write_jsonl(
    store: AssetStore, windows: object, revision_id: str | None = None
) -> None:
    if not isinstance(windows, list):
        raise ValueError("windows must be a list")
    destination = _windows_path(store, revision_id)
    root = store.root.resolve()
    temporary: Path | None = None
    try:
        for _ in range(16):
            candidate = destination.parent / f".{destination.name}.{uuid.uuid4().hex}.tmp"
            _assert_safe_path(root, candidate, "windows temporary path")
            try:
                descriptor = os.open(candidate, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                continue
            temporary = candidate
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as file:
                for window in windows:
                    json.dump(window, file, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                    file.write("\n")
                file.flush()
                os.fsync(file.fileno())
            _assert_safe_path(root, temporary, "windows temporary path")
            _assert_safe_path(root, destination, "windows destination")
            os.replace(temporary, destination)
            temporary = None
            return
        raise OSError("could not allocate a unique windows temporary file")
    finally:
        if temporary is not None and temporary.exists():
            _assert_safe_path(root, temporary, "windows temporary path")
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
