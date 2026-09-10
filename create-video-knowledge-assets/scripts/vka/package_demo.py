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


TEXT_SUFFIXES = ("md", "html")
IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".webp")


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

    rewrites = _copy_artifacts(asset, document, demo, figures)
    written: list[str] = []
    for suffix in TEXT_SUFFIXES:
        source = outputs / f"document.{suffix}"
        if not source.is_file():
            continue
        text = source.read_text(encoding="utf-8")
        for artifact_ref, local in rewrites:
            text = text.replace(f"../../{artifact_ref}", local)
            text = text.replace(artifact_ref, local)
        text = re.sub(r"!\[[^\]]*\]\((?!#|https?://|figures/|cover\.)[^)]+\)", "", text)
        text = re.sub(r'<img src="(?!#|https?://|figures/|cover\.)[^"]+"[^>]*>', "", text)
        target = demo / f"{name}.{suffix}"
        target.write_text(text, encoding="utf-8")
        written.append(str(target))

    pdf = outputs / "document.pdf"
    if pdf.is_file():
        target = demo / f"{name}.pdf"
        shutil.copy2(pdf, target)
        written.append(str(target))

    for figure in sorted(figures.glob("*")):
        if figure.name not in "".join(
            (demo / f"{name}.{suffix}").read_text(encoding="utf-8")
            for suffix in TEXT_SUFFIXES
            if (demo / f"{name}.{suffix}").is_file()
        ):
            figure.unlink()

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

    frame_dir = asset / "evidence" / "frames" / "inspected"
    for frame in sorted(frame_dir.glob("*")) if frame_dir.is_dir() else []:
        if frame.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        shutil.copy2(frame, figures / frame.name)
        rewrites.append((f"evidence/frames/inspected/{frame.name}", f"figures/{frame.name}"))
    return rewrites


def _safe_asset_path(asset: Path, relative: str) -> Path:
    candidate = (asset / relative).resolve()
    try:
        candidate.relative_to(asset.resolve())
    except ValueError as exc:
        raise ValueError(f"document artifact escapes the asset root: {relative}") from exc
    return candidate
