"""QA gates and reproducible fingerprints for retained knowledge assets."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path

from vka.lifecycle import verify_asset
from vka.store import AssetStore


REQUIRED_QA_FILES = (
    "evidence/records.jsonl",
    "knowledge/units.jsonl",
    "knowledge/relations.jsonl",
    "knowledge/synthesis.json",
)

_REQUIRED_STAGES = ("source", "evidence", "knowledge")
_COURSE_NOTES_FILES = (
    "knowledge/teaching_outline.json",
    "views/course-notes/document.json",
)
_REQUIRED_QA_OUTPUT_STAGES = {
    "evidence/records.jsonl": "evidence",
    "knowledge/units.jsonl": "knowledge",
    "knowledge/relations.jsonl": "knowledge",
    "knowledge/synthesis.json": "knowledge",
}
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def validate_qa_asset(
    asset: AssetStore | Path | str, profile_id: str = "course-notes"
) -> list[str]:
    """Return deterministic QA errors while retaining ordinary asset verification."""
    store = _as_store(asset)
    report = verify_asset(store)
    errors = _verification_errors(report)
    stages = _validated_stages(store)

    for stage in _REQUIRED_STAGES:
        if stage not in stages:
            errors.append(f"required QA stage is not completed: {stage}")

    registered_outputs = {
        stage: {output["path"] for output in _validated_outputs(store, stage, record)}
        for stage, record in stages.items()
    }
    for path, stage in _REQUIRED_QA_OUTPUT_STAGES.items():
        if path not in registered_outputs.get(stage, set()):
            errors.append(f"P4 requires {path} to be registered in {stage} stage outputs")

    required_files = list(REQUIRED_QA_FILES)
    if profile_id == "course-notes":
        required_files.extend(_COURSE_NOTES_FILES)
    for relative_path in required_files:
        if not (store.root / relative_path).is_file():
            errors.append(f"required QA file is missing: {relative_path}")

    return sorted(set(errors))


def qa_asset_fingerprint(asset: AssetStore | Path | str) -> dict[str, str]:
    """Return sorted registered output hashes for the retained canonical layers."""
    store = _as_store(asset)
    _require_real_asset_root(store)
    stages = _validated_stages(store)
    fingerprints: dict[str, str] = {}

    for stage in _REQUIRED_STAGES:
        record = stages.get(stage)
        if record is None:
            continue
        for output in _validated_outputs(store, stage, record):
            path = output["path"]
            sha256 = output["sha256"]
            if _is_reacquirable_remote_video(path):
                continue
            previous = fingerprints.get(path)
            if previous is not None and previous != sha256:
                raise ValueError(f"conflicting registered sha256 for output path: {path}")
            fingerprints[path] = sha256

    return {path: fingerprints[path] for path in sorted(fingerprints)}


def _as_store(asset: AssetStore | Path | str) -> AssetStore:
    return asset if isinstance(asset, AssetStore) else AssetStore(Path(asset))


def _verification_errors(report: object) -> list[str]:
    if not isinstance(report, Mapping):
        raise ValueError("asset verification report must be an object")
    errors = report.get("errors")
    if not isinstance(errors, list) or not all(isinstance(error, str) for error in errors):
        raise ValueError("asset verification report errors must be a list of strings")
    return list(errors)


def _validated_stages(store: AssetStore) -> Mapping[str, Mapping[str, object]]:
    try:
        manifest = store._read_manifest()
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("manifest cannot be read as JSON") from exc
    if not isinstance(manifest, Mapping):
        raise ValueError("manifest must be an object")
    source = manifest.get("source")
    if not isinstance(source, Mapping):
        raise ValueError("manifest source must be an object")
    raw_stages = manifest.get("stages")
    if not isinstance(raw_stages, Mapping):
        raise ValueError("manifest stages must be an object")

    stages: dict[str, Mapping[str, object]] = {}
    for name, record in raw_stages.items():
        if not isinstance(name, str) or not name:
            raise ValueError("manifest stage names must be non-empty strings")
        if not isinstance(record, Mapping):
            raise ValueError(f"{name} stage record must be an object")
        _validated_outputs(store, name, record)
        stages[name] = record
    return stages


def _validated_outputs(
    store: AssetStore, stage: str, record: Mapping[str, object]
) -> list[dict[str, str]]:
    outputs = record.get("outputs")
    if not isinstance(outputs, list):
        raise ValueError(f"{stage} stage outputs must be a list")

    validated: list[dict[str, str]] = []
    for output in outputs:
        if not isinstance(output, Mapping):
            raise ValueError(f"{stage} output entry must be an object")
        path = output.get("path")
        sha256 = output.get("sha256")
        if not isinstance(path, str) or not path:
            raise ValueError(f"{stage} output path must be a non-empty string")
        canonical_path = _canonical_output_path(store, stage, path)
        if not isinstance(sha256, str) or not _SHA256.fullmatch(sha256):
            raise ValueError(
                f"{stage} output sha256 must be a 64-character lowercase hexadecimal string"
            )
        validated.append({"path": canonical_path, "sha256": sha256})
    return validated


def _canonical_output_path(store: AssetStore, stage: str, path: str) -> str:
    if "\\" in path:
        raise ValueError(f"{stage} output path must use POSIX separators: {path}")
    try:
        resolved = store._resolve_asset_path(path)
        canonical = resolved.relative_to(store.root.resolve()).as_posix()
    except ValueError as exc:
        raise ValueError(
            f"{stage} output path must be a canonical asset-relative path: {path}"
        ) from exc
    if canonical == "." or path != canonical:
        raise ValueError(f"{stage} output path must be a canonical asset-relative path: {path}")
    return canonical


def _require_real_asset_root(store: AssetStore) -> None:
    root = store.root
    is_junction = getattr(root, "is_junction", None)
    if root.is_symlink() or (callable(is_junction) and is_junction()):
        raise ValueError("asset root must not be a symlink or junction")


def _is_reacquirable_remote_video(path: str) -> bool:
    return path.startswith("source/video/")
