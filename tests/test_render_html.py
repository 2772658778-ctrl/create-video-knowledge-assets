from vka.render_html import render_course_html, render_document_html


def test_document_html_renders_table_and_caption() -> None:
    html = render_document_html({
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

    assert "<table>" in html
    assert "<th>Measure</th>" in html
    assert (
        '<p class="caption">The values are illustrative.'
        '<sup class="cite"><a href="#src-2">2</a></sup></p>'
    ) in html
    assert '<li id="src-2"><span class="time">00:00:04--00:00:06</span></li>' in html


def test_general_document_html_preserves_local_image_path_without_audit_text() -> None:
    document = {
        "profile_id": "general-deep", "title": "访谈", "sections": [{"title": "概览", "blocks": [{
            "kind": "image", "image_path": "evidence/frames/chart.jpg", "caption": "趋势图。",
            "knowledge_refs": ["ku-1"], "evidence_refs": ["fr-1"],
            "source_spans": [{"start_ms": 20000, "end_ms": 28000}],
        }]}],
    }
    html = render_document_html(document)

    assert 'src="evidence/frames/chart.jpg"' in html
    assert '<li id="src-1"><span class="time">00:00:20--00:00:28</span></li>' in html
    assert "source_spans" not in html


def test_notes_part_renders_without_a_parent_provenance_catalog() -> None:
    """A document without `evidence_origins` still has a renderable notes part."""
    notes = render_document_html(
        {
            "profile_id": "general-deep",
            "title": "访谈",
            "sections": [
                {
                    "title": "概览",
                    "blocks": [
                        {
                            "kind": "paragraph",
                            "text": "正文只复述视频里的判断。",
                            "knowledge_refs": ["ku-1"],
                            "evidence_refs": ["tr-1"],
                            "source_spans": [{"start_ms": 0, "end_ms": 1000}],
                        }
                    ],
                }
            ],
            "notes": {
                "title": "边界",
                "sections": [
                    {
                        "title": "转录",
                        "blocks": [
                            {
                                "kind": "paragraph",
                                "text": "有 3 段无法确认。",
                                "knowledge_refs": ["ku-1"],
                                "evidence_refs": ["tr-1"],
                                "source_spans": [{"start_ms": 0, "end_ms": 1000}],
                            }
                        ],
                    }
                ],
            },
        },
        part="notes",
    )

    assert "<h1>边界</h1>" in notes
from vka_cli import main


def test_html_renderer_writes_readable_page_with_local_images() -> None:
    html = render_course_html(
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
                    {
                        "kind": "importantbox",
                        "title": "主线",
                        "text": "Q 提问，K 匹配，V 提供内容。",
                        "source_spans": [{"start_ms": 20_000, "end_ms": 30_000}],
                    },
                    {
                        "kind": "image",
                        "path": "D:/asset/frames/attention.jpg",
                        "caption": "直接检查过的注意力公式画面。",
                        "source_spans": [{"start_ms": 30_000, "end_ms": 40_000}],
                    },
                ],
            }
        ],
        cover_image="D:/asset/cover.jpg",
        subtitle="视频来源：Bilibili",
    )

    assert "<!doctype html>" in html
    assert "<h1>注意力机制</h1>" in html
    assert "视频来源：Bilibili" in html
    assert "file:///D:/asset/cover.jpg" in html
    assert "file:///D:/asset/frames/attention.jpg" in html
    assert "来源时间" in html
    assert '<li id="src-1"><span class="time">00:00:10--00:00:18</span></li>' in html


def test_cli_render_html_writes_draft_without_p1_gate(tmp_path) -> None:
    input_path = tmp_path / "document.json"
    output_path = tmp_path / "notes.html"
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

    assert main(["render-html", "--input", str(input_path), "--output", str(output_path)]) == 0
    assert "<h1>草稿</h1>" in output_path.read_text(encoding="utf-8")
