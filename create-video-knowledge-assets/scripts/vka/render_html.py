from __future__ import annotations

import html
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from vka.quality import document_sections_for_render, rebase_document_image_paths


def render_course_html(
    title: str,
    sections: Sequence[Any],
    *,
    cover_image: str | None = None,
    subtitle: str | None = None,
    theme: str | None = None,
    one_sentence_summary: str | None = None,
    metadata: Mapping[str, Any] | None = None,
    document_class: str | None = None,
) -> str:
    if not isinstance(title, str) or not title:
        raise ValueError("course title must be a non-empty string")
    if not isinstance(sections, Sequence) or isinstance(sections, (str, bytes)):
        raise ValueError("sections must be an array")

    body: list[str] = [
        "<!doctype html>",
        '<html lang="zh-CN">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{_escape(title)}</title>",
        "<style>",
        _STYLE,
        "</style>",
        "</head>",
        f'<body{_body_class_attribute(document_class)}>',
        "<main>",
        f"<h1>{_escape(title)}</h1>",
    ]
    if theme:
        body.append(f'<p class="theme">{_escape(theme)}</p>')
    if one_sentence_summary:
        body.append(f'<p class="summary">{_escape(one_sentence_summary)}</p>')
    if subtitle:
        body.append(f'<p class="subtitle">{_escape(subtitle)}</p>')
    metadata_lines = _metadata_lines(metadata)
    if metadata_lines:
        body.append('<dl class="metadata">')
        body.extend(metadata_lines)
        body.append("</dl>")
    if cover_image:
        body.append(
            f'<figure class="cover"><img src="{_image_src(cover_image)}" alt="视频封面"></figure>'
        )

    body.append("<nav><strong>目录</strong><ol>")
    for index, section in enumerate(sections, start=1):
        section_title = _section_title(section)
        body.append(f'<li><a href="#section-{index}">{_escape(section_title)}</a></li>')
    body.append("</ol></nav>")

    for index, section in enumerate(sections, start=1):
        section_title = _section_title(section)
        body.append(f'<section id="section-{index}">')
        body.append(f"<h2>{_escape(section_title)}</h2>")
        for block in _section_blocks(section):
            body.extend(_render_block(block))
        body.append("</section>")

    body.extend(["</main>", "</body>", "</html>", ""])
    return "\n".join(body)


def render_document_html(
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
    return render_course_html(
        title,
        sections,
        cover_image=_optional_string(document, "cover_image"),
        subtitle=_profile_optional_string(document, "subtitle", profile_id),
        theme=_profile_optional_string(document, "theme", profile_id),
        one_sentence_summary=_profile_optional_string(
            document, "one_sentence_summary", profile_id
        ),
        metadata=_profile_optional_mapping(document, "metadata", profile_id),
        document_class=_profile_document_class(profile_id),
    )


def _render_block(block: Any) -> list[str]:
    if not isinstance(block, Mapping):
        raise ValueError("block must be an object")
    kind = block.get("kind")

    if kind == "paragraph":
        _source(block)
        return [f"<p>{_inline(_text(block))}</p>"]
    if kind == "subsection":
        title = block.get("title")
        if not isinstance(title, str) or not title:
            raise ValueError("subsection title must be a non-empty string")
        return [f"<h3>{_escape(title)}</h3>"]
    if kind in {"importantbox", "knowledgebox", "warningbox"}:
        title = block.get("title")
        heading = title if isinstance(title, str) and title else {
            "importantbox": "核心提示",
            "knowledgebox": "补充知识",
            "warningbox": "易错提醒",
        }[kind]
        _source(block)
        return [
            f'<aside class="box {kind}"><strong>{_escape(heading)}</strong>',
            f"<p>{_inline(_text(block))}</p>",
            "</aside>",
        ]
    if kind in {"bullet_list", "numbered_list"}:
        items = block.get("items")
        if not isinstance(items, list) or not items:
            raise ValueError("list items must be a non-empty list")
        tag = "ol" if kind == "numbered_list" else "ul"
        lines = [f"<{tag}>"]
        for item in items:
            if not isinstance(item, str) or not item:
                raise ValueError("list item must be a non-empty string")
            lines.append(f"<li>{_inline(item)}</li>")
        _source(block)
        lines.append(f"</{tag}>")
        return lines
    if kind == "formula":
        latex = block.get("latex")
        if not isinstance(latex, str) or not latex:
            raise ValueError("formula latex must be a non-empty string")
        lines: list[str] = []
        text = block.get("text")
        if isinstance(text, str) and text:
            lines.append(f"<p>{_inline(text)}</p>")
        lines.append(f'<pre class="formula">{_escape(latex)}</pre>')
        symbols = block.get("symbols")
        if isinstance(symbols, list) and symbols:
            lines.append('<ul class="symbols">')
            for symbol in symbols:
                if not isinstance(symbol, str) or not symbol:
                    raise ValueError("formula symbol explanation must be a non-empty string")
                lines.append(f"<li>{_inline(symbol)}</li>")
            lines.append("</ul>")
        _source(block)
        return lines
    if kind == "code":
        code = block.get("code")
        if not isinstance(code, str) or not code:
            raise ValueError("code block must contain non-empty code")
        caption = block.get("caption")
        lines = []
        if isinstance(caption, str) and caption:
            lines.append(f"<p><strong>{_escape(caption)}</strong></p>")
        _source(block)
        lines.append(f"<pre><code>{_escape(code.rstrip())}</code></pre>")
        return lines
    if kind == "quote":
        _source(block)
        return [f"<blockquote>{_inline(_text(block))}</blockquote>"]
    if kind == "table":
        headers, rows = _table_data(block)
        _source(block)
        lines = ["<table>", "<thead><tr>"]
        lines.extend(f"<th>{_inline(header)}</th>" for header in headers)
        lines.extend(["</tr></thead>", "<tbody>"])
        for row in rows:
            lines.append("<tr>")
            lines.extend(f"<td>{_inline(cell)}</td>" for cell in row)
            lines.append("</tr>")
        lines.extend(["</tbody>", "</table>"])
        return lines
    if kind == "caption":
        _source(block)
        return [f'<p class="caption">{_inline(_text(block))}</p>']
    if kind == "image":
        path = block.get("path")
        caption = block.get("caption")
        if not isinstance(path, str) or not path:
            raise ValueError("image path must be a non-empty string")
        if not isinstance(caption, str) or not caption:
            raise ValueError("image caption must be a non-empty string")
        _source(block)
        return [
            "<figure>",
            f'<img src="{_image_src(path)}" alt="{_escape(caption)}">',
            f"<figcaption>{_inline(caption)}</figcaption>",
            "</figure>",
        ]

    raise ValueError("unsupported block kind")


def _section_title(section: Any) -> str:
    if not isinstance(section, Mapping):
        raise ValueError("section must be an object")
    title = section.get("title")
    if not isinstance(title, str) or not title:
        raise ValueError("section title must be a non-empty string")
    return title


def _section_blocks(section: Any) -> list[Any]:
    if not isinstance(section, Mapping):
        raise ValueError("section must be an object")
    blocks = section.get("blocks")
    if not isinstance(blocks, list):
        raise ValueError("section blocks must be a list")
    return blocks


def _text(block: Mapping[str, Any]) -> str:
    text = block.get("text")
    if not isinstance(text, str) or not text:
        raise ValueError("block text must be a non-empty string")
    return text


def _source(block: Mapping[str, Any]) -> str:
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


def _time(milliseconds: int) -> str:
    total_seconds = milliseconds // 1000
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _escape(value: str) -> str:
    return html.escape(value, quote=True)


def _inline(value: str) -> str:
    escaped = _escape(value)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    return escaped


def _image_src(value: str) -> str:
    if re.match(r"^[a-zA-Z]:/", value):
        return Path(value).as_uri()
    return _escape(value.replace("\\", "/"))


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
        lines.append(f"<dt>{_escape(label)}</dt><dd>{_escape(value.strip())}</dd>")
    return lines


def _optional_string(document: Mapping[str, Any], key: str) -> str | None:
    value = document.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"document {key} must be a string")
    return value or None


def _optional_mapping(document: Mapping[str, Any], key: str) -> Mapping[str, Any] | None:
    value = document.get(key)
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise ValueError(f"document {key} must be an object")
    return value


def _profile_document_class(profile_id: object) -> str | None:
    if not isinstance(profile_id, str):
        return None
    return {
        "creator-article": "profile-creator-article",
        "enterprise-knowledge": "profile-enterprise-knowledge",
        "research-brief": "profile-research-brief",
        "short-video-script": "profile-short-video-script",
    }.get(profile_id)


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


def _body_class_attribute(value: str | None) -> str:
    return f' class="{_escape(value)}"' if value else ""


_STYLE = """
:root {
  color-scheme: light;
  --ink: #1f2933;
  --muted: #607080;
  --line: #d9e2ec;
  --blue: #245b7d;
  --green: #2f6b4f;
  --amber: #8a5a00;
  --paper: #ffffff;
  --bg: #f4f7f9;
}
body {
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font-family: "Microsoft YaHei", "PingFang SC", "Noto Sans CJK SC", sans-serif;
  line-height: 1.75;
}
main {
  max-width: 920px;
  margin: 0 auto;
  padding: 40px 28px 72px;
  background: var(--paper);
}
h1, h2, h3 { line-height: 1.28; }
h1 { font-size: 2rem; margin-bottom: 0.25rem; }
h2 { border-top: 1px solid var(--line); padding-top: 1.4rem; margin-top: 2rem; }
h3 { color: var(--blue); margin-top: 1.4rem; }
.theme { font-size: 1.25rem; font-weight: 700; margin: 0.4rem 0 0.2rem; }
.summary { font-size: 1.05rem; margin: 0.25rem 0 0.6rem; }
.subtitle, .source, figcaption, .metadata { color: var(--muted); }
.source { font-size: 0.9rem; margin-top: -0.4rem; }
.metadata { display: grid; grid-template-columns: max-content 1fr; gap: 0.25rem 0.8rem; margin: 1rem 0; }
.metadata dt { font-weight: 700; }
.metadata dd { margin: 0; }
nav { border: 1px solid var(--line); padding: 1rem 1.2rem; margin: 1.5rem 0 2rem; }
img { max-width: 100%; height: auto; display: block; margin: 0 auto; }
figure { margin: 1.3rem 0; }
figcaption { font-size: 0.94rem; text-align: center; margin-top: 0.6rem; }
.cover img { max-height: 320px; }
.box { border-left: 5px solid var(--blue); background: #f7fbff; padding: 0.8rem 1rem; margin: 1rem 0; }
.knowledgebox { border-left-color: var(--green); background: #f6fbf7; }
.warningbox { border-left-color: var(--amber); background: #fffaf0; }
.formula, pre { overflow-x: auto; background: #f6f8fa; padding: 0.9rem; border: 1px solid var(--line); }
code, .formula { font-family: Consolas, "Cascadia Mono", monospace; }
.profile-creator-article main { max-width: 760px; }
.profile-creator-article h1 { font-size: 2.25rem; }
.profile-enterprise-knowledge main { max-width: 1040px; }
.profile-enterprise-knowledge h2 { color: var(--green); }
.profile-enterprise-knowledge table { width: 100%; border-collapse: collapse; }
.profile-enterprise-knowledge th, .profile-enterprise-knowledge td { border: 1px solid var(--line); padding: 0.55rem; text-align: left; vertical-align: top; }
.profile-research-brief main { max-width: 980px; }
.profile-research-brief h2 { color: #6b3d7a; }
.profile-research-brief blockquote { border-left: 4px solid #8b5ca0; margin: 1rem 0; padding-left: 1rem; color: var(--muted); }
.profile-short-video-script main { max-width: 820px; }
.profile-short-video-script h2 { color: var(--blue); }
@media (max-width: 680px) {
  main { padding: 24px 16px 56px; }
  h1 { font-size: 1.55rem; }
}
"""
