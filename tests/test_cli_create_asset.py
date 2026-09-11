import json
from pathlib import Path

import pytest

from vka_cli import main


DESCRIPTOR = {
    "kind": "bilibili",
    "bvid": "BV1hwtB6YEzo",
    "selection_required": False,
    "canonical_url": "https://www.bilibili.com/video/BV1hwtB6YEzo",
    "asset_id": "bili-BV1hwtB6YEzo",
}


def _write_input(tmp_path: Path, payload: object = DESCRIPTOR) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "input.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_create_asset_writes_manifest_from_the_input_descriptor(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assets_root = tmp_path / "assets"
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps({"profile": "short-video-script", "selected_asr": {"model": "base"}}),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "create-asset",
            "--assets-root",
            str(assets_root),
            "--input",
            str(_write_input(tmp_path)),
            "--config",
            str(config),
            "--tool-version",
            "asr_backend=faster-whisper",
            "--tool-version",
            "asr_model=base",
        ]
    )

    assert exit_code == 0
    report = json.loads(capsys.readouterr().out)
    assert report["asset_id"] == "bili-BV1hwtB6YEzo"
    manifest = json.loads(
        (assets_root / "bili-BV1hwtB6YEzo" / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["asset_id"] == "bili-BV1hwtB6YEzo"
    assert manifest["schema_version"] == "1.1"
    assert manifest["input"] == DESCRIPTOR
    assert manifest["config"]["profile"] == "short-video-script"
    assert manifest["tool_versions"] == {
        "asr_backend": "faster-whisper",
        "asr_model": "base",
    }
    assert manifest["stages"] == {}
    assert all(
        (assets_root / "bili-BV1hwtB6YEzo" / name).is_dir()
        for name in ("source", "evidence", "knowledge", "views", "outputs", "logs")
    )


def test_create_asset_refuses_to_reuse_an_existing_asset(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assets_root = tmp_path / "assets"
    argv = [
        "create-asset",
        "--assets-root",
        str(assets_root),
        "--input",
        str(_write_input(tmp_path)),
    ]

    assert main(argv) == 0
    capsys.readouterr()

    assert main(argv) == 1
    assert "failed to create asset" in capsys.readouterr().err


def test_create_asset_rejects_a_bad_tool_version_and_a_non_object_descriptor(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assets_root = tmp_path / "assets"

    assert (
        main(
            [
                "create-asset",
                "--assets-root",
                str(assets_root),
                "--input",
                str(_write_input(tmp_path)),
                "--tool-version",
                "asr_backend",
            ]
        )
        == 1
    )
    assert "name=value" in capsys.readouterr().err

    assert (
        main(
            [
                "create-asset",
                "--assets-root",
                str(assets_root),
                "--input",
                str(_write_input(tmp_path / "second", ["not", "an", "object"])),
            ]
        )
        == 1
    )
    assert "must be a JSON object" in capsys.readouterr().err


def test_create_asset_requires_an_asset_id(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    descriptor = {key: value for key, value in DESCRIPTOR.items() if key != "asset_id"}

    exit_code = main(
        [
            "create-asset",
            "--assets-root",
            str(tmp_path / "assets"),
            "--input",
            str(_write_input(tmp_path, descriptor)),
        ]
    )

    assert exit_code == 1
    assert "asset id must come from" in capsys.readouterr().err


def test_create_asset_accepts_a_utf8_bom_written_by_powershell(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Windows shells write BOM-prefixed JSON; the CLI must read them."""
    descriptor_path = tmp_path / "input.json"
    descriptor_path.write_bytes(
        b"\xef\xbb\xbf" + json.dumps(DESCRIPTOR, ensure_ascii=False).encode("utf-8")
    )

    exit_code = main(
        [
            "create-asset",
            "--assets-root",
            str(tmp_path / "assets"),
            "--input",
            str(descriptor_path),
        ]
    )

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out)["asset_id"] == "bili-BV1hwtB6YEzo"
