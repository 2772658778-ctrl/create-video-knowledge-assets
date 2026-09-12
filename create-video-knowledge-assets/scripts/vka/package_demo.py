"""Publish one profile view as a demo directory.

The published reader copy is one self-contained HTML file per part, so a demo
opens with a double click and carries its own cover and figures. That is why
this module inlines images instead of copying them next to the page: a demo
directory with a figures/ folder is a second thing to keep in sync, and a
reader who moves the file loses the pictures.

Only the formats recorded in the view selection are published, so a run that
asked for HTML alone does not ship a PDF nobody requested.
"""

from __future__ import annotations

import base64
import html
import json
import mimetypes
import re
import shutil
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from vka.profiles import renderer_options_for
from vka.render_html import render_document_html


PARTS = (("main", "summary"), ("notes", "notes"))
_SRC_RE = re.compile(r'src="([^"]+)"')


def package_demo(
    asset_root: Path | str,
    profile_id: str,
    *,
    demo_root: Path | str,
    name: str = "summary",
) -> dict[str, Any]:
    asset = Path(asset_root)
    document_path = asset / "views" / profile_id / "document.json"
    outputs = asset / "outputs" / profile_id
    if not document_path.is_file():
        raise ValueError(f"{profile_id} has no authored document to package")

    document = json.loads(document_path.read_text(encoding="utf-8-sig"))
    if not isinstance(document, Mapping):
        raise ValueError("document must be an object")

    formats = _delivered_formats(asset, profile_id)
    demo = Path(demo_root) / asset.name
    demo.mkdir(parents=True, exist_ok=True)

    written: list[str] = []
    for part, default_name in PARTS:
        if part == "notes" and not _has_notes(document):
            continue
        filename = name if part == "main" else default_name
        if "html" in formats and (part == "main" or _has_notes(document)):
            target = demo / f"{filename}.html"
            target.write_text(
                _self_contained_html(document, asset, profile_id, part=part),
                encoding="utf-8",
            )
            written.append(str(target))
        if "pdf" in formats:
            pdf = outputs / ("document.pdf" if part == "main" else "notes.pdf")
            if pdf.is_file():
                target = demo / f"{filename}.pdf"
                shutil.copy2(pdf, target)
                written.append(str(target))
    if not written:
        raise ValueError(f"{profile_id} has nothing to publish for {formats}")
    return {
        "asset": asset.name,
        "profile_id": profile_id,
        "formats": list(formats),
        "demo": str(demo),
        "files": written,
    }


def _delivered_formats(asset: Path, profile_id: str) -> tuple[str, ...]:
    """Read the formats this view was actually selected to deliver."""
    view_manifest = asset / "views" / profile_id / "view-manifest.json"
    if view_manifest.is_file():
        payload = json.loads(view_manifest.read_text(encoding="utf-8-sig"))
        formats = payload.get("formats") if isinstance(payload, Mapping) else None
        if isinstance(formats, list) and formats:
            return tuple(str(item) for item in formats)
    manifest_path = asset / "manifest.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        selections = manifest.get("profile_selections") if isinstance(manifest, Mapping) else None
        selection = selections.get(profile_id) if isinstance(selections, Mapping) else None
        formats = selection.get("formats") if isinstance(selection, Mapping) else None
        if isinstance(formats, list) and formats:
            return tuple(str(item) for item in formats)
    return ("html",)


def _has_notes(document: Mapping[str, Any]) -> bool:
    notes = document.get("notes")
    return isinstance(notes, Mapping) and bool(notes.get("sections"))


def _self_contained_html(
    document: Mapping[str, Any], asset: Path, profile_id: str, *, part: str
) -> str:
    """Render one part and fold every image into the page as a data URI."""
    source_navigation = bool(
        renderer_options_for(profile_id).get("source_navigation", True)
    )
    rendered = render_document_html(
        document, part=part, source_navigation=source_navigation
    )
    return _inline_images(rendered, asset)


def _inline_images(rendered: str, asset: Path) -> str:
    def replace(match: re.Match[str]) -> str:
        source = html.unescape(match.group(1))
        if source.startswith(("data:", "http://", "https://")):
            return match.group(0)
        path = _safe_asset_path(asset, source)
        if not path.is_file():
            raise ValueError(f"document references a missing image: {source}")
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return f'src="data:{mime};base64,{encoded}"'

    return _SRC_RE.sub(replace, rendered)


def _safe_asset_path(asset: Path, relative: str) -> Path:
    candidate = (asset / relative).resolve()
    try:
        candidate.relative_to(asset.resolve())
    except ValueError as exc:
        raise ValueError(f"document artifact escapes the asset root: {relative}") from exc
    return candidate
