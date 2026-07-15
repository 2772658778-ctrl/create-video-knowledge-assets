"""Pydantic contracts for grounded answers over video knowledge assets."""

from collections.abc import Iterable, Mapping
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .models import SourceSpan


ClaimStatus = Literal[
    "video_explicit",
    "agent_inference",
    "insufficient_evidence",
]
AnswerBlockKind = Literal["factual", "missing_facet"]
AnswerStatus = Literal[
    "video_explicit",
    "agent_inference",
    "insufficient_evidence",
    "mixed",
    "out_of_scope",
]


def aggregate_answer_status(statuses: Iterable[ClaimStatus]) -> AnswerStatus:
    """Summarize claim provenance; no claims mean insufficient evidence."""

    unique_statuses = set(statuses)
    if not unique_statuses:
        return "insufficient_evidence"
    if len(unique_statuses) == 1:
        return unique_statuses.pop()
    return "mixed"


class AnswerClaim(BaseModel):
    """A single answer proposition grounded in knowledge and evidence records."""

    model_config = ConfigDict(extra="forbid")

    claim_id: str | None = None
    text: str = Field(min_length=1)
    status: ClaimStatus
    knowledge_refs: list[str] = Field(min_length=1)
    evidence_refs: list[str] = Field(min_length=1)
    source_spans: list[SourceSpan] = Field(default_factory=list)

    @field_validator("claim_id", "text")
    @classmethod
    def validate_text(cls, text: str | None) -> str | None:
        if text is None:
            return text
        if not text.strip():
            raise ValueError("text and claim_id must not be blank")
        return text

    @field_validator("knowledge_refs", "evidence_refs")
    @classmethod
    def validate_references(cls, references: list[str]) -> list[str]:
        if any(not reference.strip() for reference in references):
            raise ValueError("references must not contain blank values")
        return references

    @model_validator(mode="after")
    def validate_video_claim_has_source_spans(self) -> "AnswerClaim":
        if self.status == "video_explicit" and not self.source_spans:
            raise ValueError("video_explicit claims require source_spans")
        return self


class AnswerBlock(BaseModel):
    """An ordered rendered answer segment bound to grounded claims."""

    model_config = ConfigDict(extra="forbid")

    block_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    heading: str | None = None
    purpose: str | None = None
    kind: AnswerBlockKind = "factual"
    claim_refs: list[str] = Field(default_factory=list)

    @field_validator("block_id", "text", "heading", "purpose")
    @classmethod
    def validate_text(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("block text fields must not be blank")
        return value

    @field_validator("claim_refs")
    @classmethod
    def validate_claim_refs(cls, references: list[str]) -> list[str]:
        if any(not reference.strip() for reference in references):
            raise ValueError("claim_refs must not contain blank values")
        if len(set(references)) != len(references):
            raise ValueError("claim_refs must not contain duplicates")
        return references

    @model_validator(mode="after")
    def validate_kind(self) -> "AnswerBlock":
        if self.kind == "factual" and not self.claim_refs:
            raise ValueError("factual blocks must reference one or more claims")
        if self.kind == "missing_facet" and self.claim_refs:
            raise ValueError("missing_facet blocks must not reference claims")
        return self


class AnswerExtension(BaseModel):
    """Clearly labelled non-video material kept separate from answer claims."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["agent_background", "exploration"]
    text: str = Field(min_length=1)
    visible_label: Literal[
        "\u672a\u7ecf\u9a8c\u8bc1\u7684\u6a21\u578b\u80cc\u666f\uff08\u975e\u89c6\u9891\u7ed3\u8bba\uff09",
        "\u53d1\u6563\u8ba8\u8bba\uff0c\u975e\u89c6\u9891\u7ed3\u8bba",
    ]

    @field_validator("text")
    @classmethod
    def validate_text(cls, text: str) -> str:
        if not text.strip():
            raise ValueError("text must not be blank")
        return text

    @model_validator(mode="after")
    def validate_label_for_kind(self) -> "AnswerExtension":
        expected_label = {
            "agent_background": "\u672a\u7ecf\u9a8c\u8bc1\u7684\u6a21\u578b\u80cc\u666f\uff08\u975e\u89c6\u9891\u7ed3\u8bba\uff09",
            "exploration": "\u53d1\u6563\u8ba8\u8bba\uff0c\u975e\u89c6\u9891\u7ed3\u8bba",
        }[self.kind]
        if self.visible_label != expected_label:
            raise ValueError("visible_label must match the extension kind")
        return self


class ExplicitModelBackgroundRequest(BaseModel):
    """Caller-recorded proof that a user explicitly requested model background."""

    model_config = ConfigDict(extra="forbid")
    request_source: Literal["user_explicit"]
    request_text: str = Field(min_length=1)

    @field_validator("request_text")
    @classmethod
    def validate_request_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("model background request_text must not be blank")
        return value


class ExternalClaim(BaseModel):
    """A non-video proposition cited only through the external namespace."""

    model_config = ConfigDict(extra="forbid")
    claim_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    external_evidence_refs: list[str] = Field(min_length=1)

    @field_validator("claim_id", "text")
    @classmethod
    def validate_external_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("external claim text must not be blank")
        return value

    @field_validator("external_evidence_refs")
    @classmethod
    def validate_external_refs(cls, values: list[str]) -> list[str]:
        if any(not value.startswith("external:") for value in values):
            raise ValueError("external claims must use external: evidence IDs")
        if len(set(values)) != len(values):
            raise ValueError("external_evidence_refs must not contain duplicates")
        return values


class ExternalBlock(BaseModel):
    """Visible non-video section which cannot carry video claim references."""

    model_config = ConfigDict(extra="forbid")
    block_id: str = Field(min_length=1)
    kind: Literal["background", "comparison", "research"]
    heading: str = Field(min_length=1)
    text: str = Field(min_length=1)
    claim_refs: list[str] = Field(min_length=1)

    @field_validator("block_id", "heading", "text")
    @classmethod
    def validate_external_block_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("external block text must not be blank")
        return value

    @field_validator("heading")
    @classmethod
    def require_non_video_heading(cls, value: str) -> str:
        normalized = value.lower()
        if not any(label in normalized for label in ("非视频", "外部", "non-video", "external")):
            raise ValueError("external block heading must visibly identify non-video material")
        return value

    @model_validator(mode="after")
    def require_kind_label(self) -> "ExternalBlock":
        normalized = self.heading.lower()
        required = {
            "background": ("背景", "background"),
            "comparison": ("比较", "对比", "comparison"),
            "research": ("研究", "检索", "research"),
        }[self.kind]
        if not any(marker in normalized for marker in required):
            raise ValueError("external block heading must visibly label its kind")
        return self

    @field_validator("claim_refs")
    @classmethod
    def validate_external_claim_refs(cls, values: list[str]) -> list[str]:
        if any(not value.strip() for value in values) or len(set(values)) != len(values):
            raise ValueError("external block claim_refs must be unique non-empty strings")
        return values


class SourceConflict(BaseModel):
    """A visible version difference supported by external, never implicit, evidence."""

    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1)
    video_claim_refs: list[str] = Field(min_length=1)
    external_evidence_refs: list[str] = Field(min_length=1)

    @field_validator("text")
    @classmethod
    def require_visible_conflict_disclosure(cls, value: str) -> str:
        normalized = value.lower()
        required_groups = (
            ("视频", "video"),
            ("外部", "来源", "文档", "external", "source"),
            ("版本", "条件", "适用", "version", "condition"),
            ("不同", "差异", "不一致", "冲突", "differ", "conflict"),
        )
        if not all(any(marker in normalized for marker in group) for group in required_groups):
            raise ValueError("source conflict text must state video practice, external version or conditions, and disagreement")
        return value

    @field_validator("video_claim_refs", "external_evidence_refs")
    @classmethod
    def validate_conflict_ref_list(cls, values: list[str]) -> list[str]:
        if len(set(values)) != len(values):
            raise ValueError("source conflict refs must not contain duplicates")
        return values

    @field_validator("external_evidence_refs")
    @classmethod
    def validate_conflict_refs(cls, values: list[str]) -> list[str]:
        if any(not value.startswith("external:") for value in values):
            raise ValueError("source conflicts must use external: evidence IDs")
        return values


def _contains_extension_shape(value: object) -> bool:
    if isinstance(value, AnswerExtension):
        return True
    if isinstance(value, Mapping):
        if value.get("kind") in {"agent_background", "exploration"} or "visible_label" in value:
            return True
        return any(_contains_extension_shape(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_extension_shape(item) for item in value)
    return False


def _states_video_does_not_cover(answer: str) -> bool:
    normalized = "".join(answer.lower().split())
    if any(
        phrase in normalized
        for phrase in ("doesnotcover", "notcovered", "outsidescope", "outofscope")
    ):
        return True
    if "\u89c6\u9891" not in normalized:
        return False
    return any(
        phrase in normalized
        for phrase in (
            "\u4e0d\u8986\u76d6",
            "\u672a\u8986\u76d6",
            "\u6ca1\u6709\u8986\u76d6",
            "\u672a\u6d89\u53ca",
            "\u6ca1\u6709\u6d89\u53ca",
            "\u4e0d\u5305\u542b",
            "\u672a\u5305\u542b",
            "\u4e2d\u6ca1\u6709",
            "\u4e2d\u672a",
        )
    )


class GroundedAnswer(BaseModel):
    """Answer payload whose citations can be reconciled by a later validator."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0", "1.1", "1.2"] = "1.0"
    asset_id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    mode: Literal["video_only", "video_plus_context", "explore"]
    answer_status: AnswerStatus
    claims: list[AnswerClaim] = Field(default_factory=list)
    blocks: list[AnswerBlock] = Field(default_factory=list)
    answer_plan: dict[str, object] | None = None
    knowledge_refs: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    source_spans: list[SourceSpan] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    extensions: list[AnswerExtension] = Field(default_factory=list)
    external_claims: list[ExternalClaim] = Field(default_factory=list)
    external_blocks: list[ExternalBlock] = Field(default_factory=list)
    source_conflicts: list[SourceConflict] = Field(default_factory=list)
    model_background_request: ExplicitModelBackgroundRequest | None = None
    retrieval: dict[str, object]

    @field_validator("asset_id", "question", "answer")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("field must not be blank")
        return value

    @field_validator("knowledge_refs", "evidence_refs")
    @classmethod
    def validate_references(cls, references: list[str]) -> list[str]:
        if any(not reference.strip() for reference in references):
            raise ValueError("references must not contain blank values")
        return references

    @model_validator(mode="before")
    @classmethod
    def reject_extensions_in_claims(cls, value: object) -> object:
        if isinstance(value, Mapping):
            if _contains_extension_shape(value.get("claims", [])):
                raise ValueError("extensions must stay outside answer claims")
            if _contains_extension_shape(value.get("blocks", [])):
                raise ValueError("extensions must stay outside answer blocks")
        return value

    @model_validator(mode="after")
    def validate_mode_and_scope(self) -> "GroundedAnswer":
        if self.mode == "video_only" and (
            self.extensions or self.external_claims or self.external_blocks or self.source_conflicts
        ):
            raise ValueError("video_only answers cannot include non-video sections")
        if self.extensions and self.model_background_request is None:
            raise ValueError("model-background extensions require a recorded explicit user request")
        if self.model_background_request is not None and not self.extensions:
            raise ValueError("model background request must not be present without a model-background extension")
        if self.mode in {"video_plus_context", "explore"}:
            if self.schema_version != "1.2":
                raise ValueError("context modes require schema_version 1.2")
            if not self.external_claims or not self.external_blocks:
                raise ValueError("context modes require separate external_claims and external_blocks")
            claim_ids = [claim.claim_id for claim in self.external_claims]
            if len(set(claim_ids)) != len(claim_ids):
                raise ValueError("external claim_id values must be unique")
            referenced = {claim_id for block in self.external_blocks for claim_id in block.claim_refs}
            if referenced != set(claim_ids):
                raise ValueError("external_blocks must reference every external claim exactly by ID")
            if len({block.block_id for block in self.external_blocks}) != len(self.external_blocks):
                raise ValueError("external block_id values must be unique")
            external_kinds = {block.kind for block in self.external_blocks}
            if self.mode == "video_plus_context" and external_kinds != {"background"}:
                raise ValueError("video_plus_context permits external background blocks only")
            if self.mode == "explore" and not external_kinds & {"comparison", "research"}:
                raise ValueError("explore requires a visibly labelled comparison or research block")
        if self.answer_plan is not None and self.answer_plan.get("mode") != self.mode:
            raise ValueError("answer_plan mode must match answer mode")
        if self.answer_status == "out_of_scope":
            if self.claims:
                raise ValueError("out_of_scope answers cannot include claims")
            if not _states_video_does_not_cover(self.answer):
                raise ValueError(
                    "out_of_scope answers must state that the video asset does not cover the question"
                )
        elif self.answer_status != aggregate_answer_status(
            claim.status for claim in self.claims
        ):
            raise ValueError("answer_status must equal aggregated claim statuses")
        self._validate_blocks()
        return self

    def _validate_blocks(self) -> None:
        if self.schema_version == "1.0":
            if self.blocks:
                raise ValueError("1.0 answers cannot include blocks")
            if self.answer_plan is not None:
                raise ValueError("1.0 answers cannot include answer_plan metadata")
            return

        if not self.blocks:
            raise ValueError("1.1 answers require blocks")
        claim_ids = [claim.claim_id for claim in self.claims]
        if any(claim_id is None for claim_id in claim_ids):
            raise ValueError("1.1 claims require claim_id")
        normalized_claim_ids = [claim_id for claim_id in claim_ids if claim_id is not None]
        if len(set(normalized_claim_ids)) != len(normalized_claim_ids):
            raise ValueError("1.1 claim_id values must be unique")

        block_ids = [block.block_id for block in self.blocks]
        if len(set(block_ids)) != len(block_ids):
            raise ValueError("1.1 block_id values must be unique")
        referenced_claim_ids = {
            claim_id for block in self.blocks for claim_id in block.claim_refs
        }
        unknown_claim_ids = referenced_claim_ids - set(normalized_claim_ids)
        if unknown_claim_ids:
            raise ValueError("blocks reference unknown claim_id values")
        if referenced_claim_ids != set(normalized_claim_ids):
            raise ValueError("every claim must be referenced by a factual block")

        rendered_answer = "\n\n".join(block.text for block in self.blocks)
        if self.mode in {"video_plus_context", "explore"}:
            rendered_answer = self._render_context_answer(rendered_answer)
        if self.answer != rendered_answer:
            raise ValueError("answer must be derived from its visible block sections exactly")
        if not self.answer_plan:
            raise ValueError("1.1 answers require a non-empty answer_plan")
        planned_claims = _validate_answer_plan_metadata(self.answer_plan)
        answer_blocks = {block.block_id: block for block in self.blocks}
        for block_id, expected_claim_ids in planned_claims.items():
            answer_block = answer_blocks.get(block_id)
            if answer_block is None or answer_block.kind != "factual":
                raise ValueError("every planned factual block must be rendered as a factual answer block")
            if set(answer_block.claim_refs) != expected_claim_ids:
                raise ValueError("answer block claim_refs must match its plan expected_claim_ids")
        if set(normalized_claim_ids) != set().union(*planned_claims.values()):
            raise ValueError("1.1 claim_id values must equal the plan expected_claim_ids")

    def _render_context_answer(self, video_body: str) -> str:
        """Keep every P4.2 section visibly separate in the delivered answer."""

        sections = [f"视频依据\n{video_body}"]
        if self.limitations:
            sections.append("视频推断与限制\n" + "\n".join(self.limitations))
        sections.extend(
            f"{block.heading}\n{block.text}" for block in self.external_blocks
        )
        if self.source_conflicts:
            sections.append(
                "版本差异或来源冲突\n"
                + "\n".join(conflict.text for conflict in self.source_conflicts)
            )
        sections.extend(
            f"{extension.visible_label}\n{extension.text}"
            for extension in self.extensions
        )
        return "\n\n".join(sections)


def _validate_answer_plan_metadata(answer_plan: dict[str, object]) -> dict[str, set[str]]:
    """Keep retained plan metadata as structure and references, never prose."""

    allowed_top_level = {
        "schema_version",
        "question",
        "mode",
        "inferred_intent",
        "selected_facets",
        "missing_facets",
        "blocks",
        "limitations",
    }
    if set(answer_plan) - allowed_top_level:
        raise ValueError("answer_plan contains unknown properties")
    blocks = answer_plan.get("blocks")
    if not isinstance(blocks, list):
        raise ValueError("answer_plan blocks must be a list")
    allowed_block_keys = {
        "block_id",
        "authoring_purpose",
        "expected_claim_ids",
        "knowledge_refs",
        "evidence_refs",
        "source_spans",
        "evidence_window_ids",
        "relation_refs",
    }
    block_ids: set[str] = set()
    expected_by_block: dict[str, set[str]] = {}
    all_expected_claim_ids: set[str] = set()
    for index, block in enumerate(blocks, start=1):
        if not isinstance(block, Mapping):
            raise ValueError(f"answer_plan block {index} must be an object")
        if set(block) - allowed_block_keys:
            raise ValueError("answer_plan blocks contain unknown properties")
        block_id = block.get("block_id")
        if not isinstance(block_id, str) or not block_id.strip():
            raise ValueError("answer_plan block_id must be a non-empty string")
        if block_id in block_ids:
            raise ValueError("answer_plan block_id values must be unique")
        block_ids.add(block_id)
        expected_claim_ids = block.get("expected_claim_ids")
        if not isinstance(expected_claim_ids, list) or not expected_claim_ids or not all(
            isinstance(claim_id, str) and claim_id.strip() for claim_id in expected_claim_ids
        ):
            raise ValueError("answer_plan expected_claim_ids must be a non-empty string list")
        if len(set(expected_claim_ids)) != len(expected_claim_ids):
            raise ValueError("answer_plan expected_claim_ids must not contain duplicates")
        if all_expected_claim_ids & set(expected_claim_ids):
            raise ValueError("answer_plan expected_claim_ids must be unique across blocks")
        expected_by_block[block_id] = set(expected_claim_ids)
        all_expected_claim_ids.update(expected_claim_ids)
        if _contains_extension_shape(block):
            raise ValueError("answer_plan blocks cannot contain extensions")
        if any(key in block for key in ("text", "content", "statement", "answer", "claims")):
            raise ValueError("answer_plan blocks must be reference-only")
    return expected_by_block
