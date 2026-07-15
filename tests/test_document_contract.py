import pytest

from vka.models import DocumentBlock, DocumentView


def test_document_block_requires_knowledge_and_evidence_references() -> None:
    with pytest.raises(ValueError, match="knowledge_refs"):
        DocumentBlock(kind="paragraph", text="Ungrounded prose.", evidence_refs=["tr-1"])

    with pytest.raises(ValueError, match="evidence_refs"):
        DocumentBlock(kind="paragraph", text="Ungrounded prose.", knowledge_refs=["ku-1"])


def test_document_view_requires_profile_id() -> None:
    with pytest.raises(ValueError, match="profile_id"):
        DocumentView.model_validate(
            {
                "title": "Grounded document",
                "blocks": [
                    {
                        "kind": "paragraph",
                        "text": "Grounded prose.",
                        "knowledge_refs": ["ku-1"],
                        "evidence_refs": ["tr-1"],
                    }
                ],
            }
        )


def test_document_view_accepts_an_arbitrary_external_evidence_id_in_catalog() -> None:
    document = DocumentView.model_validate(
        {
            "profile_id": "general-deep",
            "title": "External document",
            "evidence_origins": {"paper-42": "external"},
            "blocks": [
                {
                    "kind": "paragraph",
                    "text": "A paper-backed conclusion.",
                    "knowledge_refs": ["ku-1"],
                    "evidence_refs": ["paper-42"],
                }
            ],
        }
    )

    assert document.evidence_origins == {"paper-42": "external"}
