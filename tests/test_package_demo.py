import json
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
        json.dumps(
            {
                "profile_id": "deep-article",
                "title": "文章",
                "cover_image": "source/cover/BVtest.jpg",
                "sections": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (asset / "outputs" / "deep-article" / "document.pdf").write_bytes(b"%PDF-fake")
    (asset / "outputs" / "deep-article" / "notes.pdf").write_bytes(b"%PDF-notes")
    (asset / "source" / "cover" / "BVtest.jpg").write_bytes(b"cover")
    (asset / "evidence" / "frames" / "inspected" / "01-used.jpg").write_bytes(b"used")
    (asset / "evidence" / "frames" / "inspected" / "02-unused.jpg").write_bytes(b"unused")
    return asset


def test_package_demo_copies_referenced_images_and_rewrites_paths(tmp_path: Path) -> None:
    asset = _asset(tmp_path)
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

    report = package_demo(asset, "deep-article", demo_root=tmp_path / "demos")

    demo = tmp_path / "demos" / "bili-BVtest"
    assert report["demo"] == str(demo)
    assert (demo / "cover.jpg").read_bytes() == b"cover"
    assert (demo / "figures" / "01-used.jpg").is_file()
    assert (demo / "summary.pdf").read_bytes() == b"%PDF-fake"
    assert (demo / "notes.pdf").read_bytes() == b"%PDF-notes"


def test_package_demo_drops_frames_the_document_never_cites(tmp_path: Path) -> None:
    asset = _asset(tmp_path)
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

    package_demo(asset, "deep-article", demo_root=tmp_path / "demos")

    assert not (tmp_path / "demos" / "bili-BVtest" / "figures" / "02-unused.jpg").exists()


def test_package_demo_requires_an_authored_document(tmp_path: Path) -> None:
    asset = _asset(tmp_path)
    (asset / "views" / "deep-article" / "document.json").unlink()

    with pytest.raises(ValueError, match="no authored document"):
        package_demo(asset, "deep-article", demo_root=tmp_path / "demos")


def test_package_demo_rejects_a_cover_outside_the_asset(tmp_path: Path) -> None:
    asset = _asset(tmp_path)
    document = asset / "views" / "deep-article" / "document.json"
    document.write_text(
        json.dumps({"profile_id": "deep-article", "title": "x", "cover_image": "../../escape.jpg"}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="escapes the asset root"):
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
