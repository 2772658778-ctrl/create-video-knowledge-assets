from vka.render_markdown import render_course_markdown, render_document_markdown


def test_document_markdown_renders_table_and_caption() -> None:
    markdown = render_document_markdown({
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

    assert "| Measure | Value |" in markdown
    assert "| Latency | 20 ms |" in markdown
    assert "*The values are illustrative.*" in markdown


def test_external_document_block_renders_without_a_video_time_span() -> None:
    markdown = render_document_markdown({
        "profile_id": "general-deep", "title": "External view",
        "evidence_origins": {"paper-42": "external"}, "blocks": [
            {
                "kind": "heading", "text": "External context", "data": {"section_kind": "overview"},
                "knowledge_refs": ["ku-h"], "evidence_refs": ["tr-h"],
                "source_spans": [{"start_ms": 0, "end_ms": 2_000}],
            },
            {
                "kind": "paragraph", "text": "An external report provides this comparison.",
                "knowledge_refs": ["ku-e"], "evidence_refs": ["paper-42"],
            },
        ],
    })

    assert "An external report provides this comparison." in markdown


def test_general_document_markdown_preserves_conclusion_without_audit_text() -> None:
    markdown = render_document_markdown(_general_document())

    assert "关键结论" in markdown
    assert "00:00:10--00:00:18" not in markdown
    assert "source_spans" not in markdown


def _general_document() -> dict:
    return {
        "profile_id": "general-deep",
        "title": "访谈",
        "metadata": {"source_title": "访谈原片", "source_url": "https://example.test/video"},
        "sections": [
            {
                "kind": "overview", "title": "概览", "blocks": [{
                    "kind": "paragraph", "text": "关键结论：受访者将可靠性视为持续权衡。",
                    "knowledge_refs": ["ku-1"], "evidence_refs": ["tr-1"],
                    "source_spans": [{"start_ms": 10000, "end_ms": 18000}],
                }],
            },
            {
                "kind": "logical_body", "title": "理由", "blocks": [{
                    "kind": "image", "image_path": "evidence/frames/chart.jpg", "caption": "访谈中展示的趋势图。",
                    "knowledge_refs": ["ku-2"], "evidence_refs": ["fr-1"],
                    "source_spans": [{"start_ms": 20000, "end_ms": 28000}],
                }],
            },
            {
                "kind": "logical_body", "title": "取舍", "blocks": [{
                    "kind": "paragraph", "text": "成本和恢复时间决定具体方案。",
                    "knowledge_refs": ["ku-3"], "evidence_refs": ["tr-2"],
                    "source_spans": [{"start_ms": 30000, "end_ms": 38000}],
                }],
            },
            {
                "kind": "limitations", "title": "局限性", "blocks": [{
                    "kind": "paragraph", "text": "访谈未给出不同规模团队的量化比较。",
                    "knowledge_refs": ["ku-4"], "evidence_refs": ["tr-3"],
                    "source_spans": [{"start_ms": 40000, "end_ms": 48000}],
                }],
            },
            {
                "kind": "source_navigation", "title": "来源导航", "blocks": [{
                    "kind": "paragraph", "text": "前半段解释原则，后半段讨论条件。",
                    "knowledge_refs": ["ku-5"], "evidence_refs": ["tr-4"],
                    "source_spans": [{"start_ms": 50000, "end_ms": 58000}],
                }],
            },
        ],
    }
from vka_cli import main


def test_markdown_renderer_writes_semantic_blocks() -> None:
    markdown = render_course_markdown(
        "注意力机制",
        [
            {
                "title": "核心机制",
                "blocks": [
                    {
                        "kind": "paragraph",
                        "text": "注意力机制把匹配和汇总拆成两个步骤。",
                        "source_spans": [{"start_ms": 10_000, "end_ms": 18_000}],
                    },
                    {"kind": "subsection", "title": "本章小结"},
                    {
                        "kind": "importantbox",
                        "title": "主线",
                        "text": "Q 提问，K 匹配，V 提供内容。",
                        "source_spans": [{"start_ms": 20_000, "end_ms": 30_000}],
                    },
                    {
                        "kind": "image",
                        "path": "frames/attention.jpg",
                        "caption": "直接检查过的注意力公式画面。",
                        "source_spans": [{"start_ms": 30_000, "end_ms": 40_000}],
                    },
                ],
            }
        ],
        cover_image="source/cover.jpg",
        subtitle="视频来源：Bilibili",
    )

    assert "# 注意力机制" in markdown
    assert "视频来源：Bilibili" in markdown
    assert "![课程封面](source/cover.jpg)" in markdown
    assert "## 核心机制" in markdown
    assert "### 本章小结" in markdown
    assert "> **主线**" in markdown
    assert "![直接检查过的注意力公式画面。](frames/attention.jpg)" in markdown
    assert "00:00:10--00:00:18" not in markdown
    assert "来源时间" not in markdown


def test_cli_render_markdown_writes_draft_without_p1_gate(tmp_path) -> None:
    input_path = tmp_path / "document.json"
    output_path = tmp_path / "notes.md"
    input_path.write_text(
        """
        {
          "title": "草稿",
          "sections": [
            {
              "title": "短节",
              "blocks": [
                {
                  "kind": "paragraph",
                  "text": "这是给迭代用的短草稿。",
                  "source_spans": [{"start_ms": 1000, "end_ms": 3000}]
                }
              ]
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    assert main(["render-markdown", "--input", str(input_path), "--output", str(output_path)]) == 0
    assert "# 草稿" in output_path.read_text(encoding="utf-8")
