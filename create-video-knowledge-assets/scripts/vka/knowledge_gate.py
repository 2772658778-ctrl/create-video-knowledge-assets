"""Asset-level honesty checks for the canonical knowledge layer.

Reference closure is not enough. A knowledge unit can cite existing evidence
and still over-claim, for example when it is marked `video_explicit` while
every citation is a transcript row the reviewer flagged as uncertain. This gate
exists so that weakness fails loudly instead of shipping as an assertion.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from vka.models import KnowledgeUnit
from vka.validate import validate_knowledge_graph


UNCERTAIN_QUALITY_KEY = "uncertain"

# These modalities record where material came from, not what the video shows or
# says. Citing them cannot make a claim `video_explicit`.
PROVENANCE_ONLY_MODALITIES = frozenset({"metadata", "audio"})

# A transcript row can ground a `video_explicit` claim only after a reviewer
# looked at it. `unreviewed` rows are still usable as context, but nobody has
# vouched for them.
REVIEWED_STATUSES = frozenset({"repaired", "raw_preserved"})


def validate_asset_knowledge(asset: Path | str) -> dict[str, Any]:
    """Return contract and honesty errors for one asset's knowledge layer."""
    root = Path(asset)
    errors: list[str] = []
    warnings: list[str] = []

    evidence = _read_evidence_index(root, errors)
    uncertain_ids = {
        evidence_id
        for evidence_id, record in evidence.items()
        if record["quality"].get(UNCERTAIN_QUALITY_KEY) == "true"
    }
    supporting_ids = {
        evidence_id
        for evidence_id, record in evidence.items()
        if evidence_id not in uncertain_ids
        and record["modality"] not in PROVENANCE_ONLY_MODALITIES
        and (
            record["modality"] != "transcript"
            or record["quality"].get("repair_status") in REVIEWED_STATUSES
        )
    }

    units, unit_errors = _read_units(root)
    errors.extend(unit_errors)

    unit_ids: set[str] = set()
    for unit in units:
        unit_id = str(unit.get("unit_id", "<missing>"))
        unit_ids.add(unit_id)
        try:
            KnowledgeUnit.model_validate(unit)
        except ValueError:
            errors.append(f"{unit_id} does not match the knowledge unit schema")
        errors.extend(_check_refs(unit_id, unit, evidence))
        if unit.get("epistemic_status") == "video_explicit":
            errors.extend(_check_video_explicit_claim(unit_id, unit, supporting_ids))

    relations, synthesis, graph_errors = _read_graph(root)
    errors.extend(graph_errors)
    if not graph_errors:
        errors.extend(
            validate_knowledge_graph(
                unit_ids,
                relations,
                synthesis,
                set(evidence),
            )
        )

    return {
        "asset": str(root),
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "counts": {
            "knowledge_units": len(units),
            "evidence_records": len(evidence),
            "uncertain_evidence": len(uncertain_ids),
            "supporting_evidence": len(supporting_ids),
        },
    }


def _check_video_explicit_claim(
    unit_id: str,
    unit: Mapping[str, Any],
    supporting_ids: set[str],
) -> list[str]:
    evidence_refs = unit.get("evidence_refs")
    if not isinstance(evidence_refs, list) or not all(
        isinstance(ref, str) for ref in evidence_refs
    ):
        return []
    if any(ref in supporting_ids for ref in evidence_refs):
        return []
    return [
        f"{unit_id} is marked video_explicit but no citation is checked content "
        "evidence; cite a checked frame or a reviewed transcript row, or "
        "downgrade the epistemic_status"
    ]


def _check_refs(
    unit_id: str,
    unit: Mapping[str, Any],
    evidence: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    evidence_refs = unit.get("evidence_refs")
    if not isinstance(evidence_refs, list):
        return []
    return [
        f"{unit_id} references missing evidence {ref}"
        for ref in evidence_refs
        if isinstance(ref, str) and ref not in evidence
    ]


def _read_evidence_index(
    root: Path, errors: list[str]
) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for name in ("evidence/records.jsonl", "evidence/timeline.jsonl", "evidence/timeline.raw.jsonl"):
        path = root / name
        if not path.is_file():
            continue
        try:
            rows = _read_jsonl(path)
        except (OSError, ValueError) as exc:
            errors.append(f"{name} cannot be read: {exc}")
            continue
        for row in rows:
            evidence_id = row.get("evidence_id")
            if not isinstance(evidence_id, str) or not evidence_id:
                errors.append(f"{name} has a row without a usable evidence_id")
                continue
            record = row.get("quality")
            index[evidence_id] = {
                "quality": {
                    str(key): str(value)
                    for key, value in (record.items() if isinstance(record, Mapping) else ())
                },
                "modality": str(row.get("modality", "")),
            }
    if not index:
        errors.append("the asset has no readable evidence records")
    return index


def _read_units(root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    path = root / "knowledge" / "units.jsonl"
    if not path.is_file():
        return [], ["knowledge/units.jsonl is missing"]
    try:
        return _read_jsonl(path), []
    except (OSError, ValueError) as exc:
        return [], [f"knowledge/units.jsonl cannot be read: {exc}"]


def _read_graph(
    root: Path,
) -> tuple[list[Any], Any, list[str]]:
    errors: list[str] = []
    relations: Any = []
    synthesis: Any = {}

    relations_path = root / "knowledge" / "relations.jsonl"
    if relations_path.is_file():
        try:
            relations = _read_jsonl(relations_path)
        except (OSError, ValueError) as exc:
            errors.append(f"knowledge/relations.jsonl cannot be read: {exc}")
    else:
        errors.append("knowledge/relations.jsonl is missing")

    synthesis_path = root / "knowledge" / "synthesis.json"
    if synthesis_path.is_file():
        try:
            synthesis = json.loads(synthesis_path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError) as exc:
            errors.append(f"knowledge/synthesis.json cannot be read: {exc}")
    else:
        errors.append("knowledge/synthesis.json is missing")

    return relations, synthesis, errors


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{line_number} must contain a JSON object")
        rows.append(row)
    return rows
