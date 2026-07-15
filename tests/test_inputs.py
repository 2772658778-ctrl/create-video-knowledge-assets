import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from vka.inputs import (
    archive_local_video,
    asset_id_for_source,
    describe_local_video,
    normalize_bilibili_url,
    register_asset_identity,
    sanitize_acquired_metadata,
    validate_asset_identity_collision,
)
from vka_cli import main


def test_local_video_descriptor_hashes_content_without_copying_source(tmp_path: Path) -> None:
    video = tmp_path / "lesson.mp4"
    video.write_bytes(b"not-a-real-video")

    descriptor = describe_local_video(video, probe=lambda _: {"duration_ms": 12000})

    assert descriptor["kind"] == "local_video"
    assert descriptor["content_sha256"] == hashlib.sha256(b"not-a-real-video").hexdigest()
    assert descriptor["original_path"] == str(video.resolve())
    assert descriptor["asset_id"] == f"local-{descriptor['content_sha256'][:16]}"
    assert descriptor["metadata"] == {"duration_ms": 12000}
    assert list(tmp_path.iterdir()) == [video]


def test_normalize_bilibili_source_removes_tracking_and_cookie_data() -> None:
    source = normalize_bilibili_url("https://www.bilibili.com/video/BV1xx/?spm_id_from=333")

    assert source["canonical_url"] == "https://www.bilibili.com/video/BV1xx"
    assert source["asset_id"] == "bili-BV1xx"
    assert "cookie" not in source


def test_sanitize_acquired_metadata_recursively_removes_sensitive_fields_and_url_queries() -> None:
    metadata = {
        "title": "demo",
        "CookieHeader": "session=secret",
        "nested": {
            "authorization": "Bearer secret",
            "urls": [
                "https://example.test/watch?keep=1&token=secret&empty=",
                "not a URL?token=secret",
            ],
        },
        "webpage_url": "https://example.test/video?sig=abc&safe=ok&SESSION=id#chapter",
        "password_hint": "secret",
    }

    assert sanitize_acquired_metadata(metadata) == {
        "title": "demo",
        "nested": {
            "urls": [
                "https://example.test/watch",
                "not a URL?token=secret",
            ],
        },
        "webpage_url": "https://example.test/video",
    }


def test_sanitize_acquired_metadata_removes_url_credentials_and_extended_tokens() -> None:
    metadata = {
        "url": (
            "https://user:secret@example.test/path?access_token=secret&api_key=secret"
            "&access_key=secret&auth=secret&TOKEN=secret&safe=1#fragment"
        )
    }

    assert sanitize_acquired_metadata(metadata) == {
        "url": "https://example.test/path"
    }


def test_sanitize_acquired_metadata_removes_all_nested_format_url_parameters() -> None:
    metadata = {
        "formats": [
            {
                "format_id": "720p",
                "url": (
                    "https://media.example.test/playback/720p?expires=opaque-expiry"
                    "&x-signature=opaque-signature&headers=opaque-header#cue"
                ),
            }
        ]
    }

    sanitized = sanitize_acquired_metadata(metadata)

    assert sanitized == {
        "formats": [
            {
                "format_id": "720p",
                "url": "https://media.example.test/playback/720p",
            }
        ]
    }
    assert "opaque-" not in json.dumps(sanitized)


def test_sanitize_acquired_metadata_removes_components_from_scheme_url_without_netloc() -> None:
    assert sanitize_acquired_metadata(
        {"local_url": "file:///tmp/lesson;opaque-param?opaque-query#opaque-fragment"}
    ) == {"local_url": "file:///tmp/lesson"}


def test_sanitize_acquired_metadata_removes_components_from_scheme_relative_url() -> None:
    assert sanitize_acquired_metadata(
        {"url": "//user:credential@example.test/path;opaque-param?opaque-query#opaque-fragment"}
    ) == {"url": "//example.test/path"}


def test_normalize_bilibili_url_preserves_explicit_part_without_credentials() -> None:
    source = normalize_bilibili_url(
        "https://www.bilibili.com/video/BV1xx/?p=2&cookie=secret-value&token=also-secret"
    )

    assert source["selected_part"] == 2
    assert source["selection_required"] is False
    assert source["canonical_url"] == "https://www.bilibili.com/video/BV1xx?p=2"
    serialized = json.dumps(source)
    assert "secret-value" not in serialized
    assert "also-secret" not in serialized


def test_normalize_bilibili_url_marks_unselected_part_as_requiring_selection() -> None:
    source = normalize_bilibili_url("https://www.bilibili.com/video/BV1xx")

    assert source["selection_required"] is True
    assert "selected_part" not in source


def test_selected_bilibili_parts_have_distinct_asset_ids() -> None:
    first = normalize_bilibili_url("https://www.bilibili.com/video/BV1xx?p=1")
    second = normalize_bilibili_url("https://www.bilibili.com/video/BV1xx?p=2")

    assert first["asset_id"] != second["asset_id"]
    assert first["asset_id"] == "bili-BV1xx-p1"
    assert second["asset_id"] == "bili-BV1xx-p2"


def test_bilibili_asset_id_rejects_boolean_selected_part() -> None:
    with pytest.raises(ValueError, match="selected_part"):
        asset_id_for_source({"kind": "bilibili", "bvid": "BV1xx", "selected_part": True})


@pytest.mark.parametrize("path_name", ["missing.mp4", "folder.mp4", "lesson.txt"])
def test_local_video_rejects_missing_directory_and_unsupported_container(
    tmp_path: Path, path_name: str
) -> None:
    path = tmp_path / path_name
    if path_name == "folder.mp4":
        path.mkdir()
    elif path_name == "lesson.txt":
        path.write_bytes(b"video")

    with pytest.raises(ValueError, match="local video"):
        describe_local_video(path, probe=lambda _: {"duration_ms": 1})


def test_local_video_reports_unprobeable_media_without_traceback(tmp_path: Path) -> None:
    video = tmp_path / "lesson.mp4"
    video.write_bytes(b"video")

    def fail_probe(_: Path) -> dict[str, object]:
        raise ValueError("ffprobe could not read the media")

    with pytest.raises(ValueError, match="could not inspect local video"):
        describe_local_video(video, probe=fail_probe)


def test_bilibili_url_requires_a_video_bvid() -> None:
    with pytest.raises(ValueError, match="Bilibili video URL"):
        normalize_bilibili_url("https://www.bilibili.com/read/cv123")


def test_asset_identity_collision_compares_full_local_hash() -> None:
    same_prefix = "a" * 16
    existing = {"kind": "local_video", "content_sha256": same_prefix + "1" * 48}
    candidate = {"kind": "local_video", "content_sha256": same_prefix + "2" * 48}

    with pytest.raises(ValueError, match="full content SHA-256"):
        validate_asset_identity_collision(existing, candidate)


def test_register_asset_identity_rejects_a_manifest_source_with_same_prefix_and_different_hash() -> None:
    same_prefix = "a" * 16
    existing_manifest = {
        "asset_id": f"local-{same_prefix}",
        "source": {"kind": "local_video", "content_sha256": same_prefix + "1" * 48},
    }
    candidate = {"kind": "local_video", "content_sha256": same_prefix + "2" * 48}

    with pytest.raises(ValueError, match="full content SHA-256"):
        register_asset_identity(candidate, existing_identity=existing_manifest)


def test_register_asset_identity_recomputes_tampered_manifest_asset_id_before_hash_check() -> None:
    same_prefix = "a" * 16
    existing_manifest = {
        "asset_id": "local-unrelated",
        "source": {"kind": "local_video", "content_sha256": same_prefix + "1" * 48},
    }
    candidate = {"kind": "local_video", "content_sha256": same_prefix + "2" * 48}

    with pytest.raises(ValueError, match="full content SHA-256"):
        register_asset_identity(candidate, existing_identity=existing_manifest)


def test_asset_identity_and_l1_archive_never_move_the_original(tmp_path: Path) -> None:
    video = tmp_path / "lesson.mp4"
    video.write_bytes(b"video")
    descriptor = describe_local_video(video, probe=lambda _: {"duration_ms": 1})

    archived = archive_local_video(video, tmp_path / "asset" / "source" / "video", retention="L1")

    assert asset_id_for_source(descriptor) == descriptor["asset_id"]
    assert video.read_bytes() == archived.read_bytes()
    assert video.exists()
    assert archived != video


def test_cli_normalizes_bilibili_url_without_exposing_query_data(capsys) -> None:
    exit_code = main(
        [
            "normalize-bilibili-url",
            "--url",
            "https://www.bilibili.com/video/BV1xx/?spm_id_from=333",
        ]
    )

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out) == {
        "kind": "bilibili",
        "asset_id": "bili-BV1xx",
        "bvid": "BV1xx",
        "selection_required": True,
        "canonical_url": "https://www.bilibili.com/video/BV1xx",
    }


def test_cli_describe_local_video_does_not_archive_by_default(tmp_path: Path, monkeypatch, capsys) -> None:
    video = tmp_path / "lesson.mp4"
    video.write_bytes(b"video")
    descriptor = {"kind": "local_video", "original_path": str(video.resolve())}
    monkeypatch.setattr("vka_cli.describe_local_video", lambda _: descriptor)

    exit_code = main(["describe-local-video", "--input", str(video)])

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out) == descriptor
    assert list(tmp_path.iterdir()) == [video]


@pytest.mark.parametrize(
    ("argv", "setup"),
    [
        (
            ["describe-local-video", "--input", "missing.mp4"],
            lambda tmp_path, monkeypatch: None,
        ),
        (
            ["describe-local-video", "--input", "directory.mp4"],
            lambda tmp_path, monkeypatch: (tmp_path / "directory.mp4").mkdir(),
        ),
        (
            ["normalize-bilibili-url", "--url", "https://www.bilibili.com/read/cv123?token=secret"],
            lambda tmp_path, monkeypatch: None,
        ),
        (
            ["describe-local-video", "--input", "video.mp4"],
            lambda tmp_path, monkeypatch: (
                (tmp_path / "video.mp4").write_bytes(b"video"),
                monkeypatch.setattr(
                    "vka_cli.describe_local_video",
                    lambda _: (_ for _ in ()).throw(ValueError("could not inspect local video")),
                ),
            ),
        ),
    ],
)
def test_cli_input_errors_are_single_line_and_do_not_expose_query_values(
    tmp_path: Path, monkeypatch, capsys, argv: list[str], setup
) -> None:
    setup(tmp_path, monkeypatch)
    argv = [str(tmp_path / value) if value.endswith(".mp4") else value for value in argv]

    with pytest.raises(SystemExit) as exc_info:
        main(argv)

    captured = capsys.readouterr()
    assert exc_info.value.code == 1
    assert captured.err.startswith("error: ")
    assert captured.err.count("\n") == 1
    assert "Traceback" not in captured.err
    assert "secret" not in captured.err


def test_cli_reports_missing_ffprobe_as_single_line_error(tmp_path: Path, monkeypatch, capsys) -> None:
    video = tmp_path / "lesson.mp4"
    video.write_bytes(b"video")
    monkeypatch.setattr(
        "vka.inputs.require_command",
        lambda _: (_ for _ in ()).throw(ValueError("ffprobe is required but was not found on PATH")),
    )

    with pytest.raises(SystemExit) as exc_info:
        main(["describe-local-video", "--input", str(video)])

    captured = capsys.readouterr()
    assert exc_info.value.code == 1
    assert captured.err == "error: could not inspect local video " + str(video.resolve()) + ": ffprobe is required but was not found on PATH\n"
    assert "Traceback" not in captured.err


def test_cli_describe_local_video_reports_missing_existing_identity_without_traceback(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    video = tmp_path / "lesson.mp4"
    video.write_bytes(b"video")
    monkeypatch.setattr(
        "vka_cli.describe_local_video",
        lambda _: {"kind": "local_video", "original_path": str(video.resolve())},
    )
    missing_identity = tmp_path / "missing-manifest.json"

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "describe-local-video",
                "--input",
                str(video),
                "--existing-identity",
                str(missing_identity),
            ]
        )

    captured = capsys.readouterr()
    assert exc_info.value.code == 1
    assert captured.err.startswith("error: ")
    assert captured.err.count("\n") == 1
    assert "Traceback" not in captured.err


def test_cli_passes_existing_identity_to_the_descriptor_registration_boundary(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    video = tmp_path / "lesson.mp4"
    video.write_bytes(b"video")
    identity_path = tmp_path / "manifest.json"
    identity = {"asset_id": "local-aaaaaaaaaaaaaaaa", "source": {"kind": "local_video"}}
    identity_path.write_text(json.dumps(identity), encoding="utf-8")
    received: dict[str, object] = {}

    def fail_on_collision(_: Path, *, existing_identity: dict[str, object]):
        received.update(existing_identity)
        raise ValueError("asset ID collision: full content SHA-256 values differ")

    monkeypatch.setattr("vka_cli.describe_local_video", fail_on_collision)

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "describe-local-video",
                "--input",
                str(video),
                "--existing-identity",
                str(identity_path),
            ]
        )

    captured = capsys.readouterr()
    assert exc_info.value.code == 1
    assert received == identity
    assert captured.err == "error: asset ID collision: full content SHA-256 values differ\n"
    assert "Traceback" not in captured.err


def test_acquire_metadata_rejects_unselected_multipart_source_without_query_credentials(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    commands: list[list[str]] = []

    def fake_run(command, *, check, capture_output, text):
        commands.append(command)
        return subprocess.CompletedProcess(
            command,
            0,
            stdout='{"_type":"multi_video","entries":[{"id":"1"},{"id":"2"}]}',
            stderr="",
        )

    monkeypatch.setattr("vka_cli.subprocess.run", fake_run)

    exit_code = main(
        [
            "acquire-metadata",
            "--url",
            "https://www.bilibili.com/video/BV1xx?cookie=secret",
            "--output",
            str(tmp_path / "source" / "metadata.json"),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert commands == [["yt-dlp", "--dump-single-json", "https://www.bilibili.com/video/BV1xx"]]
    assert captured.err == "error: Bilibili source has multiple parts; select one with ?p=N\n"
    assert "secret" not in captured.err


def test_acquire_subs_uses_canonical_url_without_sensitive_query_values(
    tmp_path: Path, monkeypatch
) -> None:
    commands: list[list[str]] = []
    output_template = tmp_path / "source" / "video"

    def fake_run(command, *, check, capture_output, text):
        commands.append(command)
        output_template.parent.mkdir(parents=True, exist_ok=True)
        (output_template.parent / "video.zh-Hans.srt").write_text("subtitle", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("vka_cli.subprocess.run", fake_run)

    assert (
        main(
            [
                "acquire-subs",
                "--url",
                "https://www.bilibili.com/video/BV1xx?p=2&cookie=secret&token=also-secret",
                "--output-template",
                str(output_template),
            ]
        )
        == 0
    )
    assert commands == [
        [
            "yt-dlp",
            "--write-subs",
            "--sub-langs",
            "zh-Hans,zh-CN,zh,ai-zh",
            "--convert-subs",
            "srt",
            "--skip-download",
            "-o",
            str(output_template),
            "https://www.bilibili.com/video/BV1xx?p=2",
        ]
    ]


def test_acquire_subs_rejects_unselected_multipart_before_downloading_subtitles(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    commands: list[list[str]] = []
    output_template = tmp_path / "source" / "video"

    def fake_run(command, *, check, capture_output, text):
        commands.append(command)
        return subprocess.CompletedProcess(
            command,
            0,
            stdout='{"_type":"multi_video","entries":[{"id":"1"},{"id":"2"}]}',
            stderr="",
        )

    monkeypatch.setattr("vka_cli.subprocess.run", fake_run)

    exit_code = main(
        [
            "acquire-subs",
            "--url",
            "https://www.bilibili.com/video/BV1xx?cookie=secret",
            "--output-template",
            str(output_template),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert commands == [["yt-dlp", "--dump-single-json", "https://www.bilibili.com/video/BV1xx"]]
    assert captured.err == "error: Bilibili source has multiple parts; select one with ?p=N\n"
    assert not output_template.parent.exists()
    assert "secret" not in captured.err


def test_acquire_subs_downloads_subtitles_for_unselected_single_part_with_sanitized_argv(
    tmp_path: Path, monkeypatch
) -> None:
    commands: list[list[str]] = []
    output_template = tmp_path / "source" / "video"
    subtitle_path = output_template.parent / "video.zh-Hans.srt"

    def fake_run(command, *, check, capture_output, text):
        commands.append(command)
        if command[1] == "--dump-single-json":
            return subprocess.CompletedProcess(command, 0, stdout="{}", stderr="")
        subtitle_path.parent.mkdir(parents=True, exist_ok=True)
        subtitle_path.write_text("subtitle", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("vka_cli.subprocess.run", fake_run)

    assert (
        main(
            [
                "acquire-subs",
                "--url",
                "https://www.bilibili.com/video/BV1xx?cookie=secret&token=also-secret",
                "--output-template",
                str(output_template),
            ]
        )
        == 0
    )
    assert subtitle_path.read_text(encoding="utf-8") == "subtitle"
    assert commands == [
        ["yt-dlp", "--dump-single-json", "https://www.bilibili.com/video/BV1xx"],
        [
            "yt-dlp",
            "--write-subs",
            "--sub-langs",
            "zh-Hans,zh-CN,zh,ai-zh",
            "--convert-subs",
            "srt",
            "--skip-download",
            "-o",
            str(output_template),
            "https://www.bilibili.com/video/BV1xx",
        ],
    ]
