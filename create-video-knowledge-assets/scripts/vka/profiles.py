"""Registered document profiles and auditable R3 profile routing."""

from __future__ import annotations

import json
import os
import re
import stat
import time
import uuid
from collections.abc import Callable, Mapping
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
from pathlib import Path, PureWindowsPath
from types import MappingProxyType

from vka.models import ProfileSelection
from vka.projection_plan import PLAN_SCHEMA_VERSION, P3_PROFILE_IDS, validate_projection_plan
from vka.store import AssetStore, SCHEMA_VERSION


DocumentValidator = Callable[[object], list[str]]
CANONICAL_DIRECTORIES = ("source", "evidence", "knowledge")


@dataclass(frozen=True)
class ProfileSpec:
    """Immutable description of one supported reader-facing profile."""

    profile_id: str
    required_sections: tuple[str, ...]
    formats: tuple[str, ...]
    validator: DocumentValidator
    renderer_options: Mapping[str, object]
    reference_path: str
    spec_version: str = "1.0"


def _validate_course_notes(document: object) -> list[str]:
    # Imported lazily so quality.py can consult this registry without a cycle.
    from vka.quality import validate_course_document_quality

    return validate_course_document_quality(document)


def _validate_general_deep(document: object) -> list[str]:
    from vka.quality import _general_deep_document_errors

    return _general_deep_document_errors(document)


def _validate_creator_article(document: object) -> list[str]:
    from vka.quality import _creator_article_document_errors

    return _creator_article_document_errors(document)


def _validate_enterprise_knowledge(document: object) -> list[str]:
    from vka.quality import _enterprise_knowledge_document_errors

    return _enterprise_knowledge_document_errors(document)


def _validate_research_brief(document: object) -> list[str]:
    from vka.quality import _research_brief_document_errors

    return _research_brief_document_errors(document)


def _required_sections_validator(
    profile_id: str, required_sections: tuple[str, ...]
) -> DocumentValidator:
    def validate(document: object) -> list[str]:
        if not isinstance(document, Mapping):
            return [f"{profile_id} document must be an object"]
        sections = document.get("sections")
        if not isinstance(sections, list):
            return [f"{profile_id} document must declare semantic sections"]
        present = {
            section.get("kind")
            for section in sections
            if isinstance(section, Mapping) and isinstance(section.get("kind"), str)
        }
        return [
            f"{profile_id} document is missing required section {section_name!r}"
            for section_name in required_sections
            if section_name not in present
        ]

    return validate


def _options(**values: object) -> Mapping[str, object]:
    return MappingProxyType(dict(values))


PROFILES: Mapping[str, ProfileSpec] = MappingProxyType(
    {
        "general-deep": ProfileSpec(
            profile_id="general-deep",
            required_sections=("overview", "logical_body", "limitations", "source_navigation"),
            formats=("md", "html", "tex", "pdf"),
            validator=_validate_general_deep,
            renderer_options=_options(source_navigation=True),
            reference_path="references/profile-general-deep.md",
        ),
        "course-notes": ProfileSpec(
            profile_id="course-notes",
            required_sections=(
                "learning_objectives",
                "prerequisites",
                "motivation",
                "concepts",
                "mechanisms",
                "examples",
                "final_synthesis",
            ),
            formats=("md", "html", "tex", "pdf"),
            validator=_validate_course_notes,
            renderer_options=_options(teaching_footnotes=True),
            reference_path="references/profile-course-notes.md",
        ),
        "creator-article": ProfileSpec(
            profile_id="creator-article",
            required_sections=(
                "reader_promise",
                "core_point",
                "narrative",
                "video_evidence",
                "actionable_takeaway",
                "limitations_sources",
            ),
            formats=("md", "html", "tex", "pdf"),
            validator=_validate_creator_article,
            renderer_options=_options(byline=False, source_navigation=True),
            reference_path="references/profile-creator-article.md",
        ),
        "enterprise-knowledge": ProfileSpec(
            profile_id="enterprise-knowledge",
            required_sections=(
                "purpose_scope",
                "terminology",
                "process_practice",
                "roles_inputs_outputs",
                "risks",
                "limitations_sources",
            ),
            formats=("md", "html", "tex", "pdf"),
            validator=_validate_enterprise_knowledge,
            renderer_options=_options(decision_log=False, source_navigation=True),
            reference_path="references/profile-enterprise-knowledge.md",
        ),
        "research-brief": ProfileSpec(
            profile_id="research-brief",
            required_sections=(
                "video_evidence",
                "analysis_inference",
                "external_enrichment",
                "limitations_questions",
                "source_navigation",
            ),
            formats=("md", "html", "tex", "pdf"),
            validator=_validate_research_brief,
            renderer_options=_options(citation_notes=True),
            reference_path="references/profile-research-brief.md",
        ),
    }
)


# This is intentionally an exact, finite label table. It does not inspect or
# classify arbitrary prompt prose, so a route never turns a free-text request
# into a source fact.
INTENT_LABELS: Mapping[str, str] = MappingProxyType(
    {
        "课程笔记": "course-notes",
        "写成课程笔记": "course-notes",
        "公众号长文": "creator-article",
        "写成公众号长文": "creator-article",
        "企业知识库": "enterprise-knowledge",
        "写成企业知识库": "enterprise-knowledge",
        "研究简报": "research-brief",
        "写成研究简报": "research-brief",
    }
)


def get_profile(profile_id: str) -> ProfileSpec:
    try:
        return PROFILES[profile_id]
    except KeyError as exc:
        raise ValueError(f"unknown profile {profile_id!r}") from exc


def validate_profile_document(profile_id: str, document: object) -> list[str]:
    """Run the selected profile's renderer-neutral document quality gate."""
    from vka.quality import validate_document_quality

    return validate_document_quality(document, profile_id=profile_id)


def canonical_hash_tree(asset: AssetStore | Path | str) -> dict[str, str]:
    """Return a deterministic integrity snapshot of the canonical asset layers.

    Reader profiles are projections.  Their manifests and rendered outputs may
    change, but files in ``source/``, ``evidence/``, and ``knowledge/`` must
    remain byte-for-byte stable while a new view is authored.
    """
    store = asset if isinstance(asset, AssetStore) else AssetStore(Path(asset))
    if not store.root.is_dir() or _is_reparse_point(store.root):
        raise ValueError("asset directory does not exist or is unsafe")
    asset_root = store.root.resolve()
    hashes: dict[str, str] = {}
    for directory_name in CANONICAL_DIRECTORIES:
        directory = asset_root / directory_name
        _assert_safe_asset_path(asset_root, directory, f"canonical {directory_name} directory")
        if not directory.is_dir():
            raise ValueError(f"canonical {directory_name} directory does not exist")
        for path in sorted(directory.rglob("*")):
            _assert_safe_asset_path(asset_root, path, "canonical asset path")
            if path.is_file():
                hashes[path.relative_to(asset_root).as_posix()] = _sha256_file(path)
    return hashes


def reproject_profile_documents(
    asset: AssetStore | Path | str,
    documents: Mapping[str, Mapping[str, object]],
) -> dict[str, Path]:
    """Persist supplied authored profile documents without changing canonical data.

    This intentionally has no prose generation path: the caller must supply a
    complete, authored document for every requested profile.  The existing
    document writer validates its canonical references and profile quality
    before it writes a profile projection.
    """
    if not documents:
        raise ValueError("at least one authored profile document is required")
    store = asset if isinstance(asset, AssetStore) else AssetStore(Path(asset))
    for profile_id, document in documents.items():
        if not isinstance(profile_id, str) or not profile_id:
            raise ValueError("profile document mapping keys must be profile IDs")
        get_profile(profile_id)
        if not isinstance(document, Mapping):
            raise ValueError(f"authored document for {profile_id!r} must be an object")

    with _asset_write_lock(store):
        before = canonical_hash_tree(store)
        asset_root = _safe_asset_root(store)
        manifest_path = asset_root / "manifest.json"
        manifest_snapshot = _file_snapshot(manifest_path)
        view_snapshots = {
            profile_id: _snapshot_view_directory(asset_root, profile_id)
            for profile_id in documents
        }
        try:
            outputs = {
                profile_id: _write_profile_document_unlocked(
                    store, profile_id=profile_id, document=document
                )
                for profile_id, document in documents.items()
            }
            if canonical_hash_tree(store) != before:
                raise RuntimeError("profile projection changed canonical asset data")
            return outputs
        except BaseException as exc:
            _restore_view_directories(view_snapshots)
            _restore_snapshots({manifest_path: manifest_snapshot})
            if canonical_hash_tree(store) != before:
                raise RuntimeError("profile projection changed canonical asset data") from exc
            raise


def route_profile(
    explicit_profile: str | None,
    intent: str | None,
    *,
    requested_formats: tuple[str, ...] | list[str] | None = None,
) -> ProfileSelection:
    """Choose a profile without making an unrecorded inference from prompt text."""
    requested = {"explicit_profile": explicit_profile, "intent": intent}
    if explicit_profile is not None:
        spec = get_profile(explicit_profile)
        selection_source = "explicit_profile"
        reason = "selected registered explicit profile"
    elif intent is not None and intent in INTENT_LABELS:
        profile_id = INTENT_LABELS[intent]
        spec = get_profile(profile_id)
        selection_source = "intent_label"
        reason = f"selected from registered intent label {intent!r}"
    else:
        spec = get_profile("general-deep")
        selection_source = "default"
        reason = "no registered explicit profile or intent label was requested"
    resolved_requested_formats, formats = _resolve_formats(spec, requested_formats)
    return ProfileSelection(
        profile_id=spec.profile_id,
        selection_source=selection_source,
        reason=reason,
        requested=requested,
        requested_formats=resolved_requested_formats,
        formats=formats,
    )


def write_profile_selection(
    asset: AssetStore | Path | str,
    *,
    explicit_profile: str | None,
    intent: str | None,
    requested_formats: tuple[str, ...] | list[str] | None = None,
) -> ProfileSelection:
    """Persist a selection while serializing all asset manifest updates."""
    store = asset if isinstance(asset, AssetStore) else AssetStore(Path(asset))
    with _asset_write_lock(store):
        return _write_profile_selection_unlocked(
            store,
            explicit_profile=explicit_profile,
            intent=intent,
            requested_formats=requested_formats,
        )


def write_projection_plan(
    asset: AssetStore | Path | str,
    *,
    profile_id: str,
    plan: Mapping[str, object],
) -> Path:
    """Persist the P3 knowledge-to-document bridge without changing canonical data."""
    if profile_id not in P3_PROFILE_IDS:
        raise ValueError("projection plans are supported only for P3 profiles")
    store = asset if isinstance(asset, AssetStore) else AssetStore(Path(asset))
    with _asset_write_lock(store):
        asset_root = _safe_asset_root(store)
        before = canonical_hash_tree(store)
        spec = get_profile(profile_id)
        errors = validate_projection_plan(
            plan, profile_id=profile_id, required_sections=spec.required_sections
        )
        if errors:
            raise ValueError("projection plan failed validation: " + "; ".join(errors))
        _validate_projection_plan_canonical_refs(asset_root, profile_id, plan, before)
        path = _safe_projection_plan_path(asset_root, profile_id)
        serialized = _serialized_json(dict(plan))
        manifest = store._read_manifest()
        if not isinstance(manifest, dict) or manifest.get("schema_version") != SCHEMA_VERSION:
            raise ValueError(f"only {SCHEMA_VERSION} manifests can be modified")
        stages = manifest.get("stages")
        if not isinstance(stages, dict):
            raise ValueError("asset manifest stages must be an object")
        stage_name = f"views/{profile_id}/plan"
        if stage_name in stages:
            if path.is_file() and path.read_bytes() == serialized.encode("utf-8"):
                return path
            raise ValueError("completed projection plan cannot be modified")
        _write_profile_selection_unlocked(
            store, explicit_profile=profile_id, intent=None
        )
        _write_text_atomic(path, serialized)
        store.complete_stage(stage_name, [path], schema_version=SCHEMA_VERSION)
        if canonical_hash_tree(store) != before:
            raise RuntimeError("projection plan changed canonical asset data")
        return path


def _write_profile_selection_unlocked(
    asset: AssetStore | Path | str,
    *,
    explicit_profile: str | None,
    intent: str | None,
    requested_formats: tuple[str, ...] | list[str] | None = None,
) -> ProfileSelection:
    """Persist selection provenance in both profile and asset manifests."""
    store = asset if isinstance(asset, AssetStore) else AssetStore(Path(asset))
    if not store.root.is_dir() or _is_reparse_point(store.root):
        raise ValueError("asset directory does not exist or is unsafe")
    asset_root = store.root.resolve()
    _assert_safe_asset_path(asset_root, asset_root / "manifest.json", "manifest")
    manifest = store._read_manifest()
    if not isinstance(manifest, dict):
        raise ValueError("asset manifest must be an object")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"only {SCHEMA_VERSION} manifests can be modified")
    stages = manifest.get("stages")
    if not isinstance(stages, dict):
        raise ValueError("asset manifest stages must be an object")

    selection = route_profile(
        explicit_profile,
        intent,
        requested_formats=requested_formats,
    )
    spec = get_profile(selection.profile_id)
    selection_payload = selection.model_dump(mode="json")
    view_path = _safe_view_manifest_path(asset_root, spec.profile_id)

    completed_stage = stages.get(f"views/{spec.profile_id}")
    if completed_stage is not None:
        profile_selections = manifest.get("profile_selections")
        existing_selection = (
            profile_selections.get(spec.profile_id)
            if isinstance(profile_selections, Mapping)
            else None
        )
        if existing_selection != selection_payload:
            raise ValueError("completed profile view selection cannot be changed")
        return selection

    view_manifest = {
        "schema_version": "1.1",
        "profile_id": spec.profile_id,
        "profile_spec_version": spec.spec_version,
        "selection": selection_payload,
        "requested_formats": list(selection.requested_formats),
        "formats": list(selection.formats),
        "required_sections": list(spec.required_sections),
        "renderer_options": dict(spec.renderer_options),
        "reference_path": spec.reference_path,
    }
    _write_json_atomic(view_path, view_manifest)

    manifest["profile_selection"] = selection_payload
    manifest["requested_formats"] = list(selection.requested_formats)
    manifest["formats"] = list(selection.formats)
    profile_selections = manifest.setdefault("profile_selections", {})
    if not isinstance(profile_selections, dict):
        raise ValueError("asset manifest profile_selections must be an object")
    profile_selections[spec.profile_id] = selection_payload
    store._write_manifest(manifest)
    return selection


def write_profile_document(
    asset: AssetStore | Path | str,
    *,
    profile_id: str,
    document: Mapping[str, object],
) -> Path:
    """Write one supplied profile document under the asset-wide write lock."""
    store = asset if isinstance(asset, AssetStore) else AssetStore(Path(asset))
    with _asset_write_lock(store):
        return _write_profile_document_unlocked(
            store, profile_id=profile_id, document=document
        )


def _write_profile_document_unlocked(
    asset: AssetStore | Path | str,
    *,
    profile_id: str,
    document: Mapping[str, object],
) -> Path:
    """Write a validated, authored profile projection without changing canonical data.

    This is deliberately not a prose generator. Callers supply the authored
    document, whose provenance is checked against the asset's canonical
    knowledge and evidence records before the profile view is created.
    """
    store = asset if isinstance(asset, AssetStore) else AssetStore(Path(asset))
    if not store.root.is_dir() or _is_reparse_point(store.root):
        raise ValueError("asset directory does not exist or is unsafe")
    asset_root = store.root.resolve()
    _assert_safe_asset_path(asset_root, asset_root / "manifest.json", "manifest")
    spec = get_profile(profile_id)

    _validate_document_canonical_refs(asset_root, profile_id, document)
    _validate_projection_plan_binding(asset_root, profile_id, document)
    if profile_id == "course-notes":
        _validate_course_teaching_outline(asset_root, document)
    from vka.quality import validate_document_quality

    quality_errors = validate_document_quality(document, profile_id=profile_id)
    if quality_errors:
        raise ValueError("profile document failed quality gate: " + "; ".join(quality_errors))

    document_path = _safe_view_document_path(asset_root, profile_id)
    view_manifest_path = _safe_view_manifest_path(asset_root, profile_id)
    document_payload = dict(document)
    serialized_document = _serialized_json(document_payload)
    manifest = store._read_manifest()
    if not isinstance(manifest, dict) or manifest.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"only {SCHEMA_VERSION} manifests can be modified")
    stages = manifest.get("stages")
    if not isinstance(stages, dict):
        raise ValueError("asset manifest stages must be an object")
    stage_name = f"views/{profile_id}"
    if stage_name in stages:
        if document_path.is_file() and document_path.read_bytes() == serialized_document.encode("utf-8"):
            return document_path
        raise ValueError("completed profile view cannot be modified")

    # Every check above is read-only. Build all three changed artifacts before
    # writing any of them, then restore exact prior bytes if one commit fails.
    selection = _existing_or_default_profile_selection(manifest, asset_root, profile_id)
    selection_payload = selection.model_dump(mode="json")
    view_manifest = _profile_view_manifest(spec, selection)
    serialized_view_manifest = _serialized_json(view_manifest)
    updated_manifest = _manifest_with_profile_view(
        manifest,
        profile_id=profile_id,
        selection_payload=selection_payload,
        selection=selection,
        view_manifest_path=view_manifest_path,
        document_path=document_path,
        serialized_view_manifest=serialized_view_manifest,
        serialized_document=serialized_document,
    )
    snapshots = {
        view_manifest_path: _file_snapshot(view_manifest_path),
        document_path: _file_snapshot(document_path),
        asset_root / "manifest.json": _file_snapshot(asset_root / "manifest.json"),
    }
    profile_directory = document_path.parent
    profile_directory_existed = profile_directory.exists()
    try:
        _write_text_atomic(view_manifest_path, serialized_view_manifest)
        _write_text_atomic(document_path, serialized_document)
        store._write_manifest(updated_manifest)
    except BaseException:
        _restore_snapshots(snapshots)
        if not profile_directory_existed and profile_directory.exists():
            profile_directory.rmdir()
        raise
    return document_path


def _profile_view_manifest(spec: ProfileSpec, selection: ProfileSelection) -> dict[str, object]:
    return {
        "schema_version": "1.1",
        "profile_id": spec.profile_id,
        "profile_spec_version": spec.spec_version,
        "selection": selection.model_dump(mode="json"),
        "requested_formats": list(selection.requested_formats),
        "formats": list(selection.formats),
        "required_sections": list(spec.required_sections),
        "renderer_options": dict(spec.renderer_options),
        "reference_path": spec.reference_path,
    }


def _existing_or_default_profile_selection(
    manifest: Mapping[str, object], asset_root: Path, profile_id: str
) -> ProfileSelection:
    """Reuse an auditable route rather than silently replacing its intent/formats."""
    profile_selections = manifest.get("profile_selections")
    mapped_payload = (
        profile_selections.get(profile_id)
        if isinstance(profile_selections, Mapping)
        else None
    )
    latest_payload = manifest.get("profile_selection")
    asset_payload = mapped_payload
    if isinstance(latest_payload, Mapping) and latest_payload.get("profile_id") == profile_id:
        if asset_payload is not None and asset_payload != latest_payload:
            raise ValueError("profile selection manifests disagree")
        asset_payload = latest_payload

    view_path = _safe_view_manifest_path(asset_root, profile_id)
    view_payload: object | None = None
    parsed_view: Mapping[str, object] | None = None
    if view_path.exists():
        try:
            parsed_view = json.loads(view_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("profile selection view manifest is invalid") from exc
        if not isinstance(parsed_view, Mapping) or parsed_view.get("profile_id") != profile_id:
            raise ValueError("profile selection manifests disagree")
        view_payload = parsed_view.get("selection")

    if asset_payload is None and view_payload is None:
        return route_profile(profile_id, None)
    if not isinstance(asset_payload, Mapping) or not isinstance(view_payload, Mapping):
        raise ValueError("profile selection manifests disagree")
    try:
        asset_selection = ProfileSelection.model_validate(asset_payload)
        view_selection = ProfileSelection.model_validate(view_payload)
    except Exception as exc:
        raise ValueError("profile selection manifests are invalid") from exc
    if (
        asset_selection.profile_id != profile_id
        or view_selection.profile_id != profile_id
        or asset_selection.model_dump(mode="json") != view_selection.model_dump(mode="json")
    ):
        raise ValueError("profile selection manifests disagree")
    assert parsed_view is not None
    if (
        parsed_view.get("requested_formats") != list(view_selection.requested_formats)
        or parsed_view.get("formats") != list(view_selection.formats)
    ):
        raise ValueError("profile selection manifests disagree")
    if isinstance(latest_payload, Mapping) and latest_payload.get("profile_id") == profile_id:
        if (
            manifest.get("requested_formats") != list(asset_selection.requested_formats)
            or manifest.get("formats") != list(asset_selection.formats)
        ):
            raise ValueError("profile selection manifests disagree")
    return asset_selection


def _manifest_with_profile_view(
    manifest: Mapping[str, object],
    *,
    profile_id: str,
    selection_payload: dict[str, object],
    selection: ProfileSelection,
    view_manifest_path: Path,
    document_path: Path,
    serialized_view_manifest: str,
    serialized_document: str,
) -> dict[str, object]:
    updated = deepcopy(dict(manifest))
    updated["profile_selection"] = selection_payload
    updated["requested_formats"] = list(selection.requested_formats)
    updated["formats"] = list(selection.formats)
    profile_selections = updated.setdefault("profile_selections", {})
    if not isinstance(profile_selections, dict):
        raise ValueError("asset manifest profile_selections must be an object")
    profile_selections[profile_id] = selection_payload
    stages = updated.get("stages")
    if not isinstance(stages, dict):
        raise ValueError("asset manifest stages must be an object")
    stages[f"views/{profile_id}"] = {
        "completed_at": datetime.now(UTC).isoformat(),
        "schema_version": SCHEMA_VERSION,
        "outputs": [
            {
                "path": view_manifest_path.relative_to(view_manifest_path.parents[2]).as_posix(),
                "sha256": _sha256_text(serialized_view_manifest),
            },
            {
                "path": document_path.relative_to(document_path.parents[2]).as_posix(),
                "sha256": _sha256_text(serialized_document),
            },
        ],
    }
    return updated


def _safe_view_manifest_path(asset_root: Path, profile_id: str) -> Path:
    views = asset_root / "views"
    profile_directory = views / profile_id
    view_manifest = profile_directory / "view-manifest.json"
    for path, label in (
        (views, "views directory"),
        (profile_directory, "profile directory"),
        (view_manifest, "view manifest"),
    ):
        _assert_safe_asset_path(asset_root, path, label)
    return view_manifest


def _safe_view_document_path(asset_root: Path, profile_id: str) -> Path:
    views = asset_root / "views"
    profile_directory = views / profile_id
    document = profile_directory / "document.json"
    for path, label in (
        (views, "views directory"),
        (profile_directory, "profile directory"),
        (document, "profile document"),
    ):
        _assert_safe_asset_path(asset_root, path, label)
    return document


def _safe_projection_plan_path(asset_root: Path, profile_id: str) -> Path:
    views = asset_root / "views"
    profile_directory = views / profile_id
    plan = profile_directory / "projection-plan.json"
    for path, label in (
        (views, "views directory"),
        (profile_directory, "profile directory"),
        (plan, "projection plan"),
    ):
        _assert_safe_asset_path(asset_root, path, label)
    return plan


def _assert_safe_asset_path(asset_root: Path, path: Path, label: str) -> None:
    if _is_reparse_point(path):
        raise ValueError(f"{label} must not be a symlink or reparse point")
    resolved_path = path.resolve()
    try:
        resolved_path.relative_to(asset_root)
    except ValueError as exc:
        raise ValueError(f"{label} must stay within the asset root") from exc


def _safe_asset_root(store: AssetStore) -> Path:
    if not store.root.is_dir() or _is_reparse_point(store.root):
        raise ValueError("asset directory does not exist or is unsafe")
    return store.root.resolve()


def _is_reparse_point(path: Path) -> bool:
    """Return true for symlinks, junctions, and other Windows reparse points."""
    if path.is_symlink():
        return True
    try:
        attributes = os.lstat(path).st_file_attributes
    except (AttributeError, FileNotFoundError, OSError):
        return False
    return bool(attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)


@contextmanager
def _asset_write_lock(store: AssetStore):
    """Serialize manifest-changing profile writes across threads and processes."""
    asset_root = _safe_asset_root(store)
    lock_path = asset_root / ".profile-write.lock"
    _assert_safe_asset_path(asset_root, lock_path, "profile write lock")
    deadline = time.monotonic() + 10.0
    descriptor: int | None = None
    while descriptor is None:
        try:
            descriptor = os.open(lock_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            if _is_reparse_point(lock_path):
                raise ValueError("profile write lock must not be a symlink or reparse point")
            if time.monotonic() >= deadline:
                raise TimeoutError("timed out waiting for the asset profile write lock")
            time.sleep(0.01)
    try:
        with os.fdopen(descriptor, "w", encoding="ascii", closefd=False) as file:
            file.write(str(os.getpid()))
            file.flush()
            os.fsync(file.fileno())
        yield
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if lock_path.exists():
            if _is_reparse_point(lock_path) or not lock_path.is_file():
                raise ValueError("profile write lock is unsafe during release")
            lock_path.unlink()


@dataclass(frozen=True)
class _ViewDirectorySnapshot:
    directory: Path
    existed: bool
    files: Mapping[Path, bytes]


def _snapshot_view_directory(asset_root: Path, profile_id: str) -> _ViewDirectorySnapshot:
    directory = asset_root / "views" / profile_id
    _assert_safe_asset_path(asset_root, asset_root / "views", "views directory")
    _assert_safe_asset_path(asset_root, directory, "profile directory")
    if not directory.exists():
        return _ViewDirectorySnapshot(directory, False, {})
    if not directory.is_dir():
        raise ValueError("profile directory must be a directory")
    files: dict[Path, bytes] = {}
    for path in directory.rglob("*"):
        _assert_safe_asset_path(asset_root, path, "profile view path")
        if path.is_file():
            files[path.relative_to(directory)] = path.read_bytes()
    return _ViewDirectorySnapshot(directory, True, files)


def _restore_view_directories(snapshots: Mapping[str, _ViewDirectorySnapshot]) -> None:
    for snapshot in snapshots.values():
        directory = snapshot.directory
        if directory.exists():
            _remove_safe_view_directory(directory)
        if not snapshot.existed:
            continue
        directory.mkdir(parents=True, exist_ok=True)
        for relative_path, contents in snapshot.files.items():
            _replace_bytes_atomically(directory / relative_path, contents)


def _remove_safe_view_directory(directory: Path) -> None:
    if _is_reparse_point(directory) or not directory.is_dir():
        raise ValueError("profile view rollback destination is unsafe")
    paths = sorted(directory.rglob("*"), key=lambda path: len(path.parts), reverse=True)
    for path in paths:
        if _is_reparse_point(path):
            raise ValueError("profile view rollback destination is unsafe")
        if path.is_file():
            path.unlink()
        elif path.is_dir():
            path.rmdir()
        else:
            raise ValueError("profile view rollback destination is unsafe")
    directory.rmdir()


def _validate_course_teaching_outline(
    asset_root: Path, document: Mapping[str, object]
) -> None:
    reference = document.get("teaching_outline_ref")
    if not isinstance(reference, str) or not reference.strip():
        raise ValueError("course-notes teaching outline reference is required")
    normalized = reference.replace("\\", "/")
    relative = Path(normalized)
    windows_path = PureWindowsPath(reference)
    if (
        relative.is_absolute()
        or windows_path.is_absolute()
        or windows_path.drive
        or ".." in relative.parts
    ):
        raise ValueError("course-notes teaching outline must stay within the asset root")
    outline_path = asset_root / relative
    _assert_safe_asset_path(asset_root, outline_path, "course-notes teaching outline")
    if not outline_path.is_file():
        raise ValueError("course-notes teaching outline is missing")
    try:
        outline = json.loads(outline_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("course-notes teaching outline is invalid") from exc
    from vka.teaching_outline import validate_teaching_outline

    errors = validate_teaching_outline(outline)
    if errors:
        raise ValueError("course-notes teaching outline failed validation: " + "; ".join(errors))


def _validate_projection_plan_canonical_refs(
    asset_root: Path,
    profile_id: str,
    plan: Mapping[str, object],
    canonical_hashes: Mapping[str, str],
) -> None:
    """Bind a plan to this exact canonical asset and checked visual evidence."""
    if plan.get("canonical_hash_tree") != dict(canonical_hashes):
        raise ValueError("projection plan canonical_hash_tree does not match the asset")
    if plan.get("profile_spec_version") != get_profile(profile_id).spec_version:
        raise ValueError("projection plan profile_spec_version does not match the registered profile")
    knowledge_records = _jsonl_records(
        asset_root / "knowledge" / "units.jsonl", "unit_id", "knowledge"
    )
    evidence_records = _canonical_evidence_records(asset_root)
    sections = plan.get("sections")
    assert isinstance(sections, list)
    section_ids = {
        section["section_id"]
        for section in sections
        if isinstance(section, Mapping) and isinstance(section.get("section_id"), str)
    }
    for section in sections:
        if not isinstance(section, Mapping):
            continue
        for key, records, label in (
            ("knowledge_refs", knowledge_records, "knowledge"),
            ("evidence_refs", evidence_records, "evidence"),
        ):
            refs = section.get(key)
            if isinstance(refs, list):
                unknown = sorted(ref for ref in refs if isinstance(ref, str) and ref not in records)
                if unknown:
                    raise ValueError(f"projection plan references unknown canonical {label} IDs: " + ", ".join(unknown))
    figures = plan.get("selected_figures")
    if not isinstance(figures, list):
        return
    for figure in figures:
        if not isinstance(figure, Mapping):
            continue
        section_id = figure.get("section_id")
        evidence_id = figure.get("evidence_id")
        artifact_ref = figure.get("artifact_ref")
        if not isinstance(section_id, str) or section_id not in section_ids:
            raise ValueError("projection plan figure references an unknown plan section")
        if not isinstance(evidence_id, str) or evidence_id not in evidence_records:
            raise ValueError("projection plan figure references unknown canonical evidence")
        record = evidence_records[evidence_id]
        quality = record.get("quality")
        if (
            record.get("origin") != "video"
            or record.get("modality") != "frame"
            or not isinstance(quality, Mapping)
            or quality.get("review") != "directly_inspected"
            or record.get("artifact_ref") != artifact_ref
        ):
            raise ValueError("projection plan figures must use directly inspected frame evidence and exact artifact_ref")


def _validate_projection_plan_binding(
    asset_root: Path, profile_id: str, document: Mapping[str, object]
) -> None:
    """Validate an opt-in plan binding while keeping historical P3 views readable."""
    reference = document.get("projection_plan_ref")
    if reference is None:
        if profile_id in P3_PROFILE_IDS and _safe_projection_plan_path(asset_root, profile_id).is_file():
            raise ValueError("P3 document must bind the persisted projection plan")
        return
    if profile_id not in P3_PROFILE_IDS:
        raise ValueError("projection_plan_ref is supported only for P3 documents")
    if not isinstance(reference, str) or reference != f"views/{profile_id}/projection-plan.json":
        raise ValueError("document projection_plan_ref must point to its profile projection plan")
    path = _safe_projection_plan_path(asset_root, profile_id)
    if not path.is_file():
        raise ValueError("document projection plan is missing")
    try:
        plan = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("document projection plan is invalid") from exc
    spec = get_profile(profile_id)
    errors = validate_projection_plan(plan, profile_id=profile_id, required_sections=spec.required_sections)
    if errors:
        raise ValueError("document projection plan failed validation: " + "; ".join(errors))
    _validate_projection_plan_canonical_refs(
        asset_root, profile_id, plan, canonical_hash_tree(asset_root)
    )
    declared_id = document.get("projection_plan_id")
    declared_sha = document.get("projection_plan_sha256")
    if declared_id != plan.get("plan_id"):
        raise ValueError("document projection_plan_id does not match its plan")
    if declared_sha != _sha256_file(path):
        raise ValueError("document projection_plan_sha256 does not match its plan")
    if plan.get("status") != "ready":
        raise ValueError("only a ready projection plan can produce a profile document")


def _canonical_evidence_records(asset_root: Path) -> dict[str, Mapping[str, object]]:
    evidence_records: dict[str, Mapping[str, object]] = {}
    evidence_directory = asset_root / "evidence"
    if not evidence_directory.is_dir() or _is_reparse_point(evidence_directory):
        raise ValueError("canonical evidence directory does not exist or is unsafe")
    for path in evidence_directory.rglob("*.jsonl"):
        _assert_safe_asset_path(asset_root, path, "canonical evidence record")
        for evidence_id, record in _jsonl_records(path, "evidence_id", "evidence").items():
            existing = evidence_records.get(evidence_id)
            if existing is not None and existing != record:
                raise ValueError(f"canonical evidence ID {evidence_id} is ambiguous")
            evidence_records[evidence_id] = record
    return evidence_records


def _validate_document_canonical_refs(
    asset_root: Path, profile_id: str, document: Mapping[str, object]
) -> None:
    knowledge_records = _jsonl_records(
        asset_root / "knowledge" / "units.jsonl", "unit_id", "knowledge"
    )
    knowledge_ids = set(knowledge_records)
    evidence_records: dict[str, Mapping[str, object]] = {}
    evidence_directory = asset_root / "evidence"
    if not evidence_directory.is_dir() or _is_reparse_point(evidence_directory):
        raise ValueError("canonical evidence directory does not exist or is unsafe")
    for path in evidence_directory.rglob("*.jsonl"):
        _assert_safe_asset_path(asset_root, path, "canonical evidence record")
        for evidence_id, record in _jsonl_records(path, "evidence_id", "evidence").items():
            existing = evidence_records.get(evidence_id)
            if existing is not None and existing != record:
                raise ValueError(f"canonical evidence ID {evidence_id} is ambiguous")
            evidence_records[evidence_id] = record
    evidence_ids = set(evidence_records)
    document_origins = document.get("evidence_origins")

    referenced_knowledge: set[str] = set()
    referenced_evidence: set[str] = set()
    for block in _profile_document_blocks(document):
        knowledge_refs = block.get("knowledge_refs")
        evidence_refs = block.get("evidence_refs")
        if isinstance(knowledge_refs, list):
            referenced_knowledge.update(ref for ref in knowledge_refs if isinstance(ref, str))
        if isinstance(evidence_refs, list):
            referenced_evidence.update(ref for ref in evidence_refs if isinstance(ref, str))

    missing_knowledge = sorted(referenced_knowledge - knowledge_ids)
    if missing_knowledge:
        raise ValueError("unknown canonical knowledge IDs: " + ", ".join(missing_knowledge))
    missing_evidence = sorted(referenced_evidence - evidence_ids)
    if missing_evidence:
        raise ValueError("unknown canonical evidence IDs: " + ", ".join(missing_evidence))
    for block in _profile_document_blocks(document):
        evidence_refs = block.get("evidence_refs")
        if isinstance(evidence_refs, list) and any(
            isinstance(ref, str) and evidence_records[ref].get("origin") == "video"
            for ref in evidence_refs
        ) and not _has_valid_source_spans(block.get("source_spans")):
            raise ValueError("canonical video evidence requires document source_spans")
    if profile_id == "creator-article":
        for block in _profile_document_blocks(document):
            if block.get("kind") != "quote":
                continue
            refs = block.get("knowledge_refs")
            if not isinstance(refs, list) or any(
                not isinstance(ref, str)
                or knowledge_records[ref].get("epistemic_status") != "video_explicit"
                for ref in refs
            ):
                raise ValueError(
                    "creator-article quotes require video_explicit canonical knowledge"
                )
            evidence_refs = block.get("evidence_refs")
            if not isinstance(evidence_refs, list) or any(
                not isinstance(ref, str) or evidence_records[ref].get("origin") != "video"
                for ref in evidence_refs
            ):
                raise ValueError("creator-article quotes require canonical video evidence")
    if profile_id == "enterprise-knowledge":
        for block in _profile_document_blocks(document):
            evidence_refs = block.get("evidence_refs")
            if not isinstance(evidence_refs, list) or any(
                not isinstance(ref, str) or evidence_records[ref].get("origin") != "video"
                for ref in evidence_refs
            ):
                raise ValueError(
                    "enterprise-knowledge must ground operational content in canonical video evidence"
                )
    if profile_id == "research-brief":
        _validate_research_brief_canonical_refs(document, knowledge_records, evidence_records)
    _validate_profile_visual_coverage(profile_id, document, evidence_records)
    if isinstance(document_origins, Mapping):
        for evidence_id, declared_origin in document_origins.items():
            if not isinstance(evidence_id, str) or evidence_id not in evidence_records:
                raise ValueError(
                    f"document evidence_origins references unknown canonical evidence ID: {evidence_id}"
                )
            if declared_origin != evidence_records[evidence_id].get("origin"):
                raise ValueError(
                    f"document evidence_origins does not match canonical origin for {evidence_id}"
                )


def _validate_profile_visual_coverage(
    profile_id: str,
    document: Mapping[str, object],
    evidence_records: Mapping[str, Mapping[str, object]],
) -> None:
    """Require a real figure when the asset contains a reviewed visual record.

    P3 views must not turn a useful frame into a sentence that merely says a
    frame exists.  The requirement is deliberately asset-aware: interviews or
    other visually sparse videos without an inspected frame remain free to
    produce a text-first view, while a source with a readable, reviewed frame
    must project at least one of those frames as an evidence figure.
    """
    if profile_id not in {"creator-article", "enterprise-knowledge", "research-brief"}:
        return
    candidates = {
        evidence_id: record
        for evidence_id, record in evidence_records.items()
        if record.get("modality") == "frame"
        and isinstance(record.get("artifact_ref"), str)
        and record["artifact_ref"].strip()
        and isinstance(record.get("quality"), Mapping)
        and record["quality"].get("review") == "directly_inspected"
    }
    if not candidates:
        return

    blocks = _profile_document_blocks(document)
    has_selected_frame = False
    for block in blocks:
        if block.get("kind") != "image":
            continue
        evidence_refs = block.get("evidence_refs")
        path = _profile_image_path(block)
        if not isinstance(evidence_refs, list) or not isinstance(path, str):
            continue
        if any(
            isinstance(evidence_id, str)
            and evidence_id in candidates
            and candidates[evidence_id].get("artifact_ref") == path
            for evidence_id in evidence_refs
        ):
            has_selected_frame = True
            break

    errors: list[str] = []
    if not has_selected_frame:
        errors.append(
            f"{profile_id} must include an image backed by a directly inspected frame when the asset has usable visual evidence"
        )

    prose = sum(
        len(_profile_block_text(block)) for block in blocks if block.get("kind") != "image"
    )
    minimum_prose = {
        "creator-article": 550,
        "enterprise-knowledge": 550,
        "research-brief": 420,
    }[profile_id]
    if prose < minimum_prose:
        errors.append(
            f"{profile_id} is too thin for an asset with usable visual evidence; expand the profile-specific explanation before projection"
        )

    sections = document.get("sections")
    section_blocks = {
        section.get("kind"): section.get("blocks")
        for section in sections
        if isinstance(section, Mapping) and isinstance(section.get("blocks"), list)
    } if isinstance(sections, list) else {}
    if profile_id == "creator-article" and not any(
        isinstance(block, Mapping) and block.get("kind") in {"bullet_list", "numbered_list"}
        for block in section_blocks.get("actionable_takeaway", [])
    ):
        errors.append("creator-article needs a source-backed actionable checklist")
    if profile_id == "enterprise-knowledge" and not any(
        isinstance(block, Mapping) and block.get("kind") == "table"
        for section_kind in ("process_practice", "roles_inputs_outputs", "risks")
        for block in section_blocks.get(section_kind, [])
    ):
        errors.append("enterprise-knowledge needs a source-backed process, boundary, or risk table")
    if profile_id == "research-brief" and not any(
        isinstance(block, Mapping) and block.get("kind") == "table"
        for section_kind in ("video_evidence", "source_navigation")
        for block in section_blocks.get(section_kind, [])
    ):
        errors.append("research-brief needs an evidence or source-navigation table")
    if errors:
        raise ValueError("; ".join(errors))


def _profile_image_path(block: Mapping[str, object]) -> str | None:
    for key in ("image_path", "path"):
        value = block.get(key)
        if isinstance(value, str) and value.strip():
            return value.replace("\\", "/")
    data = block.get("data")
    if isinstance(data, Mapping):
        for key in ("image_path", "path"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.replace("\\", "/")
    return None


def _profile_block_text(block: Mapping[str, object]) -> str:
    values: list[str] = []
    for key in ("title", "text", "caption", "latex", "code"):
        value = block.get(key)
        if isinstance(value, str):
            values.append(value)
    items = block.get("items")
    if isinstance(items, list):
        values.extend(item for item in items if isinstance(item, str))
    data = block.get("data")
    if isinstance(data, Mapping):
        for key in ("headers", "rows"):
            value = data.get(key)
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, str):
                        values.append(item)
                    elif isinstance(item, list):
                        values.extend(cell for cell in item if isinstance(cell, str))
    return "\n".join(values)


def _validate_research_brief_canonical_refs(
    document: Mapping[str, object],
    knowledge_records: Mapping[str, Mapping[str, object]],
    evidence_records: Mapping[str, Mapping[str, object]],
) -> None:
    """Verify that a research view cannot relabel canonical source records.

    This is intentionally an asset-boundary check. A document can display a
    category, but only canonical knowledge/evidence decides whether it is a
    video claim, an agent inference, or user-provided external material.
    """
    sections = document.get("sections")
    if not isinstance(sections, list):
        return
    expected_statuses = {
        "video_evidence": {"video_explicit"},
        "analysis_inference": {"agent_inference"},
        "external_enrichment": {"external_enrichment", "not_used"},
        "limitations_questions": {"insufficient_evidence"},
    }
    for section in sections:
        if not isinstance(section, Mapping):
            continue
        section_kind = section.get("kind")
        if not isinstance(section_kind, str):
            continue
        section_title = section.get("title")
        section_title_has_video_attribution = (
            section_kind == "analysis_inference"
            and isinstance(section_title, str)
            and _has_analysis_video_attribution(section_title, "")
        )
        blocks = section.get("blocks")
        if not isinstance(blocks, list):
            continue
        for block in blocks:
            if not isinstance(block, Mapping):
                continue
            data = block.get("data")
            data = data if isinstance(data, Mapping) else {}
            status = data.get("claim_status")
            visible_label = data.get("visible_label")
            knowledge_refs = block.get("knowledge_refs")
            evidence_refs = block.get("evidence_refs")
            refs = [ref for ref in knowledge_refs if isinstance(ref, str)] if isinstance(knowledge_refs, list) else []
            evidence = [ref for ref in evidence_refs if isinstance(ref, str)] if isinstance(evidence_refs, list) else []

            external_evidence = [
                evidence_id
                for evidence_id in evidence
                if evidence_records[evidence_id].get("origin") == "external"
            ]

            for knowledge_id in refs:
                canonical_status = knowledge_records[knowledge_id].get("epistemic_status")
                if (
                    section_kind == "analysis_inference"
                    and (
                        section_title_has_video_attribution
                        or _has_analysis_video_attribution(
                            visible_label, _research_block_text(block)
                        )
                    )
                    and canonical_status != "video_explicit"
                ):
                    raise ValueError(
                        f"research-brief claim {knowledge_id} labels {str(canonical_status).replace('_', ' ')} as video evidence"
                    )
                if (
                    section_kind in expected_statuses
                    and status != "not_used"
                    and canonical_status not in expected_statuses[section_kind]
                ):
                    raise ValueError(
                        f"research-brief claim {knowledge_id} has canonical status {canonical_status!r} "
                        f"in {section_kind}"
                    )

            _validate_research_structured_refs_canonical(
                block,
                data,
                knowledge_records,
                evidence_records,
                source_navigation=section_kind == "source_navigation",
            )

            if section_kind not in {"external_enrichment", "source_navigation"} and external_evidence:
                raise ValueError(
                    "research-brief external facts must not be mixed into video, analysis, or limitation sections"
                )

            if section_kind == "video_evidence":
                if any(evidence_records[evidence_id].get("origin") != "video" for evidence_id in evidence):
                    raise ValueError("research-brief video evidence must use canonical video evidence")
            elif section_kind == "analysis_inference":
                if any(evidence_records[evidence_id].get("origin") == "external" for evidence_id in evidence):
                    raise ValueError("research-brief analysis must not present external facts as video inference")
            elif section_kind == "external_enrichment":
                if status == "not_used":
                    if any(evidence_records[evidence_id].get("origin") == "external" for evidence_id in evidence):
                        raise ValueError("research-brief unused external section cannot cite external evidence")
                    continue
                if not evidence:
                    raise ValueError("research-brief external enrichment requires existing user-supplied evidence")
                for evidence_id in evidence:
                    record = evidence_records[evidence_id]
                    if record.get("origin") != "external":
                        raise ValueError("research-brief external enrichment must use canonical external evidence")
                    _validate_user_supplied_external_evidence(evidence_id, record)
            elif section_kind == "source_navigation":
                for evidence_id in external_evidence:
                    _validate_user_supplied_external_evidence(
                        evidence_id, evidence_records[evidence_id]
                    )


def _has_analysis_video_attribution(label: object, text: str) -> bool:
    return any(
        _analysis_video_attribution_in(value)
        for value in (label, text)
        if isinstance(value, str)
    )


def _analysis_video_attribution_in(value: str) -> bool:
    limitation_patterns = (
        r"\s*(?:this\s+)?analysis\s+goes\s+beyond\s+(?:the\s+)?video\s*[.!?]*\s*",
        r"\s*(?:本)?分析(?:超出|超越|超过)视频(?:范围|内容)?\s*[。！？!?]*\s*",
        r"\s*(?:本)?分析(?:在)?视频(?:范围|内容)?之外\s*[。！？!?]*\s*",
    )
    if any(re.fullmatch(pattern, value, flags=re.IGNORECASE) for pattern in limitation_patterns):
        return False
    source_tokens = (
        r"视频|影片|影像|录像|录屏|录制(?:内容|画面)?|录音|片段|讲座|演讲|教程|讲者|演讲者|讲解者",
        r"\b(?:videos?|recordings?|footage|clip(?:s)?|screen\s+recordings?|lectures?|talks?|webinars?|tutorials?|presenter|speaker)\b",
        r"\baccording\s+to\b",
    )
    return any(re.search(pattern, value, flags=re.IGNORECASE) for pattern in source_tokens)


def _is_video_visible_claim(label: object, text: str) -> bool:
    return any(
        re.search(
            r"(?:(?:在|从|根据)视频(?:中|里)?|(?:讲者|演讲者|讲解者)|"
            r"视频(?:中|里|没有|未|不|是|为|可|能|会|应|将|把|对)|"
            r"视频(?:中(?:的)?|里)?(?:讲者|演讲者|讲解者)?(?:明确(?:指出|表明)|表明|显示|指出|讲解|讲了|讲述|介绍|讨论|展示|演示|说明|呈现|说|认为|提到)|"
            r"|(?:录像|录屏|录制(?:内容|画面)?|录音)(?:中|里|没有|未|不|是|为|可|能|会|应|将|把|对|明确(?:指出|表明)|表明|显示|指出|讲解|讲了|讲述|介绍|讨论|展示|演示|说明|呈现|说|认为|提到)|"
            r"(?:根据|从)视频(?:中|里)?(?:可以)?(?:可知|可见|看出|得知|来看)|"
            r"(?:the\s+)?video\s+(?:explicitly\s+)?(?:states?|indicates?|shows?|says?|claims?|explains?|introduces?|discusses?|demonstrates?|presents?)|"
            r"(?:the\s+)?(?:recording|footage|screen\s+recording)\s+(?:explicitly\s+)?(?:states?|indicates?|shows?|says?|claims?|explains?|introduces?|discusses?|demonstrates?|presents?)|"
            r"(?:the\s+)?(?:presenter|speaker)\s+in\s+(?:the\s+)?video\s+(?:argues?|states?|says?|claims?)|"
            r"\b(?:presenter|speaker)\b|\bin\s+(?:the\s+)?video\b|\baccording\s+to\b|"
            r"according\s+to\s+(?:the\s+)?video|"
            r"from\s+(?:the\s+)?video(?:\s+(?:we\s+)?(?:can\s+)?(?:see|infer|learn))?)",
            value,
            flags=re.IGNORECASE,
        )
        for value in (label, text)
        if isinstance(value, str)
    )


def _research_block_text(block: Mapping[str, object]) -> str:
    text = block.get("text")
    if isinstance(text, str):
        return text
    data = block.get("data")
    if isinstance(data, Mapping):
        for field in ("text", "caption"):
            value = data.get(field)
            if isinstance(value, str):
                return value
    return ""


def _validate_research_structured_refs_canonical(
    block: Mapping[str, object],
    data: Mapping[str, object],
    knowledge_records: Mapping[str, Mapping[str, object]],
    evidence_records: Mapping[str, Mapping[str, object]],
    *,
    source_navigation: bool,
) -> None:
    """Check each declared knowledge/evidence pair against canonical records."""
    structured_refs = data.get("structured_refs")
    knowledge_refs = block.get("knowledge_refs")
    evidence_refs = block.get("evidence_refs")
    category = data.get("source_category")
    if (
        not isinstance(structured_refs, list)
        or not structured_refs
        or not isinstance(knowledge_refs, list)
        or not isinstance(evidence_refs, list)
        or not isinstance(category, str)
    ):
        raise ValueError("research-brief claims must preserve matching structured refs")
    seen_knowledge: set[str] = set()
    seen_evidence: set[str] = set()
    for item in structured_refs:
        if not isinstance(item, Mapping):
            raise ValueError("research-brief claims must preserve matching structured refs")
        knowledge_id = item.get("knowledge_id")
        evidence_id = item.get("evidence_id")
        item_category = item.get("source_category")
        if (
            not isinstance(knowledge_id, str)
            or knowledge_id not in knowledge_refs
            or knowledge_id not in knowledge_records
            or not isinstance(evidence_id, str)
            or evidence_id not in evidence_refs
            or evidence_id not in evidence_records
            or not isinstance(item_category, str)
            or (not source_navigation and item_category != category)
        ):
            raise ValueError("research-brief claims must preserve matching structured refs")
        canonical_status = knowledge_records[knowledge_id].get("epistemic_status")
        canonical_evidence_refs = knowledge_records[knowledge_id].get("evidence_refs")
        if (
            isinstance(canonical_evidence_refs, list)
            and canonical_evidence_refs
            and evidence_id not in canonical_evidence_refs
        ):
            raise ValueError(
                f"research-brief structured ref {knowledge_id}/{evidence_id} is not canonical"
            )
        if item_category != "not_used" and item_category != canonical_status:
            raise ValueError(
                f"research-brief structured ref {knowledge_id} has mismatched source_category"
            )
        _validate_research_structured_ref_origin(
            knowledge_id, item_category, evidence_records[evidence_id]
        )
        seen_knowledge.add(knowledge_id)
        seen_evidence.add(evidence_id)
    if set(knowledge_refs) != seen_knowledge or set(evidence_refs) != seen_evidence:
        raise ValueError("research-brief claims must preserve matching structured refs")


def _validate_research_structured_ref_origin(
    knowledge_id: str, category: str, evidence: Mapping[str, object]
) -> None:
    origin = evidence.get("origin")
    if category == "video_explicit" and origin != "video":
        raise ValueError(f"research-brief structured ref {knowledge_id} must use video evidence")
    if category == "agent_inference" and origin == "external":
        raise ValueError(
            f"research-brief structured ref {knowledge_id} must not use external evidence"
        )
    if category == "external_enrichment":
        if origin != "external":
            raise ValueError(f"research-brief structured ref {knowledge_id} must use external evidence")
        _validate_user_supplied_external_evidence(
            str(evidence.get("evidence_id", "external")), evidence
        )


def _is_video_visible_label(value: object) -> bool:
    return isinstance(value, str) and ("视频" in value or "video" in value.casefold())


def _validate_user_supplied_external_evidence(
    evidence_id: str, record: Mapping[str, object]
) -> None:
    metadata = record.get("external")
    source = dict(record)
    if isinstance(metadata, Mapping):
        source.update(metadata)
    provenance = source.get("provenance")
    if provenance not in {"user_supplied", "user_provided"}:
        raise ValueError(
            f"research-brief external evidence {evidence_id} must be user-supplied"
        )
    acquisition = _normalize_acquisition(source.get("acquisition"))
    allowed_acquisitions = {
        "user_supplied",
        "user_provided",
        "user_upload",
        "user_import",
        "manual_upload",
        "manual_import",
        "manual_entry",
        "manual_review",
        "manual_submission",
    }
    if acquisition not in allowed_acquisitions:
        raise ValueError(
            "research-brief external evidence must use an explicit user-supplied acquisition"
        )
    has_authority = any(
        isinstance(source.get(field), str) and source[field].strip()
        for field in ("author", "institution", "author_or_institution")
    )
    required_text = ("url", "publication_date", "accessed_at", "supporting_snippet")
    if not has_authority or any(
        not isinstance(source.get(field), str) or not source[field].strip()
        for field in required_text
    ):
        raise ValueError(
            f"research-brief external evidence {evidence_id} lacks required user-material metadata"
        )


def _normalize_acquisition(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")


def _profile_document_blocks(document: Mapping[str, object]) -> list[Mapping[str, object]]:
    sections = document.get("sections")
    if isinstance(sections, list):
        blocks: list[Mapping[str, object]] = []
        for section in sections:
            if not isinstance(section, Mapping):
                continue
            section_blocks = section.get("blocks")
            if isinstance(section_blocks, list):
                blocks.extend(block for block in section_blocks if isinstance(block, Mapping))
        return blocks
    raw_blocks = document.get("blocks")
    return [block for block in raw_blocks if isinstance(block, Mapping)] if isinstance(raw_blocks, list) else []


def _has_valid_source_spans(value: object) -> bool:
    return isinstance(value, list) and bool(value) and all(
        isinstance(span, Mapping)
        and isinstance(span.get("start_ms"), int)
        and not isinstance(span.get("start_ms"), bool)
        and isinstance(span.get("end_ms"), int)
        and not isinstance(span.get("end_ms"), bool)
        and span["start_ms"] >= 0
        and span["end_ms"] > span["start_ms"]
        for span in value
    )


def _jsonl_records(path: Path, field: str, label: str) -> dict[str, Mapping[str, object]]:
    if not path.is_file() or _is_reparse_point(path):
        raise ValueError(f"canonical {label} records are missing")
    records: dict[str, Mapping[str, object]] = {}
    try:
        with path.open(encoding="utf-8") as file:
            for line_number, line in enumerate(file, start=1):
                if not line.strip():
                    continue
                record = json.loads(line)
                identifier = record.get(field) if isinstance(record, Mapping) else None
                if not isinstance(identifier, str) or not identifier.strip():
                    raise ValueError(
                        f"canonical {label} record {line_number} must contain {field}"
                    )
                if not isinstance(record, Mapping):
                    raise ValueError(f"canonical {label} record {line_number} must be an object")
                records[identifier] = record
    except json.JSONDecodeError as exc:
        raise ValueError(f"canonical {label} records are not valid JSONL") from exc
    return records


def _serialized_json(value: Mapping[str, object]) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_snapshot(path: Path) -> bytes | None:
    if _is_reparse_point(path):
        raise ValueError("profile view destination must not be a symlink or reparse point")
    return path.read_bytes() if path.exists() else None


def _restore_snapshots(snapshots: Mapping[Path, bytes | None]) -> None:
    for path, contents in snapshots.items():
        if contents is None:
            if path.exists():
                if _is_reparse_point(path) or not path.is_file():
                    raise ValueError("profile view rollback destination is unsafe")
                path.unlink()
            continue
        _replace_bytes_atomically(path, contents)


def _replace_bytes_atomically(path: Path, contents: bytes) -> None:
    if _is_reparse_point(path):
        raise ValueError("profile view rollback destination is unsafe")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        for _ in range(16):
            candidate = path.parent / f".{path.name}-{uuid.uuid4().hex}.rollback"
            try:
                descriptor = os.open(candidate, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                continue
            temporary = candidate
            with os.fdopen(descriptor, "wb") as file:
                file.write(contents)
                file.flush()
                os.fsync(file.fileno())
            if _is_reparse_point(path) or _is_reparse_point(temporary):
                raise ValueError("profile view rollback destination is unsafe")
            os.replace(temporary, path)
            temporary = None
            return
        raise OSError("could not allocate a profile view rollback file")
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def _write_json_atomic(path: Path, value: Mapping[str, object]) -> None:
    _write_text_atomic(path, _serialized_json(value))


def _write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if _is_reparse_point(path):
        raise ValueError("profile view destination must not be a symlink or reparse point")
    temporary: Path | None = None
    try:
        for _ in range(16):
            candidate = path.parent / f".{path.name}-{uuid.uuid4().hex}.tmp"
            if _is_reparse_point(candidate):
                raise ValueError("profile view temporary path must not be a symlink or reparse point")
            try:
                descriptor = os.open(candidate, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                continue
            temporary = candidate
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as file:
                file.write(text)
                file.flush()
                os.fsync(file.fileno())
            if _is_reparse_point(path) or _is_reparse_point(temporary):
                raise ValueError("profile view destination must not be a symlink or reparse point")
            os.replace(temporary, path)
            temporary = None
            return
        raise OSError("could not allocate a profile view temporary file")
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def _resolve_formats(
    spec: ProfileSpec,
    requested_formats: tuple[str, ...] | list[str] | None,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    if requested_formats is None:
        return (), spec.formats
    if isinstance(requested_formats, str):
        raise ValueError("requested_formats must be a list or tuple")
    requested = tuple(requested_formats)
    if len(set(requested)) != len(requested):
        raise ValueError("requested formats cannot contain duplicates")
    unsupported = [format_name for format_name in requested if format_name not in spec.formats]
    if unsupported:
        raise ValueError(
            f"profile {spec.profile_id!r} does not support requested format {unsupported[0]!r}"
        )
    return requested, requested or spec.formats
