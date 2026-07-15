"""Validation for authoring plans aimed at general, in-depth readers."""

from __future__ import annotations

from collections.abc import Mapping


def validate_general_outline(outline: object) -> list[str]:
    """Return errors for a general-deep authoring outline.

    This is deliberately separate from ``validate_teaching_outline``. A
    general-deep view follows the source's argument or practical flow; it does
    not need the pedagogical moves required by the course-notes profile.
    """
    if not isinstance(outline, Mapping):
        return ["general outline must be an object"]

    title = outline.get("title")
    if not isinstance(title, str) or not title.strip():
        return ["general outline title must be present"]

    sections = outline.get("sections")
    if not isinstance(sections, list):
        return ["general outline sections must be a list"]

    errors: list[str] = []
    section_kinds: list[str] = []
    for section_index, section in enumerate(sections, start=1):
        if not isinstance(section, Mapping):
            errors.append(f"section {section_index} must be an object")
            continue
        section_title = section.get("title")
        if not isinstance(section_title, str) or not section_title.strip():
            errors.append(f"section {section_index} title must be present")
        section_kind = section.get("kind")
        if isinstance(section_kind, str):
            section_kinds.append(section_kind)

    if "overview" not in section_kinds:
        errors.append("general outline needs an overview section")
    if section_kinds.count("logical_body") < 2:
        errors.append("general outline needs at least two logical-body sections")
    if not ({"limitations", "uncertainty"} & set(section_kinds)):
        errors.append("general outline needs a limitations-or-uncertainty section")
    if "source_navigation" not in section_kinds:
        errors.append("general outline needs a source-navigation section")
    return errors
