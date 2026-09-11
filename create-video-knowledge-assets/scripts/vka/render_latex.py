from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from vka.quality import (
    assign_source_notes,
    document_sections_for_part,
    format_source_note,
    rebase_document_image_paths,
)

# Block kinds whose text is a claim about the source, and therefore carry a
# numbered pointer to the source-time list at the end of the document.
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
    }
)


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
    show_cover: bool = True,
    show_toc: bool = True,
    show_source_notes: bool = True,
) -> str:
    if not isinstance(title, str):
        raise ValueError("course title must be a string")
    if not _is_sequence(sections):
        raise ValueError("sections must be an array")

    sections = [dict(section) if isinstance(section, Mapping) else section for section in sections]
    _source_notes = _assign_source_notes(sections) if show_source_notes else []

    lines = [
        r"\documentclass[UTF8,a4paper]{ctexart}",
        r"\usepackage{fontspec}",
        r"\IfFontExistsTF{SimSun}{\setCJKmainfont{SimSun}}{}",
        r"\IfFontExistsTF{Microsoft YaHei}{\setCJKsansfont{Microsoft YaHei}\setCJKmonofont{Microsoft YaHei}}{}",
        r"\IfFontExistsTF{Times New Roman}{\setmainfont{Times New Roman}}{}",
        r"\usepackage[a4paper,top=2.4cm,bottom=2.6cm,left=2.5cm,right=2.5cm,includeheadfoot]{geometry}",
        r"\usepackage{graphicx}",
        r"\usepackage{float}",
        r"\usepackage{xcolor}",
        r"\usepackage{amsmath}",
        r"\usepackage{array}",
        r"\usepackage{tabularx}",
        r"\usepackage{longtable}",
        r"\usepackage{listings}",
        r"\usepackage[bottom]{footmisc}",
        r"\usepackage{caption}",
        r"\usepackage{enumitem}",
        r"\usepackage{needspace}",
        r"\usepackage{multicol}",
        r"\usepackage{hyperref}",
        r"\DeclareCaptionLabelFormat{vkagreen}{{\color{vkaGreen}#1~#2}}",
        r"\captionsetup{format=hang,width=.92\linewidth,font={small},labelfont={bf,sf},labelformat=vkagreen,labelsep=quad,justification=raggedright,singlelinecheck=false,skip=7pt}",
        r"\hypersetup{unicode=true,hidelinks}",
        r"\ctexset{section={format=\Large\bfseries\sffamily\raggedright,beforeskip=1.6em,afterskip=.6em,number={\color{vkaGreen}\arabic{section}},aftertitle={\par\nobreak\vspace{.3em}{\noindent\color{vkaRule}\rule{\linewidth}{0.4pt}}}},subsection={format=\large\bfseries\sffamily\raggedright,beforeskip=1.2em,afterskip=.5em}}",
        r"\renewcommand{\contentsname}{目录}",
        r"\renewcommand{\numberline}[1]{{\color{vkaGreen}#1}}",
        r"\pagestyle{plain}",
        r"\setcounter{tocdepth}{2}",
        r"\setcounter{secnumdepth}{2}",
        r"\AtBeginDocument{\fontsize{10.5}{16.5}\selectfont}",
        # A boundary document is a companion note rather than an article, so it
        # is set a little tighter to stay short.
        rf"\setlength{{\parskip}}{{{'0.3em' if not show_cover else '0.45em'}}}",
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
        r"\definecolor{vkaInk}{HTML}{1A1A1A}",
        r"\definecolor{vkaMuted}{HTML}{8A8A8A}",
        r"\definecolor{vkaRule}{HTML}{DCDCDC}",
        r"\setlength{\fboxsep}{0pt}",
        r"\setlength{\fboxrule}{0.4pt}",
        r"\newsavebox{\vkapic}",
        r"\color{vkaInk}",
        r"\newenvironment{vkabox}[2]{\par\medskip\noindent{\color{#1}\rule{0.8em}{0.8em}}\hspace{0.4em}\textbf{#2}\par\smallskip\noindent\begingroup\leftskip=1.2em\rightskip=0.6em\ignorespaces}{\par\endgroup\medskip}",
        r"\lstset{basicstyle=\ttfamily\small,breaklines=true,columns=fullflexible,frame=single}",
        "",
        r"\begin{document}",
    ]

    if show_cover:
        lines.extend(
            [
                r"\begin{titlepage}",
                r"\thispagestyle{empty}",
                r"\centering",
                r"\vspace*{0.02\textheight}",
                r"\begin{center}\begin{minipage}{0.94\textwidth}\centering",
                rf"{{\sffamily\bfseries\fontsize{{24}}{{32}}\selectfont {_cover_title_latex(title)}\par}}",
                r"\end{minipage}\end{center}",
            ]
        )
    else:
        # A boundary document is a short companion, not a publication: give it
        # a heading line instead of a cover page nobody needs to turn past.
        lines.extend(
            [
                rf"{{\sffamily\bfseries\fontsize{{15}}{{20}}\selectfont {_escape_latex(title)}\par}}",
                r"\vspace{0.35em}",
                r"\noindent{\color{vkaRule}\rule{\linewidth}{0.4pt}}",
                r"\vspace{0.9em}",
            ]
        )

    if show_cover and theme:
        lines.extend(
            [
                r"\vspace{0.35cm}",
                rf"{{\sffamily\fontsize{{14}}{{20}}\selectfont\color{{vkaGreen}} {_escape_latex(theme)}\par}}",
            ]
        )
    if show_cover and one_sentence_summary:
        lines.extend(
            [
                r"\vspace{0.45cm}",
                r"\begin{center}",
                r"\begin{minipage}{0.76\textwidth}",
                r"\raggedright\fontsize{10.5}{16}\selectfont\color{vkaMuted}",
                rf"{_escape_latex(one_sentence_summary)}\par",
                r"\end{minipage}",
                r"\end{center}",
            ]
        )
    if show_cover and subtitle:
        lines.extend(
            [
                r"\vspace{0.45cm}",
                rf"{{\sffamily\fontsize{{9.5}}{{13}}\selectfont\color{{vkaMuted}} {_escape_latex(subtitle)}\par}}",
            ]
        )

    if show_cover and cover_image:
        lines.extend(
            [
                r"\vspace{0.6cm}",
                r"\begin{center}",
                rf"\fcolorbox{{vkaRule}}{{white}}{{\includegraphics[width=0.62\linewidth,height=0.21\textheight,keepaspectratio]{{{_latex_path(cover_image)}}}}}",
                r"\end{center}",
            ]
        )

    metadata_lines = _metadata_lines(metadata)
    if metadata_lines:
        lines.extend(
            [
                r"\vspace{0.5cm}",
                r"\begin{center}",
                r"\begin{minipage}{0.8\textwidth}",
                r"\centering\sffamily\fontsize{8.5}{13}\selectfont\color{vkaMuted}",
                *(line + r"\par" for line in _compact_metadata(metadata)),
                r"\end{minipage}",
                r"\end{center}",
            ]
        )

    if show_cover:
        lines.append(r"\end{titlepage}")
    lines.append(r"\pagenumbering{arabic}")
    # The contents list opens the first content page instead of taking a page
    # of its own: a short document's table of contents is a signpost, and a
    # signpost on an otherwise empty page reads as a missing file.
    if show_toc and sections:
        lines.extend(
            [
                r"\begingroup",
                r"\ctexset{section={format=\sffamily\bfseries\fontsize{10.5}{14}\selectfont,beforeskip=0pt,afterskip=.6em,aftertitle={}}}",
                r"\tableofcontents",
                r"\endgroup",
                r"\vspace{0.5\baselineskip}",
            ]
        )
    lines.append("")

    for section_index, section in enumerate(sections):
        section_title = _section_title(section)
        if section_index:
            lines.append(r"\par\vspace{1.15\baselineskip}")
        lines.append(rf"\section{{{_escape_latex(section_title)}}}")
        lines.append("")

        for block in _section_blocks(section):
            lines.extend(_render_block(block))
            lines.append("")

        lines.append(r"\vspace{0.6\baselineskip}")

    notes = _source_notes if show_source_notes else []
    if notes:
        lines.extend(
            [
                r"\needspace{5\baselineskip}",
                r"\vspace{1.5\baselineskip}",
                r"{\sffamily\bfseries\fontsize{11}{14}\selectfont\color{vkaGreen} 来源时间\par}",
                r"\vspace{0.3\baselineskip}",
                r"\noindent{\color{vkaRule}\rule{\linewidth}{0.4pt}}",
                r"\vspace{0.5\baselineskip}",
                r"{\fontsize{8.5}{13}\selectfont\color{vkaMuted} 正文中的上标编号对应下面列出的时间范围，标注该段内容在视频中的位置。\par}",
                r"\vspace{0.4\baselineskip}",
                r"{\fontsize{8}{11.5}\selectfont\ttfamily\color{black!65}",
                r"\begin{multicols}{2}",
                r"\begin{enumerate}[leftmargin=1.8em,labelsep=.5em,itemsep=2pt,topsep=3pt]",
                *(rf"\item {text}" for _, text in notes),
                r"\end{enumerate}",
                r"\end{multicols}",
                r"}",
            ]
        )
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
    is_reader_part = part == "main"
    return render_course_tex(
        title,
        sections,
        cover_image=_optional_string(document, "cover_image") if is_reader_part else None,
        subtitle=_optional_string(document, "subtitle") if is_reader_part else None,
        theme=_optional_string(document, "theme") if is_reader_part else None,
        one_sentence_summary=(
            _optional_string(document, "one_sentence_summary") if is_reader_part else None
        ),
        metadata=_optional_mapping(document, "metadata"),
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

    marker = _source_footnote(block)
    latex_path = _latex_path(path)
    return [
        r"\begin{center}",
        rf"\sbox{{\vkapic}}{{\fcolorbox{{vkaRule}}{{white}}{{\includegraphics[width=0.9\linewidth,height=0.27\textheight,keepaspectratio]{{{latex_path}}}}}}}",
        r"\begin{minipage}{\wd\vkapic}",
        r"\centering",
        r"\usebox{\vkapic}\par",
        r"\captionsetup{width=\wd\vkapic}",
        rf"\captionof{{figure}}{{{_escape_latex(caption)}{marker}}}",
        r"\end{minipage}",
        r"\end{center}",
        r"\vspace{0.4\baselineskip}",
    ]


def _render_list_block(block: Mapping[str, Any], *, ordered: bool) -> list[str]:
    items = block.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError("list items must be a non-empty list")

    env = "enumerate" if ordered else "itemize"
    lines = [
        rf"\begin{{{env}}}[leftmargin=1.6em,labelsep=.5em,itemsep=2pt,topsep=2pt,parsep=1pt]"
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
    # The citation rides in the last cell: a marker emitted after the table
    # would otherwise be stranded alone at the foot of the page.
    footnote = _source_footnote(block)
    cells = [[_escape_table_cell(cell) for cell in row] for row in rows]
    if footnote:
        cells[-1][-1] = cells[-1][-1] + footnote
    # Equal-width wrapping columns. `longtable` is in LaTeX's own tools bundle,
    # so a table that outgrows a page can break without a new dependency.
    width = rf"\dimexpr(\linewidth-{2 * len(headers)}\tabcolsep)/{len(headers)}\relax"
    columns = "".join(rf">{{\raggedright\arraybackslash}}p{{{width}}}" for _ in headers)
    # A table may be longer than a page (a tutorial's step ledger is), so it
    # breaks across pages and repeats its header instead of jumping whole.
    lines = [
        r"{\renewcommand{\arraystretch}{1.2}\small",
        rf"\begin{{longtable}}{{{columns}}}",
        r"\hline",
    ]
    lines.append(" & ".join(_escape_table_cell(cell) for cell in headers) + r"\\")
    lines.append(r"\hline")
    lines.append(r"\endhead")
    for row in cells:
        lines.append(" & ".join(row) + r"\\")
    lines.extend([r"\hline", r"\end{longtable}", r"}"])
    return lines


def _source_lines(block: Mapping[str, Any]) -> list[str]:
    return [_source_footnote(block)]


def _source_footnote(block: Mapping[str, Any]) -> str:
    """Mark the claim in place; the source times are listed at the end."""
    number = block.get("_note_number")
    if not isinstance(number, int):
        return ""
    return rf"\textsuperscript{{{number}}}"


def _assign_source_notes(sections: Sequence[Any]) -> list[tuple[int, str]]:
    """Number every sourced block once, for the end-of-document source list."""
    return assign_source_notes(
        sections,
        sourced_kinds=SOURCED_BLOCK_KINDS,
        spans_of=_source_spans,
    )


def _source_note_text(block: Mapping[str, Any]) -> str:
    """Compact the source times, without repeating a prefix on every line."""
    return _escape_latex(format_source_note(_source_spans(block)))


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


def _compact_metadata(metadata: Mapping[str, Any] | None) -> list[str]:
    """One or two grey lines of source attribution, not an eight-row form."""
    if not isinstance(metadata, Mapping):
        return []
    parts: list[str] = []
    for key in ("source_title", "author", "uploader", "publish_date", "duration"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            text = value.strip().strip("《》")
            rendered = f"《{text}》" if key == "source_title" else text
            if rendered not in parts:
                parts.append(rendered)

    notes: list[str] = []
    for key in ("subtitle_source", "transcript_source"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            notes.append(value.strip())

    lines: list[str] = []
    if parts:
        lines.append(_escape_latex("　·　".join(parts)))
    if notes:
        lines.append(_escape_latex("；".join(notes)))
    url = metadata.get("source_url")
    if isinstance(url, str) and url.strip():
        lines.append(_escape_latex(url.strip()))
    return lines


def _cover_title_latex(title: str) -> str:
    """Break a Chinese title at its colon, the way its author would.

    Left to itself LaTeX breaks a long centred title wherever the measure
    runs out, which splits a word across two lines.
    """
    escaped = _escape_latex(title)
    head, separator, tail = escaped.partition("：")
    if separator and tail.strip():
        return head + separator + r"\\" + tail
    return escaped


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
