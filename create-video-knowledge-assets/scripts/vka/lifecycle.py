"""Verification, resumability, and L2 retention for completed video assets."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from vka.store import AssetStore, SCHEMA_VERSION


FRAME_SUFFIXES = frozenset({".jpg", ".jpeg", ".png", ".webp"})


def verify_asset(asset: AssetStore | Path | str) -> dict[str, object]:
    """Validate a complete asset without modifying it.

    Stage output hashes remain the authority for generated artifacts.  The
    extra checks here deliberately cover files that are only referenced by a
    document, where a dangling image would otherwise evade stage validation.
    """
    store = _store_for_asset(asset)
    errors: list[str] = []
    if store.root.is_symlink():
        return _verification_report(store.root, ["asset root must not be a symlink"])

    manifest, manifest_error = store._manifest_for_verification()
    if manifest_error is not None:
        return _verification_report(store.root, [manifest_error])
    assert manifest is not None

    asset_id = manifest.get("asset_id")
    if not isinstance(asset_id, str) or not asset_id:
        errors.append("manifest asset_id must be a non-empty string")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"manifest schema_version must be {SCHEMA_VERSION}")

    stages = manifest.get("stages")
    if not isinstance(stages, dict):
        errors.append("manifest stages must be an object")
    else:
        for stage, record in stages.items():
            if not isinstance(stage, str) or not stage:
                errors.append("manifest stage names must be non-empty strings")
                continue
            if not isinstance(record, dict):
                errors.append(f"{stage} stage record must be an object")
                continue
            errors.extend(store.verify_stage(stage, schema_version=SCHEMA_VERSION))
            errors.extend(_stage_output_symlink_errors(store, stage, record))
        errors.extend(_dependency_errors(stages))

    errors.extend(_document_image_errors(store))
    errors.extend(_asset_symlink_errors(store.root))
    return _verification_report(store.root, errors)


def plan_l2_cleanup(asset: AssetStore | Path | str) -> dict[str, object]:
    """Return a non-mutating L2 retention plan for a verified completed asset."""
    store = _store_for_asset(asset)
    report = verify_asset(store)
    if not report["valid"]:
        raise ValueError("asset cannot be cleaned: " + "; ".join(report["errors"]))

    manifest = store._read_manifest()
    if not isinstance(manifest, dict):  # guarded above; retains a clear type boundary
        raise ValueError("asset cannot be cleaned: manifest must be an object")
    stages = manifest.get("stages")
    if not isinstance(stages, dict) or not stages:
        raise ValueError("asset cannot be cleaned: asset has no completed stages")
    completion_errors = _completion_errors(stages)
    if completion_errors:
        raise ValueError("asset cannot be cleaned: " + "; ".join(completion_errors))

    referenced_images = _referenced_document_images(store)
    completed_outputs = _completed_output_paths(store, stages)
    source = manifest.get("source")
    remote_source = isinstance(source, Mapping) and source.get("kind") == "bilibili"
    keep: list[dict[str, str]] = []
    delete: list[str] = []
    reacquire: list[dict[str, str]] = []
    reasons: dict[str, str] = {}

    for path in sorted(_asset_files(store.root)):
        relative = path.relative_to(store.root).as_posix()
        action, reason = _l2_action(
            relative,
            remote_source,
            referenced_images,
            completed_outputs,
        )
        reasons[relative] = reason
        if action == "delete":
            delete.append(relative)
            if relative.startswith("source/video/"):
                reacquire.append(
                    {
                        "path": relative,
                        "reason": "remote video is intentionally omitted at L2 and can be downloaded again",
                    }
                )
        else:
            keep.append({"path": relative, "reason": reason})

    return {
        "asset": str(store.root),
        "level": "L2",
        "keep": keep,
        "delete": delete,
        "reacquire": reacquire,
        "reasons": reasons,
        "checks": report,
    }


def execute_l2_cleanup(
    asset: AssetStore | Path | str, plan: Mapping[str, object] | None = None
) -> dict[str, object]:
    """Apply a previously reviewed L2 plan after revalidating every deletion."""
    store = _store_for_asset(asset)
    fresh_plan = plan_l2_cleanup(store)
    if plan is not None:
        _validate_supplied_plan(store, plan, fresh_plan)
    delete = fresh_plan["delete"]
    assert isinstance(delete, list)

    # Validate the whole deletion set before touching any file.  This protects
    # against traversal, symlink replacement, and a stale plan causing a
    # partial cleanup.
    delete_paths = [_safe_deletion_path(store, relative) for relative in delete]
    for path in delete_paths:
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"asset cannot be cleaned: unsafe deletion target {path}")

    for path in delete_paths:
        path.unlink()

    manifest = store._read_manifest()
    if not isinstance(manifest, dict):
        raise ValueError("asset manifest became invalid during cleanup")
    manifest["retention"] = {
        "level": "L2",
        "last_cleanup": {
            "kept": [entry["path"] for entry in fresh_plan["keep"]],
            "deleted": list(delete),
            "reacquire": fresh_plan["reacquire"],
            "checks": fresh_plan["checks"],
        },
    }
    store._write_manifest(manifest)
    return fresh_plan


def _store_for_asset(asset: AssetStore | Path | str) -> AssetStore:
    store = asset if isinstance(asset, AssetStore) else AssetStore(Path(asset))
    root = store.root
    if not root.exists() or not root.is_dir():
        raise ValueError("asset directory does not exist")
    if root.is_symlink():
        raise ValueError("asset root must not be a symlink")
    return AssetStore(root.resolve())


def _verification_report(root: Path, errors: list[str]) -> dict[str, object]:
    return {
        "asset": str(root),
        "valid": not errors,
        "errors": list(dict.fromkeys(errors)),
    }


def _stage_output_symlink_errors(
    store: AssetStore, stage: str, record: Mapping[str, object]) -> list[str]:
    outputs = record.get("outputs")
    if not isinstance(outputs, list):
        return []
    errors: list[str] = []
    for output in outputs:
        if not isinstance(output, Mapping):
            continue
        relative = output.get("path")
        if not isinstance(relative, str):
            continue
        try:
            path = store._resolve_asset_path(relative)
        except ValueError:
            continue
        if _contains_symlink(store.root, relative) or path.is_symlink():
            errors.append(f"{stage} output must not be a symlink: {relative}")
    return errors


def _dependency_errors(stages: Mapping[object, object]) -> list[str]:
    stage_names = {stage for stage, value in stages.items() if isinstance(stage, str) and isinstance(value, dict)}
    errors: list[str] = []
    for stage in sorted(stage_names):
        for dependency in _dependencies_for_stage(stage, stage_names):
            if dependency not in stage_names:
                errors.append(f"{stage} requires completed {dependency} stage")
    return errors


def _completion_errors(stages: Mapping[object, object]) -> list[str]:
    names = {
        stage
        for stage, record in stages.items()
        if isinstance(stage, str) and isinstance(record, dict)
    }
    missing = [stage for stage in ("evidence", "knowledge") if stage not in names]
    if not any(stage == "views" or stage.startswith("views/") for stage in names):
        missing.append("views")
    if missing:
        return ["asset is incomplete: missing completed " + ", ".join(missing) + " stage"]
    return []


def _dependencies_for_stage(stage: str, stage_names: set[str]) -> tuple[str, ...]:
    if stage == "knowledge":
        return ("evidence",)
    if stage == "views" or stage.startswith("views/"):
        return ("evidence", "knowledge")
    if stage == "outputs":
        return ("evidence", "knowledge", "views")
    if stage.startswith("outputs/"):
        profile = stage.removeprefix("outputs/")
        view_stage = f"views/{profile}"
        if view_stage in stage_names:
            return ("evidence", "knowledge", view_stage)
        return ("evidence", "knowledge", "views")
    return ()


def _document_image_errors(store: AssetStore) -> list[str]:
    errors: list[str] = []
    for document_path in _document_paths(store.root):
        relative_document = document_path.relative_to(store.root).as_posix()
        try:
            document = json.loads(document_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            errors.append(f"{relative_document} is not valid JSON")
            continue
        image_paths = _image_paths(document)
        if _has_image_block(document) and not image_paths:
            errors.append("document image block must have a safe local image_path")
        for image_path in image_paths:
            try:
                relative_image, resolved = _normalized_asset_relative_path(store, image_path)
            except ValueError:
                errors.append(f"document image_path is outside asset root: {image_path}")
                continue
            if not resolved.is_file():
                errors.append(f"document image_path does not exist: {image_path}")
                continue
            if _contains_symlink(store.root, relative_image) or resolved.is_symlink():
                errors.append(f"document image_path must not be a symlink: {image_path}")
    return errors


def _document_paths(root: Path) -> list[Path]:
    views = root / "views"
    if not views.is_dir() or views.is_symlink():
        return []
    return [path for path in views.rglob("document.json") if path.is_file() and not path.is_symlink()]


def _image_paths(document: object) -> set[str]:
    if not isinstance(document, Mapping):
        return set()
    blocks = _document_blocks(document)
    paths: set[str] = set()
    for block in blocks:
        if not isinstance(block, Mapping) or block.get("kind") != "image":
            continue
        value: Any = block.get("image_path", block.get("path"))
        if value is None and isinstance(block.get("data"), Mapping):
            value = block["data"].get("image_path", block["data"].get("path"))
        if isinstance(value, str):
            paths.add(value)
    return paths


def _has_image_block(document: object) -> bool:
    if not isinstance(document, Mapping):
        return False
    return any(
        isinstance(block, Mapping) and block.get("kind") == "image"
        for block in _document_blocks(document)
    )


def _document_blocks(document: Mapping[str, object]) -> list[object]:
    blocks = document.get("blocks")
    if isinstance(blocks, list):
        return blocks
    sections = document.get("sections")
    if not isinstance(sections, list):
        return []
    blocks: list[object] = []
    for section in sections:
        if not isinstance(section, Mapping):
            continue
        section_blocks = section.get("blocks")
        if isinstance(section_blocks, list):
            blocks.extend(section_blocks)
    return blocks


def _referenced_document_images(store: AssetStore) -> set[str]:
    paths: set[str] = set()
    for document_path in _document_paths(store.root):
        document = json.loads(document_path.read_text(encoding="utf-8"))
        for image_path in _image_paths(document):
            try:
                relative_image, _ = _normalized_asset_relative_path(store, image_path)
            except ValueError:
                # `plan_l2_cleanup` only calls this after `verify_asset`; this
                # keeps the helper defensive if it is reused independently.
                continue
            paths.add(relative_image)
    return paths


def _completed_output_paths(
    store: AssetStore, stages: Mapping[object, object]
) -> set[str]:
    paths: set[str] = set()
    for record in stages.values():
        if not isinstance(record, Mapping):
            continue
        outputs = record.get("outputs")
        if not isinstance(outputs, list):
            continue
        for output in outputs:
            if not isinstance(output, Mapping):
                continue
            path = output.get("path")
            if not isinstance(path, str):
                continue
            try:
                relative_path, _ = _normalized_asset_relative_path(store, path)
            except ValueError:
                # Verification has already rejected an unsafe stage output.
                continue
            paths.add(relative_path)
    return paths


def _normalized_asset_relative_path(store: AssetStore, path: str) -> tuple[str, Path]:
    resolved = store._resolve_asset_path(path)
    relative = resolved.relative_to(store.root.resolve()).as_posix()
    return relative, resolved


def _asset_symlink_errors(root: Path) -> list[str]:
    return [
        f"asset must not contain symlinks: {path.relative_to(root).as_posix()}"
        for path in root.rglob("*")
        if path.is_symlink()
    ]


def _contains_symlink(root: Path, relative: str) -> bool:
    current = root
    for part in Path(relative).parts:
        current = current / part
        if current.is_symlink():
            return True
    return False


def _asset_files(root: Path) -> list[Path]:
    return [path for path in root.rglob("*") if path.is_file() and not path.is_symlink()]


def _l2_action(
    relative: str,
    remote_source: bool,
    referenced_images: set[str],
    completed_outputs: set[str],
) -> tuple[str, str]:
    if relative == "manifest.json":
        return "keep", "manifest preserves identity, integrity, and retention history"
    if relative in completed_outputs:
        return "keep", "completed stage output is retained for integrity and resumption"
    if relative.startswith("source/audio/"):
        return "delete", "audio is rebuildable from the video source"
    if relative.startswith("source/video/") and remote_source:
        return "delete", "remote downloaded video is rebuildable"
    if relative.startswith("evidence/frames/") and Path(relative).suffix.lower() in FRAME_SUFFIXES:
        if relative in referenced_images or Path(relative).name.startswith("selected"):
            return "keep", "selected or document-referenced frame is evidence"
        return "delete", "unselected candidate frame is rebuildable"
    if relative.startswith("source/"):
        return "keep", "metadata and original or selected subtitle inputs are retained"
    if relative.startswith("evidence/"):
        return "keep", "evidence, including raw and repaired transcripts, is retained"
    if relative.startswith("knowledge/"):
        return "keep", "knowledge is retained"
    if relative.startswith("views/"):
        return "keep", "profile view is retained"
    if relative.startswith("outputs/"):
        return "keep", "rendered output is retained"
    return "keep", "asset support file is retained"


def _safe_deletion_path(store: AssetStore, relative: object) -> Path:
    if not isinstance(relative, str):
        raise ValueError("asset cannot be cleaned: deletion path must be a string")
    try:
        path = store._resolve_asset_path(relative)
    except ValueError as exc:
        raise ValueError(f"asset cannot be cleaned: unsafe deletion path {relative}") from exc
    if _contains_symlink(store.root, relative):
        raise ValueError(f"asset cannot be cleaned: deletion path contains a symlink: {relative}")
    return path


def _validate_supplied_plan(
    store: AssetStore, supplied: Mapping[str, object], fresh: Mapping[str, object]
) -> None:
    if supplied.get("asset") != str(store.root):
        raise ValueError("asset cannot be cleaned: plan belongs to a different asset")
    if supplied.get("delete") != fresh.get("delete"):
        raise ValueError("asset cannot be cleaned: plan is stale or was modified")
