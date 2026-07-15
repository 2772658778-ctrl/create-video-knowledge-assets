from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class SourceSpan(BaseModel):
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_increasing_time_span(self) -> "SourceSpan":
        if self.end_ms <= self.start_ms:
            raise ValueError("end_ms must be greater than start_ms")
        return self


class Evidence(BaseModel):
    evidence_id: str = Field(min_length=1)
    origin: Literal["video", "external", "generated"]
    modality: Literal["metadata", "transcript", "audio", "frame", "document"]
    spans: list[SourceSpan] = Field(default_factory=list)
    content: str = Field(min_length=1)
    artifact_ref: str | None = None
    acquisition: str = Field(min_length=1)
    quality: dict[str, str] = Field(default_factory=dict)
    parent_ids: list[str] = Field(default_factory=list)
    schema_version: str = "1.0"

    @model_validator(mode="after")
    def validate_video_has_source_span(self) -> "Evidence":
        if self.origin == "video" and not self.spans:
            raise ValueError("video evidence requires a source span")
        return self


class KnowledgeUnit(BaseModel):
    unit_id: str = Field(min_length=1)
    type: Literal[
        "concept",
        "claim",
        "mechanism",
        "procedure",
        "example",
        "formula",
        "code",
        "quote",
        "limitation",
        "question",
        "takeaway",
    ]
    title: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    evidence_refs: list[str] = Field(min_length=1)
    epistemic_status: Literal[
        "video_explicit",
        "agent_inference",
        "external_enrichment",
        "insufficient_evidence",
    ]
    importance: Literal["low", "medium", "high"]
    limitations: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    extensions: dict[str, object] = Field(default_factory=dict)
    schema_version: str = "1.0"


DocumentBlockKind = Literal[
    "heading",
    "paragraph",
    "list",
    "table",
    "formula",
    "code",
    "image",
    "caption",
    "callout",
    "quote",
    "summary",
]


class DocumentBlock(BaseModel):
    """A renderer-neutral document block with source-grounding metadata."""

    kind: DocumentBlockKind
    text: str | None = None
    items: list[str] = Field(default_factory=list)
    data: dict[str, object] = Field(default_factory=dict)
    knowledge_refs: list[str] = Field(min_length=1)
    evidence_refs: list[str] = Field(min_length=1)
    source_spans: list[SourceSpan] = Field(default_factory=list)


class DocumentView(BaseModel):
    """A profile-specific, renderer-neutral view of an asset."""

    profile_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    blocks: list[DocumentBlock] = Field(min_length=1)
    evidence_origins: dict[str, Literal["video", "external", "generated"]] = Field(
        default_factory=dict
    )
    schema_version: str = "1.1"


class ProfileSelection(BaseModel):
    """The reproducible explanation for choosing a registered document profile."""

    profile_id: str = Field(min_length=1)
    selection_source: Literal["explicit_profile", "intent_label", "default"]
    reason: str = Field(min_length=1)
    requested: dict[str, str | None]
    requested_formats: tuple[Literal["md", "html", "tex", "pdf"], ...] = ()
    formats: tuple[Literal["md", "html", "tex", "pdf"], ...] = Field(min_length=1)
    schema_version: str = "1.1"

    @model_validator(mode="after")
    def validate_requested_shape(self) -> "ProfileSelection":
        expected = {"explicit_profile", "intent"}
        if set(self.requested) != expected:
            raise ValueError("requested must contain explicit_profile and intent")
        if len(set(self.requested_formats)) != len(self.requested_formats):
            raise ValueError("requested_formats cannot contain duplicates")
        if len(set(self.formats)) != len(self.formats):
            raise ValueError("formats cannot contain duplicates")
        return self


class KnowledgeRelation(BaseModel):
    relation_id: str = Field(min_length=1)
    source_unit_id: str = Field(min_length=1)
    target_unit_id: str = Field(min_length=1)
    relation_type: Literal[
        "prerequisite",
        "explains",
        "supports",
        "contradicts",
        "causes",
        "contrasts",
        "exemplifies",
        "part_of",
    ]
    evidence_refs: list[str] = Field(min_length=1)
    schema_version: str = "1.1"


class Synthesis(BaseModel):
    """Global knowledge-layer synthesis that separates source and agent content."""

    video_summary: str = Field(min_length=1)
    video_summary_refs: list[str] = Field(min_length=1)
    agent_extensions: list[str] = Field(default_factory=list)
    agent_extension_refs: list[str] = Field(min_length=1)
    evidence_refs: list[str] = Field(min_length=1)
    schema_version: str = "1.1"

    @field_validator("agent_extensions")
    @classmethod
    def validate_agent_extensions(cls, extensions: list[str]) -> list[str]:
        if any(not extension.strip() for extension in extensions):
            raise ValueError("agent_extensions cannot contain blank text")
        return extensions
