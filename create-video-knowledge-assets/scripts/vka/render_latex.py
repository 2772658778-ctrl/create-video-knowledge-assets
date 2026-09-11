from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from vka.quality import document_sections_for_part, rebase_document_image_paths


URL_RE = re.compile(
    r"https?://[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]+"
)
URL_TRAILING_PUNCTUATION = "，。；：！？、）】》」』"


def _format_time(milliseconds: int) -> str:
    if not _is_int(milliseconds):
        raise ValueError("milliseconds must be an integer")
    if milliseconds < 0:
        raise ValueError("milliseconds must be non-negative")

    total_seconds = milliseconds // 1000
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def render_course_tex(
    title: str,
    sections: Sequence[Any],
    *,
    cover_image: str | None = None,
    subtitle: str | None = None,
    theme: str | None = None,
    one_sentence_summary: str | None = None,
    metadata: Mapping[str, Any] | None = None,
    title_page_label: str = "Codex course notes",
    show_cover: bool = True,
    show_toc: bool = True,
) -> str:
    if not isinstance(title, str):
        raise ValueError("course title must be a string")
    if not _is_sequence(sections):
        raise ValueError("sections must be an array")

    lines = [
        r"\documentclass[UTF8,a4paper]{ctexart}",
        r"\usepackage{fontspec}",
        r"\IfFontExistsTF{Microsoft YaHei}{\setCJKmainfont{Microsoft YaHei}\setCJKsansfont{Microsoft YaHei UI}\setCJKmonofont{Microsoft YaHei}}{}",
        r"\usepackage[margin=2.5cm]{geometry}",
        r"\usepackage{graphicx}",
        r"\usepackage{float}",
        r"\usepackage{xcolor}",
        r"\usepackage{amsmath}",
        r"\usepackage{array}",
        r"\usepackage{tabularx}",
        r"\usepackage{listings}",
        r"\usepackage[bottom]{footmisc}",
        r"\usepackage{caption}",
        r"\usepackage{enumitem}",
        r"\usepackage{needspace}",
        r"\usepackage{hyperref}",
        r"\captionsetup{width=.92\linewidth,font=small,labelfont=bf,justification=raggedright,singlelinecheck=false,skip=6pt}",
        r"\hypersetup{unicode=true,hidelinks}",
        r"\ctexset{section={format=\Large\bfseries\raggedright,beforeskip=1.6em,afterskip=.7em},subsection={format=\large\bfseries\raggedright,beforeskip=1.1em,afterskip=.45em}}",
        r"\pagestyle{plain}",
        r"\setcounter{tocdepth}{2}",
        r"\setcounter{secnumdepth}{2}",
        r"\setlength{\parskip}{0.42em}",
        r"\setlength{\parindent}{2em}",
        r"\raggedbottom",
        r"\setlength{\intextsep}{0.7em}",
        r"\setlength{\textfloatsep}{0.7em}",
        r"\renewcommand{\topfraction}{0.92}",
        r"\renewcommand{\bottomfraction}{0.6}",
        r"\renewcommand{\textfraction}{0.06}",
        r"\renewcommand{\floatpagefraction}{0.72}",
        r"\renewcommand{\footnotesize}{\fontsize{8.5}{11}\selectfont}",
        r"\setlength{\skip\footins}{1.1em plus .3em}",
        r"\interfootnotelinepenalty=10000",
        r"\definecolor{vkaBlue}{HTML}{245B7D}",
        r"\definecolor{vkaGreen}{HTML}{3B6B4F}",
        r"\definecolor{vkaAmber}{HTML}{8A5A00}",
        r"\newenvironment{vkabox}[2]{\par\medskip\noindent{\color{#1}\rule{0.8em}{0.8em}}\hspace{0.4em}\textbf{#2}\par\smallskip\noindent\begingroup\leftskip=1.2em\rightskip=0.6em\ignorespaces}{\par\endgroup\medskip}",
        r"\lstset{basicstyle=\ttfamily\small,breaklines=true,columns=fullflexible,frame=single}",
        "",
        r"\begin{document}",
        r"\begin{titlepage}",
        r"\thispagestyle{empty}",
        r"\centering",
        r"\vspace*{0.03\textheight}",
        rf"{{\Huge\bfseries {_escape_latex(title)}\par}}",
    ]

    if theme:
        lines.extend([r"\vspace{0.4cm}", rf"{{\Large\bfseries {_escape_latex(theme)}\par}}"])
    if one_sentence_summary:
        lines.extend(
            [
                r"\vspace{0.35cm}",
                r"\begin{center}",
                r"\begin{minipage}{0.82\textwidth}",
                r"\centering\large",
                rf"{_escape_latex(one_sentence_summary)}\par",
                r"\end{minipage}",
                r"\end{center}",
            ]
        )
    if subtitle:
        lines.extend([r"\vspace{0.4cm}", rf"{{\normalsize {_escape_latex(subtitle)}\par}}"])

    if cover_image and show_cover:
        lines.extend(
            [
                r"\vfill",
                r"\begin{center}",
                rf"\includegraphics[width=0.62\linewidth,height=0.26\textheight,keepaspectratio]{{{_latex_path(cover_image)}}}",
                r"\end{center}",
            ]
        )

    metadata_lines = _metadata_lines(metadata)
    if metadata_lines:
        lines.extend(
            [
                r"\vfill",
                r"\begin{center}",
                r"\begin{tabularx}{0.88\textwidth}{>{\bfseries}r>{\raggedright\arraybackslash}X}",
                *metadata_lines,
                r"\end{tabularx}",
                r"\end{center}",
            ]
        )

    lines.extend(
        [
            r"\vfill",
            rf"{{\small\color{{black!55}} {_escape_latex(title_page_label)}\par}}",
            r"\end{titlepage}",
        ]
    )
    if show_toc:
        lines.extend(
            [
                r"\pagenumbering{roman}",
                r"\tableofcontents",
                r"\vspace{1.2em}",
                r"\begin{center}",
                r"{\small\color{black!55} 脚注标注该段内容在视频中的时间位置。\par}",
                r"\end{center}",
                r"\newpage",
                r"\pagenumbering{arabic}",
                "",
            ]
        )
    else:
        lines.append("")

    for section_index, section in enumerate(sections):
        section_title = _section_title(section)
        if section_index:
            lines.append(r"\par\vspace{1.15\baselineskip}")
            lines.append(r"\needspace{4\baselineskip}")
        lines.append(rf"\section{{{_escape_latex(section_title)}}}")
        lines.append("")

        for block in _section_blocks(section):
            lines.extend(_render_block(block))
            lines.append("")

    lines.append(r"\end{document}")
    lines.append("")
    return "\n".join(lines)


def render_document_tex(
    document: object,
    *,
    asset_root: str | None = None,
    output_directory: str | None = None,
    source_navigation: bool = True,
    part: str = "main",
) -> str:
    """Render a profile-selected document without applying P1's course gate."""
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
    title_page_label = {
        "course-notes": "Codex course notes",
        "creator-article": "Codex source-led article",
        "enterprise-knowledge": "Codex internal knowledge record",
        "research-brief": "Codex evidence-separated research brief",
        "short-video-script": "Codex short-video script",
    }.get(profile_id, "Codex knowledge document")
    if part == "notes":
        title_page_label = "Codex source notes"
    is_reader_part = part == "main"
    return render_course_tex(
        title,
        sections,
        cover_image=_optional_string(document, "cover_image") if is_reader_part else None,
        subtitle=(
            _profile_optional_string(document, "subtitle", profile_id)
            if is_reader_part
            else None
        ),
        theme=(
            _profile_optional_string(document, "theme", profile_id) if is_reader_part else None
        ),
        one_sentence_summary=(
            _profile_optional_string(document, "one_sentence_summary", profile_id)
            if is_reader_part
            else None
        ),
        metadata=_profile_optional_mapping(document, "metadata", profile_id),
        title_page_label=title_page_label,
        show_cover=part == "main",
        show_toc=part == "main",
    )


def _validate_source_span(span: Any) -> None:
    if not isinstance(span, Mapping):
        raise ValueError("source span must be an object")

    start_ms = span.get("start_ms")
    end_ms = span.get("end_ms")
    if not _is_int(start_ms) or not _is_int(end_ms):
        raise ValueError("source span start_ms and end_ms must be integers")
    if start_ms < 0 or end_ms < 0:
        raise ValueError("source span times must be non-negative")
    if end_ms <= start_ms:
        raise ValueError("source span end_ms must be greater than start_ms")


def _section_title(section: Any) -> str:
    if not isinstance(section, Mapping):
        raise ValueError("section must be an object")
    title = section.get("title")
    if not isinstance(title, str):
        raise ValueError("section title must be a string")
    return title


def _section_blocks(section: Mapping[str, Any]) -> Sequence[Any]:
    if "blocks" not in section:
        raise ValueError("section blocks must be present")
    blocks = section["blocks"]
    if not isinstance(blocks, list):
        raise ValueError("section blocks must be a list")
    return blocks


def _render_block(block: Any) -> list[str]:
    if not isinstance(block, Mapping):
        raise ValueError("block must be an object")

    kind = block.get("kind")
    if kind == "paragraph":
        paragraph = _escape_prose_latex(_paragraph_text(block))
        return [f"{paragraph}{_source_footnote(block)}"]

    if kind == "subsection":
        title = block.get("title")
        if not isinstance(title, str) or not title:
            raise ValueError("subsection title must be a non-empty string")
        return [rf"\subsection{{{_escape_latex(title)}}}"]

    if kind in {"bullet_list", "numbered_list"}:
        return _render_list_block(block, ordered=kind == "numbered_list")

    if kind in {"importantbox", "knowledgebox", "warningbox"}:
        return _render_box_block(block, kind)

    if kind == "formula":
        return _render_formula_block(block)

    if kind == "code":
        return _render_code_block(block)

    if kind == "quote":
        quote_text = block.get("text")
        if not isinstance(quote_text, str) or not quote_text:
            raise ValueError("quote text must be a non-empty string")
        text = _escape_prose_latex(quote_text)
        return [r"\begin{quote}", f"{text}{_source_footnote(block)}", r"\end{quote}"]

    if kind == "table":
        return _render_table_block(block)

    if kind == "caption":
        return [
            rf"\textit{{{_escape_prose_latex(_text_field(block, 'caption text'))}}}"
            f"{_source_footnote(block)}"
        ]

    if kind == "image":
        return _render_image_block(block)

    raise ValueError("unsupported block kind")


def _render_image_block(block: Mapping[str, Any]) -> list[str]:
    path = block.get("path")
    if not isinstance(path, str) or not path:
        raise ValueError("image path must be a non-empty string")

    caption = block.get("caption")
    if not isinstance(caption, str) or not caption:
        raise ValueError("image caption must be a non-empty string")

    footnote = _source_footnote(block)
    latex_path = _latex_path(path)
    return [
        r"\begin{figure}[H]",
        r"\centering",
        rf"\includegraphics[width=\linewidth,height=0.32\textheight,keepaspectratio]{{{latex_path}}}",
        (
            rf"\caption{{{_escape_latex(caption)}\protect\footnotemark}}"
            if footnote
            else rf"\caption{{{_escape_latex(caption)}}}"
        ),
        r"\end{figure}",
        *([rf"\footnotetext{{{_source_note_text(block)}}}"] if footnote else []),
    ]


def _render_list_block(block: Mapping[str, Any], *, ordered: bool) -> list[str]:
    items = block.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError("list items must be a non-empty list")

    env = "enumerate" if ordered else "itemize"
    lines = [
        rf"\begin{{{env}}}[leftmargin=1.6em,labelsep=.5em,itemsep=3pt,topsep=3pt,parsep=2pt]"
    ]
    for index, item in enumerate(items):
        if not isinstance(item, str) or not item.strip():
            raise ValueError("list item must be a non-empty string")
        suffix = _source_footnote(block) if index == len(items) - 1 else ""
        lines.append(rf"\item {_escape_latex(item)}{suffix}")
    lines.append(rf"\end{{{env}}}")
    return lines


def _render_box_block(block: Mapping[str, Any], kind: str) -> list[str]:
    title = block.get("title")
    text = _text_field(block, "box text")
    color = {
        "importantbox": "vkaBlue",
        "knowledgebox": "vkaGreen",
        "warningbox": "vkaAmber",
    }[kind]
    heading = title if isinstance(title, str) and title else {
        "importantbox": "核心提示",
        "knowledgebox": "补充知识",
        "warningbox": "易错提醒",
    }[kind]
    footnote = _source_footnote(block)
    return [
        rf"\begin{{vkabox}}{{{color}}}{{{_escape_latex(heading)}}}",
        f"{_escape_latex(text)}{footnote}",
        r"\end{vkabox}",
    ]


def _render_formula_block(block: Mapping[str, Any]) -> list[str]:
    latex = block.get("latex")
    if not isinstance(latex, str) or not latex.strip():
        raise ValueError("formula latex must be a non-empty string")
    explanation = block.get("text")
    lines: list[str] = []
    if isinstance(explanation, str) and explanation.strip():
        lines.append(_escape_latex(explanation))
    lines.extend([r"\[", latex, r"\]"])
    symbols = block.get("symbols")
    if isinstance(symbols, list) and symbols:
        lines.append(r"\begin{itemize}")
        for symbol in symbols:
            if not isinstance(symbol, str) or not symbol.strip():
                raise ValueError("formula symbol explanation must be a non-empty string")
            lines.append(rf"\item {_escape_latex(symbol)}")
        lines.append(r"\end{itemize}")
    lines.extend(_source_lines(block))
    return lines


def _render_code_block(block: Mapping[str, Any]) -> list[str]:
    code = block.get("code")
    if not isinstance(code, str) or not code.strip():
        raise ValueError("code block must contain non-empty code")
    caption = block.get("caption")
    caption_option = ""
    if isinstance(caption, str) and caption:
        caption_option = f"[caption={{{_escape_latex(caption)}}}]"
    lines = [
        rf"\begin{{lstlisting}}{caption_option}",
        code.rstrip(),
        r"\end{lstlisting}",
    ]
    lines.extend(_source_lines(block))
    return lines


def _render_table_block(block: Mapping[str, Any]) -> list[str]:
    headers, rows = _table_data(block)
    columns = "".join(r">{\raggedright\arraybackslash}X" for _ in headers)
    lines = [r"\begin{center}", rf"\begin{{tabularx}}{{\linewidth}}{{{columns}}}", r"\hline"]
    lines.append(" & ".join(_escape_table_cell(cell) for cell in headers) + r"\\")
    lines.append(r"\hline")
    for row in rows:
        lines.append(" & ".join(_escape_table_cell(cell) for cell in row) + r"\\")
    lines.extend([r"\hline", r"\end{tabularx}", r"\end{center}"])
    footnote = _source_footnote(block)
    if footnote:
        lines.append(footnote)
    return lines


def _source_lines(block: Mapping[str, Any]) -> list[str]:
    return [_source_footnote(block)]


def _source_footnote(block: Mapping[str, Any]) -> str:
    if block.get("_allow_empty_source_spans") is True and not block.get("source_spans"):
        return ""
    return rf"\footnote{{{_source_note_text(block)}}}"


def _source_note_text(block: Mapping[str, Any]) -> str:
    """Compact the source times: merge overlaps, drop the repeated prefix.

    The reader is told once, under the table of contents, that footnotes carry
    video times; repeating "来源时间：" on every line only adds noise.
    """
    spans = _source_spans(block)
    merged: list[list[int]] = []
    for span in sorted(spans, key=lambda item: item["start_ms"]):
        start_ms = span["start_ms"]
        end_ms = span["end_ms"]
        if merged and start_ms <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end_ms)
        else:
            merged.append([start_ms, end_ms])
    ranges = [f"{_format_time(start)}--{_format_time(end)}" for start, end in merged]
    return _escape_latex("，".join(ranges))


def _paragraph_text(block: Any) -> str:
    if not isinstance(block, Mapping):
        raise ValueError("block must be an object")
    if block.get("kind") != "paragraph":
        raise ValueError("unsupported block kind")
    text = block.get("text")
    if not isinstance(text, str):
        raise ValueError("paragraph text must be a string")
    return text


def _text_field(block: Mapping[str, Any], label: str) -> str:
    text = block.get("text")
    if not isinstance(text, str) or not text:
        raise ValueError(f"{label} must be a non-empty string")
    return text


def _source_spans(block: Mapping[str, Any]) -> Sequence[Any]:
    if "source_spans" not in block:
        if block.get("_allow_empty_source_spans") is True:
            return []
        raise ValueError("source_spans must be present")
    source_spans = block["source_spans"]
    if not isinstance(source_spans, list):
        raise ValueError("source_spans must be a list")
    if not source_spans and block.get("_allow_empty_source_spans") is True:
        return []
    if not source_spans:
        raise ValueError("source_spans must not be empty")
    for span in source_spans:
        _validate_source_span(span)
    return source_spans


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


def _escape_table_cell(value: str) -> str:
    """Escape prose while retaining breakable hyperlinks inside dense tables."""
    return _escape_prose_latex(value)


def _escape_prose_latex(value: str) -> str:
    """Escape prose while retaining breakable hyperlinks in any text block."""
    parts: list[str] = []
    offset = 0
    for match in URL_RE.finditer(value):
        parts.append(_escape_latex(value[offset:match.start()]))
        matched_url = match.group()
        url = matched_url.rstrip(URL_TRAILING_PUNCTUATION)
        suffix = matched_url[len(url) :]
        parts.append(rf"\url{{{_escape_url(url)}}}")
        parts.append(_escape_latex(suffix))
        offset = match.end()
    parts.append(_escape_latex(value[offset:]))
    return "".join(parts)


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
        lines.append(rf"{_escape_latex(label)} & {_metadata_value_tex(key, value.strip())}\\")
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


def _metadata_value_tex(key: str, value: str) -> str:
    if key == "source_url":
        return rf"\url{{{_escape_url(value)}}}"
    return _escape_latex(value)


def _is_sequence(value: Any) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes))


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _escape_latex(value: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "_": r"\_",
        "#": r"\#",
        "{": r"\{",
        "}": r"\}",
        "$": r"\$",
        "^": r"\textasciicircum{}",
        "~": r"\textasciitilde{}",
    }
    return "".join(replacements.get(char, char) for char in value)


def _escape_url(value: str) -> str:
    replacements = {
        "\\": "/",
        "%": r"\%",
        "#": r"\#",
        "{": r"\{",
        "}": r"\}",
    }
    return "".join(replacements.get(char, char) for char in value)


def _latex_path(value: str) -> str:
    return value.replace("\\", "/").replace("#", r"\#").replace("%", r"\%")
