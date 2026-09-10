"""Semantic validation for grounded answers over retained QA assets."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path

from pydantic import ValidationError

from vka.models import Evidence, KnowledgeRelation, KnowledgeUnit
from vka.qa_asset import qa_asset_fingerprint, validate_qa_asset
from vka.qa_contract import GroundedAnswer
from vka.qa_external import EXTERNAL_EVIDENCE_PATH, read_external_evidence
from vka.qa_revision import load_knowledge_revision
from vka.lifecycle import verify_asset
from vka.store import AssetStore


_CANONICAL_REF_FIELDS = frozenset({"knowledge_refs", "evidence_refs", "source_spans"})
_INSUFFICIENT_TYPES = frozenset({"limitation", "question"})


def validate_grounded_answer(
    asset: AssetStore | Path | str, answer: GroundedAnswer | Mapping[str, object]
) -> list[str]:
    """Return all deterministic grounding errors without changing the asset or index.

    The answer contract validates payload shape. This boundary reconciles that
    payload against the canonical evidence and knowledge records in an asset.
    """
    store = _as_store(asset)
    try:
        readiness_errors = validate_qa_asset(store)
        verification = verify_asset(store)
        integrity_errors = _verification_errors(verification)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        return [f"asset integrity cannot be verified: {exc}"]
    asset_errors = [f"asset integrity error: {error}" for error in integrity_errors]
    asset_errors.extend(f"asset QA error: {error}" for error in sorted(set(readiness_errors)))
    if asset_errors:
        return _unique(asset_errors)

    try:
        # Recompute the P4 retained-layer fingerprint before trusting its records.
        qa_fingerprint = qa_asset_fingerprint(store)
        manifest = store._read_manifest()
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        return [f"asset fingerprint cannot be computed: {exc}"]

    errors = _extension_errors(answer)
    grounded_answer, contract_errors = _as_grounded_answer(answer)
    errors.extend(contract_errors)
    if grounded_answer is None:
        return _unique(errors)

    manifest_asset_id = manifest.get("asset_id") if isinstance(manifest, Mapping) else None
    if not isinstance(manifest_asset_id, str) or not manifest_asset_id:
        errors.append("manifest asset_id must be a non-empty string")
    elif grounded_answer.asset_id != manifest_asset_id:
        errors.append("answer asset_id does not match manifest asset_id")

    evidence, evidence_errors = _read_evidence(store.root / "evidence" / "records.jsonl")
    errors.extend(evidence_errors)

    if grounded_answer.knowledge_revision is not None:
        try:
            revision = load_knowledge_revision(store, grounded_answer.knowledge_revision)
        except ValueError as exc:
            return _unique([f"knowledge revision cannot be loaded: {exc}", *errors])
        if _revision_sha256(revision) != grounded_answer.knowledge_revision_sha256:
            errors.append(
                "knowledge_revision_sha256 does not match the retained revision identity"
            )
        knowledge, knowledge_errors = _read_knowledge_records(
            revision["units"], "knowledge revision"
        )
        relations, relation_errors = _read_relations_records(
            revision["relations"], knowledge, evidence, "relation revision"
        )
    else:
        knowledge, knowledge_errors = _read_knowledge(
            store.root / "knowledge" / "units.jsonl"
        )
        relations, relation_errors = _read_relations(
            store.root / "knowledge" / "relations.jsonl", knowledge, evidence
        )
    errors.extend(knowledge_errors)
    errors.extend(relation_errors)
    if evidence_errors or knowledge_errors or relation_errors:
        return _unique(errors)

    video_external_namespace = sorted(
        evidence_id for evidence_id in evidence if evidence_id.startswith("external:")
    )
    errors.extend(
        f"video evidence must not use external namespace {evidence_id}"
        for evidence_id in video_external_namespace
    )
    if grounded_answer.mode in {"video_plus_context", "explore"}:
        external_evidence, external_errors = read_external_evidence(
            store.root / EXTERNAL_EVIDENCE_PATH, required=True
        )
        errors.extend(external_errors)
        collisions = sorted(set(evidence) & set(external_evidence))
        errors.extend(
            f"external evidence ID collides with video evidence {evidence_id}"
            for evidence_id in collisions
        )
        if external_errors or video_external_namespace or collisions:
            return _unique(errors)
        errors.extend(_external_context_errors(grounded_answer, external_evidence))

    errors.extend(
        _answer_plan_errors(
            store,
            grounded_answer,
            knowledge,
            evidence,
            relations,
            qa_fingerprint,
        )
    )

    has_inference_claim = False
    has_insufficient_claim = False
    claim_knowledge_refs: list[str] = []
    claim_evidence_refs: list[str] = []
    claim_spans: list[dict[str, int]] = []

    for claim_number, claim in enumerate(grounded_answer.claims, start=1):
        claim_knowledge_refs.extend(claim.knowledge_refs)
        claim_evidence_refs.extend(claim.evidence_refs)
        actual_spans = _spans_from_models(claim.source_spans)
        claim_spans.extend(actual_spans)

        known_units = []
        for knowledge_id in claim.knowledge_refs:
            unit = knowledge.get(knowledge_id)
            if unit is None:
                errors.append(f"claim {claim_number} references unknown knowledge {knowledge_id}")
            else:
                known_units.append((knowledge_id, unit))

        known_evidence = []
        for evidence_id in claim.evidence_refs:
            record = evidence.get(evidence_id)
            if record is None:
                errors.append(f"claim {claim_number} references unknown evidence {evidence_id}")
            else:
                known_evidence.append((evidence_id, record))

        canonical_evidence = {
            evidence_id
            for _, unit in known_units
            for evidence_id in unit["evidence_refs"]
        }
        for evidence_id, _ in known_evidence:
            if evidence_id not in canonical_evidence:
                errors.append(
                    f"claim {claim_number} evidence {evidence_id} is not a canonical evidence_ref for its knowledge_refs"
                )

        for knowledge_id, unit in known_units:
            if unit["epistemic_status"] == "external_enrichment":
                errors.append(
                    f"claim {claim_number} references external_enrichment knowledge {knowledge_id}"
                )
        for evidence_id, record in known_evidence:
            if record["origin"] == "external":
                errors.append(f"claim {claim_number} references external evidence {evidence_id}")
            if record["modality"] == "frame" and not _window_eligible_evidence(record):
                errors.append(
                    f"claim {claim_number} frame evidence {evidence_id} must be directly_inspected"
                )

        expected_spans = _sorted_unique_spans(
            span
            for _, record in known_evidence
            if record["origin"] == "video"
            for span in record["spans"]
        )
        if actual_spans != expected_spans:
            errors.append(
                f"claim {claim_number} source_spans must equal resolved video evidence spans"
            )

        if claim.status == "video_explicit":
            for knowledge_id, unit in known_units:
                if unit["epistemic_status"] != "video_explicit":
                    errors.append(
                        f"claim {claim_number} video_explicit references non-video-explicit knowledge {knowledge_id}"
                    )
            for evidence_id, record in known_evidence:
                if record["origin"] != "video":
                    errors.append(
                        f"claim {claim_number} video_explicit references non-video evidence {evidence_id}"
                    )
        elif claim.status == "agent_inference":
            has_inference_claim = True
            if not any(
                unit["epistemic_status"] == "agent_inference" for _, unit in known_units
            ):
                errors.append(
                    f"claim {claim_number} agent_inference requires an agent_inference knowledge unit"
                )
            for knowledge_id, unit in known_units:
                if unit["epistemic_status"] not in {
                    "video_explicit",
                    "agent_inference",
                }:
                    errors.append(
                        f"claim {claim_number} agent_inference references unsupported knowledge {knowledge_id}"
                    )
            for evidence_id, record in known_evidence:
                if record["origin"] != "video":
                    errors.append(
                        f"claim {claim_number} agent_inference references non-video evidence {evidence_id}"
                    )
        elif claim.status == "insufficient_evidence":
            has_insufficient_claim = True
            for knowledge_id, unit in known_units:
                if (
                    unit["type"] not in _INSUFFICIENT_TYPES
                    and unit["epistemic_status"] != "insufficient_evidence"
                ):
                    errors.append(
                        f"claim {claim_number} insufficient_evidence references unsupported knowledge {knowledge_id}"
                    )

    if has_inference_claim and not _has_inference_limitation(grounded_answer.limitations):
        errors.append(
            "agent_inference answers require limitations containing 推断 or 未由视频直接证明"
        )
    if has_insufficient_claim and not grounded_answer.limitations:
        errors.append("insufficient_evidence answers require limitations")

    if grounded_answer.answer_status == "out_of_scope" and grounded_answer.claims:
        errors.append("out_of_scope answers cannot include claims")

    if grounded_answer.knowledge_refs != _sorted_unique_strings(claim_knowledge_refs):
        errors.append("top-level knowledge_refs must equal the union of claim knowledge_refs")
    if grounded_answer.evidence_refs != _sorted_unique_strings(claim_evidence_refs):
        errors.append("top-level evidence_refs must equal the union of claim evidence_refs")
    for evidence_id in grounded_answer.evidence_refs:
        record = evidence.get(evidence_id)
        if record is not None and record["modality"] == "frame" and not _window_eligible_evidence(record):
            errors.append(
                f"top-level frame evidence {evidence_id} must be directly_inspected"
            )
    if _spans_from_models(grounded_answer.source_spans) != _sorted_unique_spans(claim_spans):
        errors.append("top-level source_spans must equal the union of claim source_spans")

    return _unique(errors)


def _external_context_errors(
    answer: GroundedAnswer, external_evidence: Mapping[str, object]
) -> list[str]:
    """Reconcile non-video claims solely with the external artifact namespace."""

    errors: list[str] = []
    claim_ids = {claim.claim_id for claim in answer.external_claims}
    for number, claim in enumerate(answer.external_claims, start=1):
        for evidence_id in claim.external_evidence_refs:
            if evidence_id not in external_evidence:
                errors.append(
                    f"external claim {number} references unknown external evidence {evidence_id}"
                )
    for number, block in enumerate(answer.external_blocks, start=1):
        unknown = sorted(set(block.claim_refs) - claim_ids)
        errors.extend(
            f"external block {number} references unknown external claim {claim_id}"
            for claim_id in unknown
        )
    for number, conflict in enumerate(answer.source_conflicts, start=1):
        video_claim_ids = {claim.claim_id for claim in answer.claims if claim.claim_id}
        for claim_id in conflict.video_claim_refs:
            if claim_id not in video_claim_ids:
                errors.append(
                    f"source conflict {number} references unknown video claim {claim_id}"
                )
        for evidence_id in conflict.external_evidence_refs:
            if evidence_id not in external_evidence:
                errors.append(
                    f"source conflict {number} references unknown external evidence {evidence_id}"
                )
    return errors


def _as_store(asset: AssetStore | Path | str) -> AssetStore:
    return asset if isinstance(asset, AssetStore) else AssetStore(Path(asset))


def _artifact_path(store: AssetStore, filename: str) -> Path:
    return store.root / "index" / filename


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


def _retained_topology_errors(
    path: Path, revision_id: str | None, revision_sha256: str | None
) -> list[str]:
    try:
        topology = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return ["retained QA topology cannot be verified"]
    if not isinstance(topology, Mapping):
        return ["retained QA topology cannot be verified"]
    if (
        topology.get("knowledge_revision") != revision_id
        or topology.get("knowledge_revision_sha256") != revision_sha256
    ):
        return ["retained QA topology revision identity does not match the answer"]
    return []


def _verification_errors(report: object) -> list[str]:
    if not isinstance(report, Mapping):
        raise ValueError("asset verification report must be an object")
    errors = report.get("errors")
    if not isinstance(errors, list) or not all(isinstance(error, str) for error in errors):
        raise ValueError("asset verification report errors must be a list of strings")
    return sorted(set(errors))


def _as_grounded_answer(
    answer: GroundedAnswer | Mapping[str, object],
) -> tuple[GroundedAnswer | None, list[str]]:
    if isinstance(answer, GroundedAnswer):
        answer = answer.model_dump(mode="python")
    if not isinstance(answer, Mapping):
        return None, ["answer must be a GroundedAnswer or mapping"]
    try:
        return GroundedAnswer.model_validate(answer), []
    except ValidationError as exc:
        details = sorted(
            {
                f"answer contract error: {item['loc']}: {item['msg']}"
                for item in exc.errors()
            }
        )
        return None, details


def _extension_errors(answer: GroundedAnswer | Mapping[str, object]) -> list[str]:
    if isinstance(answer, GroundedAnswer):
        value: object = answer.model_dump(mode="python")
    else:
        value = answer
    if not isinstance(value, Mapping):
        return []

    errors: list[str] = []
    if _contains_extension_shape({key: item for key, item in value.items() if key != "extensions"}):
        errors.append("extensions must only appear at top level")
    extensions = value.get("extensions", [])
    if _contains_canonical_refs(extensions):
        errors.append("extensions must not carry canonical refs")
    return errors


def _contains_extension_shape(value: object) -> bool:
    if isinstance(value, Mapping):
        if value.get("kind") in {"agent_background", "exploration"} or "visible_label" in value:
            return True
        return any(_contains_extension_shape(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_extension_shape(item) for item in value)
    return False


def _answer_plan_errors(
    store: AssetStore,
    answer: GroundedAnswer,
    knowledge: Mapping[str, Mapping[str, object]],
    evidence: Mapping[str, Mapping[str, object]],
    relations: Mapping[str, tuple[str, str]],
    qa_fingerprint: Mapping[str, str],
) -> list[str]:
    """Reconcile optional reference-only plan slots with rendered factual blocks."""

    if answer.answer_plan is None:
        return []
    plan_blocks = answer.answer_plan.get("blocks")
    if not isinstance(plan_blocks, list):
        return ["answer_plan blocks must be a list"]

    errors: list[str] = []
    revision_id = answer.knowledge_revision
    revision_sha256 = answer.knowledge_revision_sha256
    if revision_id is not None:
        windows_path = store.root / "index" / "revisions" / revision_id / "evidence-windows.jsonl"
        errors.extend(
            _retained_topology_errors(
                store.root / "index" / "revisions" / revision_id / "qa-topology.json",
                revision_id,
                revision_sha256,
            )
        )
    else:
        windows_path = _artifact_path(store, "evidence-windows.jsonl")
    retained_windows, window_errors = _read_retained_windows(
        windows_path,
        knowledge,
        evidence,
        qa_fingerprint,
        revision_id=revision_id,
        revision_sha256=revision_sha256,
    )
    errors.extend(window_errors)
    answer_blocks = {block.block_id: block for block in answer.blocks}
    claims = {
        claim.claim_id: claim
        for claim in answer.claims
        if claim.claim_id is not None
    }
    plan_ids: set[str] = set()
    selected_knowledge_ids: set[str] = set()
    plan_slots: list[tuple[str, str, Mapping[str, object]]] = []
    for index, plan_block in enumerate(plan_blocks, start=1):
        if not isinstance(plan_block, Mapping):
            errors.append(f"answer_plan block {index} must be an object")
            continue
        block_id = plan_block.get("block_id")
        if not isinstance(block_id, str) or not block_id.strip():
            errors.append(f"answer_plan block {index} has an invalid block_id")
            continue
        if block_id in plan_ids:
            errors.append(f"answer_plan has duplicate block_id {block_id}")
            continue
        plan_ids.add(block_id)

        plan_knowledge_refs = _plan_string_refs(
            plan_block.get("knowledge_refs"), "knowledge_refs", block_id, errors
        )
        plan_evidence_refs = _plan_string_refs(
            plan_block.get("evidence_refs"), "evidence_refs", block_id, errors
        )
        plan_source_spans = _parse_strict_spans(plan_block.get("source_spans"))
        if plan_source_spans is None:
            errors.append(f"answer_plan block {block_id} source_spans must be a list of valid spans")
            plan_source_spans = []
        for knowledge_id in plan_knowledge_refs:
            unit = knowledge.get(knowledge_id)
            if unit is None:
                errors.append(
                    f"answer_plan block {block_id} references unknown knowledge {knowledge_id}"
                )
            elif unit["epistemic_status"] == "external_enrichment":
                errors.append(
                    f"answer_plan block {block_id} references external_enrichment knowledge {knowledge_id}"
                )
        for evidence_id in plan_evidence_refs:
            record = evidence.get(evidence_id)
            if record is None:
                errors.append(
                    f"answer_plan block {block_id} references unknown evidence {evidence_id}"
                )
            elif record["origin"] != "video":
                errors.append(
                    f"answer_plan block {block_id} references external evidence {evidence_id}"
                )
        expected_plan_spans = _sorted_unique_spans(
            span
            for evidence_id in plan_evidence_refs
            if evidence_id in evidence and evidence[evidence_id]["origin"] == "video"
            for span in evidence[evidence_id]["spans"]
        )
        if plan_source_spans != expected_plan_spans:
            errors.append(
                f"answer_plan block {block_id} source_spans must equal resolved video evidence spans"
            )

        if len(plan_knowledge_refs) != 1:
            errors.append(
                f"answer_plan block {block_id} must select exactly one knowledge_ref"
            )
        else:
            knowledge_id = next(iter(plan_knowledge_refs))
            if knowledge_id in selected_knowledge_ids:
                errors.append(
                    f"answer_plan selects duplicate knowledge {knowledge_id}"
                )
            selected_knowledge_ids.add(knowledge_id)
            plan_slots.append((block_id, knowledge_id, plan_block))

        answer_block = answer_blocks.get(block_id)
        if answer_block is None or answer_block.kind != "factual":
            errors.append(f"answer_plan block {block_id} has no factual answer block")
            continue
        for claim_id in answer_block.claim_refs:
            claim = claims.get(claim_id)
            if claim is None:
                continue
            if not set(claim.knowledge_refs).issubset(plan_knowledge_refs):
                errors.append(
                    f"block {block_id} claim {claim_id} references knowledge outside its answer_plan slot"
                )
            if not set(claim.evidence_refs).issubset(plan_evidence_refs):
                errors.append(
                    f"block {block_id} claim {claim_id} references evidence outside its answer_plan slot"
                )
            claim_spans = _spans_from_models(claim.source_spans)
            if not {
                (span["start_ms"], span["end_ms"]) for span in claim_spans
            }.issubset(
                {(span["start_ms"], span["end_ms"]) for span in plan_source_spans}
            ):
                errors.append(
                    f"block {block_id} claim {claim_id} references source spans outside its answer_plan slot"
                )

    for block in answer.blocks:
        if block.kind == "factual" and block.block_id not in plan_ids:
            errors.append(
                f"factual block {block.block_id} is not present in answer_plan metadata"
            )
    selected_knowledge_ids = _selected_plan_knowledge_ids(
        answer.answer_plan, selected_knowledge_ids, errors
    )
    errors.extend(
        _plan_window_and_relation_errors(
            plan_slots, selected_knowledge_ids, retained_windows, relations
        )
    )
    return errors


def _selected_plan_knowledge_ids(
    answer_plan: Mapping[str, object],
    slot_knowledge_ids: set[str],
    errors: list[str],
) -> set[str]:
    """Use declared facets when present, while requiring slots to agree exactly."""

    if "selected_facets" not in answer_plan:
        return slot_knowledge_ids
    facets = answer_plan.get("selected_facets")
    if not isinstance(facets, list):
        errors.append("answer_plan selected_facets must be a list")
        return slot_knowledge_ids
    selected_ids: set[str] = set()
    for index, facet in enumerate(facets, start=1):
        if not isinstance(facet, Mapping):
            errors.append(f"answer_plan selected_facet {index} must be an object")
            continue
        knowledge_id = facet.get("knowledge_id")
        if not isinstance(knowledge_id, str) or not knowledge_id.strip():
            errors.append(
                f"answer_plan selected_facet {index} has an invalid knowledge_id"
            )
            continue
        if knowledge_id in selected_ids:
            errors.append(f"answer_plan selected_facets contains duplicate knowledge {knowledge_id}")
            continue
        selected_ids.add(knowledge_id)
    if selected_ids != slot_knowledge_ids:
        errors.append("answer_plan selected_facets must equal block knowledge_refs")
    return selected_ids


def _read_retained_windows(
    path: Path,
    knowledge: Mapping[str, Mapping[str, object]],
    evidence: Mapping[str, Mapping[str, object]],
    qa_fingerprint: Mapping[str, str],
    *,
    revision_id: str | None = None,
    revision_sha256: str | None = None,
) -> tuple[dict[str, list[dict[str, object]]], list[str]]:
    """Read the latest bounded windows without regenerating derived artifacts."""

    records, errors = _jsonl_records(path, "retained evidence windows")
    if errors:
        return {}, ["retained evidence windows cannot be verified"]
    windows_by_knowledge: dict[str, list[dict[str, object]]] = {}
    seen_ids: set[str] = set()
    allowed_window_keys = {
        "schema_version",
        "profile_id",
        "qa_asset_fingerprint",
        "window_id",
        "knowledge_id",
        "anchor_evidence_refs",
        "evidence_refs",
        "source_spans",
        "evidence",
    }
    if revision_id is not None:
        allowed_window_keys.update({"knowledge_revision", "knowledge_revision_sha256"})
    for line_number, record in records:
        label = f"retained evidence window {line_number}"
        if set(record) != allowed_window_keys:
            errors.append(f"{label} has unknown or missing properties")
            continue
        if revision_id is not None and (
            record.get("knowledge_revision") != revision_id
            or record.get("knowledge_revision_sha256") != revision_sha256
        ):
            errors.append(f"{label} revision identity does not match the answer")
            continue
        window_id = record.get("window_id")
        knowledge_id = record.get("knowledge_id")
        if not isinstance(window_id, str) or not window_id.strip():
            errors.append(f"{label} has an invalid window_id")
            continue
        if not isinstance(knowledge_id, str) or not knowledge_id.strip():
            errors.append(f"{label} has an invalid knowledge_id")
            continue
        if window_id in seen_ids:
            errors.append(f"retained evidence windows contain duplicate window_id {window_id}")
            continue
        seen_ids.add(window_id)
        sequence = window_id.removeprefix(f"window:{knowledge_id}:")
        if (
            not window_id.startswith(f"window:{knowledge_id}:")
            or not sequence.isdecimal()
            or int(sequence) < 1
        ):
            errors.append(f"{label} has an invalid window_id")
            continue
        if record.get("schema_version") != "1.0":
            errors.append(f"{label} has an invalid schema_version")
            continue
        if record.get("profile_id") != "course-notes":
            errors.append(f"{label} has an invalid profile_id")
            continue
        if record.get("qa_asset_fingerprint") != dict(qa_fingerprint):
            errors.append(f"{label} fingerprint does not match the QA asset")
            continue
        unit = knowledge.get(knowledge_id)
        if unit is None:
            errors.append(f"{label} references unknown knowledge {knowledge_id}")
            continue
        if unit["epistemic_status"] == "external_enrichment":
            errors.append(f"{label} references external_enrichment knowledge {knowledge_id}")
            continue
        evidence_refs = _retained_window_refs(
            record.get("evidence_refs"), "evidence_refs", label, errors, required=True
        )
        anchor_refs = _retained_window_refs(
            record.get("anchor_evidence_refs"),
            "anchor_evidence_refs",
            label,
            errors,
            required=True,
        )
        source_spans = _parse_strict_spans(record.get("source_spans"))
        if source_spans is None:
            errors.append(f"{label} source_spans must be a list of valid spans")
            source_spans = []
        payload = record.get("evidence")
        if not isinstance(payload, list) or not payload:
            errors.append(f"{label} must contain evidence payload")
            payload = []
        payload_ids: list[str] = []
        for item_index, item in enumerate(payload, start=1):
            if not isinstance(item, Mapping):
                errors.append(f"{label} evidence {item_index} must be an object")
                continue
            evidence_id = item.get("evidence_id")
            if not isinstance(evidence_id, str) or not evidence_id.strip():
                errors.append(f"{label} evidence {item_index} has an invalid evidence_id")
                continue
            payload_ids.append(evidence_id)
            canonical = evidence.get(evidence_id)
            if canonical is None:
                errors.append(f"{label} references unknown evidence {evidence_id}")
                continue
            expected_item = {
                "evidence_id": evidence_id,
                "origin": canonical["origin"],
                "modality": canonical["modality"],
                "content": canonical["content"],
                "artifact_ref": canonical["artifact_ref"],
                "spans": canonical["spans"],
            }
            if dict(item) != expected_item:
                errors.append(f"{label} evidence {evidence_id} does not match canonical payload")
        if payload_ids != evidence_refs:
            errors.append(f"{label} evidence_refs must match evidence payload")
        if any(reference not in evidence for reference in evidence_refs):
            for reference in sorted(set(evidence_refs) - set(evidence)):
                errors.append(f"{label} references unknown evidence {reference}")
        for reference in evidence_refs:
            canonical = evidence.get(reference)
            if canonical is not None and not _window_eligible_evidence(canonical):
                errors.append(f"{label} includes ineligible evidence {reference}")
        if not set(anchor_refs).issubset(evidence_refs):
            errors.append(f"{label} anchor_evidence_refs must be included in evidence_refs")
        if not set(anchor_refs).issubset(unit["evidence_refs"]):
            errors.append(f"{label} anchor_evidence_refs must be direct knowledge evidence")
        expected_spans = _sorted_unique_spans(
            span
            for reference in evidence_refs
            if reference in evidence
            for span in evidence[reference]["spans"]
        )
        if source_spans != expected_spans:
            errors.append(f"{label} source_spans must equal resolved evidence spans")
        if any(error.startswith(label) for error in errors):
            continue
        windows_by_knowledge.setdefault(knowledge_id, []).append(
            {
                "window_id": window_id,
                "evidence_refs": evidence_refs,
                "source_spans": source_spans,
            }
        )
    for knowledge_id, windows in windows_by_knowledge.items():
        if not _is_window_partition(
            knowledge_id, [str(window["window_id"]) for window in windows]
        ):
            errors.append(
                f"retained evidence windows have an invalid partition for knowledge {knowledge_id}"
            )
    return windows_by_knowledge, errors


def _retained_window_refs(
    value: object,
    field: str,
    label: str,
    errors: list[str],
    *,
    required: bool,
) -> list[str]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        errors.append(f"{label} {field} must be a list of non-empty strings")
        return []
    if required and not value:
        errors.append(f"{label} must contain {field}")
    if len(set(value)) != len(value):
        errors.append(f"{label} {field} must not contain duplicates")
    return list(value)


def _window_eligible_evidence(record: Mapping[str, object]) -> bool:
    if record["origin"] != "video":
        return False
    if record["modality"] == "transcript":
        return True
    quality = record.get("quality")
    return (
        record["modality"] == "frame"
        and isinstance(quality, Mapping)
        and quality.get("review") == "directly_inspected"
    )


def _plan_window_and_relation_errors(
    plan_slots: list[tuple[str, str, Mapping[str, object]]],
    selected_knowledge_ids: set[str],
    retained_windows: Mapping[str, list[Mapping[str, object]]],
    relations: Mapping[str, tuple[str, str]],
) -> list[str]:
    errors: list[str] = []
    for knowledge_id in selected_knowledge_ids:
        windows = retained_windows.get(knowledge_id, [])
        window_ids = [window["window_id"] for window in windows]
        if not windows:
            errors.append(
                f"retained evidence windows are missing selected knowledge {knowledge_id}"
            )
        elif not _is_window_partition(knowledge_id, window_ids):
            errors.append(
                f"retained evidence windows have an invalid partition for knowledge {knowledge_id}"
            )

    for block_id, knowledge_id, plan_block in plan_slots:
        plan_window_ids = _plan_string_refs(
            plan_block.get("evidence_window_ids"),
            "evidence_window_ids",
            block_id,
            errors,
        )
        retained_for_knowledge = retained_windows.get(knowledge_id, [])
        expected_window_ids = {
            window["window_id"] for window in retained_for_knowledge
        }
        if plan_window_ids != expected_window_ids:
            errors.append(
                f"answer_plan block {block_id} evidence_window_ids do not match retained windows for {knowledge_id}"
            )
        declared_windows = [
            window
            for window in retained_for_knowledge
            if window["window_id"] in plan_window_ids
        ]
        window_evidence_refs = {
            evidence_id
            for window in declared_windows
            for evidence_id in window["evidence_refs"]
            if isinstance(evidence_id, str)
        }
        window_span_keys = {
            (span["start_ms"], span["end_ms"])
            for window in declared_windows
            for span in window["source_spans"]
            if isinstance(span, Mapping)
        }
        plan_evidence_refs = _plan_string_refs(
            plan_block.get("evidence_refs"), "evidence_refs", block_id, errors
        )
        if not plan_evidence_refs.issubset(window_evidence_refs):
            errors.append(
                f"answer_plan block {block_id} evidence_refs are not covered by declared evidence windows"
            )
        plan_spans = _parse_spans(plan_block.get("source_spans")) or []
        if not {
            (span["start_ms"], span["end_ms"]) for span in plan_spans
        }.issubset(window_span_keys):
            errors.append(
                f"answer_plan block {block_id} source_spans are not covered by declared evidence windows"
            )

        plan_relation_ids = _plan_string_refs(
            plan_block.get("relation_refs"), "relation_refs", block_id, errors
        )
        expected_relation_ids: set[str] = set()
        for relation_id, (source_id, target_id) in relations.items():
            if knowledge_id not in {source_id, target_id}:
                continue
            other_id = target_id if source_id == knowledge_id else source_id
            if other_id == knowledge_id:
                continue
            if other_id in selected_knowledge_ids:
                expected_relation_ids.add(relation_id)
            elif relation_id in plan_relation_ids:
                errors.append(
                    f"answer_plan block {block_id} relation {relation_id} reaches unselected knowledge {other_id}"
                )
        for relation_id in plan_relation_ids - set(relations):
            errors.append(
                f"answer_plan block {block_id} references unknown relation {relation_id}"
            )
        for relation_id in plan_relation_ids & set(relations):
            source_id, target_id = relations[relation_id]
            if knowledge_id not in {source_id, target_id}:
                errors.append(
                    f"answer_plan block {block_id} relation {relation_id} is not adjacent to {knowledge_id}"
                )
        if plan_relation_ids != expected_relation_ids:
            errors.append(
                f"answer_plan block {block_id} relation_refs do not match canonical selected topology adjacency"
            )
    return errors


def _is_window_partition(knowledge_id: str, window_ids: list[str]) -> bool:
    return sorted(window_ids) == [
        f"window:{knowledge_id}:{sequence:03d}"
        for sequence in range(1, len(window_ids) + 1)
    ]


def _plan_string_refs(
    value: object, field: str, block_id: str, errors: list[str]
) -> set[str]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        errors.append(f"answer_plan block {block_id} {field} must be a list of non-empty strings")
        return set()
    if len(set(value)) != len(value):
        errors.append(f"answer_plan block {block_id} {field} must not contain duplicates")
    return set(value)


def _contains_canonical_refs(value: object) -> bool:
    if isinstance(value, Mapping):
        return bool(_CANONICAL_REF_FIELDS & set(value)) or any(
            _contains_canonical_refs(item) for item in value.values()
        )
    if isinstance(value, (list, tuple)):
        return any(_contains_canonical_refs(item) for item in value)
    return False


def _read_evidence(path: Path) -> tuple[dict[str, dict[str, object]], list[str]]:
    records, errors = _jsonl_records(path, "evidence")
    evidence: dict[str, dict[str, object]] = {}
    for line_number, record in records:
        try:
            parsed = Evidence.model_validate(record)
        except ValidationError as exc:
            errors.extend(_schema_errors(f"evidence record {line_number}", exc))
            continue
        if parsed.evidence_id in evidence:
            errors.append(f"duplicate evidence_id: {parsed.evidence_id}")
            continue
        evidence[parsed.evidence_id] = {
            "origin": parsed.origin,
            "modality": parsed.modality,
            "spans": _sorted_unique_spans(_spans_from_models(parsed.spans)),
            "content": parsed.content,
            "artifact_ref": parsed.artifact_ref,
            "quality": parsed.quality,
        }
    return evidence, errors


def _read_knowledge(path: Path) -> tuple[dict[str, dict[str, object]], list[str]]:
    records, errors = _jsonl_records(path, "knowledge")
    knowledge, record_errors = _read_knowledge_records(
        [record for _, record in records], "knowledge", line_numbers=[line for line, _ in records]
    )
    return knowledge, errors + record_errors


def _read_knowledge_records(
    records: list[Mapping[str, object]], label: str, *, line_numbers: list[int] | None = None
) -> tuple[dict[str, dict[str, object]], list[str]]:
    knowledge: dict[str, dict[str, object]] = {}
    errors: list[str] = []
    for index, record in enumerate(records, start=1):
        line_number = line_numbers[index - 1] if line_numbers is not None else index
        try:
            parsed = KnowledgeUnit.model_validate(record)
        except ValidationError as exc:
            errors.extend(_schema_errors(f"{label} record {line_number}", exc))
            continue
        if parsed.unit_id in knowledge:
            errors.append(f"duplicate unit_id: {parsed.unit_id}")
            continue
        knowledge[parsed.unit_id] = {
            "type": parsed.type,
            "epistemic_status": parsed.epistemic_status,
            "evidence_refs": parsed.evidence_refs,
        }
    return knowledge, errors


def _read_relations(
    path: Path,
    knowledge: Mapping[str, Mapping[str, object]],
    evidence: Mapping[str, Mapping[str, object]],
) -> tuple[dict[str, tuple[str, str]], list[str]]:
    records, errors = _jsonl_records(path, "relation")
    relations, record_errors = _read_relations_records(
        [record for _, record in records], knowledge, evidence, "relation", line_numbers=[line for line, _ in records]
    )
    return relations, errors + record_errors


def _read_relations_records(
    records: list[Mapping[str, object]],
    knowledge: Mapping[str, Mapping[str, object]],
    evidence: Mapping[str, Mapping[str, object]],
    label_prefix: str,
    *,
    line_numbers: list[int] | None = None,
) -> tuple[dict[str, tuple[str, str]], list[str]]:
    relations: dict[str, tuple[str, str]] = {}
    errors: list[str] = []
    for index, record in enumerate(records, start=1):
        line_number = line_numbers[index - 1] if line_numbers is not None else index
        try:
            parsed = KnowledgeRelation.model_validate(record)
        except ValidationError as exc:
            errors.extend(_schema_errors(f"{label_prefix} record {line_number}", exc))
            continue
        if not all(
            isinstance(value, str) and value.strip()
            for value in (
                parsed.relation_id,
                parsed.source_unit_id,
                parsed.target_unit_id,
            )
        ):
            errors.append(f"relation record {line_number} has blank IDs")
            continue
        if parsed.relation_id in relations:
            errors.append(f"duplicate relation_id: {parsed.relation_id}")
            continue
        if any(not evidence_id.strip() for evidence_id in parsed.evidence_refs):
            errors.append(
                f"relation {parsed.relation_id} evidence_refs must be non-empty strings"
            )
            continue
        if len(set(parsed.evidence_refs)) != len(parsed.evidence_refs):
            errors.append(f"relation {parsed.relation_id} evidence_refs must not contain duplicates")
            continue
        unknown_evidence_ids = sorted(set(parsed.evidence_refs) - set(evidence))
        if unknown_evidence_ids:
            errors.extend(
                f"relation {parsed.relation_id} references unknown evidence {evidence_id}"
                for evidence_id in unknown_evidence_ids
            )
            continue
        source = knowledge.get(parsed.source_unit_id)
        target = knowledge.get(parsed.target_unit_id)
        if source is None or target is None:
            errors.append(f"relation {parsed.relation_id} references unknown knowledge")
            continue
        endpoint_evidence_refs = set(source["evidence_refs"]) | set(
            target["evidence_refs"]
        )
        if not set(parsed.evidence_refs).issubset(endpoint_evidence_refs):
            errors.append(
                f"relation {parsed.relation_id} evidence_refs must be endpoint evidence"
            )
            continue
        invalid_video_evidence = [
            evidence_id
            for evidence_id in parsed.evidence_refs
            if evidence[evidence_id]["origin"] != "video"
            or not evidence[evidence_id]["spans"]
        ]
        if invalid_video_evidence:
            errors.extend(
                f"relation {parsed.relation_id} evidence {evidence_id} must be video evidence with source spans"
                for evidence_id in invalid_video_evidence
            )
            continue
        if (
            source["epistemic_status"] == "external_enrichment"
            or target["epistemic_status"] == "external_enrichment"
        ):
            continue
        relations[parsed.relation_id] = (parsed.source_unit_id, parsed.target_unit_id)
    return relations, errors


def _jsonl_records(path: Path, label: str) -> tuple[list[tuple[int, Mapping[str, object]]], list[str]]:
    records: list[tuple[int, Mapping[str, object]]] = []
    try:
        with path.open(encoding="utf-8") as file:
            for line_number, line in enumerate(file, start=1):
                if not line.strip():
                    continue
                value = json.loads(line)
                if not isinstance(value, Mapping):
                    return records, [f"{label} record {line_number} must be an object"]
                records.append((line_number, value))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return [], [f"{label} records are not valid JSONL"]
    return records, []


def _schema_errors(label: str, error: ValidationError) -> list[str]:
    errors = []
    for item in error.errors():
        location = ".".join(str(part) for part in item["loc"]) or "root"
        errors.append(f"{label} schema error at {location}: {item['msg']}")
    return sorted(set(errors))


def _parse_spans(value: object) -> list[dict[str, int]] | None:
    if not isinstance(value, list):
        return None
    spans: list[dict[str, int]] = []
    for span in value:
        if not isinstance(span, Mapping):
            return None
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
            return None
        spans.append({"start_ms": start_ms, "end_ms": end_ms})
    return spans


def _parse_strict_spans(value: object) -> list[dict[str, int]] | None:
    """Parse untrusted retained metadata without accepting injected span keys."""

    if not isinstance(value, list):
        return None
    spans: list[dict[str, int]] = []
    for span in value:
        if not isinstance(span, Mapping) or set(span) != {"start_ms", "end_ms"}:
            return None
        start_ms = span["start_ms"]
        end_ms = span["end_ms"]
        if (
            not isinstance(start_ms, int)
            or isinstance(start_ms, bool)
            or not isinstance(end_ms, int)
            or isinstance(end_ms, bool)
            or start_ms < 0
            or end_ms <= start_ms
        ):
            return None
        spans.append({"start_ms": start_ms, "end_ms": end_ms})
    return spans


def _spans_from_models(spans: object) -> list[dict[str, int]]:
    parsed = _parse_spans(
        [span.model_dump(mode="python") if hasattr(span, "model_dump") else span for span in spans]
    )
    return parsed or []


def _sorted_unique_spans(spans: object) -> list[dict[str, int]]:
    return [
        {"start_ms": start_ms, "end_ms": end_ms}
        for start_ms, end_ms in sorted(
            {
                (span["start_ms"], span["end_ms"])
                for span in spans
            }
        )
    ]


def _sorted_unique_strings(values: list[str]) -> list[str]:
    return sorted(set(values))


def _has_inference_limitation(limitations: list[str]) -> bool:
    return any("推断" in limitation or "未由视频直接证明" in limitation for limitation in limitations)


def _unique(errors: list[str]) -> list[str]:
    return list(dict.fromkeys(errors))
