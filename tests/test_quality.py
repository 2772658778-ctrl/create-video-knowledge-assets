import json

from vka.quality import (
    validate_course_document_quality,
    validate_document_image_files,
    validate_document_quality,
)


def test_general_deep_document_gate_requires_limits_and_grounded_blocks() -> None:
    errors = validate_document_quality(
        {"profile_id": "general-deep", "title": "访谈", "sections": []}
    )

    assert "general-deep document needs a limitations section" in errors
    assert "document blocks must preserve evidence_refs and source_spans" in errors


def test_document_gate_rejects_a_conflicting_selected_profile() -> None:
    errors = validate_document_quality(
        {"profile_id": "course-notes", "title": "Interview", "sections": []},
        profile_id="general-deep",
    )

    assert "document profile_id must match selected profile" in errors


def test_document_provenance_allows_explicit_external_evidence_without_spans() -> None:
    external_document = {
        "profile_id": "general-deep",
        "title": "External source",
        "evidence_origins": {"paper-42": "external", "derived:summary": "generated"},
        "blocks": [
            {
                "kind": "paragraph", "text": "External report conclusion.",
                "knowledge_refs": ["ku-1"], "evidence_refs": ["paper-42"],
            },
            {
                "kind": "paragraph", "text": "A generated aggregate is clearly marked.",
                "knowledge_refs": ["ku-2"], "evidence_refs": ["derived:summary"],
            },
        ],
    }
    video_document = {
        "profile_id": "general-deep",
        "title": "Video source",
        "blocks": [{
            "kind": "paragraph", "text": "Video conclusion.",
            "knowledge_refs": ["ku-1"], "evidence_refs": ["tr-1"],
        }],
    }

    assert "document video blocks must preserve source_spans" not in validate_document_quality(external_document)
    assert "document video blocks must preserve source_spans" in validate_document_quality(video_document)


def test_generated_declaration_cannot_waive_spans_for_video_evidence_refs() -> None:
    document = {
        "profile_id": "general-deep",
        "title": "Mislabelled video source",
        "evidence_origins": {"tr-1": "video"},
        "blocks": [{
            "kind": "paragraph", "text": "This still cites video evidence.",
            "knowledge_refs": ["ku-1"], "evidence_refs": ["tr-1"],
            "evidence_origin": "generated",
        }],
    }

    assert "document video blocks must preserve source_spans" in validate_document_quality(document)


def test_general_deep_accepts_canonical_top_level_blocks_and_cli_renders_them(tmp_path, capsys) -> None:
    asset_root = tmp_path / "asset"
    input_path = asset_root / "views" / "general-deep" / "document.json"
    output_path = asset_root / "outputs" / "general-deep" / "document.html"
    input_path.parent.mkdir(parents=True)
    prose = "The document explains the source's argument and its limits. " * 15
    section_kinds = [
        ("overview", "Overview"),
        ("logical_body", "First reason"),
        ("logical_body", "Second reason"),
        ("limitations", "Limits"),
        ("source_navigation", "Source navigation"),
    ]
    blocks = []
    for index, (section_kind, title) in enumerate(section_kinds, start=1):
        blocks.extend([
            {
                "kind": "heading", "text": title, "data": {"section_kind": section_kind},
                "knowledge_refs": [f"ku-h{index}"], "evidence_refs": [f"tr-h{index}"],
                "source_spans": [{"start_ms": index * 10_000, "end_ms": index * 10_000 + 2_000}],
            },
            {
                "kind": "paragraph", "text": prose,
                "knowledge_refs": [f"ku-{index}"], "evidence_refs": [f"tr-{index}"],
                "source_spans": [{"start_ms": index * 10_000 + 2_000, "end_ms": index * 10_000 + 8_000}],
            },
        ])
    image_path = asset_root / "evidence" / "frames" / "chart.jpg"
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(b"image")
    blocks.append({
        "kind": "image", "image_path": "evidence/frames/chart.jpg", "caption": "A chart from the source.",
        "knowledge_refs": ["ku-image"], "evidence_refs": ["fr-image"],
        "source_spans": [{"start_ms": 70_000, "end_ms": 74_000}],
    })
    document = {
        "profile_id": "general-deep", "title": "Canonical view",
        "metadata": {
            "source_title": "Original video", "source_url": "https://example.test/video",
            "author": "Speaker", "publish_date": "2026-07-12",
        },
        "blocks": blocks,
    }
    input_path.write_text(json.dumps(document), encoding="utf-8")

    assert validate_document_quality(document) == []
    assert main(["validate-document", "--input", str(input_path), "--profile", "general-deep"]) == 0
    assert main([
        "render-document", "--input", str(input_path), "--output", str(output_path),
        "--profile", "general-deep", "--format", "html",
    ]) == 0
    assert "First reason" in output_path.read_text(encoding="utf-8")
    assert 'src="../../evidence/frames/chart.jpg"' in output_path.read_text(encoding="utf-8")
    assert "passed quality gate" in capsys.readouterr().out


def test_course_quality_requires_evidence_references_for_grounded_content() -> None:
    errors = validate_course_document_quality(
        {
            "title": "Course", "theme": "Useful theme", "one_sentence_summary": "A sufficiently long summary for this course.",
            "metadata": _metadata(), "teaching_outline_ref": "knowledge/outline.json",
            "sections": [{"title": "Core question", "blocks": [{
                "kind": "paragraph", "text": "This paragraph has a plausible time span but no evidence reference.",
                "source_spans": [{"start_ms": 0, "end_ms": 8_000}],
            }]}],
        }
    )

    assert "section 1 block 1 must preserve evidence_refs" in errors


def test_cli_render_course_p1_gate_rejects_content_without_evidence_refs(tmp_path, capsys) -> None:
    input_path = tmp_path / "course.json"
    output_path = tmp_path / "course.tex"
    input_path.write_text(json.dumps({
        "title": "Course", "sections": [{"title": "Core", "blocks": [{
            "kind": "paragraph", "text": "This claim only pretends to be grounded.",
            "source_spans": [{"start_ms": 0, "end_ms": 8_000}],
        }]}],
    }), encoding="utf-8")

    assert main(["render-course", "--input", str(input_path), "--output", str(output_path)]) == 1
    assert "section 1 block 1 must preserve evidence_refs" in capsys.readouterr().err
    assert not output_path.exists()


def test_document_gate_rejects_unsafe_local_image_paths() -> None:
    errors = validate_document_quality(
        {
            "profile_id": "general-deep",
            "title": "Interview",
            "sections": [
                {
                    "title": "Overview",
                    "blocks": [
                        {
                            "kind": "image",
                            "image_path": "../outside.jpg",
                            "caption": "Unsafe path.",
                            "knowledge_refs": ["ku-1"],
                            "evidence_refs": ["fr-1"],
                            "source_spans": [{"start_ms": 0, "end_ms": 2_000}],
                        }
                    ],
                }
            ],
        }
    )

    assert "image blocks must preserve a safe local image_path" in errors


def test_image_file_validation_uses_the_asset_root_for_view_documents(tmp_path) -> None:
    asset_root = tmp_path / "asset"
    image_path = asset_root / "evidence" / "frames" / "chart.jpg"
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(b"image")
    document = {
        "profile_id": "general-deep",
        "title": "Interview",
        "sections": [{"title": "Overview", "blocks": [{
            "kind": "image", "image_path": "evidence/frames/chart.jpg", "caption": "Chart.",
            "knowledge_refs": ["ku-1"], "evidence_refs": ["fr-1"],
            "source_spans": [{"start_ms": 0, "end_ms": 2_000}],
        }]}],
    }

    assert validate_document_image_files(document, asset_root) == []


def test_cli_validate_and_render_document_use_the_selected_profile(tmp_path, capsys) -> None:
    input_path = tmp_path / "general.json"
    output_path = tmp_path / "general.md"
    prose = "This explanation preserves the interview's claim and its scope. " * 15
    section_kinds = [
        ("overview", "Overview"),
        ("logical_body", "First reason"),
        ("logical_body", "Second reason"),
        ("limitations", "Limits"),
        ("source_navigation", "Source navigation"),
    ]
    document = {
        "profile_id": "general-deep",
        "title": "Interview",
        "metadata": {
            "source_title": "Original interview",
            "source_url": "https://example.test/video",
            "author": "Speaker",
            "publish_date": "2026-07-12",
        },
        "sections": [
            {
                "kind": kind,
                "title": title,
                "blocks": [
                    {
                        "kind": "paragraph",
                        "text": prose,
                        "knowledge_refs": [f"ku-{index}"],
                        "evidence_refs": [f"tr-{index}"],
                        "source_spans": [{"start_ms": index * 10_000, "end_ms": index * 10_000 + 8_000}],
                    }
                ],
            }
            for index, (kind, title) in enumerate(section_kinds, start=1)
        ],
    }
    input_path.write_text(json.dumps(document), encoding="utf-8")

    assert main(["validate-document", "--input", str(input_path), "--profile", "general-deep"]) == 0
    assert main([
        "render-document", "--input", str(input_path), "--output", str(output_path),
        "--profile", "general-deep", "--format", "md",
    ]) == 0
    assert "general-deep document passed quality gate" in capsys.readouterr().out
    assert "This explanation" in output_path.read_text(encoding="utf-8")
from vka_cli import main


def test_quality_gate_rejects_smoke_summary_document() -> None:
    document = {
        "title": "Transformer QKV 注意力机制课程笔记",
        "theme": "注意力机制的核心问题",
        "one_sentence_summary": "本课解释词向量为什么要通过注意力吸收上下文。",
        "metadata": _metadata(),
        "teaching_outline_ref": "knowledge/teaching_outline.json",
        "sections": [
            {
                "title": "学习目标与先修知识",
                "blocks": [
                    {
                        "kind": "paragraph",
                        "text": "学习目标：理解 Q、K、V 的作用。",
                        "source_spans": [{"start_ms": 10_000, "end_ms": 11_000}],
                    }
                ],
            }
        ],
    }

    errors = validate_course_document_quality(document)

    assert "course document must contain at least four teaching sections" in errors
    assert "course document prose is too short; expand explanations before rendering" in errors
    assert "source spans are too narrow; use transcript windows, not one-second guesses" in errors


def test_quality_gate_accepts_teachable_document() -> None:
    long_text = (
        "本节先说明问题动机，再解释关键机制。讲者并不是要求记住一个孤立公式，"
        "而是把注意力机制看作可学习的信息检索过程：查询负责提出问题，键负责提供"
        "匹配线索，值负责携带最终要汇总的信息。这个顺序能帮助读者把矩阵乘法和"
        "实际语义联系起来，避免只背诵 QK^T V 的符号。"
    )
    document = {
        "title": "注意力机制课程笔记",
        "theme": "注意力是一种可学习的信息检索",
        "one_sentence_summary": "每个词用 Query 找相关 Key，再按权重汇总 Value 形成上下文表示。",
        "metadata": _metadata(),
        "teaching_outline_ref": "knowledge/teaching_outline.json",
        "sections": [
            _section("学习目标与先修知识", long_text, 0),
            _section("问题动机", long_text, 60_000),
            _section("核心机制", long_text, 120_000),
                {
                    "title": "总结与延伸",
                    "blocks": [
                        {
                            "kind": "subsection",
                            "title": "核心主线",
                        },
                        {
                            "kind": "paragraph",
                            "text": long_text * 2,
                            "source_spans": [{"start_ms": 200_000, "end_ms": 210_000}],
                        },
                        {
                            "kind": "subsection",
                            "title": "练习与延伸",
                        },
                        {
                            "kind": "importantbox",
                            "title": "带走的主线",
                        "text": "把注意力理解为检索，比把它理解为神秘公式更适合复习。",
                        "source_spans": [{"start_ms": 200_000, "end_ms": 210_000}],
                    },
                ],
            },
        ],
    }

    for section in document["sections"]:
        for block in section["blocks"]:
            if block.get("kind") != "subsection":
                block["evidence_refs"] = ["tr-grounded"]

    assert validate_course_document_quality(document) == []


def test_quality_gate_rejects_flat_chapters_without_subsections() -> None:
    long_text = (
        "本节先说明问题动机，再解释关键机制。讲者并不是要求记住一个孤立公式，"
        "而是把注意力机制看作可学习的信息检索过程：查询负责提出问题，键负责提供"
        "匹配线索，值负责携带最终要汇总的信息。这个顺序能帮助读者把矩阵乘法和"
        "实际语义联系起来，避免只背诵 QK^T V 的符号。"
    )
    flat_section = {
        "title": "问题动机",
        "blocks": [
            {
                "kind": "paragraph",
                "text": long_text * 3,
                "source_spans": [{"start_ms": 0, "end_ms": 8_000}],
            },
            {
                "kind": "image",
                "path": "frames/0.jpg",
                "caption": "直接检查过的关键教学画面，显示本节所讲的公式或流程。",
                "source_spans": [{"start_ms": 0, "end_ms": 8_000}],
            },
        ],
    }
    document = {
        "title": "注意力机制课程笔记",
        "theme": "注意力是一种可学习的信息检索",
        "one_sentence_summary": "每个词用 Query 找相关 Key，再按权重汇总 Value 形成上下文表示。",
        "metadata": _metadata(),
        "teaching_outline_ref": "knowledge/teaching_outline.json",
        "sections": [
            flat_section,
            _section("核心机制", long_text, 60_000),
            _section("公式解释", long_text, 120_000),
            {
                "title": "总结与延伸",
                "blocks": [
                    {"kind": "subsection", "title": "核心主线"},
                    {
                        "kind": "paragraph",
                        "text": long_text * 2,
                        "source_spans": [{"start_ms": 200_000, "end_ms": 210_000}],
                    },
                    {"kind": "subsection", "title": "练习与延伸"},
                    {
                        "kind": "importantbox",
                        "title": "带走的主线",
                        "text": "把注意力理解为检索，比把它理解为神秘公式更适合复习。",
                        "source_spans": [{"start_ms": 200_000, "end_ms": 210_000}],
                    },
                ],
            },
        ],
    }

    errors = validate_course_document_quality(document)

    assert "section 1 needs at least two teaching subsections before its summary" in errors
    assert "section 1 is missing a chapter summary subsection/block" in errors


def test_quality_gate_rejects_internal_outline_labels_in_visible_headings() -> None:
    document = {
        "title": "测试课程笔记",
        "theme": "测试主题",
        "one_sentence_summary": "这是一句足够长的课程核心总结。",
        "metadata": _metadata(),
        "teaching_outline_ref": "knowledge/teaching_outline.json",
        "sections": [
            {
                "title": "synthesis: final review",
                "blocks": [
                    {
                        "kind": "subsection",
                        "title": "motivation: why this matters",
                    },
                    {
                        "kind": "paragraph",
                        "text": "这段文字用于确认内部规划标签不会被渲染到用户可见标题里。",
                        "source_spans": [{"start_ms": 0, "end_ms": 8_000}],
                    },
                ],
            }
        ],
    }

    errors = validate_course_document_quality(document)

    assert "section 1 title leaks internal outline labels" in errors
    assert "section 1 subsection 1 leaks internal outline labels" in errors


def test_cli_render_course_rejects_low_quality_document(tmp_path, capsys) -> None:
    input_path = tmp_path / "document.json"
    output_path = tmp_path / "notes.tex"
    input_path.write_text(
        '{"title":"????","sections":[{"title":"短","blocks":[]}]}',
        encoding="utf-8",
    )

    exit_code = main(["render-course", "--input", str(input_path), "--output", str(output_path)])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "failed P1 quality gate" in captured.err
    assert not output_path.exists()


def _section(title: str, text: str, start_ms: int) -> dict:
    return {
        "title": title,
        "blocks": [
            {
                "kind": "subsection",
                "title": "问题动机",
            },
            {
                "kind": "paragraph",
                "text": text * 2,
                "source_spans": [{"start_ms": start_ms, "end_ms": start_ms + 8_000}],
            },
            {
                "kind": "importantbox",
                "title": "核心主线",
                "text": "核心主线：先抓住这一节真正要解决的问题，再把公式、画面和例子都放回这条解释路径中。",
                "source_spans": [{"start_ms": start_ms, "end_ms": start_ms + 8_000}],
            },
            {
                "kind": "subsection",
                "title": "机制展开",
            },
            {
                "kind": "image",
                "path": f"frames/{start_ms}.jpg",
                "caption": "直接检查过的关键教学画面，显示本节所讲的公式或流程。",
                "source_spans": [{"start_ms": start_ms, "end_ms": start_ms + 8_000}],
            },
            {
                "kind": "subsection",
                "title": "本章小结",
            },
            {
                "kind": "paragraph",
                "text": "这一节的关键是把局部公式放回问题动机中理解，并确认读者知道本节概念如何服务后续机制说明。",
                "source_spans": [{"start_ms": start_ms, "end_ms": start_ms + 8_000}],
            },
        ],
    }


def _metadata() -> dict:
    return {
        "source_title": "测试视频",
        "author": "测试作者",
        "publish_date": "2026-07-11",
        "subtitle_source": "ASR repaired",
        "data_sources": "Bilibili metadata, repaired transcript, inspected frames",
    }
