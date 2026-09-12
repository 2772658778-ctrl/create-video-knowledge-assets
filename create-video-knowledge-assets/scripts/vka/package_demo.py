"""Publish one rendered profile as a demo directory.

Renderers rebase image paths against the asset output directory, so a demo
copy needs the referenced images next to it and the paths rewritten. Doing that
by hand is the same throwaway-script problem the rest of the pipeline avoids.
The demo publishes one document twice per part: a PDF for archiving and a
standalone HTML file for continuous reading on screen.
"""

from __future__ import annotations

import copy
import json
import shutil
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from vka.profiles import renderer_options_for
from vka.render_html import render_document_html


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

    rebased = _document_with_demo_paths(asset, document, demo, figures)

    written: list[str] = []
    parts: list[tuple[str, str]] = []
    for part, filename in (("main", name), ("notes", "notes")):
        pdf = outputs / ("document.pdf" if part == "main" else "notes.pdf")
        if pdf.is_file():
            target = demo / f"{filename}.pdf"
            shutil.copy2(pdf, target)
            written.append(str(target))
            parts.append((part, filename))
    if not written:
        raise ValueError(f"{profile_id} has no rendered PDF to package")

    source_navigation = bool(
        renderer_options_for(profile_id).get("source_navigation", True)
    )
    for part, filename in parts:
        target = demo / f"{filename}.html"
        target.write_text(
            render_document_html(
                rebased, part=part, source_navigation=source_navigation
            ),
            encoding="utf-8",
        )
        written.append(str(target))
    return {"asset": asset.name, "profile_id": profile_id, "demo": str(demo), "files": written}


def _document_with_demo_paths(
    asset: Path,
    document: Mapping[str, Any],
    demo: Path,
    figures: Path,
) -> dict[str, Any]:
    """Copy every delivered image next to the demo and repoint the document.

    The HTML has to open on its own, so it may not reach back into the asset
    directory for a cover or a figure.
    """
    rewrites = _copy_artifacts(asset, document, demo, figures)
    rebased = copy.deepcopy(dict(document))

    cover_ref = rebased.get("cover_image")
    if isinstance(cover_ref, str) and cover_ref in rewrites:
        rebased["cover_image"] = rewrites[cover_ref]

    for block in _image_blocks(rebased):
        for container in (block, block.get("data")):
            if not isinstance(container, dict):
                continue
            for key in ("path", "image_path"):
                value = container.get(key)
                if isinstance(value, str) and value in rewrites:
                    container[key] = rewrites[value]
    return rebased


def _copy_artifacts(
    asset: Path,
    document: Mapping[str, Any],
    demo: Path,
    figures: Path,
) -> dict[str, str]:
    """Copy the cover and the cited figures, mapping each old path to its copy."""
    rewrites: dict[str, str] = {}

    cover_ref = document.get("cover_image")
    if isinstance(cover_ref, str) and cover_ref:
        source = _safe_asset_path(asset, cover_ref)
        if source.is_file():
            shutil.copy2(source, demo / f"cover{source.suffix}")
            rewrites[cover_ref] = f"cover{source.suffix}"

    for figure_ref in _referenced_figures(document):
        source = _safe_asset_path(asset, figure_ref)
        if not source.is_file():
            raise ValueError(f"document references a missing figure: {figure_ref}")
        shutil.copy2(source, figures / source.name)
        rewrites[figure_ref] = f"figures/{source.name}"
    return rewrites


def _image_blocks(document: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Every image block of both delivered parts, in document order."""
    parts: list[object] = [document.get("sections")]
    notes = document.get("notes")
    if isinstance(notes, Mapping):
        parts.append(notes.get("sections"))

    blocks: list[Mapping[str, Any]] = []
    for sections in parts:
        if not isinstance(sections, list):
            continue
        for section in sections:
            if not isinstance(section, Mapping):
                continue
            for block in section.get("blocks") or []:
                if isinstance(block, Mapping) and block.get("kind") == "image":
                    blocks.append(block)
    return blocks


def _referenced_figures(document: Mapping[str, Any]) -> list[str]:
    """Every image the delivered parts actually show, in document order."""
    refs: list[str] = []
    for block in _image_blocks(document):
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
