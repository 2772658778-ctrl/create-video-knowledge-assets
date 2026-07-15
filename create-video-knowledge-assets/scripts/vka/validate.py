from __future__ import annotations

from collections.abc import Mapping

from vka.models import KnowledgeRelation, Synthesis


KNOWLEDGE_RELATION_TYPES = frozenset(
    {
        "prerequisite",
        "explains",
        "supports",
        "contradicts",
        "causes",
        "contrasts",
        "exemplifies",
        "part_of",
    }
)


def validate_knowledge_evidence_refs(
    evidence_ids: set[str], knowledge_rows: list[dict[str, object]]
) -> list[str]:
    errors: list[str] = []
    for row in knowledge_rows:
        unit_id = row.get("unit_id")
        if not isinstance(unit_id, str) or not unit_id:
            errors.append("knowledge row has invalid unit_id")
            continue
        evidence_refs = row.get("evidence_refs")
        if not isinstance(evidence_refs, list) or not evidence_refs:
            errors.append(f"{unit_id} has invalid evidence_refs")
            continue

        for evidence_id in evidence_refs:
            if not isinstance(evidence_id, str):
                errors.append(f"{unit_id} has invalid evidence_refs")
                continue
            if evidence_id not in evidence_ids:
                errors.append(f"{unit_id} references missing evidence {evidence_id}")
    return errors


def validate_knowledge_graph(
    unit_ids: set[str],
    relations: object,
    synthesis: object,
    evidence_ids: set[str] | None = None,
) -> list[str]:
    """Return contract and reference errors for a U1 knowledge layer.

    ``evidence_ids`` is optional to retain compatibility with callers that only
    have the knowledge graph. When it is supplied, relation and synthesis
    evidence references must resolve to those evidence records.
    """
    if not isinstance(relations, list):
        return ["relations must be a list"]

    errors: list[str] = []
    for relation_index, relation in enumerate(relations, start=1):
        if not isinstance(relation, Mapping):
            errors.append(f"relation {relation_index} must be an object")
            continue

        _validate_relation_id(errors, relation_index, relation)
        _validate_relation_endpoint(
            errors, relation_index, relation, "source_unit_id", unit_ids
        )
        _validate_relation_endpoint(
            errors, relation_index, relation, "target_unit_id", unit_ids
        )
        relation_type = relation.get("relation_type")
        if (
            not isinstance(relation_type, str)
            or relation_type not in KNOWLEDGE_RELATION_TYPES
        ):
            errors.append(f"relation {relation_index} has invalid relation_type")
        _validate_evidence_refs(
            errors, f"relation {relation_index}", relation, evidence_ids
        )
        _validate_relation_model(errors, relation_index, relation)

    if not isinstance(synthesis, Mapping):
        return [*errors, "synthesis must be an object"]
    video_summary = synthesis.get("video_summary")
    if not isinstance(video_summary, str) or not video_summary.strip():
        errors.append("synthesis has invalid video_summary")
    _validate_agent_extensions(errors, synthesis)
    for field_name in ("video_summary_refs", "agent_extension_refs"):
        _validate_synthesis_refs(errors, synthesis, field_name, unit_ids)
    _validate_evidence_refs(errors, "synthesis", synthesis, evidence_ids)
    _validate_synthesis_model(errors, synthesis)
    return errors


def _validate_relation_id(
    errors: list[str], relation_index: int, relation: Mapping[object, object]
) -> None:
    relation_id = relation.get("relation_id")
    if not isinstance(relation_id, str) or not relation_id.strip():
        errors.append(f"relation {relation_index} has invalid relation_id")


def _validate_relation_endpoint(
    errors: list[str],
    relation_index: int,
    relation: Mapping[object, object],
    field_name: str,
    unit_ids: set[str],
) -> None:
    unit_id = relation.get(field_name)
    if not isinstance(unit_id, str) or not unit_id:
        errors.append(f"relation {relation_index} has invalid {field_name}")
    elif unit_id not in unit_ids:
        errors.append(
            f"relation {relation_index} {field_name} references missing unit {unit_id}"
        )


def _validate_synthesis_refs(
    errors: list[str],
    synthesis: Mapping[object, object],
    field_name: str,
    unit_ids: set[str],
) -> None:
    refs = synthesis.get(field_name)
    if not isinstance(refs, list) or not refs or not all(
        isinstance(unit_id, str) and unit_id for unit_id in refs
    ):
        errors.append(f"synthesis {field_name} must be a non-empty list of unit ids")
        return
    for unit_id in refs:
        if unit_id not in unit_ids:
            errors.append(
                f"synthesis {field_name} references missing unit {unit_id}"
            )


def _validate_evidence_refs(
    errors: list[str],
    subject: str,
    record: Mapping[object, object],
    evidence_ids: set[str] | None,
) -> None:
    evidence_refs = record.get("evidence_refs")
    if not isinstance(evidence_refs, list) or not evidence_refs or not all(
        isinstance(evidence_id, str) and evidence_id for evidence_id in evidence_refs
    ):
        errors.append(f"{subject} has invalid evidence_refs")
        return
    if evidence_ids is None:
        return
    for evidence_id in evidence_refs:
        if evidence_id not in evidence_ids:
            errors.append(
                f"{subject} evidence_refs references missing evidence {evidence_id}"
            )


def _validate_agent_extensions(
    errors: list[str], synthesis: Mapping[object, object]
) -> None:
    agent_extensions = synthesis.get("agent_extensions", [])
    if not isinstance(agent_extensions, list) or not all(
        isinstance(extension, str) and extension.strip()
        for extension in agent_extensions
    ):
        errors.append("synthesis has invalid agent_extensions")


def _validate_relation_model(
    errors: list[str], relation_index: int, relation: Mapping[object, object]
) -> None:
    try:
        KnowledgeRelation.model_validate(relation)
    except ValueError:
        if not any(error.startswith(f"relation {relation_index} ") for error in errors):
            errors.append(f"relation {relation_index} does not match the relation schema")


def _validate_synthesis_model(
    errors: list[str], synthesis: Mapping[object, object]
) -> None:
    try:
        Synthesis.model_validate(synthesis)
    except ValueError:
        if not any(error.startswith("synthesis ") for error in errors):
            errors.append("synthesis does not match the synthesis schema")
