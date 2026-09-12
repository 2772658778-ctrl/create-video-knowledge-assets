import json
import shutil
from pathlib import Path

import pytest

from vka.package_demo import package_demo
from vka_cli import main


def _asset(tmp_path: Path) -> Path:
    asset = tmp_path / "assets" / "bili-BVtest"
    (asset / "views" / "deep-article").mkdir(parents=True)
    (asset / "outputs" / "deep-article").mkdir(parents=True)
    (asset / "source" / "cover").mkdir(parents=True)
    (asset / "evidence" / "frames" / "inspected").mkdir(parents=True)

    (asset / "views" / "deep-article" / "document.json").write_text(
        json.dumps(_renderable_document(), ensure_ascii=False),
        encoding="utf-8",
    )
    (asset / "outputs" / "deep-article" / "document.pdf").write_bytes(b"%PDF-fake")
    (asset / "outputs" / "deep-article" / "notes.pdf").write_bytes(b"%PDF-notes")
    (asset / "source" / "cover" / "BVtest.jpg").write_bytes(b"cover")
    (asset / "evidence" / "frames" / "inspected" / "01-used.jpg").write_bytes(b"used")
    (asset / "evidence" / "frames" / "inspected" / "02-unused.jpg").write_bytes(b"unused")
    return asset


def _paragraph(text: str) -> dict:
    return {
        "kind": "paragraph",
        "text": text,
        "knowledge_refs": ["ku-1"],
        "evidence_refs": ["ev-1"],
        "source_spans": [{"start_ms": 0, "end_ms": 1000}],
    }


def _renderable_document() -> dict:
    """A minimal document both renderers accept, with a cover and two parts."""
    return {
        "profile_id": "deep-article",
        "title": "文章",
        "cover_image": "source/cover/BVtest.jpg",
        "sections": [
            {"kind": "overview", "title": "总览", "blocks": [_paragraph("正文只复述视频给的判断。")]}
        ],
        "notes": {
            "title": "边界与来源",
            "sections": [
                {"kind": "limits", "title": "边界", "blocks": [_paragraph("转录有 3 段无法确认。")]}
            ],
        },
    }


def _with_image(asset: Path) -> dict:
    document = json.loads(
        (asset / "views" / "deep-article" / "document.json").read_text(encoding="utf-8")
    )
    document["sections"] = [
        {
            "kind": "overview",
            "title": "总览",
            "blocks": [
                {
                    "kind": "image",
                    "path": "evidence/frames/inspected/01-used.jpg",
                    "caption": "用来说明边界的画面。",
                    "knowledge_refs": ["ku-1"],
                    "evidence_refs": ["ev-1"],
                    "source_spans": [{"start_ms": 0, "end_ms": 1000}],
                }
            ],
        }
    ]
    (asset / "views" / "deep-article" / "document.json").write_text(
        json.dumps(document, ensure_ascii=False), encoding="utf-8"
    )
    return document


def _select_formats(asset: Path, formats: list[str]) -> None:
    (asset / "views" / "deep-article" / "view-manifest.json").write_text(
        json.dumps({"profile_id": "deep-article", "formats": formats}, ensure_ascii=False),
        encoding="utf-8",
    )


def test_package_demo_writes_one_self_contained_file_per_part(tmp_path: Path) -> None:
    asset = _asset(tmp_path)
    _with_image(asset)

    report = package_demo(asset, "deep-article", demo_root=tmp_path / "demos")

    demo = tmp_path / "demos" / "bili-BVtest"
    summary = (demo / "summary.html").read_text(encoding="utf-8")
    notes = (demo / "notes.html").read_text(encoding="utf-8")
    assert report["demo"] == str(demo)
    assert report["formats"] == ["html"]
    assert 'src="data:image/jpeg;base64,' in summary
    assert "evidence/frames" not in summary
    assert "source/cover" not in summary
    assert "<h2>总览</h2>" in summary
    # The boundary document ships as its own file, not inside the reader copy.
    assert "<h2>边界</h2>" in notes
    assert "总览" not in notes
    assert not (demo / "figures").exists()
    assert str(demo / "summary.html") in report["files"]
    assert str(demo / "notes.html") in report["files"]


def test_package_demo_publishes_pdfs_only_when_the_view_asked_for_one(tmp_path: Path) -> None:
    asset = _asset(tmp_path)
    _with_image(asset)

    package_demo(asset, "deep-article", demo_root=tmp_path / "demos")
    demo = tmp_path / "demos" / "bili-BVtest"
    assert not (demo / "summary.pdf").exists()

    _select_formats(asset, ["html", "pdf"])
    package_demo(asset, "deep-article", demo_root=tmp_path / "demos")
    assert (demo / "summary.pdf").read_bytes() == b"%PDF-fake"
    assert (demo / "notes.pdf").read_bytes() == b"%PDF-notes"

    _select_formats(asset, ["pdf"])
    shutil.rmtree(demo)
    package_demo(asset, "deep-article", demo_root=tmp_path / "demos")
    assert (demo / "summary.pdf").is_file()
    assert not (demo / "summary.html").exists()


def test_package_demo_requires_an_authored_document(tmp_path: Path) -> None:
    asset = _asset(tmp_path)
    (asset / "views" / "deep-article" / "document.json").unlink()

    with pytest.raises(ValueError, match="no authored document"):
        package_demo(asset, "deep-article", demo_root=tmp_path / "demos")


def test_package_demo_rejects_a_cover_outside_the_asset(tmp_path: Path) -> None:
    asset = _asset(tmp_path)
    path = asset / "views" / "deep-article" / "document.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["cover_image"] = "../../escape.jpg"
    path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="cover_image must preserve a safe local image_path"):
        package_demo(asset, "deep-article", demo_root=tmp_path / "demos")


def test_cli_package_demo_reports_the_demo_directory(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    asset = _asset(tmp_path)

    exit_code = main(
        [
            "package-demo",
            "--asset",
            str(asset),
            "--profile",
            "deep-article",
            "--demo-root",
            str(tmp_path / "demos"),
        ]
    )

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out)["profile_id"] == "deep-article"


def test_cli_package_demo_reports_failure_without_a_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = main(
        [
            "package-demo",
            "--asset",
            str(tmp_path / "missing"),
            "--profile",
            "deep-article",
            "--demo-root",
            str(tmp_path / "demos"),
        ]
    )

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "failed to package demo" in captured.err
    assert "Traceback" not in captured.err
