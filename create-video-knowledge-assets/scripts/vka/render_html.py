from __future__ import annotations

import html
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from vka.quality import (
    assign_source_notes,
    document_sections_for_part,
    format_source_note,
    rebase_document_image_paths,
)

# Block kinds that make a claim about the source, so they carry a numbered
# pointer into the 来源时间 list at the end of the document.
SOURCED_BLOCK_KINDS = frozenset(
    {
        "paragraph",
        "quote",
        "bullet_list",
        "numbered_list",
        "table",
        "image",
        "caption",
        "summary",
        "importantbox",
        "knowledgebox",
        "warningbox",
    }
)


def render_course_html(
    title: str,
    sections: Sequence[Any],
    *,
    cover_image: str | None = None,
    subtitle: str | None = None,
    theme: str | None = None,
    one_sentence_summary: str | None = None,
    metadata: Mapping[str, Any] | None = None,
    show_source_notes: bool = True,
) -> str:
    if not isinstance(title, str) or not title:
        raise ValueError("course title must be a non-empty string")
    if not isinstance(sections, Sequence) or isinstance(sections, (str, bytes)):
        raise ValueError("sections must be an array")

    sections = [dict(section) if isinstance(section, Mapping) else section for section in sections]

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
        "<body>",
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
        body.append('<p class="metadata">')
        body.append("<br>".join(metadata_lines))
        body.append("</p>")
    if cover_image:
        body.append(
            f'<figure class="cover"><img src="{_image_src(cover_image)}" alt="视频封面"></figure>'
        )

    body.append("<nav><strong>目录</strong><ol>")
    for index, section in enumerate(sections, start=1):
        section_title = _section_title(section)
        body.append(f'<li><a href="#section-{index}">{_escape(section_title)}</a></li>')
    body.append("</ol></nav>")

    # Number every citation before the body is written: the markers and the
    # endnote list must come from the same pass, or the reader sees times with
    # nothing pointing at them.
    sources = (
        assign_source_notes(
            sections,
            sourced_kinds=SOURCED_BLOCK_KINDS,
            spans_of=_source_spans,
        )
        if show_source_notes
        else []
    )

    for index, section in enumerate(sections, start=1):
        section_title = _section_title(section)
        body.append(f'<section id="section-{index}">')
        body.append(f"<h2>{_escape(section_title)}</h2>")
        for block in _section_blocks(section):
            body.extend(_render_block(block))
        body.append("</section>")

    if sources:
        body.extend(
            [
                '<section class="notes" id="source-times">',
                "<h2>来源时间</h2>",
                '<ol class="notes-list">',
                *(
                    f'<li id="src-{number}"><span class="time">{_escape(text)}</span></li>'
                    for number, text in sources
                ),
                "</ol>",
                "</section>",
            ]
        )

    body.extend(["</main>", "</body>", "</html>", ""])
    return "\n".join(body)


def render_document_html(
    document: object,
    *,
    asset_root: str | None = None,
    output_directory: str | None = None,
    source_navigation: bool = True,
    part: str = "main",
) -> str:
    """Render a neutral document while keeping provenance out of reader copy."""
    if not isinstance(document, Mapping):
        raise ValueError("document must be an object")
    if (asset_root is None) != (output_directory is None):
        raise ValueError("asset_root and output_directory must be provided together")
    rebased_image_paths = asset_root is not None and output_directory is not None
    if rebased_image_paths:
        document = rebase_document_image_paths(document, asset_root, output_directory)
    title, sections = document_sections_for_part(
        document,
        part=part,
        allow_rebased_image_paths=rebased_image_paths,
        source_navigation=source_navigation,
    )
    profile_id = document.get("profile_id")
    return render_course_html(
        title,
        sections,
        cover_image=_optional_string(document, "cover_image") if part == "main" else None,
        subtitle=(
            _profile_optional_string(document, "subtitle", profile_id)
            if part == "main"
            else None
        ),
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
        return [f"<p>{_inline(_text(block))}{_source(block)}</p>"]
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
        marker = _source(block)
        return [
            f'<aside class="box {kind}"><strong>{_escape(heading)}</strong>',
            f"<p>{_inline(_text(block))}{marker}</p>",
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
        marker = _source(block)
        if marker and len(lines) > 1:
            lines[-1] = lines[-1].replace("</li>", f"{marker}</li>")
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
        marker = _source(block)
        if marker and lines:
            lines[-1] = lines[-1].replace("</ul>", f"{marker}</ul>")
        return lines
    if kind == "code":
        code = block.get("code")
        if not isinstance(code, str) or not code:
            raise ValueError("code block must contain non-empty code")
        caption = block.get("caption")
        lines = []
        if isinstance(caption, str) and caption:
            lines.append(f"<p><strong>{_escape(caption)}</strong></p>")
        marker = _source(block)
        lines.append(f"<pre><code>{_escape(code.rstrip())}</code></pre>{marker}")
        return lines
    if kind == "quote":
        return [f"<blockquote>{_inline(_text(block))}{_source(block)}</blockquote>"]
    if kind == "table":
        headers, rows = _table_data(block)
        marker = _source(block)
        lines = ["<table>", "<thead><tr>"]
        lines.extend(f"<th>{_inline(header)}</th>" for header in headers)
        lines.extend(["</tr></thead>", "<tbody>"])
        for row in rows:
            lines.append("<tr>")
            lines.extend(f"<td>{_inline(cell)}</td>" for cell in row)
            lines.append("</tr>")
        lines.extend(["</tbody>", f"</table>{marker}"])
        return lines
    if kind == "caption":
        return [f'<p class="caption">{_inline(_text(block))}{_source(block)}</p>']
    if kind == "image":
        path = block.get("path")
        caption = block.get("caption")
        if not isinstance(path, str) or not path:
            raise ValueError("image path must be a non-empty string")
        if not isinstance(caption, str) or not caption:
            raise ValueError("image caption must be a non-empty string")
        marker = _source(block)
        return [
            "<figure>",
            f'<img src="{_image_src(path)}" alt="{_escape(caption)}">',
            f"<figcaption>{_inline(caption)}{marker}</figcaption>",
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
    spans = _source_spans(block)
    if not spans:
        return ""
    number = block.get("_note_number")
    if not isinstance(number, int):
        return ""
    return f'<sup class="cite"><a href="#src-{number}">{number}</a></sup>'


def _source_spans(block: Mapping[str, Any]) -> list[Any]:
    """Validated source spans, or an empty list when the block is unsourced."""
    spans = block.get("source_spans")
    if spans in (None, []) and block.get("_allow_empty_source_spans") is True:
        return []
    if not isinstance(spans, list) or not spans:
        raise ValueError("source_spans must be a non-empty list")
    for span in spans:
        if not isinstance(span, Mapping):
            raise ValueError("source span must be an object")
        start = span.get("start_ms")
        end = span.get("end_ms")
        if not isinstance(start, int) or not isinstance(end, int) or end <= start:
            raise ValueError("source span must have increasing integer times")
    return list(spans)


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
    """Three short grey lines: who made it, how it was read, where it lives.

    Identity reads as one scannable line so the cover answers "what am I
    looking at" at a glance; the transcript audit trail keeps its own line
    instead of running into the title.
    """
    if not isinstance(metadata, Mapping):
        return []
    identity: list[str] = []
    for key in ("source_title", "author", "uploader", "publish_date", "duration"):
        value = _metadata_value(metadata, key)
        if value is None:
            continue
        rendered = f"《{value}》" if key == "source_title" else value
        if rendered not in identity:
            identity.append(rendered)
    provenance = [
        value
        for key in ("subtitle_source", "transcript_source", "data_sources")
        if (value := _metadata_value(metadata, key)) is not None
    ]
    url = _metadata_value(metadata, "source_url")
    lines: list[str] = []
    if identity:
        lines.append(_escape("　·　".join(identity)))
    if provenance:
        lines.append(_escape("；".join(provenance)))
    if url:
        lines.append(_escape(url))
    return lines


def _metadata_value(metadata: Mapping[str, Any], key: str) -> str | None:
    value = metadata.get(key)
    if isinstance(value, list):
        value = "；".join(str(item) for item in value if str(item).strip())
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


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


_STYLE = """
:root {
  color-scheme: light;
  --ink: #23211f;
  --ink-soft: #46423f;
  --muted: #8b8681;
  --line: #e7e3dc;
  --accent: #2f6b52;
  --blue: #245b7d;
  --amber: #8a5a00;
  --paper: #fffefb;
  --bg: #f1eee8;
  --serif: "Source Han Serif SC", "Noto Serif CJK SC", "Noto Serif SC", "Songti SC", STSong, SimSun, Georgia, serif;
  --sans: "PingFang SC", "Microsoft YaHei", "Noto Sans CJK SC", "Hiragino Sans GB", sans-serif;
  --mono: ui-monospace, "Cascadia Mono", Consolas, "Courier New", monospace;
}
html { -webkit-text-size-adjust: 100%; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font-family: var(--serif);
  font-size: 17px;
  line-height: 1.85;
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
}
main {
  max-width: 680px;
  margin: 0 auto;
  padding: 72px 52px 104px;
  background: var(--paper);
  box-shadow: 0 1px 48px rgba(35, 33, 31, 0.06);
  counter-reset: sec fig;
}
h1, h2, h3 { font-family: var(--sans); color: var(--ink); line-height: 1.34; text-wrap: balance; }
h1 { font-size: 2rem; font-weight: 700; letter-spacing: 0.005em; margin: 0 0 0.5em; }
h2 { font-size: 1.34rem; font-weight: 700; margin: 3.2rem 0 1.1rem; counter-increment: sec; }
h2::before {
  content: counter(sec, decimal-leading-zero);
  display: block;
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.22em;
  color: var(--accent);
  margin-bottom: 0.35em;
}
h3 { font-size: 1.06rem; font-weight: 600; margin: 2.1rem 0 0.7em; color: var(--ink-soft); }
p { margin: 0 0 1.15em; }
.theme { font-family: var(--sans); font-size: 1.02rem; font-weight: 500; color: var(--accent); margin: 0 0 1rem; }
.summary { font-size: 1rem; color: var(--ink-soft); margin: 0 0 0.7rem; padding-left: 0.9rem; border-left: 2px solid var(--line); }
.subtitle, .source, figcaption, .metadata { color: var(--muted); font-size: 0.84rem; }
.subtitle { margin: 0 0 0.8rem; letter-spacing: 0.02em; }
.metadata { display: block; margin: 0 0 2rem; line-height: 1.95; }
nav { margin: 2.6rem 0 3.2rem; padding: 1.3rem 0; border-top: 1px solid var(--line); border-bottom: 1px solid var(--line); }
nav strong { font-family: var(--sans); font-size: 0.75rem; color: var(--muted); letter-spacing: 0.22em; }
nav ol { list-style: none; margin: 0.9rem 0 0; padding: 0; counter-reset: toc; }
nav li { counter-increment: toc; margin: 0.55rem 0; font-size: 1rem; line-height: 1.6; }
nav li a { color: var(--ink); text-decoration: none; border-bottom: 1px solid transparent; }
nav li a::before {
  content: counter(toc, decimal-leading-zero);
  margin-right: 0.75em;
  font-family: var(--sans);
  font-size: 0.78em;
  letter-spacing: 0.06em;
  color: var(--accent);
}
nav li a:hover { border-bottom-color: var(--accent); }
img { max-width: 100%; height: auto; display: block; margin: 0 auto; }
figure { margin: 2.3rem 0 2.5rem; }
figure:not(.cover) { counter-increment: fig; }
figure img { border: 1px solid var(--line); border-radius: 3px; }
figcaption { text-align: left; margin-top: 0.75rem; line-height: 1.7; }
figure:not(.cover) figcaption::before {
  content: "图 " counter(fig) "　";
  font-family: var(--sans);
  font-size: 0.9em;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: var(--accent);
}
.caption { font-size: 0.84rem; line-height: 1.75; color: var(--muted); margin: -1.6rem 0 2.2rem; }
.cover { margin: 0 0 2.4rem; }
.cover img { width: 100%; border-radius: 4px; }
.cite { font-size: 0.6em; vertical-align: super; line-height: 0; margin-left: 0.12em; }
.cite a { color: var(--muted); text-decoration: none; }
.cite a:hover { color: var(--accent); }
table { width: 100%; border-collapse: collapse; margin: 1.4rem 0; font-size: 0.9rem; }
th, td { border-bottom: 1px solid var(--line); padding: 0.55rem 0.6rem; text-align: left; vertical-align: top; }
th { font-family: var(--sans); font-size: 0.85rem; color: var(--muted); font-weight: 600; }
blockquote { margin: 1.5rem 0; padding: 0.2rem 0 0.2rem 1.1rem; border-left: 2px solid var(--accent); color: var(--ink-soft); }
.notes { margin-top: 4.5rem; padding-top: 1.7rem; border-top: 1px solid var(--line); }
.notes h2 { counter-increment: none; font-family: var(--sans); font-size: 0.78rem; font-weight: 600; letter-spacing: 0.22em; color: var(--muted); margin: 0 0 1.2rem; }
.notes h2::before { content: none; }
.notes-list { list-style: none; margin: 0; padding: 0; counter-reset: note; font-size: 0.8rem; line-height: 1.7; color: var(--muted); }
.notes-list li { counter-increment: note; display: grid; grid-template-columns: 2.6em 1fr; margin: 0.3rem 0; }
.notes-list li::before { content: counter(note) "."; color: var(--muted); }
.notes-list .time { font-family: var(--mono); font-size: 0.94em; }
.box { border-left: 4px solid var(--blue); background: #f7fbff; padding: 0.85rem 1.1rem; margin: 1.4rem 0; }
.knowledgebox { border-left-color: var(--accent); background: #f4faf6; }
.warningbox { border-left-color: var(--amber); background: #fffaf0; }
.box strong { font-family: var(--sans); font-size: 0.9rem; letter-spacing: 0.04em; }
.formula, pre { overflow-x: auto; background: #f7f5f1; padding: 0.9rem 1rem; border: 1px solid var(--line); border-radius: 3px; }
code, .formula { font-family: var(--mono); font-size: 0.88em; }
@media (max-width: 720px) {
  body { font-size: 16.5px; }
  main { padding: 32px 20px 64px; }
  h1 { font-size: 1.6rem; }
  h2 { font-size: 1.2rem; margin-top: 2.6rem; }
}
@media print {
  body { background: #fff; }
  main { max-width: none; padding: 0; box-shadow: none; }
}
"""
