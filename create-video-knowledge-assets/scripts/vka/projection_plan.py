"""Schema checks for the auditable P3 knowledge-to-document bridge."""

from __future__ import annotations

from collections.abc import Mapping, Sequence


PLAN_SCHEMA_VERSION = "1.0"
P3_PROFILE_IDS = frozenset({"creator-article", "enterprise-knowledge", "research-brief"})
PLAN_STATUSES = frozenset({"ready", "declined", "evidence_inventory"})


def validate_projection_plan(
    plan: object,
    *,
    profile_id: str | None = None,
    required_sections: Sequence[str] | None = None,
) -> list[str]:
    """Validate the structure of a profile authoring plan.

    Canonical IDs and exact frame eligibility are deliberately checked at the
    asset boundary in ``profiles.py``.  This module stays pure so an author can
    validate a draft before attaching it to an asset.
    """
    if not isinstance(plan, Mapping):
        return ["projection plan must be an object"]
    errors: list[str] = []
    if plan.get("schema_version") != PLAN_SCHEMA_VERSION:
        errors.append(f"projection plan schema_version must be {PLAN_SCHEMA_VERSION}")
    declared_profile = plan.get("profile_id")
    if not isinstance(declared_profile, str) or not declared_profile.strip():
        errors.append("projection plan profile_id must be present")
    elif declared_profile not in P3_PROFILE_IDS:
        errors.append("projection plan profile_id must be a supported P3 profile")
    if profile_id is not None and declared_profile != profile_id:
        errors.append("projection plan profile_id must match selected profile")
    for key in ("plan_id", "profile_spec_version", "reader_goal"):
        if not isinstance(plan.get(key), str) or not plan[key].strip():
            errors.append(f"projection plan {key} must be a non-empty string")
    if not _valid_hash_tree(plan.get("canonical_hash_tree")):
        errors.append("projection plan canonical_hash_tree must be a non-empty hash map")
    status = plan.get("status")
    if status not in PLAN_STATUSES:
        errors.append("projection plan status must be ready, declined, or evidence_inventory")

    sections = plan.get("sections")
    if not isinstance(sections, list) or not sections:
        errors.append("projection plan must contain sections")
    else:
        seen_ids: set[str] = set()
        kinds: list[str] = []
        for index, section in enumerate(sections, start=1):
            if not isinstance(section, Mapping):
                errors.append(f"projection plan section {index} must be an object")
                continue
            section_id = section.get("section_id")
            kind = section.get("kind")
            if not isinstance(section_id, str) or not section_id.strip() or section_id in seen_ids:
                errors.append(f"projection plan section {index} needs a unique section_id")
            elif isinstance(section_id, str):
                seen_ids.add(section_id)
            if not isinstance(kind, str) or not kind.strip():
                errors.append(f"projection plan section {index} needs a kind")
            else:
                kinds.append(kind)
            if not isinstance(section.get("reader_question"), str) or len(section["reader_question"].strip()) < 12:
                errors.append(f"projection plan section {index} needs a substantive reader_question")
            if not _valid_refs(section.get("knowledge_refs")):
                errors.append(f"projection plan section {index} needs knowledge_refs")
            if not _valid_refs(section.get("evidence_refs")):
                errors.append(f"projection plan section {index} needs evidence_refs")
            blocks = section.get("required_blocks")
            if not isinstance(blocks, list) or not blocks or not all(
                isinstance(block, str) and block.strip() for block in blocks
            ):
                errors.append(f"projection plan section {index} needs required_blocks")
        if required_sections is not None and tuple(kinds) != tuple(required_sections):
            errors.append("projection plan sections must follow the selected profile semantic order")

    figures = plan.get("selected_figures")
    if not isinstance(figures, list):
        errors.append("projection plan selected_figures must be a list")
    else:
        for index, figure in enumerate(figures, start=1):
            if not isinstance(figure, Mapping):
                errors.append(f"projection plan selected figure {index} must be an object")
                continue
            for key in ("section_id", "evidence_id", "artifact_ref", "reader_purpose", "caption_intent"):
                if not isinstance(figure.get(key), str) or not figure[key].strip():
                    errors.append(f"projection plan selected figure {index} needs {key}")
            if figure.get("required") is not True:
                errors.append(f"projection plan selected figure {index} must be required")
    rejected = plan.get("rejected_frames", [])
    if not isinstance(rejected, list) or any(
        not isinstance(item, Mapping)
        or not isinstance(item.get("evidence_id"), str)
        or not isinstance(item.get("reason"), str)
        or not item["reason"].strip()
        for item in rejected
    ):
        errors.append("projection plan rejected_frames must contain evidence_id and reason")
    targets = plan.get("quality_targets")
    if not isinstance(targets, Mapping):
        errors.append("projection plan quality_targets must be an object")
    else:
        minimum = targets.get("minimum_meaningful_blocks")
        if not isinstance(minimum, int) or isinstance(minimum, bool) or minimum < 1:
            errors.append("projection plan quality_targets needs a positive minimum_meaningful_blocks")
        if not isinstance(targets.get("requires_visual"), bool):
            errors.append("projection plan quality_targets requires_visual must be boolean")
    if status == "ready" and isinstance(targets, Mapping) and targets.get("requires_visual") is True and not figures:
        errors.append("ready projection plan requiring visuals needs selected_figures")
    return list(dict.fromkeys(errors))


def _valid_refs(value: object) -> bool:
    return isinstance(value, list) and bool(value) and all(
        isinstance(item, str) and item.strip() for item in value
    )


def _valid_hash_tree(value: object) -> bool:
    return isinstance(value, Mapping) and bool(value) and all(
        isinstance(path, str)
        and path.strip()
        and isinstance(digest, str)
        and len(digest) == 64
        for path, digest in value.items()
    )
