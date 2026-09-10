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
    (asset / "outputs" / "deep-article" / "document.md").write_text(
        "# 文章\n\n![视频封面](../../source/cover/BVtest.jpg)\n\n"
        "![用来说明边界的画面。](../../evidence/frames/inspected/01-used.jpg)\n",
        encoding="utf-8",
    )
    (asset / "outputs" / "deep-article" / "document.html").write_text(
        '<img src="../../evidence/frames/inspected/01-used.jpg" alt="已用">',
        encoding="utf-8",
    )
    (asset / "outputs" / "deep-article" / "document.pdf").write_bytes(b"%PDF-fake")
    (asset / "source" / "cover" / "BVtest.jpg").write_bytes(b"cover")
    (asset / "evidence" / "frames" / "inspected" / "01-used.jpg").write_bytes(b"used")
    (asset / "evidence" / "frames" / "inspected" / "02-unused.jpg").write_bytes(b"unused")
    return asset


def test_package_demo_copies_referenced_images_and_rewrites_paths(tmp_path: Path) -> None:
    asset = _asset(tmp_path)

    report = package_demo(asset, "deep-article", demo_root=tmp_path / "demos")

    demo = tmp_path / "demos" / "bili-BVtest"
    markdown = (demo / "summary.md").read_text(encoding="utf-8")
    assert report["demo"] == str(demo)
    assert "![视频封面](cover.jpg)" in markdown
    assert "(figures/01-used.jpg)" in markdown
    assert "../../" not in markdown
    assert (demo / "cover.jpg").read_bytes() == b"cover"
    assert (demo / "figures" / "01-used.jpg").is_file()
    assert (demo / "summary.pdf").read_bytes() == b"%PDF-fake"
    assert "figures/01-used.jpg" in (demo / "summary.html").read_text(encoding="utf-8")


def test_package_demo_drops_frames_the_document_never_cites(tmp_path: Path) -> None:
    asset = _asset(tmp_path)

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
