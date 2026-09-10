"""Local, schema-checked external evidence for P4.2 answer context."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator


EXTERNAL_EVIDENCE_PATH = Path("evidence") / "external.jsonl"
_SENSITIVE_TEXT = re.compile(
    r"\b(?:cookie|headers?|authorization)\b|(?:^|[\r\n])\s*(?:manifest|log)\s*[:=]|[\"'](?:manifest|log)[\"']\s*:",
    re.IGNORECASE | re.MULTILINE,
)
_HTTP_URL_IN_TEXT = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)


def _has_sensitive_url(value: str) -> bool:
    """Reject credentials, query strings, and fragments embedded in saved prose."""

    for match in _HTTP_URL_IN_TEXT.finditer(value):
        parsed = urlsplit(match.group(0))
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            return True
    return False


class ExternalEvidence(BaseModel):
    """One user-supplied, stable external source excerpt; never video evidence."""

    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(pattern=r"^external:[A-Za-z0-9][A-Za-z0-9._:-]*$")
    source_title: str = Field(min_length=1)
    source_type: str = Field(min_length=1)
    stable_url: str = Field(min_length=1)
    acquired_at: datetime
    publication_date: str | None = None
    version: str | None = None
    content: str = Field(min_length=1)

    @field_validator("source_title", "source_type", "publication_date", "version", "content")
    @classmethod
    def non_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("text fields must not be blank")
        if value is not None and _SENSITIVE_TEXT.search(value):
            raise ValueError("text fields must not contain Cookie, header, authorization, manifest, or log labels")
        if value is not None and _has_sensitive_url(value):
            raise ValueError("text fields must not contain URLs with credentials, query, or fragment")
        return value

    @field_validator("stable_url")
    @classmethod
    def stable_public_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("stable_url must be an absolute http(s) URL")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("stable_url must not contain credentials, query, or fragment")
        return value


def read_external_evidence(
    path: Path, *, required: bool = False
) -> tuple[dict[str, ExternalEvidence], list[str]]:
    """Read the distinct external namespace without treating it as video evidence."""

    records: dict[str, ExternalEvidence] = {}
    errors: list[str] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return records, ["external evidence artifact is missing"] if required else errors
    except (OSError, UnicodeDecodeError) as exc:
        return records, [f"external evidence cannot be read: {exc}"]
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
            if not isinstance(value, Mapping):
                raise ValueError("record must be an object")
            record = ExternalEvidence.model_validate(value)
        except Exception as exc:  # Pydantic and JSON errors are user-facing validation failures.
            errors.append(f"external evidence record {line_number} is invalid: {exc}")
            continue
        if record.evidence_id in records:
            errors.append(f"duplicate external evidence_id: {record.evidence_id}")
        else:
            records[record.evidence_id] = record
    return records, errors


def register_external_evidence(asset: Path, source: Path) -> Path:
    """Validate structured local input and atomically replace the external artifact."""

    raw = source.read_text(encoding="utf-8")
    try:
        value = json.loads(raw)
        rows = value if isinstance(value, list) else [value]
    except json.JSONDecodeError:
        try:
            rows = [json.loads(line) for line in raw.splitlines() if line.strip()]
        except json.JSONDecodeError as exc:
            raise ValueError("external evidence input is not valid JSON or JSONL") from exc
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        raise ValueError("external evidence input must be a JSON object, array, or JSONL")
    parsed = [ExternalEvidence.model_validate(row) for row in rows]
    ids = [record.evidence_id for record in parsed]
    if len(set(ids)) != len(ids):
        raise ValueError("external evidence input contains duplicate evidence_id values")
    video_path = asset / "evidence" / "records.jsonl"
    if video_path.is_file():
        try:
            video_ids = {
                value.get("evidence_id")
                for line in video_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
                for value in [json.loads(line)]
                if isinstance(value, Mapping) and isinstance(value.get("evidence_id"), str)
            }
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("canonical video evidence cannot be read for namespace validation") from exc
        collisions = sorted(set(ids) & video_ids)
        if collisions:
            raise ValueError("external evidence IDs collide with video evidence: " + ", ".join(collisions))
    destination = asset / EXTERNAL_EVIDENCE_PATH
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(
        "".join(json.dumps(record.model_dump(mode="json"), ensure_ascii=False, sort_keys=True) + "\n" for record in parsed),
        encoding="utf-8",
    )
    os.replace(temporary, destination)
    return destination
