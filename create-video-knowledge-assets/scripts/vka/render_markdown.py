from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from vka.quality import document_sections_for_render, rebase_document_image_paths


def render_course_markdown(
    title: str,
    sections: Sequence[Any],
    *,
    cover_image: str | None = None,
    subtitle: str | None = None,
    theme: str | None = None,
    one_sentence_summary: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> str:
    if not isinstance(title, str) or not title:
        raise ValueError("course title must be a non-empty string")
    if not isinstance(sections, Sequence) or isinstance(sections, (str, bytes)):
        raise ValueError("sections must be an array")

    lines = [f"# {title}", ""]
    if theme:
        lines.extend([f"## {theme}", ""])
    if one_sentence_summary:
        lines.extend([f"> {one_sentence_summary}", ""])
    if subtitle:
        lines.extend([subtitle, ""])
    metadata_lines = _metadata_lines(metadata)
    if metadata_lines:
        lines.extend(metadata_lines)
        lines.append("")
    if cover_image:
        lines.extend([f"![视频封面]({cover_image})", ""])
    for section in sections:
        if not isinstance(section, Mapping):
            raise ValueError("section must be an object")
        section_title = section.get("title")
        if not isinstance(section_title, str) or not section_title:
            raise ValueError("section title must be a non-empty string")
        blocks = section.get("blocks")
        if not isinstance(blocks, list):
            raise ValueError("section blocks must be a list")

        lines.extend([f"## {section_title}", ""])
        for block in blocks:
            lines.extend(_render_block(block))
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def render_document_markdown(
    document: object,
    *,
    asset_root: str | None = None,
    output_directory: str | None = None,
) -> str:
    """Render a neutral document while keeping provenance out of reader copy."""
    if not isinstance(document, Mapping):
        raise ValueError("document must be an object")
    if (asset_root is None) != (output_directory is None):
        raise ValueError("asset_root and output_directory must be provided together")
    rebased_image_paths = asset_root is not None and output_directory is not None
    if rebased_image_paths:
        document = rebase_document_image_paths(document, asset_root, output_directory)
    title, sections = document_sections_for_render(
        document, allow_rebased_image_paths=rebased_image_paths
    )
    profile_id = document.get("profile_id")
    return render_course_markdown(
        title,
        sections,
        cover_image=_optional_string(document, "cover_image"),
        subtitle=_profile_optional_string(document, "subtitle", profile_id),
        theme=_profile_optional_string(document, "theme", profile_id),
        one_sentence_summary=_profile_optional_string(
            document, "one_sentence_summary", profile_id
        ),
        metadata=_profile_optional_mapping(document, "metadata", profile_id),
    )


def _render_block(block: Any) -> list[str]:
    if not isinstance(block, Mapping):
        raise ValueError("block must be an object")
    kind = block.get("kind")

    if kind == "paragraph":
        _sources(block)
        return [_text(block)]
    if kind == "subsection":
        title = block.get("title")
        if not isinstance(title, str) or not title:
            raise ValueError("subsection title must be a non-empty string")
        return [f"### {title}"]
    if kind in {"importantbox", "knowledgebox", "warningbox"}:
        label = {
            "importantbox": "核心提示",
            "knowledgebox": "补充知识",
            "warningbox": "易错提醒",
        }[kind]
        title = block.get("title")
        heading = title if isinstance(title, str) and title else label
        _sources(block)
        return [f"> **{heading}**", ">", f"> {_text(block)}"]
    if kind in {"bullet_list", "numbered_list"}:
        items = block.get("items")
        if not isinstance(items, list) or not items:
            raise ValueError("list items must be a non-empty list")
        lines: list[str] = []
        for index, item in enumerate(items, start=1):
            if not isinstance(item, str) or not item:
                raise ValueError("list item must be a non-empty string")
            prefix = f"{index}." if kind == "numbered_list" else "-"
            lines.append(f"{prefix} {item}")
        _sources(block)
        return lines
    if kind == "formula":
        latex = block.get("latex")
        if not isinstance(latex, str) or not latex:
            raise ValueError("formula latex must be a non-empty string")
        lines = []
        text = block.get("text")
        if isinstance(text, str) and text:
            lines.append(text)
        lines.extend(["", f"$$\n{latex}\n$$"])
        symbols = block.get("symbols")
        if isinstance(symbols, list) and symbols:
            lines.extend(["", "符号说明："])
            lines.extend(f"- {item}" for item in symbols if isinstance(item, str) and item)
        _sources(block)
        return lines
    if kind == "code":
        code = block.get("code")
        if not isinstance(code, str) or not code:
            raise ValueError("code block must contain non-empty code")
        caption = block.get("caption")
        lines = [f"**{caption}**" if isinstance(caption, str) and caption else "代码："]
        _sources(block)
        lines.extend(["```", code.rstrip(), "```"])
        return lines
    if kind == "quote":
        _sources(block)
        return [f"> {_text(block)}"]
    if kind == "table":
        headers, rows = _table_data(block)
        _sources(block)
        return [
            _markdown_table_row(headers),
            _markdown_table_row(["---"] * len(headers)),
            *[_markdown_table_row(row) for row in rows],
        ]
    if kind == "caption":
        _sources(block)
        return [f"*{_text(block)}*"]
    if kind == "image":
        path = block.get("path")
        caption = block.get("caption")
        if not isinstance(path, str) or not path:
            raise ValueError("image path must be a non-empty string")
        if not isinstance(caption, str) or not caption:
            raise ValueError("image caption must be a non-empty string")
        _sources(block)
        return [f"![{caption}]({path})"]

    raise ValueError("unsupported block kind")


def _text(block: Mapping[str, Any]) -> str:
    text = block.get("text")
    if not isinstance(text, str) or not text:
        raise ValueError("block text must be a non-empty string")
    return text


def _sources(block: Mapping[str, Any]) -> str:
    spans = block.get("source_spans")
    if spans in (None, []) and block.get("_allow_empty_source_spans") is True:
        return ""
    if not isinstance(spans, list) or not spans:
        raise ValueError("source_spans must be a non-empty list")
    for span in spans:
        if not isinstance(span, Mapping):
            raise ValueError("source span must be an object")
        start = span.get("start_ms")
        end = span.get("end_ms")
        if not isinstance(start, int) or not isinstance(end, int) or end <= start:
            raise ValueError("source span must have increasing integer times")
    return ""


def _table_data(block: Mapping[str, Any]) -> tuple[list[str], list[list[str]]]:
    data = block.get("data")
    if not isinstance(data, Mapping):
        raise ValueError("table data must be an object")
    headers = data.get("headers")
    rows = data.get("rows")
    if not isinstance(headers, list) or not headers or not all(isinstance(cell, str) and cell for cell in headers):
        raise ValueError("table headers must be a non-empty list of strings")
    if not isinstance(rows, list) or not rows:
        raise ValueError("table rows must be a non-empty list")
    normalized_rows: list[list[str]] = []
    for row in rows:
        if not isinstance(row, list) or len(row) != len(headers) or not all(
            isinstance(cell, str) for cell in row
        ):
            raise ValueError("table rows must match the header width")
        normalized_rows.append(row)
    return headers, normalized_rows


def _markdown_table_row(row: Sequence[str]) -> str:
    return "| " + " | ".join(cell.replace("|", r"\|") for cell in row) + " |"


def _time(milliseconds: int) -> str:
    total_seconds = milliseconds // 1000
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _metadata_lines(metadata: Mapping[str, Any] | None) -> list[str]:
    if not isinstance(metadata, Mapping):
        return []
    fields = [
        ("source_title", "视频名称"),
        ("author", "作者/UP主"),
        ("uploader", "作者/UP主"),
        ("publish_date", "发布时间"),
        ("duration", "视频时长"),
        ("subtitle_source", "字幕来源"),
        ("transcript_source", "转录来源"),
        ("data_sources", "数据来源"),
        ("source_url", "视频链接"),
    ]
    seen_labels: set[str] = set()
    lines: list[str] = []
    for key, label in fields:
        if label in seen_labels:
            continue
        value = metadata.get(key)
        if isinstance(value, list):
            value = "；".join(str(item) for item in value if str(item).strip())
        if not isinstance(value, str) or not value.strip():
            continue
        seen_labels.add(label)
        lines.append(f"- **{label}**：{value.strip()}")
    return lines


def _optional_string(document: Mapping[str, Any], key: str) -> str | None:
    value = document.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"document {key} must be a string")
    return value or None


def _profile_optional_string(
    document: Mapping[str, Any], key: str, profile_id: object
) -> str | None:
    if profile_id == "short-video-script":
        return None
    return _optional_string(document, key)


def _profile_optional_mapping(
    document: Mapping[str, Any], key: str, profile_id: object
) -> Mapping[str, Any] | None:
    if profile_id == "short-video-script":
        return None
    return _optional_mapping(document, key)


def _optional_mapping(document: Mapping[str, Any], key: str) -> Mapping[str, Any] | None:
    value = document.get(key)
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise ValueError(f"document {key} must be an object")
    return value
