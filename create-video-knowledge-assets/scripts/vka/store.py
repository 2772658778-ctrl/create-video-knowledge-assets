from __future__ import annotations

import hashlib
import json
import os
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable


STANDARD_DIRECTORIES = ("source", "evidence", "knowledge", "views", "index", "outputs", "logs")
SCHEMA_VERSION = "1.1"


@dataclass(frozen=True)
class AssetStore:
    root: Path

    @classmethod
    def create(
        cls,
        assets_root: Path | str,
        asset_id: str,
        source: dict[str, object],
        *,
        config: dict[str, object] | None = None,
        tool_versions: dict[str, str] | None = None,
    ) -> "AssetStore":
        _validate_asset_id(asset_id)
        assets_root_path = Path(assets_root).resolve()
        assets_root_path.mkdir(parents=True, exist_ok=True)
        root = (assets_root_path / asset_id).resolve()

        try:
            root.mkdir(exist_ok=False)
        except FileExistsError:
            raise FileExistsError(f"asset already exists: {asset_id}")

        for name in STANDARD_DIRECTORIES:
            (root / name).mkdir(exist_ok=True)

        store = cls(root=root)
        store._write_manifest(
            {
                "asset_id": asset_id,
                "schema_version": SCHEMA_VERSION,
                "source": source,
                "input": source,
                "config": config or {},
                "tool_versions": tool_versions or {},
                "created_at": _utc_now_iso(),
                "stages": {},
            }
        )
        return store

    def write_jsonl(self, relative_path: Path | str, rows: Iterable[dict[str, object]]) -> Path:
        path = self._resolve_asset_path(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as file:
            for row in rows:
                file.write(json.dumps(row, ensure_ascii=False))
                file.write("\n")
        return path

    def complete_stage(
        self,
        stage: str,
        outputs: Iterable[Path | str],
        *,
        schema_version: str = SCHEMA_VERSION,
    ) -> None:
        manifest = self._read_manifest()
        if not isinstance(manifest, dict):
            raise ValueError("manifest must be an object")
        if manifest.get("schema_version") != SCHEMA_VERSION:
            raise ValueError(f"only {SCHEMA_VERSION} manifests can be modified")

        stages = manifest.setdefault("stages", {})
        if not isinstance(stages, dict):
            raise ValueError("manifest stages must be an object")

        stages[stage] = {
            "completed_at": _utc_now_iso(),
            "schema_version": schema_version,
            "outputs": [
                {
                    "path": self._relative_asset_path(output),
                    "sha256": self._sha256_file(output),
                }
                for output in outputs
            ],
        }
        self._write_manifest(manifest)

    def verify_stage(self, stage: str, *, schema_version: str) -> list[str]:
        """Return integrity errors for a completed stage without changing its manifest."""
        return self._stage_errors(stage, schema_version)

    def reopen_stage(self, stage: str) -> None:
        """Drop a completed stage so it can be rebuilt.

        A completed view is immutable by default; re-authoring one has to be an
        explicit act, so the stage record is removed first and every downstream
        reader sees the stage as unfinished until it is completed again.
        """
        manifest = self._read_manifest()
        if not isinstance(manifest, dict):
            raise ValueError("manifest must be an object")
        if manifest.get("schema_version") != SCHEMA_VERSION:
            raise ValueError(f"only {SCHEMA_VERSION} manifests can be modified")
        stages = manifest.get("stages")
        if not isinstance(stages, dict):
            raise ValueError("manifest stages must be an object")
        if stage not in stages:
            raise ValueError(f"{stage} stage is not completed")
        del stages[stage]
        self._write_manifest(manifest)

    def _stage_errors(self, stage: str, schema_version: str) -> list[str]:
        manifest, manifest_error = self._manifest_for_verification()
        if manifest_error is not None:
            return [manifest_error]

        stages = manifest.get("stages")
        if not isinstance(stages, dict):
            return ["manifest stages must be an object"]

        stage_record = stages.get(stage)
        if not isinstance(stage_record, dict):
            return [f"{stage} stage is not completed"]

        errors: list[str] = []
        if stage_record.get("schema_version") != schema_version:
            errors.append(f"{stage} schema_version does not match manifest")

        outputs = stage_record.get("outputs")
        if not isinstance(outputs, list):
            return [*errors, f"{stage} outputs must be a list"]

        for output in outputs:
            if not isinstance(output, dict):
                errors.append(f"{stage} output entry must be an object")
                continue

            relative_path = output.get("path")
            expected_sha256 = output.get("sha256")
            if not isinstance(relative_path, str) or not isinstance(expected_sha256, str):
                errors.append(f"{stage} output entry is missing path or sha256")
                continue

            try:
                path = self._resolve_asset_path(relative_path)
            except ValueError:
                errors.append(f"{relative_path} is outside the asset root")
                continue

            if not path.is_file():
                errors.append(f"{relative_path} is missing")
                continue

            if self._sha256_file(path) != expected_sha256:
                errors.append(f"{relative_path} sha256 does not match manifest")

            serialized_error = self._serialized_file_error(path, relative_path)
            if serialized_error is not None:
                errors.append(serialized_error)

        return errors

    def resume_status(self) -> dict[str, str]:
        """Report stage readiness without rewriting an existing asset.

        An invalid stage makes only its declared downstream stages stale.  In
        particular, a changed profile view does not invalidate other profiles.
        """
        manifest, manifest_error = self._manifest_for_verification()
        if manifest_error is not None:
            return {"manifest": "invalid"}
        assert manifest is not None
        stages = manifest.get("stages")
        if not isinstance(stages, dict):
            return {"manifest": "invalid"}

        if not all(isinstance(name, str) and isinstance(record, dict) for name, record in stages.items()):
            return {"manifest": "invalid"}
        records = {name: record for name, record in stages.items()}
        status: dict[str, str] = {}
        for stage, record in records.items():
            schema_version = record.get("schema_version")
            expected = schema_version if isinstance(schema_version, str) else SCHEMA_VERSION
            status[stage] = "invalid" if self.verify_stage(stage, schema_version=expected) else "ready"

        changed = True
        while changed:
            changed = False
            for stage in records:
                if status[stage] != "ready":
                    continue
                dependencies = _stage_dependencies(stage, set(records))
                if any(status.get(dependency) in {"invalid", "stale"} for dependency in dependencies) or any(
                    dependency not in status for dependency in dependencies
                ):
                    status[stage] = "stale"
                    changed = True
        return status

    def _read_manifest(self) -> dict[str, object]:
        with (self.root / "manifest.json").open(encoding="utf-8") as file:
            return json.load(file)

    def _manifest_for_verification(self) -> tuple[dict[str, object] | None, str | None]:
        try:
            manifest = self._read_manifest()
        except FileNotFoundError:
            return None, "manifest.json is missing"
        except UnicodeDecodeError:
            return None, "manifest.json is not valid UTF-8"
        except json.JSONDecodeError:
            return None, "manifest.json is not valid JSON"
        except OSError:
            return None, "manifest.json cannot be read"

        if not isinstance(manifest, dict):
            return None, "manifest.json must be an object"
        if "schema_version" not in manifest:
            return None, "manifest schema_version is missing"

        manifest_schema_version = manifest["schema_version"]
        if not isinstance(manifest_schema_version, str):
            return None, "manifest schema_version must be a string"
        if manifest_schema_version != SCHEMA_VERSION:
            return None, f"manifest schema_version must be {SCHEMA_VERSION}"
        return manifest, None

    def _write_manifest(self, manifest: dict[str, object]) -> None:
        root = self._manifest_write_root()
        manifest_path = root / "manifest.json"
        # Earlier versions used this predictable name. Never follow it: an
        # old or hostile reparse point must not redirect a manifest write.
        _assert_safe_manifest_path(root, root / "manifest.json.tmp", "manifest temporary path")
        _assert_safe_manifest_path(root, manifest_path, "manifest destination")

        tmp_path: Path | None = None
        try:
            for _ in range(16):
                candidate = root / f".manifest-{uuid.uuid4().hex}.tmp"
                _assert_safe_manifest_path(root, candidate, "manifest temporary path")
                try:
                    descriptor = os.open(
                        candidate,
                        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                        0o600,
                    )
                except FileExistsError:
                    continue
                tmp_path = candidate
                with os.fdopen(descriptor, "w", encoding="utf-8") as file:
                    json.dump(manifest, file, ensure_ascii=False, indent=2)
                    file.write("\n")
                    file.flush()
                    os.fsync(file.fileno())
                _assert_safe_manifest_path(root, tmp_path, "manifest temporary path")
                _assert_safe_manifest_path(root, manifest_path, "manifest destination")
                os.replace(tmp_path, manifest_path)
                tmp_path = None
                return
            raise OSError("could not allocate a unique manifest temporary file")
        finally:
            if tmp_path is not None and tmp_path.exists():
                _assert_safe_manifest_path(root, tmp_path, "manifest temporary path")
                tmp_path.unlink()

    def _manifest_write_root(self) -> Path:
        if not self.root.is_dir() or _is_link(self.root):
            raise ValueError("asset root must be a real directory")
        return self.root.resolve()

    def _resolve_asset_path(self, path: Path | str) -> Path:
        candidate = Path(path)
        if candidate.is_absolute():
            raise ValueError("asset paths must be relative")

        resolved_root = self.root.resolve()
        resolved_path = (resolved_root / candidate).resolve()
        try:
            resolved_path.relative_to(resolved_root)
        except ValueError as exc:
            raise ValueError("asset paths must stay within the asset root") from exc
        return resolved_path

    def _relative_asset_path(self, path: Path | str) -> str:
        candidate = Path(path)
        if candidate.is_absolute():
            resolved_path = candidate.resolve()
        else:
            resolved_path = (self.root.resolve() / candidate).resolve()

        try:
            return resolved_path.relative_to(self.root.resolve()).as_posix()
        except ValueError as exc:
            raise ValueError("stage outputs must be within the asset root") from exc

    def _sha256_file(self, path: Path | str) -> str:
        resolved_path = self.root / self._relative_asset_path(path)
        digest = hashlib.sha256()
        with resolved_path.open("rb") as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _serialized_file_error(path: Path, relative_path: str) -> str | None:
        suffix = path.suffix.lower()
        if suffix not in {".json", ".jsonl"}:
            return None

        try:
            with path.open(encoding="utf-8") as file:
                if suffix == ".json":
                    json.load(file)
                else:
                    for line in file:
                        json.loads(line)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            label = "JSONL" if suffix == ".jsonl" else "JSON"
            return f"{relative_path} is not valid {label}"
        return None


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _validate_asset_id(asset_id: str) -> None:
    path = Path(asset_id)
    if (
        not asset_id
        or path.is_absolute()
        or len(path.parts) != 1
        or path.name != asset_id
        or asset_id in {".", ".."}
    ):
        raise ValueError("asset_id must be a single safe directory name")


def _is_link(path: Path) -> bool:
    is_junction = getattr(path, "is_junction", None)
    return path.is_symlink() or (callable(is_junction) and is_junction())


def _assert_safe_manifest_path(root: Path, path: Path, label: str) -> None:
    if _is_link(path):
        raise ValueError(f"{label} must not be a symlink")
    resolved_path = path.resolve()
    try:
        resolved_path.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"{label} must stay within the asset root") from exc


def _stage_dependencies(stage: str, available_stages: set[str]) -> tuple[str, ...]:
    if stage == "knowledge":
        return ("evidence",)
    if stage == "views" or stage.startswith("views/"):
        return ("evidence", "knowledge")
    if stage == "outputs":
        return ("evidence", "knowledge", "views")
    if stage.startswith("outputs/"):
        profile = stage.removeprefix("outputs/")
        profile_view = f"views/{profile}"
        if profile_view in available_stages:
            return ("evidence", "knowledge", profile_view)
        return ("evidence", "knowledge", "views")
    return ()
