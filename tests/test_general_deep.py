from vka.general_deep import validate_general_outline


def test_general_outline_requires_body_and_source_navigation_sections() -> None:
    outline = {
        "title": "Interview with a database engineer",
        "sections": [
            {"kind": "overview", "title": "What the conversation covers"},
            {"kind": "limitations", "title": "What remains uncertain"},
        ],
    }

    assert validate_general_outline(outline) == [
        "general outline needs at least two logical-body sections",
        "general outline needs a source-navigation section",
    ]


def test_general_outline_accepts_a_general_reader_structure() -> None:
    outline = {
        "title": "Interview with a database engineer",
        "sections": [
            {"kind": "overview", "title": "What the conversation covers"},
            {"kind": "logical_body", "title": "The central point"},
            {"kind": "logical_body", "title": "Reasons and trade-offs"},
            {"kind": "limitations", "title": "What remains uncertain"},
            {"kind": "source_navigation", "title": "Where each point came from"},
        ],
    }

    assert validate_general_outline(outline) == []


def test_general_outline_requires_overview_and_limits_or_uncertainty() -> None:
    outline = {
        "title": "Interview with a database engineer",
        "sections": [
            {"kind": "logical_body", "title": "The central point"},
            {"kind": "logical_body", "title": "Reasons and trade-offs"},
            {"kind": "source_navigation", "title": "Where each point came from"},
        ],
    }

    assert validate_general_outline(outline) == [
        "general outline needs an overview section",
        "general outline needs a limitations-or-uncertainty section",
    ]


def test_general_outline_rejects_non_object_sections_and_missing_titles() -> None:
    outline = {
        "title": "Interview with a database engineer",
        "sections": [
            {"kind": "overview", "title": "What the conversation covers"},
            {"kind": "logical_body", "title": "The central point"},
            {"kind": "logical_body", "title": "   "},
            "not a section object",
            {"kind": "limitations", "title": "What remains uncertain"},
            {"kind": "source_navigation", "title": "Where each point came from"},
        ],
    }

    errors = validate_general_outline(outline)

    assert "section 3 title must be present" in errors
    assert "section 4 must be an object" in errors
