"""Reference-only answer planning for grounded video QA."""

from __future__ import annotations

from collections.abc import Mapping, Sequence


ANSWER_PLAN_SCHEMA_VERSION = "1.0"
_MODES = frozenset({"video_only", "video_plus_context", "explore"})


def build_answer_plan(grounding_pack: object) -> dict[str, object]:
    """Build a deterministic authoring plan without generating answer content.

    Candidate order is the retrieval rank.  The plan preserves that rank instead
    of arranging facts into a pre-defined instructional outline.
    """
    pack = _mapping(grounding_pack, "grounding pack")
    if "answer" in pack or "claims" in pack:
        raise ValueError("grounding pack must not contain an answer or claims")

    question = _required_string(pack, "question", "grounding pack")
    mode = _required_string(pack, "mode", "grounding pack")
    if mode not in _MODES:
        raise ValueError("grounding pack mode is invalid")

    revision_identity = _revision_identity(pack, "grounding pack")

    candidates = _candidates(pack.get("candidates"))
    candidate_ids = [candidate["knowledge_id"] for candidate in candidates]
    candidate_id_set = set(candidate_ids)
    facets = _facets(
        pack.get("topology"), candidate_id_set, revision_identity
    )
    windows = _windows(pack.get("evidence_windows"), candidate_id_set, revision_identity)

    if candidates:
        missing_window_ids = candidate_id_set - set(windows)
        if missing_window_ids:
            raise ValueError("evidence windows missing selected candidates")
    elif windows:
        raise ValueError("empty candidate packs must not contain evidence windows")
    _validate_candidate_support(candidates, facets, windows)

    missing_facets = [] if candidates else ["question_relevant_coverage"]

    selected_facets = [
        {"knowledge_id": candidate_id}
        for candidate_id in candidate_ids
    ]
    blocks = [
        _block(
            index,
            candidate,
            windows[candidate["knowledge_id"]]["window_ids"],
            candidate_id_set,
        )
        for index, candidate in enumerate(candidates, start=1)
    ]

    limitations: list[str] = []
    if not candidates:
        limitations.append("no_grounded_candidates")

    plan: dict[str, object] = {
        "schema_version": ANSWER_PLAN_SCHEMA_VERSION,
        "question": question,
        "mode": mode,
        "inferred_intent": {
            "question": question,
            "strategy": "selected_video_facets_only",
        },
        "selected_facets": selected_facets,
        "missing_facets": missing_facets,
        "blocks": blocks,
        "limitations": limitations,
    }
    if revision_identity is not None:
        plan.update(revision_identity)
    return plan


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return value


def _required_string(record: Mapping[str, object], key: str, label: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} {key} must be a non-empty string")
    return value


def _revision_identity(
    record: Mapping[str, object], label: str
) -> dict[str, str] | None:
    revision = record.get("knowledge_revision")
    revision_hash = record.get("knowledge_revision_sha256")
    if revision is None and revision_hash is None:
        return None
    if (
        not isinstance(revision, str)
        or not revision.strip()
        or not isinstance(revision_hash, str)
        or len(revision_hash) != 64
        or any(character not in "0123456789abcdef" for character in revision_hash)
    ):
        raise ValueError(f"{label} knowledge revision identity is invalid")
    return {"knowledge_revision": revision, "knowledge_revision_sha256": revision_hash}


def _string_list(value: object, label: str) -> list[str]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise ValueError(f"{label} must be a list of non-empty strings")
    if len(set(value)) != len(value):
        raise ValueError(f"{label} must not contain duplicates")
    return list(value)


def _spans(value: object, label: str) -> list[dict[str, int]]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list")
    spans: list[dict[str, int]] = []
    seen: set[tuple[int, int]] = set()
    for item in value:
        span = _mapping(item, label + " span")
        start = span.get("start_ms")
        end = span.get("end_ms")
        if (
            not isinstance(start, int)
            or isinstance(start, bool)
            or not isinstance(end, int)
            or isinstance(end, bool)
            or start < 0
            or end <= start
        ):
            raise ValueError(f"{label} spans must have increasing integer milliseconds")
        key = (start, end)
        if key not in seen:
            spans.append({"start_ms": start, "end_ms": end})
            seen.add(key)
    return spans


def _candidates(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        raise ValueError("grounding pack candidates must be a list")
    candidates: list[dict[str, object]] = []
    known_ids: set[str] = set()
    for index, item in enumerate(value, start=1):
        candidate = _mapping(item, f"candidate {index}")
        knowledge_id = _required_string(candidate, "knowledge_id", f"candidate {index}")
        if knowledge_id in known_ids:
            raise ValueError("grounding pack candidates must not contain duplicate knowledge IDs")
        knowledge_refs = _string_list(
            candidate.get("knowledge_refs"), f"candidate {knowledge_id} knowledge_refs"
        )
        if knowledge_refs != [knowledge_id]:
            raise ValueError("candidate knowledge_refs must contain its knowledge_id only")
        evidence_refs = _string_list(
            candidate.get("evidence_refs"), f"candidate {knowledge_id} evidence_refs"
        )
        source_spans = _spans(
            candidate.get("source_spans", []), f"candidate {knowledge_id} source_spans"
        )
        related_units = candidate.get("related_units", [])
        if not isinstance(related_units, list):
            raise ValueError(f"candidate {knowledge_id} related_units must be a list")
        normalized_relations: list[dict[str, str]] = []
        for relation_index, relation_value in enumerate(related_units, start=1):
            relation = _mapping(
                relation_value, f"candidate {knowledge_id} related unit {relation_index}"
            )
            normalized_relations.append(
                {
                    "knowledge_id": _required_string(
                        relation, "knowledge_id", "candidate related unit"
                    ),
                    "relation_id": _required_string(
                        relation, "relation_id", "candidate related unit"
                    ),
                    "direction": _relation_direction(relation),
                }
            )
        candidates.append(
            {
                "knowledge_id": knowledge_id,
                "evidence_refs": evidence_refs,
                "source_spans": source_spans,
                "related_units": normalized_relations,
            }
        )
        known_ids.add(knowledge_id)
    return candidates


def _relation_direction(relation: Mapping[str, object]) -> str:
    direction = _required_string(relation, "direction", "candidate related unit")
    if direction not in {"incoming", "outgoing"}:
        raise ValueError("candidate related unit direction must be incoming or outgoing")
    return direction


def _facets(
    value: object, candidate_ids: set[str], revision_identity: Mapping[str, str] | None
) -> dict[str, dict[str, list[str]]]:
    topology = _mapping(value, "grounding pack topology")
    if _revision_identity(topology, "grounding pack topology") != revision_identity:
        raise ValueError("grounding pack topology revision identity must match the pack")
    facet_values = topology.get("facets")
    if not isinstance(facet_values, list):
        raise ValueError("grounding pack topology facets must be a list")
    facets: dict[str, dict[str, list[str]]] = {}
    for index, value in enumerate(facet_values, start=1):
        facet = _mapping(value, f"topology facet {index}")
        knowledge_id = _required_string(facet, "unit_id", f"topology facet {index}")
        if knowledge_id in facets:
            raise ValueError("grounding pack topology facets must not contain duplicates")
        inbound_relation_ids = _string_list(
            facet.get("inbound_relation_ids", []),
            f"topology facet {knowledge_id} inbound_relation_ids",
        )
        outbound_relation_ids = _string_list(
            facet.get("outbound_relation_ids", []),
            f"topology facet {knowledge_id} outbound_relation_ids",
        )
        facets[knowledge_id] = {
            "inbound_relation_ids": inbound_relation_ids,
            "outbound_relation_ids": outbound_relation_ids,
            "relation_ids": sorted(set(inbound_relation_ids + outbound_relation_ids)),
        }
    if set(facets) != candidate_ids:
        raise ValueError("grounding pack topology must not contain unselected candidates")

    return facets


def _windows(
    value: object, candidate_ids: set[str], revision_identity: Mapping[str, str] | None
) -> dict[str, dict[str, object]]:
    if not isinstance(value, list):
        raise ValueError("grounding pack evidence_windows must be a list")
    result: dict[str, dict[str, object]] = {}
    window_ids: set[str] = set()
    for index, value in enumerate(value, start=1):
        window = _mapping(value, f"evidence window {index}")
        if _revision_identity(window, f"evidence window {index}") != revision_identity:
            raise ValueError("grounding pack evidence window revision identity must match the pack")
        window_id = _required_string(window, "window_id", f"evidence window {index}")
        if window_id in window_ids:
            raise ValueError("grounding pack evidence windows must not contain duplicate IDs")
        knowledge_id = _required_string(window, "knowledge_id", f"evidence window {index}")
        if knowledge_id not in candidate_ids:
            raise ValueError("evidence window references an unselected candidate")
        evidence_refs = _string_list(
            window.get("evidence_refs"), f"evidence window {window_id} evidence_refs"
        )
        source_spans = _spans(
            window.get("source_spans"), f"evidence window {window_id} source_spans"
        )
        support = result.setdefault(
            knowledge_id,
            {"window_ids": [], "evidence_refs": set(), "source_spans": set()},
        )
        support["window_ids"].append(window_id)
        support["evidence_refs"].update(evidence_refs)
        support["source_spans"].update(
            (span["start_ms"], span["end_ms"]) for span in source_spans
        )
        window_ids.add(window_id)
    return result


def _validate_candidate_support(
    candidates: Sequence[Mapping[str, object]],
    facets: Mapping[str, Mapping[str, list[str]]],
    windows: Mapping[str, Mapping[str, object]],
) -> None:
    for candidate in candidates:
        knowledge_id = candidate["knowledge_id"]
        assert isinstance(knowledge_id, str)
        support = windows.get(knowledge_id)
        if support is None:
            continue
        window_evidence_refs = support["evidence_refs"]
        assert isinstance(window_evidence_refs, set)
        candidate_evidence_refs = candidate["evidence_refs"]
        assert isinstance(candidate_evidence_refs, list)
        if not set(candidate_evidence_refs).issubset(window_evidence_refs):
            raise ValueError(
                f"candidate evidence_refs are not covered by selected windows: {knowledge_id}"
            )

        window_source_spans = support["source_spans"]
        assert isinstance(window_source_spans, set)
        candidate_source_spans = candidate["source_spans"]
        assert isinstance(candidate_source_spans, list)
        candidate_span_keys = {
            (span["start_ms"], span["end_ms"])
            for span in candidate_source_spans
            if isinstance(span, Mapping)
        }
        if not candidate_span_keys.issubset(window_source_spans):
            raise ValueError(
                f"candidate source_spans are not covered by selected windows: {knowledge_id}"
            )

        facet = facets[knowledge_id]
        allowed_relation_ids = set(facet["relation_ids"])
        related_units = candidate["related_units"]
        assert isinstance(related_units, list)
        for relation in related_units:
            assert isinstance(relation, Mapping)
            relation_id = relation["relation_id"]
            assert isinstance(relation_id, str)
            if relation_id not in allowed_relation_ids:
                raise ValueError(
                    f"candidate relation is not present in selected topology: {relation_id}"
                )
            related_knowledge_id = relation["knowledge_id"]
            direction = relation["direction"]
            assert isinstance(related_knowledge_id, str)
            assert isinstance(direction, str)
            if related_knowledge_id not in facets:
                continue
            own_adjacency = (
                facet["outbound_relation_ids"]
                if direction == "outgoing"
                else facet["inbound_relation_ids"]
            )
            related_adjacency = (
                facets[related_knowledge_id]["inbound_relation_ids"]
                if direction == "outgoing"
                else facets[related_knowledge_id]["outbound_relation_ids"]
            )
            if relation_id not in own_adjacency or relation_id not in related_adjacency:
                raise ValueError(
                    f"candidate relation lacks reciprocal selected topology adjacency: {relation_id}"
                )


def _block(
    index: int,
    candidate: Mapping[str, object],
    window_ids: Sequence[str],
    selected_ids: set[str],
) -> dict[str, object]:
    relation_refs = sorted(
        {
            relation["relation_id"]
            for relation in candidate["related_units"]
            if relation["knowledge_id"] in selected_ids
        }
    )
    return {
        "block_id": f"block:{index:03d}",
        "authoring_purpose": "address_selected_facet",
        "expected_claim_ids": [f"claim:{index:03d}"],
        "knowledge_refs": [candidate["knowledge_id"]],
        "evidence_refs": candidate["evidence_refs"],
        "source_spans": candidate["source_spans"],
        "evidence_window_ids": list(window_ids),
        "relation_refs": relation_refs,
    }
