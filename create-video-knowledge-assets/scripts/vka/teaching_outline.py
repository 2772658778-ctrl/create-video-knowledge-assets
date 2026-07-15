from __future__ import annotations

from collections.abc import Mapping
from typing import Any


CORE_MOVES = {
    "motivation",
    "wrong_intuition",
    "mechanism",
    "worked_example",
    "formula_or_visual",
    "misconception",
    "takeaway",
}
FINAL_MOVES = {"synthesis", "practice", "takeaway"}


def validate_teaching_outline(outline: object) -> list[str]:
    """Return errors for a reader-facing teaching outline."""
    if not isinstance(outline, Mapping):
        return ["teaching outline must be an object"]

    sections = outline.get("sections")
    if not isinstance(sections, list):
        return ["teaching outline sections must be a list"]
    if len(sections) < 3:
        return ["teaching outline must contain at least three teaching sections"]

    errors: list[str] = []
    for section_index, section in enumerate(sections, start=1):
        if not isinstance(section, Mapping):
            errors.append(f"section {section_index} must be an object")
            continue
        title = section.get("title")
        if not isinstance(title, str) or not title.strip():
            errors.append(f"section {section_index} title must be present")

        moves = section.get("moves")
        if not isinstance(moves, list) or not moves:
            errors.append(f"section {section_index} must contain teaching moves")
            continue

        move_kinds: set[str] = set()
        text_chars = 0
        for move_index, move in enumerate(moves, start=1):
            if not isinstance(move, Mapping):
                errors.append(f"section {section_index} move {move_index} must be an object")
                continue
            kind = move.get("kind")
            if not isinstance(kind, str) or not kind:
                errors.append(f"section {section_index} move {move_index} kind must be present")
            else:
                move_kinds.add(kind)

            text = move.get("text")
            if not isinstance(text, str) or len(text.strip()) < 40:
                errors.append(
                    f"section {section_index} move {move_index} needs teaching prose"
                )
            else:
                text_chars += len(text)

            refs = move.get("evidence_refs")
            if not isinstance(refs, list) or not refs or not all(
                isinstance(ref, str) and ref for ref in refs
            ):
                errors.append(
                    f"section {section_index} move {move_index} needs evidence_refs"
                )

        is_final = section_index == len(sections) or _is_final_title(title)
        if is_final:
            missing = sorted(FINAL_MOVES - move_kinds)
            if missing:
                errors.append(
                    f"final section {section_index} is missing teaching moves: {', '.join(missing)}"
                )
        else:
            if "mechanism" not in move_kinds:
                errors.append(f"section {section_index} is missing a mechanism move")
            if "takeaway" not in move_kinds:
                errors.append(f"section {section_index} is missing a takeaway move")
            if not ({"motivation", "wrong_intuition"} & move_kinds):
                errors.append(
                    f"section {section_index} needs motivation or wrong_intuition"
                )
            if not ({"worked_example", "formula_or_visual"} & move_kinds):
                errors.append(
                    f"section {section_index} needs a worked_example or formula_or_visual move"
                )

        min_chars = 220 if is_final else 260
        if text_chars < min_chars:
            errors.append(f"section {section_index} is too thin for a course-note chapter")

    return errors


def _is_final_title(title: object) -> bool:
    return isinstance(title, str) and any(
        marker in title for marker in ("总结", "延伸", "复习", "练习", "synthesis")
    )
