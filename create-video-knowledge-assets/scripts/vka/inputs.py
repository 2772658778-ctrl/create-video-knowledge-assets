from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import TypeAlias
from urllib.parse import parse_qs, urlparse, urlunparse

from vka.preflight import require_command


Probe: TypeAlias = Callable[[Path], Mapping[str, object]]

ALLOWED_VIDEO_SUFFIXES = frozenset(
    {".avi", ".m4v", ".mkv", ".mov", ".mp4", ".mpeg", ".mpg", ".ts", ".webm"}
)
HASH_CHUNK_SIZE = 1024 * 1024
LOCAL_ASSET_ID_PREFIX_LENGTH = 16
SENSITIVE_METADATA_KEY_FRAGMENTS = ("cookie", "authorization", "password", "secret")
def describe_local_video(
    path: Path | str,
    *,
    probe: Probe | None = None,
    existing_identity: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Describe a local video without copying it into an asset directory."""
    video_path = Path(path)
    resolved_path = video_path.resolve()
    _validate_local_video_path(video_path, resolved_path)

    try:
        metadata = dict((probe or _probe_with_ffprobe)(resolved_path))
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        raise ValueError(f"could not inspect local video {resolved_path}: {exc}") from None

    content_sha256 = _sha256_file(resolved_path)
    descriptor: dict[str, object] = {
        "kind": "local_video",
        "content_sha256": content_sha256,
        "original_path": str(resolved_path),
        "metadata": metadata,
    }
    return register_asset_identity(descriptor, existing_identity=existing_identity)


def normalize_bilibili_url(url: str) -> dict[str, object]:
    """Keep only a Bilibili BV identifier and its stable canonical URL."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() not in {
        "bilibili.com",
        "www.bilibili.com",
        "m.bilibili.com",
    }:
        raise ValueError("Bilibili video URL must use bilibili.com/video/BV...")

    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2 or parts[0] != "video" or not _is_bvid(parts[1]):
        raise ValueError("Bilibili video URL must use bilibili.com/video/BV...")

    bvid = parts[1]
    selected_part = _selected_bilibili_part(parsed.query)
    source: dict[str, object] = {
        "kind": "bilibili",
        "bvid": bvid,
        "selection_required": selected_part is None,
        "canonical_url": _canonical_bilibili_url(bvid, selected_part),
    }
    if selected_part is not None:
        source["selected_part"] = selected_part
    return register_asset_identity(source)


def sanitize_acquired_metadata(value: object) -> object:
    """Remove credentials from yt-dlp metadata before it is persisted."""
    if isinstance(value, Mapping):
        return {
            key: sanitize_acquired_metadata(item)
            for key, item in value.items()
            if not _is_sensitive_metadata_key(key)
        }
    if isinstance(value, list):
        return [sanitize_acquired_metadata(item) for item in value]
    if isinstance(value, str):
        return _sanitize_url_query(value)
    return value


def asset_id_for_source(source: Mapping[str, object]) -> str:
    kind = source.get("kind")
    if kind == "local_video":
        content_sha256 = _required_sha256(source, "content_sha256")
        return f"local-{content_sha256[:LOCAL_ASSET_ID_PREFIX_LENGTH]}"
    if kind == "bilibili":
        bvid = source.get("bvid")
        if not isinstance(bvid, str) or not _is_bvid(bvid):
            raise ValueError("Bilibili source must include a valid BV identifier")
        selected_part = source.get("selected_part")
        if selected_part is not None:
            if isinstance(selected_part, bool) or not isinstance(selected_part, int) or selected_part < 1:
                raise ValueError("Bilibili source selected_part must be a positive integer")
            return f"bili-{bvid}-p{selected_part}"
        return f"bili-{bvid}"
    raise ValueError("source kind must be local_video or bilibili")


def register_asset_identity(
    source: Mapping[str, object],
    *,
    existing_identity: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Attach a stable ID and reject a full-hash collision before registration."""
    registered = dict(source)
    registered["asset_id"] = asset_id_for_source(registered)
    if existing_identity is None:
        return registered

    existing_source = _source_from_identity(existing_identity)
    canonical_existing_asset_id = asset_id_for_source(existing_source)
    declared_asset_id = existing_identity.get("asset_id")
    if declared_asset_id is not None and not isinstance(declared_asset_id, str):
        raise ValueError("existing asset identity must include a string asset_id")
    if canonical_existing_asset_id == registered["asset_id"]:
        validate_asset_identity_collision(existing_source, registered)
    if declared_asset_id is not None and declared_asset_id != canonical_existing_asset_id:
        raise ValueError("existing asset identity asset_id does not match its source")
    return registered


def validate_asset_identity_collision(
    existing_source: Mapping[str, object], candidate_source: Mapping[str, object]
) -> None:
    """Reject a truncated local asset-id collision by comparing full hashes."""
    if asset_id_for_source(existing_source) != asset_id_for_source(candidate_source):
        return

    if existing_source.get("kind") == candidate_source.get("kind") == "local_video":
        existing_hash = _required_sha256(existing_source, "content_sha256")
        candidate_hash = _required_sha256(candidate_source, "content_sha256")
        if existing_hash != candidate_hash:
            raise ValueError("asset ID collision: full content SHA-256 values differ")


def validate_bilibili_part_selection(
    source: Mapping[str, object], metadata: Mapping[str, object]
) -> None:
    """Require an explicit p selection when inspected metadata is multipart."""
    if source.get("kind") != "bilibili" or source.get("selection_required") is not True:
        return
    if _is_multipart_metadata(metadata):
        raise ValueError("Bilibili source has multiple parts; select one with ?p=N")


def archive_local_video(
    path: Path | str,
    destination_directory: Path | str,
    *,
    retention: str,
) -> Path:
    """Copy a local source into source/video only for an explicit L1 request."""
    if retention != "L1":
        raise ValueError("local video archival requires explicit retention='L1'")

    source_path = Path(path).resolve()
    _validate_local_video_path(Path(path), source_path)
    destination = Path(destination_directory).resolve() / source_path.name
    if destination == source_path:
        raise ValueError("L1 archive destination must differ from the original local video")
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(source_path, destination)
    except OSError as exc:
        raise ValueError(f"could not archive local video to {destination}: {exc}") from None
    return destination


def _probe_with_ffprobe(path: Path) -> Mapping[str, object]:
    ffprobe = require_command("ffprobe")
    command = [
        str(ffprobe),
        "-v",
        "error",
        "-show_format",
        "-show_streams",
        "-of",
        "json",
        str(path),
    ]
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        raise ValueError(f"ffprobe could not read the media (exit {exc.returncode})") from None
    except OSError as exc:
        raise ValueError(f"could not run ffprobe: {exc}") from None

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(f"ffprobe returned invalid JSON: {exc.msg}") from None
    if not isinstance(payload, dict):
        raise ValueError("ffprobe returned an invalid metadata object")
    return payload


def _validate_local_video_path(original_path: Path, resolved_path: Path) -> None:
    if not original_path.exists():
        raise ValueError(f"local video does not exist: {original_path}")
    if not original_path.is_file():
        raise ValueError(f"local video must be a regular file: {original_path}")
    if resolved_path.suffix.lower() not in ALLOWED_VIDEO_SUFFIXES:
        allowed = ", ".join(sorted(ALLOWED_VIDEO_SUFFIXES))
        raise ValueError(f"local video container must be one of: {allowed}")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as file:
            for chunk in iter(lambda: file.read(HASH_CHUNK_SIZE), b""):
                digest.update(chunk)
    except OSError as exc:
        raise ValueError(f"could not read local video {path}: {exc}") from None
    return digest.hexdigest()


def _required_sha256(source: Mapping[str, object], key: str) -> str:
    value = source.get(key)
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError(f"local video source must include a full {key}")
    try:
        int(value, 16)
    except ValueError:
        raise ValueError(f"local video source must include a full {key}") from None
    return value.lower()


def _source_from_identity(identity: Mapping[str, object]) -> Mapping[str, object]:
    source = identity.get("source", identity)
    if not isinstance(source, Mapping):
        raise ValueError("existing asset identity source must be an object")
    return source


def _is_bvid(value: str) -> bool:
    return len(value) > 2 and value.startswith("BV") and value[2:].isalnum()


def _selected_bilibili_part(query: str) -> int | None:
    values = parse_qs(query, keep_blank_values=True).get("p")
    if values is None:
        return None
    if len(values) != 1 or not values[0].isdigit() or int(values[0]) < 1:
        raise ValueError("Bilibili part selection must be one positive p value")
    return int(values[0])


def _canonical_bilibili_url(bvid: str, selected_part: int | None) -> str:
    url = f"https://www.bilibili.com/video/{bvid}"
    if selected_part is not None:
        return f"{url}?p={selected_part}"
    return url


def _is_multipart_metadata(metadata: Mapping[str, object]) -> bool:
    entries = metadata.get("entries")
    if isinstance(entries, list) and len(entries) > 1:
        return True
    for key in ("playlist_count", "page_count"):
        value = metadata.get(key)
        if isinstance(value, int) and value > 1:
            return True
    return False


def _is_sensitive_metadata_key(key: object) -> bool:
    return isinstance(key, str) and any(
        fragment in key.casefold() for fragment in SENSITIVE_METADATA_KEY_FRAGMENTS
    )


def _sanitize_url_query(value: str) -> str:
    parsed = urlparse(value)
    if not parsed.scheme and not parsed.netloc:
        return value

    netloc = parsed.netloc.rsplit("@", 1)[-1]
    path = parsed.path.split(";", 1)[0]
    if (
        netloc == parsed.netloc
        and path == parsed.path
        and not parsed.params
        and not parsed.query
        and not parsed.fragment
    ):
        return value
    return urlunparse(
        parsed._replace(
            netloc=netloc,
            path=path,
            params="",
            query="",
            fragment="",
        )
    )
