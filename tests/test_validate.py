from vka.validate import validate_knowledge_evidence_refs, validate_knowledge_graph


def test_missing_evidence_reference_is_reported() -> None:
    errors = validate_knowledge_evidence_refs(
        {"tr-000001"}, [{"unit_id": "ku-001", "evidence_refs": ["tr-404"]}]
    )
    assert errors == ["ku-001 references missing evidence tr-404"]


def test_missing_evidence_refs_is_reported_as_invalid() -> None:
    errors = validate_knowledge_evidence_refs({"tr-000001"}, [{"unit_id": "ku-001"}])

    assert errors == ["ku-001 has invalid evidence_refs"]


def test_empty_evidence_refs_is_reported_as_invalid() -> None:
    errors = validate_knowledge_evidence_refs(
        {"tr-000001"}, [{"unit_id": "ku-001", "evidence_refs": []}]
    )

    assert errors == ["ku-001 has invalid evidence_refs"]


def test_non_list_evidence_refs_is_reported_as_invalid() -> None:
    errors = validate_knowledge_evidence_refs(
        {"tr-000001"}, [{"unit_id": "ku-001", "evidence_refs": "tr-000001"}]
    )

    assert errors == ["ku-001 has invalid evidence_refs"]


def test_non_string_evidence_ref_is_reported_as_invalid() -> None:
    errors = validate_knowledge_evidence_refs(
        {"tr-000001"}, [{"unit_id": "ku-001", "evidence_refs": [123]}]
    )

    assert errors == ["ku-001 has invalid evidence_refs"]


def test_missing_unit_id_is_reported_as_invalid() -> None:
    errors = validate_knowledge_evidence_refs(
        {"tr-000001"}, [{"evidence_refs": ["tr-000001"]}]
    )

    assert errors == ["knowledge row has invalid unit_id"]


def test_knowledge_graph_reports_missing_relation_and_synthesis_units() -> None:
    errors = validate_knowledge_graph(
        {"ku-a"},
        [
            {
                "relation_id": "rel-1",
                "source_unit_id": "ku-a",
                "target_unit_id": "ku-missing",
                "relation_type": "supports",
                "evidence_refs": ["tr-a"],
            }
        ],
        {
            "video_summary": "The source supports this summary.",
            "video_summary_refs": ["ku-a"],
            "agent_extensions": ["The agent makes this extension explicit."],
            "agent_extension_refs": ["ku-missing"],
            "evidence_refs": ["tr-a"],
        },
    )

    assert errors == [
        "relation 1 target_unit_id references missing unit ku-missing",
        "synthesis agent_extension_refs references missing unit ku-missing",
    ]


def test_knowledge_graph_rejects_relation_types_outside_the_schema() -> None:
    errors = validate_knowledge_graph(
        {"ku-a", "ku-b"},
        [
            {
                "relation_id": "rel-1",
                "source_unit_id": "ku-a",
                "target_unit_id": "ku-b",
                "relation_type": "composes",
                "evidence_refs": ["tr-a"],
            }
        ],
        {
            "video_summary": "The source supports this summary.",
            "video_summary_refs": ["ku-a"],
            "agent_extensions": ["The agent makes this extension explicit."],
            "agent_extension_refs": ["ku-b"],
            "evidence_refs": ["tr-a"],
        },
    )

    assert errors == ["relation 1 has invalid relation_type"]


def test_knowledge_graph_rejects_unhashable_relation_type_object() -> None:
    errors = _validate_graph_with_relation_type({})

    assert errors == ["relation 1 has invalid relation_type"]


def test_knowledge_graph_rejects_unhashable_relation_type_list() -> None:
    errors = _validate_graph_with_relation_type([])

    assert errors == ["relation 1 has invalid relation_type"]


def test_knowledge_graph_requires_relation_and_synthesis_contract_fields() -> None:
    errors = validate_knowledge_graph(
        {"ku-a"},
        [
            {
                "source_unit_id": "ku-a",
                "target_unit_id": "ku-a",
                "relation_type": "supports",
            }
        ],
        {
            "video_summary_refs": ["ku-a"],
            "agent_extension_refs": ["ku-a"],
        },
    )

    assert errors == [
        "relation 1 has invalid relation_id",
        "relation 1 has invalid evidence_refs",
        "synthesis has invalid video_summary",
        "synthesis has invalid evidence_refs",
    ]


def test_knowledge_graph_checks_relation_and_synthesis_evidence_references() -> None:
    errors = validate_knowledge_graph(
        {"ku-a"},
        [
            {
                "relation_id": "rel-1",
                "source_unit_id": "ku-a",
                "target_unit_id": "ku-a",
                "relation_type": "supports",
                "evidence_refs": ["tr-missing"],
            }
        ],
        {
            "video_summary": "The source supports this summary.",
            "video_summary_refs": ["ku-a"],
            "agent_extensions": ["The agent makes this extension explicit."],
            "agent_extension_refs": ["ku-a"],
            "evidence_refs": ["tr-missing"],
        },
        {"tr-a"},
    )

    assert errors == [
        "relation 1 evidence_refs references missing evidence tr-missing",
        "synthesis evidence_refs references missing evidence tr-missing",
    ]


def test_knowledge_graph_rejects_blank_agent_extension() -> None:
    errors = validate_knowledge_graph(
        {"ku-a"},
        [
            {
                "relation_id": "rel-1",
                "source_unit_id": "ku-a",
                "target_unit_id": "ku-a",
                "relation_type": "supports",
                "evidence_refs": ["tr-a"],
            }
        ],
        {
            "video_summary": "The source supports this summary.",
            "video_summary_refs": ["ku-a"],
            "agent_extensions": ["  "],
            "agent_extension_refs": ["ku-a"],
            "evidence_refs": ["tr-a"],
        },
    )

    assert errors == ["synthesis has invalid agent_extensions"]


def _validate_graph_with_relation_type(relation_type: object) -> list[str]:
    return validate_knowledge_graph(
        {"ku-a"},
        [
            {
                "relation_id": "rel-1",
                "source_unit_id": "ku-a",
                "target_unit_id": "ku-a",
                "relation_type": relation_type,
                "evidence_refs": ["tr-a"],
            }
        ],
        {
            "video_summary": "The source supports this summary.",
            "video_summary_refs": ["ku-a"],
            "agent_extensions": ["The agent makes this extension explicit."],
            "agent_extension_refs": ["ku-a"],
            "evidence_refs": ["tr-a"],
        },
    )
