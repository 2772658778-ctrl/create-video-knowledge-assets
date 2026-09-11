"""Publish one rendered profile as a demo directory.

Renderers rebase image paths against the asset output directory, so a demo
copy needs the referenced images next to it and the paths rewritten. Doing that
by hand is the same throwaway-script problem the rest of the pipeline avoids.
"""

from __future__ import annotations

import json
import re
import shutil
from collections.abc import Mapping
from pathlib import Path
from typing import Any


IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".webp")
PARTS = ("main", "notes")


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

    demo = Path(demo_root) / asset.name
    figures = demo / "figures"
    figures.mkdir(parents=True, exist_ok=True)

    _copy_artifacts(asset, document, demo, figures)

    written: list[str] = []
    for part, filename in (("main", name), ("notes", "notes")):
        pdf = outputs / ("document.pdf" if part == "main" else "notes.pdf")
        if pdf.is_file():
            target = demo / f"{filename}.pdf"
            shutil.copy2(pdf, target)
            written.append(str(target))
    if not written:
        raise ValueError(f"{profile_id} has no rendered PDF to package")
    return {"asset": asset.name, "profile_id": profile_id, "demo": str(demo), "files": written}


def _copy_artifacts(
    asset: Path,
    document: Mapping[str, Any],
    demo: Path,
    figures: Path,
) -> list[tuple[str, str]]:
    rewrites: list[tuple[str, str]] = []

    cover_ref = document.get("cover_image")
    if isinstance(cover_ref, str) and cover_ref:
        source = _safe_asset_path(asset, cover_ref)
        if source.is_file():
            shutil.copy2(source, demo / f"cover{source.suffix}")
            rewrites.append((cover_ref, f"cover{source.suffix}"))

    for figure_ref in _referenced_figures(document):
        source = _safe_asset_path(asset, figure_ref)
        if not source.is_file():
            raise ValueError(f"document references a missing figure: {figure_ref}")
        shutil.copy2(source, figures / source.name)
        rewrites.append((figure_ref, f"figures/{source.name}"))
    return rewrites


def _referenced_figures(document: Mapping[str, Any]) -> list[str]:
    """Every image the delivered parts actually show, in document order."""
    parts: list[object] = [document.get("sections")]
    notes = document.get("notes")
    if isinstance(notes, Mapping):
        parts.append(notes.get("sections"))

    refs: list[str] = []
    for sections in parts:
        if not isinstance(sections, list):
            continue
        for section in sections:
            if not isinstance(section, Mapping):
                continue
            for block in section.get("blocks") or []:
                if not isinstance(block, Mapping) or block.get("kind") != "image":
                    continue
                path = block.get("path") or block.get("image_path")
                if isinstance(path, str) and path and path not in refs:
                    refs.append(path)
    return refs


def _safe_asset_path(asset: Path, relative: str) -> Path:
    candidate = (asset / relative).resolve()
    try:
        candidate.relative_to(asset.resolve())
    except ValueError as exc:
        raise ValueError(f"document artifact escapes the asset root: {relative}") from exc
    return candidate
