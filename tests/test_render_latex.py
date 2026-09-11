import subprocess

import pytest

from vka.render_latex import render_course_tex, render_document_tex
from vka.render_html import render_document_html
from vka.render_markdown import render_document_markdown
from vka_cli import main, render_all_formats


def test_document_tex_renders_table_and_caption_with_source_footnote() -> None:
    tex = render_document_tex({
        "profile_id": "general-deep", "title": "Table view", "blocks": [
            {
                "kind": "heading", "text": "Comparison", "data": {"section_kind": "overview"},
                "knowledge_refs": ["ku-h"], "evidence_refs": ["tr-h"],
                "source_spans": [{"start_ms": 0, "end_ms": 2_000}],
            },
            {
                "kind": "table", "data": {"headers": ["Measure", "Value"], "rows": [["Latency", "20 ms"]]},
                "knowledge_refs": ["ku-t"], "evidence_refs": ["tr-t"],
                "source_spans": [{"start_ms": 2_000, "end_ms": 4_000}],
            },
            {
                "kind": "caption", "text": "The values are illustrative.",
                "knowledge_refs": ["ku-c"], "evidence_refs": ["tr-c"],
                "source_spans": [{"start_ms": 4_000, "end_ms": 6_000}],
            },
        ],
    })

    assert r"\begin{tabularx}{\linewidth}" in tex
    assert "Measure & Value" in tex
    assert r"\textit{The values are illustrative.}" in tex
    assert "00:00:02--00:00:04" in tex


def test_document_tex_uses_wrapping_tabularx_columns_for_long_chinese_cells() -> None:
    tex = render_document_tex({
        "profile_id": "general-deep", "title": "Long table", "blocks": [
            {
                "kind": "heading", "text": "Comparison", "data": {"section_kind": "overview"},
                "knowledge_refs": ["ku-h"], "evidence_refs": ["tr-h"],
                "source_spans": [{"start_ms": 0, "end_ms": 2_000}],
            },
            {
                "kind": "table", "data": {
                    "headers": ["维度", "长说明"],
                    "rows": [["适用范围", "这是一段足够长的中文说明，用于确认表格单元格在 A4 页面上会自动换行，而不是越过右侧页面边界。"]],
                },
                "knowledge_refs": ["ku-t"], "evidence_refs": ["tr-t"],
                "source_spans": [{"start_ms": 2_000, "end_ms": 4_000}],
            },
        ],
    })

    assert r"\begin{tabularx}{\linewidth}" in tex
    assert r">{\raggedright\arraybackslash}X" in tex
    assert r"\end{tabularx}" in tex


def test_document_tex_wraps_long_url_table_cells_with_url_macro() -> None:
    long_url = "https://example.test/reports/very-long-path/with_many_segments?query=still_long&mode=table"
    tex = render_document_tex({
        "profile_id": "general-deep", "title": "URL table", "blocks": [
            {
                "kind": "heading", "text": "Sources", "data": {"section_kind": "overview"},
                "knowledge_refs": ["ku-h"], "evidence_refs": ["tr-h"],
                "source_spans": [{"start_ms": 0, "end_ms": 2_000}],
            },
            {
                "kind": "table", "data": {"headers": ["Source", "URL"], "rows": [["Report", long_url]]},
                "knowledge_refs": ["ku-t"], "evidence_refs": ["tr-t"],
                "source_spans": [{"start_ms": 2_000, "end_ms": 4_000}],
            },
        ],
    })

    escaped_url = long_url.replace("%", r"\%").replace("#", r"\#")
    assert rf"\url{{{escaped_url}}}" in tex


def test_document_tex_wraps_long_url_paragraphs_with_url_macro() -> None:
    tex = render_document_tex({
        "profile_id": "general-deep", "title": "URL paragraph", "blocks": [
            {
                "kind": "paragraph",
                "text": "来源导航：https://example.test/video/BV1tHdoYnEGm。继续阅读。",
                "knowledge_refs": ["ku-p"], "evidence_refs": ["tr-p"],
                "source_spans": [{"start_ms": 0, "end_ms": 2_000}],
            }
        ],
    })

    assert r"\url{https://example.test/video/BV1tHdoYnEGm}" in tex
    assert r"\url{https://example.test/video/BV1tHdoYnEGm}。" in tex


@pytest.mark.parametrize(
    "renderer",
    [render_document_markdown, render_document_html, render_document_tex],
)
def test_direct_document_renderers_reject_unsafe_cover_paths(renderer) -> None:
    document = {
        "profile_id": "general-deep", "title": "Unsafe cover", "cover_image": "../secret.jpg",
        "blocks": [{
            "kind": "heading", "text": "Overview", "data": {"section_kind": "overview"},
            "knowledge_refs": ["ku-h"], "evidence_refs": ["tr-h"],
            "source_spans": [{"start_ms": 0, "end_ms": 2_000}],
        }],
    }

    with pytest.raises(ValueError, match="cover_image must preserve a safe local image_path"):
        renderer(document)


def test_render_all_formats_rejects_missing_asset_root_image(tmp_path) -> None:
    document = {
        "profile_id": "general-deep", "title": "Image view", "blocks": [
            {
                "kind": "heading", "text": "Visual", "data": {"section_kind": "overview"},
                "knowledge_refs": ["ku-h"], "evidence_refs": ["tr-h"],
                "source_spans": [{"start_ms": 0, "end_ms": 2_000}],
            },
            {
                "kind": "image", "image_path": "evidence/frames/missing.jpg", "caption": "Missing image.",
                "knowledge_refs": ["ku-i"], "evidence_refs": ["fr-i"],
                "source_spans": [{"start_ms": 2_000, "end_ms": 4_000}],
            },
        ],
    }

    with pytest.raises(ValueError, match="image_path does not exist"):
        render_all_formats(document, tmp_path / "output", asset_root=tmp_path / "asset")


def test_render_all_formats_rebases_asset_images_for_independent_outputs(tmp_path) -> None:
    asset_root = tmp_path / "asset"
    image_path = asset_root / "source" / "frames" / "chart.jpg"
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(b"image")
    cover_path = asset_root / "source" / "cover.jpg"
    cover_path.write_bytes(b"cover")
    document = {
        "profile_id": "general-deep", "title": "Image view", "cover_image": "source/cover.jpg", "blocks": [
            {
                "kind": "heading", "text": "Visual", "data": {"section_kind": "overview"},
                "knowledge_refs": ["ku-h"], "evidence_refs": ["tr-h"],
                "source_spans": [{"start_ms": 0, "end_ms": 2_000}],
            },
            {
                "kind": "image", "image_path": "source/frames/chart.jpg", "caption": "Chart.",
                "knowledge_refs": ["ku-i"], "evidence_refs": ["fr-i"],
                "source_spans": [{"start_ms": 2_000, "end_ms": 4_000}],
            },
        ],
    }
    output_directory = asset_root / "outputs" / "general-deep"

    outputs = render_all_formats(document, output_directory, asset_root=asset_root)

    relative_path = "../../source/frames/chart.jpg"
    assert relative_path in outputs["md"].read_text(encoding="utf-8")
    assert relative_path in outputs["html"].read_text(encoding="utf-8")
    assert relative_path in outputs["tex"].read_text(encoding="utf-8")
    assert "../../source/cover.jpg" in outputs["md"].read_text(encoding="utf-8")
    assert "../../source/cover.jpg" in outputs["html"].read_text(encoding="utf-8")
    assert "../../source/cover.jpg" in outputs["tex"].read_text(encoding="utf-8")
    assert (outputs["html"].parent / relative_path).resolve() == image_path.resolve()
    assert (outputs["html"].parent / "../../source/cover.jpg").resolve() == cover_path.resolve()


@pytest.mark.parametrize("cover_image", ["../outside.jpg", "source/missing.jpg"])
def test_render_all_formats_rejects_unsafe_or_missing_cover_without_output(tmp_path, cover_image) -> None:
    asset_root = tmp_path / "asset"
    output_directory = asset_root / "outputs" / "general-deep"
    document = {
        "profile_id": "general-deep", "title": "Cover view", "cover_image": cover_image,
        "blocks": [{
            "kind": "heading", "text": "Overview", "data": {"section_kind": "overview"},
            "knowledge_refs": ["ku-h"], "evidence_refs": ["tr-h"],
            "source_spans": [{"start_ms": 0, "end_ms": 2_000}],
        }],
    }

    with pytest.raises(ValueError):
        render_all_formats(document, output_directory, asset_root=asset_root)

    assert not (output_directory / "document.md").exists()


def test_render_all_formats_rejects_image_symlink_escaping_asset_root(tmp_path) -> None:
    asset_root = tmp_path / "asset"
    outside_image = tmp_path / "outside.jpg"
    outside_image.write_bytes(b"outside")
    image_link = asset_root / "source" / "frames" / "escape.jpg"
    image_link.parent.mkdir(parents=True)
    try:
        image_link.symlink_to(outside_image)
    except OSError:
        pytest.skip("symbolic links are unavailable in this environment")
    document = {
        "profile_id": "general-deep", "title": "Unsafe image", "blocks": [
            {
                "kind": "heading", "text": "Visual", "data": {"section_kind": "overview"},
                "knowledge_refs": ["ku-h"], "evidence_refs": ["tr-h"],
                "source_spans": [{"start_ms": 0, "end_ms": 2_000}],
            },
            {
                "kind": "image", "image_path": "source/frames/escape.jpg", "caption": "Escaped image.",
                "knowledge_refs": ["ku-i"], "evidence_refs": ["fr-i"],
                "source_spans": [{"start_ms": 2_000, "end_ms": 4_000}],
            },
        ],
    }
    output_directory = asset_root / "outputs" / "general-deep"

    with pytest.raises(ValueError, match="symlink"):
        render_all_formats(document, output_directory, asset_root=asset_root)

    assert not (output_directory / "document.md").exists()


def test_general_document_tex_keeps_time_footnotes_and_all_formats_write(tmp_path) -> None:
    document = {
        "profile_id": "general-deep", "title": "访谈", "sections": [{"title": "概览", "blocks": [{
            "kind": "paragraph", "text": "关键结论：受访者将可靠性视为持续权衡。",
            "knowledge_refs": ["ku-1"], "evidence_refs": ["tr-1"],
            "source_spans": [{"start_ms": 10000, "end_ms": 18000}],
        }]}],
    }
    tex = render_document_tex(document)
    outputs = render_all_formats(document, tmp_path)

    assert "00:00:10--00:00:18" in tex
    assert "关键结论" in outputs["md"].read_text(encoding="utf-8")
    assert "00:00:10--00:00:18" in outputs["tex"].read_text(encoding="utf-8")


def test_short_video_script_hides_source_footnotes_but_keeps_them_elsewhere(
    tmp_path,
) -> None:
    script = {
        "profile_id": "short-video-script", "title": "脚本", "sections": [{"title": "开场", "blocks": [{
            "kind": "paragraph", "text": "三年少卖十个亿，这是开场的第一句。",
            "knowledge_refs": ["ku-1"], "evidence_refs": ["tr-1"],
            "source_spans": [{"start_ms": 0, "end_ms": 1680}],
        }]}],
    }
    deep = {**script, "profile_id": "general-deep"}

    script_outputs = render_all_formats(script, tmp_path / "script")
    deep_tex = render_all_formats(deep, tmp_path / "deep")["tex"].read_text(encoding="utf-8")

    script_tex = script_outputs["tex"].read_text(encoding="utf-8")
    assert r"\section*{来源时间}" not in script_tex
    assert "00:00:00--00:00:01" not in script_tex
    assert "开场" in script_tex
    assert r"\item 00:00:00--00:00:01" in deep_tex


def test_renderer_writes_section_with_bottom_time_footnote() -> None:
    tex = render_course_tex(
        "测试课程",
        [
            {
                "title": "核心概念",
                "blocks": [
                    {
                        "kind": "paragraph",
                        "text": "这是解释。",
                        "source_spans": [{"start_ms": 12_000, "end_ms": 16_000}],
                    }
                ],
            }
        ],
    )
    assert "\\section{核心概念}" in tex
    assert "\\documentclass[UTF8,a4paper]{ctexart}" in tex
    assert "00:00:12--00:00:16" in tex
    assert r"\textsuperscript{1}" in tex


def test_renderer_writes_cover_image_and_subtitle() -> None:
    tex = render_course_tex(
        "测试课程",
        [],
        cover_image="source/cover.jpg",
        subtitle="视频标题与来源说明",
        theme="核心主题",
        one_sentence_summary="一句话说明这门课真正要解决的问题。",
        metadata={
            "source_title": "原视频标题",
            "author": "讲者",
            "publish_date": "2026-07-11",
            "subtitle_source": "ASR repaired",
        },
    )

    assert r"\begin{titlepage}" in tex
    assert "核心主题" in tex and r"\color{vkaGreen}" in tex
    assert "一句话说明这门课真正要解决的问题" in tex
    assert "一份基于视频证据的深度总结" in tex or "视频标题与来源说明" in tex
    assert "原视频标题" in tex
    assert "ASR repaired" in tex
    assert (
        r"\includegraphics[width=0.52\linewidth,height=0.21\textheight,keepaspectratio]"
        r"{source/cover.jpg}"
    ) in tex
    assert tex.index(r"\end{titlepage}") < tex.index(r"\tableofcontents")


def test_renderer_escapes_latex_special_characters_without_touching_time() -> None:
    tex = render_course_tex(
        r"标题 & % _ # \ { } $ ^ ~",
        [
            {
                "title": r"章节 & % _ # \ { } $ ^ ~",
                "blocks": [
                    {
                        "kind": "paragraph",
                        "text": r"正文 & % _ # \ { } $ ^ ~",
                        "source_spans": [{"start_ms": 12_000, "end_ms": 16_000}],
                    }
                ],
            }
        ],
    )

    assert r"\&" in tex
    assert r"\%" in tex
    assert r"\_" in tex
    assert r"\#" in tex
    assert r"\textbackslash{}" in tex
    assert r"\{" in tex
    assert r"\}" in tex
    assert r"\$" in tex
    assert r"\textasciicircum{}" in tex
    assert r"\textasciitilde{}" in tex
    assert "00:00:12--00:00:16" in tex


def test_renderer_validates_and_renders_multiple_source_spans() -> None:
    tex = render_course_tex(
        "测试课程",
        [
            {
                "title": "核心概念",
                "blocks": [
                    {
                        "kind": "paragraph",
                        "text": "这是解释。",
                        "source_spans": [
                            {"start_ms": 12_000, "end_ms": 16_000},
                            {"start_ms": 20_000, "end_ms": 24_000},
                        ],
                    }
                ],
            }
        ],
    )

    assert "00:00:12--00:00:16" in tex
    assert "00:00:20--00:00:24" in tex
    assert r"\textsuperscript{1}" in tex


def test_renderer_writes_image_block_with_caption_and_source() -> None:
    tex = render_course_tex(
        "Image Test",
        [
            {
                "title": "Visual Evidence",
                "blocks": [
                    {
                        "kind": "image",
                        "path": "evidence/frames/frame-001.jpg",
                        "caption": "A directly inspected frame.",
                        "source_spans": [{"start_ms": 12_000, "end_ms": 16_000}],
                    }
                ],
            }
        ],
    )

    assert r"\usepackage{graphicx}" in tex
    assert r"\begin{figure}[htbp]" in tex
    assert (
        r"\includegraphics[width=\linewidth,height=0.32\textheight,keepaspectratio]"
        r"{evidence/frames/frame-001.jpg}"
    ) in tex
    assert r"\caption{A directly inspected frame.\textsuperscript{1}}" in tex
    assert r"\item 00:00:12--00:00:16" in tex
    assert "00:00:12--00:00:16" in tex


def test_renderer_writes_teaching_blocks_formula_and_code() -> None:
    tex = render_course_tex(
        "Rich Test",
        [
            {
                "title": "核心机制",
                "blocks": [
                    {"kind": "subsection", "title": "机制解释"},
                    {
                        "kind": "importantbox",
                        "title": "主线",
                        "text": "Q 提出查询，K 提供索引，V 承载信息。",
                        "source_spans": [{"start_ms": 12_000, "end_ms": 16_000}],
                    },
                    {
                        "kind": "formula",
                        "text": "缩放点积注意力把匹配分数变成权重。",
                        "latex": r"\mathrm{Attention}(Q,K,V)=\mathrm{softmax}(QK^T/\sqrt{d_k})V",
                        "symbols": ["Q 表示 Query。", "K 表示 Key。"],
                        "source_spans": [{"start_ms": 20_000, "end_ms": 30_000}],
                    },
                    {
                        "kind": "code",
                        "caption": "注意力伪代码",
                        "code": "scores = q @ k.T\nweights = softmax(scores)",
                        "source_spans": [{"start_ms": 30_000, "end_ms": 40_000}],
                    },
                    {
                        "kind": "bullet_list",
                        "items": ["先算相似度。", "再汇总 Value。"],
                        "source_spans": [{"start_ms": 40_000, "end_ms": 50_000}],
                    },
                ],
            }
        ],
    )

    assert r"\subsection{机制解释}" in tex
    assert r"\begin{vkabox}" in tex
    assert r"\mathrm{Attention}(Q,K,V)" in tex
    assert r"\begin{lstlisting}" in tex
    assert r"\begin{itemize}" in tex


@pytest.mark.parametrize(
    "source_span",
    [
        {"start_ms": -1, "end_ms": 16_000},
        {"start_ms": 12_000, "end_ms": -1},
        {"start_ms": 16_000, "end_ms": 12_000},
        {"start_ms": 12_000, "end_ms": 12_000},
    ],
)
def test_renderer_rejects_invalid_source_spans(source_span) -> None:
    with pytest.raises(ValueError):
        render_course_tex(
            "测试课程",
            [
                {
                    "title": "核心概念",
                    "blocks": [
                        {
                            "kind": "paragraph",
                            "text": "这是解释。",
                            "source_spans": [source_span],
                        }
                    ],
                }
            ],
        )


@pytest.mark.parametrize(
    "section",
    [
        "not a mapping",
        {"title": "核心概念"},
        {"blocks": []},
        {"title": "核心概念", "blocks": {}},
        {"title": "核心概念", "blocks": ["not a mapping"]},
        {"title": "核心概念", "blocks": [{"kind": "list", "text": "x"}]},
        {"title": "核心概念", "blocks": [{"kind": "paragraph"}]},
        {"title": "核心概念", "blocks": [{"kind": "paragraph", "text": 123}]},
        {"title": "核心概念", "blocks": [{"kind": "paragraph", "text": "x"}]},
        {
            "title": "核心概念",
            "blocks": [{"kind": "paragraph", "text": "x", "source_spans": {}}],
        },
        {
            "title": "核心概念",
            "blocks": [{"kind": "paragraph", "text": "x", "source_spans": []}],
        },
    ],
)
def test_renderer_rejects_invalid_sections_and_blocks(section) -> None:
    with pytest.raises(ValueError):
        render_course_tex("测试课程", [section])


def test_cli_render_course_rejects_invalid_json_without_traceback(tmp_path, capsys) -> None:
    input_path = tmp_path / "document.json"
    output_path = tmp_path / "notes.tex"
    input_path.write_text("{", encoding="utf-8")

    exit_code = main(
        ["render-course", "--input", str(input_path), "--output", str(output_path)]
    )

    captured = capsys.readouterr()
    assert exit_code != 0
    assert "error: invalid course document JSON:" in captured.err
    assert "Traceback" not in captured.err
    assert "Traceback" not in captured.out
    assert not output_path.exists()


def test_cli_render_course_rejects_missing_sections_without_traceback(
    tmp_path,
    capsys,
) -> None:
    input_path = tmp_path / "document.json"
    output_path = tmp_path / "notes.tex"
    input_path.write_text('{"title": "Only title"}', encoding="utf-8")

    exit_code = main(
        ["render-course", "--input", str(input_path), "--output", str(output_path)]
    )

    captured = capsys.readouterr()
    assert exit_code != 0
    assert "error:" in captured.err
    assert "Traceback" not in captured.err
    assert "Traceback" not in captured.out
    assert not output_path.exists()


def test_cli_render_course_reports_missing_input_without_traceback(tmp_path, capsys) -> None:
    output_path = tmp_path / "notes.tex"

    exit_code = main(
        [
            "render-course",
            "--input",
            str(tmp_path / "missing.json"),
            "--output",
            str(output_path),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code != 0
    assert "error: failed to render course:" in captured.err
    assert "Traceback" not in captured.err
    assert "Traceback" not in captured.out
    assert not output_path.exists()


def test_cli_render_course_reports_output_write_failure_without_traceback(
    tmp_path,
    capsys,
) -> None:
    input_path = tmp_path / "document.json"
    input_path.write_text(
        '{"title":"测试课程","sections":[{"title":"核心概念","blocks":[]}]}',
        encoding="utf-8",
    )

    exit_code = main(
        [
            "render-course",
            "--input",
            str(input_path),
            "--output",
            str(tmp_path),
            "--quality-floor",
            "smoke",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code != 0
    assert "error: failed to render course:" in captured.err
    assert "Traceback" not in captured.err
    assert "Traceback" not in captured.out


def test_cli_compile_pdf_reports_missing_xelatex(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setattr("vka_cli.find_command", lambda command: None)

    exit_code = main(
        [
            "compile-pdf",
            "--tex",
            str(tmp_path / "notes.tex"),
            "--output-directory",
            str(tmp_path / "build"),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code != 0
    assert "error: xelatex was not found on PATH" in captured.err
    assert "Traceback" not in captured.err


def test_cli_compile_pdf_writes_failed_build_log(monkeypatch, tmp_path, capsys) -> None:
    def fake_run(command, *, check, capture_output, text, **kwargs):
        raise subprocess.CalledProcessError(
            returncode=1,
            cmd=command,
            output="xelatex stdout",
            stderr="xelatex stderr",
        )

    output_directory = tmp_path / "asset" / "build"
    monkeypatch.setattr("vka_cli.find_command", lambda command: "xelatex")
    monkeypatch.setattr("vka_cli.subprocess.run", fake_run)

    exit_code = main(
        [
            "compile-pdf",
            "--tex",
            str(tmp_path / "notes.tex"),
            "--output-directory",
            str(output_directory),
        ]
    )

    captured = capsys.readouterr()
    log_path = tmp_path / "asset" / "logs" / "latex-build.log"
    assert exit_code == 1
    assert "error: xelatex failed (exit 1)" in captured.err
    assert "Traceback" not in captured.err
    assert "xelatex stdout" in log_path.read_text(encoding="utf-8")
    assert "xelatex stderr" in log_path.read_text(encoding="utf-8")


def test_cli_compile_pdf_reports_output_directory_failure_without_traceback(
    monkeypatch,
    tmp_path,
    capsys,
) -> None:
    output_directory = tmp_path / "not-a-directory"
    output_directory.write_text("occupied", encoding="utf-8")
    monkeypatch.setattr("vka_cli.find_command", lambda command: "xelatex")

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "compile-pdf",
                "--tex",
                str(tmp_path / "notes.tex"),
                "--output-directory",
                str(output_directory),
            ]
        )

    captured = capsys.readouterr()
    assert exc_info.value.code == 1
    assert "error:" in captured.err
    assert "Traceback" not in captured.err
