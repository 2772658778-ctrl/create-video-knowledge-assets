from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from copy import deepcopy
import os
from pathlib import Path, PureWindowsPath
from typing import Any


PLACEHOLDER_RE = re.compile(r"(\?{3,}|？{3,}|�|□)")
FINAL_TITLE_RE = re.compile(r"(总结|小结|延伸|练习|实践)")
SUMMARY_TITLE_RE = re.compile(r"(本章小结|章节小结|小结)")
VISIBLE_SOURCE_TIME_RE = re.compile(r"(来源时间|视频画面时间区间|source[_ -]?spans)")
CORE_SIGNAL_RE = re.compile(r"(核心|主线|一句话|总览|为什么|问题|动机|导读)")
INTERNAL_LABEL_RE = re.compile(
    r"^\s*(synthesis|summary|outline|takeaway|motivation|mechanism|practice|"
    r"transition|worked_example|formula_or_visual)\s*[:：-]",
    re.IGNORECASE,
)
CREATOR_OUTCOME_RE = re.compile(
    r"(?:我|本人|笔者|作者).{0,24}(?:亲自|亲身|实操|实践).{0,48}"
    r"(?:赚|获利|收入|营收|成交|客户|粉丝|订单)",
    re.DOTALL,
)
CREATOR_AUTHOR_RESULT_RE = re.compile(
    r"(?:我|本人|笔者|作者).{0,40}(?:赚到|赚了|获利|收入|营收|成交|订单|客户)",
    re.DOTALL,
)
ENTERPRISE_ACTION_RE = re.compile(
    r"(?:下周|本周|明天|必须|上线|负责人|执行人|截止|到期|行动项|待办|"
    r"owner|due(?:\s+date)?|action\s+item|must\s+(?:ship|launch)|decision)",
    re.IGNORECASE,
)
INSUFFICIENT_EVIDENCE_RE = re.compile(
    r"(?:证据不足|未在视频中说明|视频未说明|需要确认|待确认|未知|"
    r"insufficient\s+evidence|not\s+stated|needs?\s+confirmation)",
    re.IGNORECASE,
)
SHORT_VIDEO_SCRIPT_ABSTRACT_RE = re.compile(
    r"(?:总结来说|总的来说|本质上|核心在于|一句话|换句话说|从多个角度|"
    r"简单来说|大家可以看到|我们可以看到|你会发现|非常重要|值得注意|"
    r"有必要|可以理解为|抽象地说|意义很大|很多人会|都是为了)",
    re.IGNORECASE,
)
SHORT_VIDEO_SCRIPT_CONCRETE_RE = re.compile(
    r"(?:\d|比如|例如|案例|镜头|画面|字幕|台词|步骤|对比|数据|实验|"
    r"场景|按钮|页面|参数|公式|模型|函数|代码|人物|地点|时间点)",
    re.IGNORECASE,
)

SHORT_VIDEO_SCRIPT_VACUOUS_PHRASES = (
    "总结来说",
    "总的来说",
    "本质上",
    "核心在于",
    "一句话",
    "换句话说",
    "从多个角度",
    "简单来说",
    "大家可以看到",
    "我们可以看到",
    "你会发现",
    "非常重要",
    "值得注意",
    "有必要",
    "可以理解为",
    "抽象地说",
    "意义很大",
    "很多人会",
    "都是为了",
)

# Short-form scripts are spoken, not read. Two openings end a video before it
# starts and two endings hand the viewer a moral instead of a thought, so the
# gate names them instead of leaving the difference to taste.
SHORT_VIDEO_SCRIPT_ANNOUNCEMENT_OPENERS = re.compile(
    r"^\s*(?:大家好|各位好|哈喽|hello|hi\b|今天(?:我们|我来|我来给|给大家)|"
    r"本期视频|这个视频|这一期|在这期)",
    re.IGNORECASE,
)
SHORT_VIDEO_SCRIPT_LESSON_ENDINGS = (
    "希望对你有所帮助",
    "希望对你有帮助",
    "希望这个视频",
    "希望你能",
    "记住这句话",
    "最后想说的是",
    "与大家共勉",
    "共勉",
    "愿你我",
)
SHORT_VIDEO_SCRIPT_WRITTEN_CONNECTIVES = (
    "综上所述",
    "综上",
    "总而言之",
    "由此可见",
    "因此",
)


def validate_course_document_quality(document: object) -> list[str]:
    """Return quality errors that would make a P1 course-note document unreadable."""
    errors: list[str] = []
    if not isinstance(document, Mapping):
        return ["course document must be an object"]

    title = document.get("title")
    if not isinstance(title, str) or not title.strip():
        errors.append("course document title must be present")
    elif PLACEHOLDER_RE.search(title):
        errors.append("course document title contains unresolved placeholders")

    teaching_outline_ref = document.get("teaching_outline_ref")
    if not isinstance(teaching_outline_ref, str) or not teaching_outline_ref.strip():
        errors.append("course document must reference a validated teaching outline")

    theme = document.get("theme")
    if not isinstance(theme, str) or len(theme.strip()) < 4:
        errors.append("course document must include a concise theme for the title page")

    one_sentence_summary = document.get("one_sentence_summary")
    if not isinstance(one_sentence_summary, str) or len(one_sentence_summary.strip()) < 12:
        errors.append("course document must include a one-sentence core summary")

    metadata = document.get("metadata")
    if not isinstance(metadata, Mapping):
        errors.append("course document must include title-page source metadata")
    else:
        if not _metadata_text(metadata, "source_title"):
            errors.append("title-page metadata must include source_title")
        if not (_metadata_text(metadata, "author") or _metadata_text(metadata, "uploader")):
            errors.append("title-page metadata must include author or uploader")
        if not _metadata_text(metadata, "publish_date"):
            errors.append("title-page metadata must include publish_date")
        if not (
            _metadata_text(metadata, "subtitle_source")
            or _metadata_text(metadata, "transcript_source")
            or _metadata_text(metadata, "data_sources")
        ):
            errors.append("title-page metadata must describe subtitle/transcript data sources")

    sections = document.get("sections")
    if not isinstance(sections, list):
        return errors + ["course document sections must be a list"]

    if len(sections) < 4:
        errors.append("course document must contain at least four teaching sections")

    paragraph_chars = 0
    image_count = 0
    has_teaching_box = False
    has_final_section = False
    has_short_only_spans = True

    for index, section in enumerate(sections, start=1):
        if not isinstance(section, Mapping):
            errors.append(f"section {index} must be an object")
            continue
        section_title = section.get("title")
        is_final_section = False
        if not isinstance(section_title, str) or not section_title.strip():
            errors.append(f"section {index} title must be present")
        elif PLACEHOLDER_RE.search(section_title):
            errors.append(f"section {index} title contains unresolved placeholders")
        elif INTERNAL_LABEL_RE.search(section_title):
            errors.append(f"section {index} title leaks internal outline labels")
        elif FINAL_TITLE_RE.search(section_title):
            has_final_section = True
            is_final_section = True

        blocks = section.get("blocks")
        if not isinstance(blocks, list) or not blocks:
            errors.append(f"section {index} must contain content blocks")
            continue

        summary_subsections = 0
        semantic_subsections = 0
        for block_index, block in enumerate(blocks, start=1):
            if not isinstance(block, Mapping):
                errors.append(f"section {index} block {block_index} must be an object")
                continue
            kind = block.get("kind")
            text = _block_text(block)
            if kind != "subsection" and not _valid_refs(block.get("evidence_refs")):
                errors.append(f"section {index} block {block_index} must preserve evidence_refs")
            if text and PLACEHOLDER_RE.search(text):
                errors.append(
                    f"section {index} block {block_index} contains unresolved placeholders"
                )
            if text and VISIBLE_SOURCE_TIME_RE.search(text):
                errors.append(
                    f"section {index} block {block_index} leaks source-time audit text"
                )
            if kind == "paragraph":
                paragraph_chars += len(text)
                if len(text) < 30:
                    errors.append(
                        f"section {index} paragraph {block_index} is too short for teaching notes"
                    )
                if _has_long_span(block):
                    has_short_only_spans = False
            elif kind == "image":
                image_count += 1
                if not isinstance(block.get("caption"), str) or len(block["caption"]) < 12:
                    errors.append(f"section {index} image {block_index} needs a specific caption")
                if _has_long_span(block):
                    has_short_only_spans = False
            elif kind in {"importantbox", "knowledgebox", "warningbox"}:
                has_teaching_box = True
                paragraph_chars += len(text)
                if _has_long_span(block):
                    has_short_only_spans = False
            elif kind in {"bullet_list", "numbered_list", "formula", "code", "quote", "subsection"}:
                paragraph_chars += len(text)
                if _has_long_span(block):
                    has_short_only_spans = False
            else:
                errors.append(f"section {index} block {block_index} has unsupported kind {kind!r}")

            if kind == "subsection":
                block_title = block.get("title")
                if isinstance(block_title, str):
                    if INTERNAL_LABEL_RE.search(block_title):
                        errors.append(
                            f"section {index} subsection {block_index} leaks internal outline labels"
                        )
                    if SUMMARY_TITLE_RE.search(block_title):
                        summary_subsections += 1
                    else:
                        semantic_subsections += 1
                else:
                    semantic_subsections += 1

        if index < len(sections) and not is_final_section and semantic_subsections < 2:
            errors.append(
                f"section {index} needs at least two teaching subsections before its summary"
            )
        if index < len(sections) and not is_final_section and summary_subsections < 1:
            errors.append(f"section {index} is missing a chapter summary subsection/block")
        if is_final_section and semantic_subsections < 2:
            errors.append("final synthesis section needs at least two structured subsections")

        if index == 1 and not is_final_section:
            errors.extend(_first_section_errors(section, blocks))

    if paragraph_chars < 900:
        errors.append("course document prose is too short; expand explanations before rendering")
    if image_count < 2:
        errors.append("course document needs at least two inspected teaching images")
    if not has_teaching_box:
        errors.append("course document should include at least one high-signal teaching box")
    if not has_final_section:
        errors.append("course document needs a final synthesis/extension section")
    if has_short_only_spans:
        errors.append("source spans are too narrow; use transcript windows, not one-second guesses")

    return errors


def validate_document_quality(document: object, *, profile_id: str | None = None) -> list[str]:
    """Return profile-aware errors for renderer-neutral document views.

    This deliberately does not reuse the P1 course-note gate: a general reader
    needs source navigation and limits, not a course recap or two illustrations.
    """
    errors: list[str] = []
    if not isinstance(document, Mapping):
        return ["document must be an object"]

    selected_profile = profile_id if profile_id is not None else document.get("profile_id")
    if not isinstance(selected_profile, str) or not selected_profile.strip():
        errors.append("document profile_id must be present")
    declared_profile = document.get("profile_id")
    if profile_id is not None and declared_profile != profile_id:
        errors.append("document profile_id must match selected profile")
    title = document.get("title")
    if not isinstance(title, str) or not title.strip():
        errors.append("document title must be present")

    contract_errors = validate_document_render_contract(document)
    errors.extend(contract_errors)
    if isinstance(selected_profile, str) and selected_profile.strip():
        from vka.profiles import get_profile

        try:
            profile = get_profile(selected_profile)
        except ValueError:
            errors.append(f"unsupported document profile {selected_profile!r}")
        else:
            errors.extend(profile.validator(document))
    return _unique_errors(errors)


def validate_document_render_contract(document: object) -> list[str]:
    """Validate renderer invariants without imposing a profile's editorial gate."""
    if not isinstance(document, Mapping):
        return ["document must be an object"]
    blocks = list(_document_blocks(document))
    if not blocks:
        return ["document blocks must preserve evidence_refs and source_spans"]

    errors: list[str] = []
    provenance_invalid = False
    video_span_invalid = False
    catalog_invalid = not _valid_evidence_origins(document.get("evidence_origins", {}))
    evidence_origins = _evidence_origins(document)
    cover_invalid = document.get("cover_image") is not None and _safe_local_path(
        document.get("cover_image")
    ) is None
    knowledge_invalid = False
    image_invalid = False
    for block in blocks:
        if not isinstance(block, Mapping):
            provenance_invalid = True
            knowledge_invalid = True
            continue
        refs = block.get("evidence_refs")
        spans = block.get("source_spans")
        if not _valid_refs(refs):
            provenance_invalid = True
        elif spans is None or spans == []:
            if not _block_allows_empty_source_spans(block, evidence_origins):
                video_span_invalid = True
        elif not _valid_source_spans(spans):
            video_span_invalid = True
        if not _valid_refs(block.get("knowledge_refs")):
            knowledge_invalid = True
        if block.get("kind") == "image" and not _safe_local_image_path(block):
            image_invalid = True
    if provenance_invalid:
        errors.append("document blocks must preserve evidence_refs")
    if video_span_invalid:
        errors.append("document video blocks must preserve source_spans")
    if catalog_invalid:
        errors.append("document evidence_origins must map evidence IDs to origins")
    if cover_invalid:
        errors.append("document cover_image must preserve a safe local image_path")
    if knowledge_invalid:
        errors.append("document blocks must preserve knowledge_refs")
    if image_invalid:
        errors.append("image blocks must preserve a safe local image_path")
    return errors


def validate_document_image_files(document: object, asset_root: str | Path) -> list[str]:
    """Check image files at the asset boundary, where relative paths are meaningful."""
    if not isinstance(document, Mapping):
        return ["document must be an object"]
    root = Path(asset_root).resolve()
    errors: list[str] = []
    cover_path = _safe_local_path(document.get("cover_image"))
    if document.get("cover_image") is not None:
        if cover_path is None:
            errors.append("document cover_image must preserve a safe local image_path")
        else:
            _append_image_file_error(errors, root, cover_path)
    for block in _document_blocks(document):
        if not isinstance(block, Mapping) or block.get("kind") != "image":
            continue
        path = _safe_local_image_path(block)
        if path is None:
            continue
        _append_image_file_error(errors, root, path)
    return _unique_errors(errors)


def rebase_document_image_paths(
    document: object, asset_root: str | Path, output_directory: str | Path
) -> object:
    """Copy a document with asset-root image paths made relative to an output."""
    contract_errors = validate_document_render_contract(document)
    image_errors = validate_document_image_files(document, asset_root)
    if contract_errors or image_errors:
        raise ValueError("; ".join(contract_errors + image_errors))
    if not isinstance(document, Mapping):
        raise ValueError("document must be an object")

    rebased = deepcopy(document)
    root = Path(asset_root).resolve()
    output = Path(output_directory).resolve()
    cover_path = _safe_local_path(rebased.get("cover_image"))
    if cover_path is not None:
        rebased["cover_image"] = os.path.relpath(
            _resolve_asset_image_path(root, cover_path), output
        ).replace("\\", "/")
    for block in _document_blocks(rebased):
        if not isinstance(block, dict) or block.get("kind") != "image":
            continue
        path = _safe_local_image_path(block)
        if path is None:
            raise ValueError("image blocks must preserve a safe local image_path")
        source_path = _resolve_asset_image_path(root, path)
        relative_path = os.path.relpath(source_path, output).replace("\\", "/")
        _replace_image_path(block, relative_path)
    return rebased


def document_sections_for_render(
    document: object,
    *,
    allow_rebased_image_paths: bool = False,
    source_navigation: bool = True,
) -> tuple[str, list[dict[str, Any]]]:
    """Return the legacy section surface while retaining generic document provenance.

    `source_navigation=False` means the profile's visible copy has to stand on
    its own, so source-time footnotes are dropped from the rendered view. The
    canonical document keeps its spans; only the delivery surface loses them.
    """
    if not isinstance(document, Mapping):
        raise ValueError("document must be an object")
    title = document.get("title")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("document title must be a non-empty string")
    errors = validate_document_render_contract(document)
    if allow_rebased_image_paths:
        errors = [
            error
            for error in errors
            if error
            not in {
                "image blocks must preserve a safe local image_path",
                "document cover_image must preserve a safe local image_path",
            }
        ]
    if errors:
        raise ValueError("; ".join(errors))

    evidence_origins = _evidence_origins(document)
    sections = document.get("sections")
    if isinstance(sections, list):
        normalized: list[dict[str, Any]] = []
        for index, section in enumerate(sections, start=1):
            if not isinstance(section, Mapping):
                raise ValueError(f"section {index} must be an object")
            section_title = section.get("title")
            if not isinstance(section_title, str) or not section_title.strip():
                raise ValueError(f"section {index} title must be a non-empty string")
            raw_blocks = section.get("blocks")
            if not isinstance(raw_blocks, list):
                raise ValueError(f"section {index} blocks must be a list")
            normalized.append(
                {
                    "title": section_title,
                    "blocks": [
                        _normalise_document_block(
                            block,
                            evidence_origins,
                            source_navigation=source_navigation,
                        )
                        for block in raw_blocks
                    ],
                }
            )
        return title, normalized

    raw_blocks = document.get("blocks")
    if not isinstance(raw_blocks, list):
        raise ValueError("document sections or blocks must be a list")
    return title, _sections_from_document_blocks(raw_blocks, evidence_origins)


def _general_deep_document_errors(document: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    metadata = document.get("metadata")
    required_metadata = ("source_title", "source_url", "publish_date")
    if not isinstance(metadata, Mapping) or any(
        not _metadata_text(metadata, field) for field in required_metadata
    ) or not (_metadata_text(metadata, "author") or _metadata_text(metadata, "uploader")):
        errors.append("general-deep document needs complete source metadata")

    sections = _semantic_sections(document)
    if not sections:
        errors.extend(
            [
                "general-deep document needs an overview section",
                "general-deep document needs at least two logical body sections",
                "general-deep document needs a limitations section",
                "general-deep document needs a source navigation section",
            ]
        )
        return errors
    kinds = [section.get("kind") for section in sections if isinstance(section, Mapping)]
    if "overview" not in kinds:
        errors.append("general-deep document needs an overview section")
    if kinds.count("logical_body") < 2:
        errors.append("general-deep document needs at least two logical body sections")
    if not ({"limitations", "uncertainty"} & set(kinds)):
        errors.append("general-deep document needs a limitations section")
    if "source_navigation" not in kinds:
        errors.append("general-deep document needs a source navigation section")
    prose = sum(
        len(_block_text(block))
        for block in _document_blocks(document)
        if isinstance(block, Mapping) and block.get("kind") != "image"
    )
    if prose < 600:
        errors.append("general-deep document needs sufficient explanatory prose")
    if document.get("video_has_visual_value") is True and not any(
        isinstance(block, Mapping) and block.get("kind") == "image"
        for block in _document_blocks(document)
    ):
        errors.append("general-deep document needs an inspected image when video visuals add value")
    return errors


def _short_video_script_document_errors(document: object) -> list[str]:
    """Validate a short-form script without leaking provenance into visible copy."""
    if not isinstance(document, Mapping):
        return ["short-video-script document must be an object"]

    required_sections = (
        "hook",
        "context",
        "core_point",
        "evidence",
        "payoff",
        "closing",
    )
    errors = _required_profile_sections(
        document,
        "short-video-script",
        tuple(
            (section, f"short-video-script needs {section.replace('_', ' ')}")
            for section in required_sections
        ),
    )

    sections = document.get("sections")
    if not isinstance(sections, list):
        return errors

    section_kinds = tuple(
        section.get("kind") if isinstance(section, Mapping) else None for section in sections
    )
    if section_kinds != required_sections:
        errors.append("short-video-script sections must follow the required hook-to-closing order")

    prose_parts: list[str] = []
    quote_seen = False
    quote_with_source = False

    for section in sections:
        if not isinstance(section, Mapping):
            continue
        section_kind = section.get("kind")
        if section_kind not in required_sections:
            continue
        blocks = section.get("blocks")
        if not isinstance(blocks, list) or not any(
            isinstance(block, Mapping) and _block_has_content(block) for block in blocks
        ):
            errors.append(
                f"short-video-script section {section_kind!r} must contain non-empty content blocks"
            )
            continue

        section_text = "\n".join(_block_text(block) for block in blocks if isinstance(block, Mapping))
        prose_parts.append(section_text)

        if section_kind == "hook":
            errors.extend(_short_video_script_opening_errors(blocks))
        if section_kind == "closing":
            errors.extend(_short_video_script_ending_errors(blocks))

        for block in blocks:
            if not isinstance(block, Mapping):
                continue
            if block.get("kind") == "quote":
                quote_seen = True
                if _valid_source_spans(block.get("source_spans")):
                    quote_with_source = True
                else:
                    errors.append("short-video-script quote blocks must preserve source spans")

    prose = "\n".join(prose_parts).strip()
    if _short_video_script_is_vacuous(prose):
        errors.append("short-video-script prose is too abstract; add concrete script beats")
    if quote_seen and not quote_with_source:
        errors.append("short-video-script needs at least one source-backed quote")
    written = [word for word in SHORT_VIDEO_SCRIPT_WRITTEN_CONNECTIVES if word in prose]
    if written:
        errors.append(
            "short-video-script must sound spoken, not written; replace "
            + "、".join(written)
        )
    return errors


def _short_video_script_opening_errors(blocks: Sequence[object]) -> list[str]:
    first = next(
        (block for block in blocks if isinstance(block, Mapping) and block.get("kind") == "paragraph"),
        None,
    )
    if first is None:
        return []
    text = _block_text(first).strip()
    if SHORT_VIDEO_SCRIPT_ANNOUNCEMENT_OPENERS.search(text):
        return [
            "short-video-script hook must start mid-conversation, not with an "
            "announcement (大家好 / 今天我们来讲 / 本期视频)"
        ]
    return []


def _short_video_script_ending_errors(blocks: Sequence[object]) -> list[str]:
    last = next(
        (
            block
            for block in reversed(list(blocks))
            if isinstance(block, Mapping) and block.get("kind") == "paragraph"
        ),
        None,
    )
    if last is None:
        return []
    text = _block_text(last).strip()
    matched = [phrase for phrase in SHORT_VIDEO_SCRIPT_LESSON_ENDINGS if phrase in text]
    if matched:
        return [
            "short-video-script must end on the thought, not on a lesson or a "
            "golden line"
        ]
    return []


def _creator_article_document_errors(document: object) -> list[str]:
    """Validate a source-led article without manufacturing author testimony."""
    if not isinstance(document, Mapping):
        return ["creator-article document must be an object"]
    required_sections = (
        "reader_promise",
        "core_point",
        "narrative",
        "video_evidence",
        "actionable_takeaway",
        "limitations_sources",
    )
    errors = _required_profile_sections(
        document,
        "creator-article",
        tuple((section, f"creator-article needs {section.replace('_', ' ')}") for section in required_sections),
    )
    sections = document.get("sections")
    if isinstance(sections, list):
        section_kinds = tuple(
            section.get("kind") if isinstance(section, Mapping) else None for section in sections
        )
        if section_kinds != required_sections:
            errors.append("creator-article sections must follow the required semantic order")
        for section in sections:
            if not isinstance(section, Mapping):
                continue
            section_kind = section.get("kind")
            if section_kind not in required_sections:
                continue
            blocks = section.get("blocks")
            if not isinstance(blocks, list) or not any(
                isinstance(block, Mapping) and _block_has_content(block) for block in blocks
            ):
                errors.append(
                    f"creator-article section {section_kind!r} must contain non-empty content blocks"
                )
    blocks = _document_blocks(document)
    prose = "\n".join(
        _block_text(block) for block in blocks if isinstance(block, Mapping)
    )
    if CREATOR_OUTCOME_RE.search(prose) or CREATOR_AUTHOR_RESULT_RE.search(prose):
        errors.append("creator-article must not invent author experience or outcome")
    if not _section_has_video_span(document, "video_evidence"):
        errors.append("creator-article video evidence must retain video source spans")
    return errors


def _enterprise_knowledge_document_errors(document: object) -> list[str]:
    """Validate an operational view without inventing commitments from a video."""
    if not isinstance(document, Mapping):
        return ["enterprise-knowledge document must be an object"]
    errors = _required_profile_sections(
        document,
        "enterprise-knowledge",
        (
            ("purpose_scope", "enterprise-knowledge needs purpose/scope and applicability"),
            ("terminology", "enterprise-knowledge needs terminology"),
            ("process_practice", "enterprise-knowledge needs process/practice"),
            (
                "roles_inputs_outputs",
                "enterprise-knowledge needs roles, inputs, and outputs",
            ),
            ("risks", "enterprise-knowledge needs risks"),
            ("limitations_sources", "enterprise-knowledge needs limitations and sources"),
        ),
    )
    blocks = _document_blocks(document)
    origins = _evidence_origins(document)
    for block in blocks:
        if not isinstance(block, Mapping):
            continue
        refs = block.get("evidence_refs")
        spans = block.get("source_spans")
        has_video_span = _valid_source_spans(spans)
        uses_nonvideo_origin = isinstance(refs, list) and any(
            origins.get(ref) in {"external", "generated"}
            for ref in refs
            if isinstance(ref, str)
        )
        if uses_nonvideo_origin or not has_video_span:
            errors.append("enterprise-knowledge must ground operational content in video evidence")
            break
    for block in blocks:
        if not isinstance(block, Mapping):
            continue
        for sentence in _content_sentences(_block_text(block)):
            if ENTERPRISE_ACTION_RE.search(sentence) and not INSUFFICIENT_EVIDENCE_RE.search(sentence):
                errors.append("enterprise-knowledge cannot present unsourced decisions/action items")
                return errors
    return errors


def _research_brief_document_errors(document: object) -> list[str]:
    """Keep video claims, inference, and user-provided material distinct."""
    if not isinstance(document, Mapping):
        return ["research-brief document must be an object"]

    required_sections = (
        "video_evidence",
        "analysis_inference",
        "external_enrichment",
        "limitations_questions",
        "source_navigation",
    )
    errors = _required_profile_sections(
        document,
        "research-brief",
        tuple(
            (section, f"research-brief needs {section.replace('_', ' ')}")
            for section in required_sections
        ),
    )
    sections = document.get("sections")
    if not isinstance(sections, list):
        return errors
    section_kinds = tuple(
        section.get("kind") if isinstance(section, Mapping) else None for section in sections
    )
    if section_kinds != required_sections:
        errors.append("research-brief sections must follow the required evidence-separated order")

    expected_statuses = {
        "video_evidence": {"video_explicit"},
        "analysis_inference": {"agent_inference"},
        "external_enrichment": {"external_enrichment", "not_used"},
        "limitations_questions": {"insufficient_evidence"},
        "source_navigation": {"source_navigation"},
    }
    expected_categories = {
        "video_evidence": {"video", "video_evidence", "video_explicit"},
        "analysis_inference": {"analysis", "analysis_inference", "agent_inference"},
        "external_enrichment": {"external", "external_enrichment", "not_used"},
        "limitations_questions": {"insufficient_evidence", "limitations_questions"},
        "source_navigation": {"source_navigation"},
    }
    represented_categories: set[str] = set()
    navigation_categories: set[str] = set()
    represented_refs: set[tuple[str, str, str]] = set()
    navigation_refs: set[tuple[str, str, str]] = set()
    for section in sections:
        if not isinstance(section, Mapping):
            continue
        section_kind = section.get("kind")
        if section_kind not in required_sections:
            continue
        section_title = section.get("title")
        section_title_has_video_attribution = (
            section_kind == "analysis_inference"
            and isinstance(section_title, str)
            and _has_analysis_video_attribution(section_title, "")
        )
        blocks = section.get("blocks")
        if not isinstance(blocks, list) or not any(
            isinstance(block, Mapping) and _block_has_content(block) for block in blocks
        ):
            errors.append(
                f"research-brief section {section_kind!r} must contain non-empty content blocks"
            )
            continue
        for block in blocks:
            if not isinstance(block, Mapping) or not _block_has_content(block):
                continue
            data = block.get("data")
            if not isinstance(data, Mapping):
                errors.append("research-brief claims must declare source category and structured refs")
                continue
            status = data.get("claim_status")
            category = data.get("source_category")
            visible_label = data.get("visible_label")
            if status not in expected_statuses[section_kind]:
                errors.append(
                    f"research-brief {section_kind} claim has an incompatible claim_status"
                )
            if category not in expected_categories[section_kind]:
                errors.append(
                    f"research-brief {section_kind} claim has an incompatible source_category"
                )
            if not isinstance(visible_label, str) or not visible_label.strip():
                errors.append("research-brief claims must display a visible source label")
            if not _research_structured_refs_match(
                block,
                data.get("structured_refs"),
                claim_status=status,
                source_navigation=section_kind == "source_navigation",
            ):
                errors.append("research-brief claims must preserve matching structured refs")
            if section_kind == "source_navigation":
                for item in data.get("structured_refs", []):
                    if not isinstance(item, Mapping):
                        continue
                    knowledge_id = item.get("knowledge_id")
                    evidence_id = item.get("evidence_id")
                    item_category = item.get("source_category")
                    if all(isinstance(value, str) for value in (knowledge_id, evidence_id, item_category)):
                        navigation_categories.add(item_category)
                        navigation_refs.add((knowledge_id, evidence_id, item_category))
            elif status != "not_used" and isinstance(status, str):
                represented_categories.add(status)
                for item in data.get("structured_refs", []):
                    if not isinstance(item, Mapping):
                        continue
                    knowledge_id = item.get("knowledge_id")
                    evidence_id = item.get("evidence_id")
                    item_category = item.get("source_category")
                    if all(isinstance(value, str) for value in (knowledge_id, evidence_id, item_category)):
                        represented_refs.add((knowledge_id, evidence_id, item_category))
            if (
                section_kind == "analysis_inference"
                and (
                    section_title_has_video_attribution
                    or _has_analysis_video_attribution(visible_label, _block_text(block))
                )
                and status != "video_explicit"
            ):
                refs = block.get("knowledge_refs")
                if isinstance(refs, list):
                    for reference in refs:
                        if isinstance(reference, str) and reference.strip():
                            errors.append(
                                f"research-brief claim {reference} labels {str(status).replace('_', ' ')} as video evidence"
                            )
    missing_categories = sorted(represented_categories - navigation_categories)
    if missing_categories:
        errors.append(
            "research-brief source navigation is missing categories: "
            + ", ".join(missing_categories)
        )
    if represented_refs - navigation_refs:
        errors.append("research-brief source navigation is missing structured refs")
    return _unique_errors(errors)




def _has_analysis_video_attribution(label: object, text: str) -> bool:
    return any(
        _analysis_video_attribution_in(value)
        for value in (label, text)
        if isinstance(value, str)
    )


def _analysis_video_attribution_in(value: str) -> bool:
    limitation_patterns = (
        r"\s*(?:this\s+)?analysis\s+goes\s+beyond\s+(?:the\s+)?video\s*[.!?]*\s*",
        r"\s*(?:本)?分析(?:超出|超越|超过)视频(?:范围|内容)?\s*[。！？!?]*\s*",
        r"\s*(?:本)?分析(?:在)?视频(?:范围|内容)?之外\s*[。！？!?]*\s*",
    )
    if any(re.fullmatch(pattern, value, flags=re.IGNORECASE) for pattern in limitation_patterns):
        return False
    source_tokens = (
        r"视频|影片|影像|录像|录屏|录制(?:内容|画面)?|录音|片段|讲座|演讲|教程|讲者|演讲者|讲解者",
        r"\b(?:videos?|recordings?|footage|clip(?:s)?|screen\s+recordings?|lectures?|talks?|webinars?|tutorials?|presenter|speaker)\b",
        r"\baccording\s+to\b",
    )
    return any(re.search(pattern, value, flags=re.IGNORECASE) for pattern in source_tokens)


def _research_video_claim(label: object, text: str) -> bool:
    candidates = [value for value in (label, text) if isinstance(value, str)]
    return any(
        re.search(
            r"(?:(?:在|从|根据)视频(?:中|里)?|(?:讲者|演讲者|讲解者)|"
            r"视频(?:中|里|没有|未|不|是|为|可|能|会|应|将|把|对)|"
            r"视频(?:中(?:的)?|里)?(?:讲者|演讲者|讲解者)?(?:明确(?:指出|表明)|表明|显示|指出|讲解|讲了|讲述|介绍|讨论|展示|演示|说明|呈现|说|认为|提到)|"
            r"|(?:录像|录屏|录制(?:内容|画面)?|录音)(?:中|里|没有|未|不|是|为|可|能|会|应|将|把|对|明确(?:指出|表明)|表明|显示|指出|讲解|讲了|讲述|介绍|讨论|展示|演示|说明|呈现|说|认为|提到)|"
            r"(?:根据|从)视频(?:中|里)?(?:可以)?(?:可知|可见|看出|得知|来看)|"
            r"(?:the\s+)?video\s+(?:explicitly\s+)?(?:states?|indicates?|shows?|says?|claims?|explains?|introduces?|discusses?|demonstrates?|presents?)|"
            r"(?:the\s+)?(?:recording|footage|screen\s+recording)\s+(?:explicitly\s+)?(?:states?|indicates?|shows?|says?|claims?|explains?|introduces?|discusses?|demonstrates?|presents?)|"
            r"(?:the\s+)?(?:presenter|speaker)\s+in\s+(?:the\s+)?video\s+(?:argues?|states?|says?|claims?)|"
            r"\b(?:presenter|speaker)\b|\bin\s+(?:the\s+)?video\b|\baccording\s+to\b|"
            r"according\s+to\s+(?:the\s+)?video|"
            r"from\s+(?:the\s+)?video(?:\s+(?:we\s+)?(?:can\s+)?(?:see|infer|learn))?)",
            value,
            flags=re.IGNORECASE,
        )
        for value in candidates
    )


def _research_structured_refs_match(
    block: Mapping[str, Any],
    value: object,
    *,
    claim_status: object,
    source_navigation: bool,
) -> bool:
    if not isinstance(value, list) or not value:
        return False
    knowledge_refs = block.get("knowledge_refs")
    evidence_refs = block.get("evidence_refs")
    if not _valid_refs(knowledge_refs) or not _valid_refs(evidence_refs):
        return False
    declared_knowledge: set[str] = set()
    declared_evidence: set[str] = set()
    for item in value:
        if not isinstance(item, Mapping):
            return False
        knowledge_id = item.get("knowledge_id")
        evidence_id = item.get("evidence_id")
        category = item.get("source_category")
        if (
            not isinstance(knowledge_id, str)
            or knowledge_id not in knowledge_refs
            or not isinstance(evidence_id, str)
            or evidence_id not in evidence_refs
            or not isinstance(category, str)
            or (not source_navigation and category != claim_status)
        ):
            return False
        declared_knowledge.add(knowledge_id)
        declared_evidence.add(evidence_id)
    return set(knowledge_refs) == declared_knowledge and set(evidence_refs) == declared_evidence


def _required_profile_sections(
    document: Mapping[str, Any],
    profile_id: str,
    requirements: Sequence[tuple[str, str]],
) -> list[str]:
    sections = document.get("sections")
    if not isinstance(sections, list):
        return [f"{profile_id} document must declare semantic sections"]
    present = {
        section.get("kind")
        for section in sections
        if isinstance(section, Mapping) and isinstance(section.get("kind"), str)
    }
    return [error for section_kind, error in requirements if section_kind not in present]


def _section_has_video_span(document: Mapping[str, Any], section_kind: str) -> bool:
    sections = document.get("sections")
    if not isinstance(sections, list):
        return False
    for section in sections:
        if not isinstance(section, Mapping) or section.get("kind") != section_kind:
            continue
        blocks = section.get("blocks")
        if isinstance(blocks, list) and any(
            isinstance(block, Mapping) and _valid_source_spans(block.get("source_spans"))
            for block in blocks
        ):
            return True
    return False


def _block_has_content(block: Mapping[str, Any]) -> bool:
    if _block_text(block).strip():
        return True
    data = block.get("data")
    if not isinstance(data, Mapping):
        return False
    kind = block.get("kind")
    if kind == "table":
        return _structured_items_present(data.get("headers")) or _structured_items_present(data.get("rows"))
    if kind in {"formula", "code", "caption", "paragraph", "quote", "summary", "heading", "callout"}:
        return any(
            isinstance(data.get(key), str) and data[key].strip()
            for key in ("text", "latex", "code", "caption")
        )
    if kind == "image":
        return any(
            isinstance(data.get(key), str) and data[key].strip()
            for key in ("image_path", "path", "caption")
        )
    if kind == "list":
        return _structured_items_present(data.get("items"))
    return False


def _structured_items_present(value: object) -> bool:
    if not isinstance(value, list):
        return False
    return any(
        isinstance(item, str) and item.strip()
        or isinstance(item, list) and any(isinstance(cell, str) and cell.strip() for cell in item)
        for item in value
    )


def _content_sentences(text: str) -> list[str]:
    return [sentence.strip() for sentence in re.split(r"(?<=[。！？.!?])", text) if sentence.strip()]


def _document_blocks(document: Mapping[str, Any]) -> Sequence[object]:
    sections = document.get("sections")
    if isinstance(sections, list):
        blocks: list[object] = []
        for section in sections:
            if isinstance(section, Mapping) and isinstance(section.get("blocks"), list):
                blocks.extend(section["blocks"])
        return blocks
    blocks = document.get("blocks")
    return blocks if isinstance(blocks, list) else []


def _semantic_sections(document: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    sections = document.get("sections")
    if isinstance(sections, list):
        return [section for section in sections if isinstance(section, Mapping)]
    blocks = document.get("blocks")
    if not isinstance(blocks, list):
        return []
    try:
        return _sections_from_document_blocks(blocks, _evidence_origins(document))
    except ValueError:
        return []


def _valid_refs(value: object) -> bool:
    return isinstance(value, list) and bool(value) and all(
        isinstance(item, str) and item.strip() for item in value
    )


def _valid_source_spans(value: object) -> bool:
    return isinstance(value, list) and bool(value) and all(
        isinstance(span, Mapping)
        and isinstance(span.get("start_ms"), int)
        and not isinstance(span.get("start_ms"), bool)
        and isinstance(span.get("end_ms"), int)
        and not isinstance(span.get("end_ms"), bool)
        and span["start_ms"] >= 0
        and span["end_ms"] > span["start_ms"]
        for span in value
    )


def _block_allows_empty_source_spans(
    block: Mapping[str, Any], evidence_origins: Mapping[str, str]
) -> bool:
    refs = block.get("evidence_refs")
    if not isinstance(refs, list) or not refs:
        return False
    return all(
        isinstance(ref, str) and evidence_origins.get(ref) in {"external", "generated"}
        for ref in refs
    )


def _evidence_origins(document: Mapping[str, Any]) -> Mapping[str, str]:
    value = document.get("evidence_origins")
    return value if isinstance(value, Mapping) else {}


def _valid_evidence_origins(value: object) -> bool:
    return isinstance(value, Mapping) and all(
        isinstance(evidence_id, str)
        and evidence_id.strip()
        and origin in {"video", "external", "generated"}
        for evidence_id, origin in value.items()
    )


def _image_path(block: Mapping[str, Any]) -> str | None:
    for value in (block.get("image_path"), block.get("path")):
        if isinstance(value, str) and value.strip():
            return value
    data = block.get("data")
    if isinstance(data, Mapping):
        for value in (data.get("image_path"), data.get("path")):
            if isinstance(value, str) and value.strip():
                return value
    return None


def _safe_local_image_path(block: Mapping[str, Any]) -> str | None:
    path = _image_path(block)
    return _safe_local_path(path)


def _safe_local_path(path: object) -> str | None:
    if not isinstance(path, str) or not path.strip():
        return None
    normalized = path.replace("\\", "/")
    windows_path = PureWindowsPath(path)
    candidate = Path(normalized)
    if (
        candidate.is_absolute()
        or windows_path.is_absolute()
        or windows_path.drive
        or ".." in candidate.parts
        or not candidate.suffix
    ):
        return None
    return normalized


def _append_image_file_error(errors: list[str], asset_root: Path, path: str) -> None:
    try:
        resolved = _resolve_asset_image_path(asset_root, path)
    except ValueError as exc:
        errors.append(str(exc))
        return
    if not resolved.is_file():
        errors.append(f"document image_path does not exist: {path}")


def _replace_image_path(block: dict[str, Any], value: str) -> None:
    if "image_path" in block:
        block["image_path"] = value
    if "path" in block:
        block["path"] = value
    data = block.get("data")
    if isinstance(data, dict):
        if "image_path" in data:
            data["image_path"] = value
        if "path" in data:
            data["path"] = value


def _resolve_asset_image_path(asset_root: Path, path: str) -> Path:
    candidate = asset_root / path
    current = asset_root
    for part in Path(path).parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"document image_path must not traverse a symlink: {path}")
    resolved = candidate.resolve()
    try:
        resolved.relative_to(asset_root)
    except ValueError as exc:
        raise ValueError(f"document image_path escapes asset root: {path}") from exc
    return resolved


def _normalise_document_block(
    block: object,
    evidence_origins: Mapping[str, str],
    *,
    source_navigation: bool = True,
) -> dict[str, Any]:
    if not isinstance(block, Mapping):
        raise ValueError("block must be an object")
    normalized = dict(block)
    data = normalized.get("data")
    if isinstance(data, Mapping):
        for key in ("text", "items", "latex", "code", "caption", "path", "image_path"):
            normalized.setdefault(key, data.get(key))
    if normalized.get("kind") == "image":
        path = _image_path(normalized)
        if path:
            normalized["path"] = path
    kind_map = {"list": "bullet_list", "callout": "importantbox", "summary": "paragraph"}
    normalized["kind"] = kind_map.get(normalized.get("kind"), normalized.get("kind"))
    if not source_navigation:
        normalized.pop("source_spans", None)
        normalized["_allow_empty_source_spans"] = True
    elif _block_allows_empty_source_spans(normalized, evidence_origins) and not normalized.get("source_spans"):
        normalized["_allow_empty_source_spans"] = True
    return normalized


def _sections_from_document_blocks(
    blocks: Sequence[object], evidence_origins: Mapping[str, str]
) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for block in blocks:
        if not isinstance(block, Mapping):
            raise ValueError("block must be an object")
        if block.get("kind") == "heading":
            heading = block.get("text") or block.get("title")
            if not isinstance(heading, str) or not heading.strip():
                raise ValueError("heading text must be a non-empty string")
            data = block.get("data")
            section_kind = data.get("section_kind") if isinstance(data, Mapping) else None
            current = {
                "title": heading,
                "kind": section_kind if isinstance(section_kind, str) else None,
                "blocks": [],
            }
            sections.append(current)
            continue
        if current is None:
            current = {"title": "Document", "blocks": []}
            sections.append(current)
        current["blocks"].append(_normalise_document_block(block, evidence_origins))
    return sections


def _unique_errors(errors: Sequence[str]) -> list[str]:
    return list(dict.fromkeys(errors))


def _short_video_script_is_vacuous(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    if len(stripped) < 80:
        return True
    if SHORT_VIDEO_SCRIPT_ABSTRACT_RE.search(stripped) and not SHORT_VIDEO_SCRIPT_CONCRETE_RE.search(
        stripped
    ):
        return True
    if not SHORT_VIDEO_SCRIPT_CONCRETE_RE.search(stripped):
        return True
    if any(phrase in stripped for phrase in SHORT_VIDEO_SCRIPT_VACUOUS_PHRASES):
        return True
    sentence_count = len(_content_sentences(stripped))
    if sentence_count <= 2 and len(stripped) < 160:
        return True
    return False


def _block_text(block: Mapping[str, Any]) -> str:
    parts: list[str] = []
    for key in ("title", "text", "caption", "latex", "code"):
        value = block.get(key)
        if isinstance(value, str):
            parts.append(value)
    items = block.get("items")
    if isinstance(items, list):
        parts.extend(item for item in items if isinstance(item, str))
    return "\n".join(parts)


def _has_long_span(block: Mapping[str, Any]) -> bool:
    spans = block.get("source_spans")
    if not isinstance(spans, list):
        return False
    for span in spans:
        if not isinstance(span, Mapping):
            continue
        start_ms = span.get("start_ms")
        end_ms = span.get("end_ms")
        if isinstance(start_ms, int) and isinstance(end_ms, int) and end_ms - start_ms >= 2_000:
            return True
    return False


def _metadata_text(metadata: Mapping[str, Any], key: str) -> str:
    value = metadata.get(key)
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return " ".join(str(item).strip() for item in value if str(item).strip())
    return ""


def _first_section_errors(section: Mapping[str, Any], blocks: Sequence[object]) -> list[str]:
    errors: list[str] = []
    title = section.get("title")
    first_text_parts: list[str] = []
    has_core_box = False
    semantic_subsections = 0
    for block in blocks[:5]:
        if not isinstance(block, Mapping):
            continue
        kind = block.get("kind")
        text = _block_text(block)
        if text:
            first_text_parts.append(text)
        if kind in {"importantbox", "knowledgebox"} and CORE_SIGNAL_RE.search(text):
            has_core_box = True
        if kind == "subsection":
            block_title = block.get("title")
            if isinstance(block_title, str) and not SUMMARY_TITLE_RE.search(block_title):
                semantic_subsections += 1

    opening_text = "\n".join(first_text_parts)
    if isinstance(title, str) and not CORE_SIGNAL_RE.search(title + "\n" + opening_text):
        errors.append("first chapter must open with the video's core question or main thesis")
    if not has_core_box:
        errors.append("first chapter needs a high-signal core insight box near the opening")
    if len(opening_text) < 220:
        errors.append("first chapter opening is too thin for a readable golden prelude")
    if semantic_subsections < 2:
        errors.append("first chapter needs at least two opening teaching moves before summary")
    return errors
