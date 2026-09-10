from vka.teaching_outline import validate_teaching_outline


def test_teaching_outline_accepts_pedagogical_moves() -> None:
    outline = {
        "title": "QKV attention",
        "sections": [
            _teaching_section("为什么要注意力", 0),
            _teaching_section("QKV 如何解决问题", 60_000),
            {
                "title": "总结与练习",
                "moves": [
                    _move("synthesis", 120_000),
                    _move("practice", 130_000),
                    _move("takeaway", 140_000),
                ],
            },
        ],
    }

    assert validate_teaching_outline(outline) == []


def test_teaching_outline_rejects_schema_projection_disguised_as_notes() -> None:
    outline = {
        "title": "QKV attention",
        "sections": [
            {
                "title": "QKV 是三组投影",
                "moves": [
                    {
                        "kind": "mechanism",
                        "text": "Q、K、V 由三组矩阵生成。",
                        "evidence_refs": ["tw-qkv"],
                    }
                ],
            },
            _teaching_section("QK 分数", 60_000),
            {
                "title": "总结与练习",
                "moves": [
                    _move("synthesis", 120_000),
                    _move("practice", 130_000),
                    _move("takeaway", 140_000),
                ],
            },
        ],
    }

    errors = validate_teaching_outline(outline)

    assert "section 1 is missing a takeaway move" in errors
    assert "section 1 needs motivation or wrong_intuition" in errors
    assert "section 1 needs a worked_example or formula_or_visual move" in errors
    assert "section 1 is too thin for a course-note chapter" in errors


def _teaching_section(title: str, start_ms: int) -> dict:
    return {
        "title": title,
        "moves": [
            _move("motivation", start_ms),
            _move("mechanism", start_ms + 10_000),
            _move("formula_or_visual", start_ms + 20_000),
            _move("takeaway", start_ms + 30_000),
        ],
    }


def _move(kind: str, start_ms: int) -> dict:
    return {
        "kind": kind,
        "text": (
            "这一段用教师口吻解释问题、机制和例子之间的关系，"
            "让读者知道为什么这个步骤出现、解决什么限制、下一步怎样继续。"
            "它不是复述字幕，而是把直觉、符号和图像证据连成可阅读的学习路径。"
        ),
        "evidence_refs": [f"tw-{start_ms}"],
    }
