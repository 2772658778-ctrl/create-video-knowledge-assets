import json
import subprocess
from pathlib import Path

import pytest

from vka.acquire import metadata_command, subtitle_command
from vka_cli import main


def test_metadata_command_uses_machine_readable_json() -> None:
    assert metadata_command("https://www.bilibili.com/video/BV1xx") == [
        "yt-dlp",
        "--dump-single-json",
        "https://www.bilibili.com/video/BV1xx",
    ]


def test_acquisition_commands_include_an_optional_cookie_file() -> None:
    url = "https://www.bilibili.com/video/BV1xx"

    assert metadata_command(url, "cookies.txt") == [
        "yt-dlp",
        "--cookies",
        "cookies.txt",
        "--dump-single-json",
        url,
    ]
    assert metadata_command(url, cookie_file="cookies.txt") == [
        "yt-dlp",
        "--cookies",
        "cookies.txt",
        "--dump-single-json",
        url,
    ]
    assert subtitle_command(url, "source/video", cookie_file="cookies.txt") == [
        "yt-dlp",
        "--cookies",
        "cookies.txt",
        "--write-subs",
        "--sub-langs",
        "zh-Hans,zh-CN,zh,ai-zh",
        "--convert-subs",
        "srt",
        "--skip-download",
        "-o",
        "source/video",
        url,
    ]
    assert subtitle_command(url, "source/video", "cookies.txt") == [
        "yt-dlp",
        "--cookies",
        "cookies.txt",
        "--write-subs",
        "--sub-langs",
        "zh-Hans,zh-CN,zh,ai-zh",
        "--convert-subs",
        "srt",
        "--skip-download",
        "-o",
        "source/video",
        url,
    ]


def test_acquisition_commands_can_use_a_workspace_cache_dir(
    monkeypatch, tmp_path
) -> None:
    cache_dir = tmp_path / ".cache" / "yt-dlp"
    monkeypatch.setenv("VKA_YTDLP_CACHE_DIR", str(cache_dir))

    assert metadata_command("https://www.bilibili.com/video/BV1xx") == [
        "yt-dlp",
        "--cache-dir",
        str(cache_dir),
        "--dump-single-json",
        "https://www.bilibili.com/video/BV1xx",
    ]
    assert subtitle_command("https://www.bilibili.com/video/BV1xx", "source/video") == [
        "yt-dlp",
        "--cache-dir",
        str(cache_dir),
        "--write-subs",
        "--sub-langs",
        "zh-Hans,zh-CN,zh,ai-zh",
        "--convert-subs",
        "srt",
        "--skip-download",
        "-o",
        "source/video",
        "https://www.bilibili.com/video/BV1xx",
    ]


def test_subtitle_command_preserves_srt_timing_without_downloading_video() -> None:
    command = subtitle_command("https://www.bilibili.com/video/BV1xx", "source/video")
    assert "--write-subs" in command
    assert "--skip-download" in command
    assert command[-1] == "https://www.bilibili.com/video/BV1xx"


def test_acquire_metadata_writes_captured_stdout(tmp_path, monkeypatch) -> None:
    output_path = tmp_path / "source" / "metadata.json"
    calls = []

    def fake_run(command, *, check, capture_output, text, **kwargs):
        calls.append((command, check, capture_output, text))
        return subprocess.CompletedProcess(command, 0, stdout='{"title":"demo"}', stderr="")

    monkeypatch.setattr("vka_cli.subprocess.run", fake_run)

    exit_code = main(
        [
            "acquire-metadata",
            "--url",
            "https://www.bilibili.com/video/BV1xx",
            "--output",
            str(output_path),
        ]
    )

    assert exit_code == 0
    assert calls == [
        (
            ["yt-dlp", "--dump-single-json", "https://www.bilibili.com/video/BV1xx"],
            True,
            True,
            True,
        )
    ]
    assert output_path.read_text(encoding="utf-8") == '{"title":"demo"}'


def test_acquire_metadata_sanitizes_metadata_and_passes_cookie_file(tmp_path, monkeypatch) -> None:
    output_path = tmp_path / "source" / "metadata.json"
    cookie_file = tmp_path / "cookies.txt"
    cookie_file.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")
    calls = []

    def fake_run(command, *, check, capture_output, text, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=(
                '{"title":"demo","cookie":"secret",'
                '"webpage_url":"https://example.test/watch?keep=1&token=secret"}'
            ),
            stderr="",
        )

    monkeypatch.setattr("vka_cli.subprocess.run", fake_run)

    assert (
        main(
            [
                "acquire-metadata",
                "--url",
                "https://www.bilibili.com/video/BV1xx",
                "--cookie-file",
                str(cookie_file),
                "--output",
                str(output_path),
            ]
        )
        == 0
    )
    assert calls == [
        [
            "yt-dlp",
            "--cookies",
            str(cookie_file),
            "--dump-single-json",
            "https://www.bilibili.com/video/BV1xx",
        ]
    ]
    assert json.loads(output_path.read_text(encoding="utf-8")) == {
        "title": "demo",
        "webpage_url": "https://example.test/watch",
    }


def test_acquire_metadata_rejects_invalid_json_without_writing(tmp_path, monkeypatch, capsys) -> None:
    output_path = tmp_path / "source" / "metadata.json"

    def fake_run(command, *, check, capture_output, text, **kwargs):
        return subprocess.CompletedProcess(command, 0, stdout="not json", stderr="")

    monkeypatch.setattr("vka_cli.subprocess.run", fake_run)

    exit_code = main(
        [
            "acquire-metadata",
            "--url",
            "https://www.bilibili.com/video/BV1xx",
            "--output",
            str(output_path),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code != 0
    assert "error: invalid metadata JSON:" in captured.err
    assert "Traceback" not in captured.err
    assert not output_path.exists()


def test_acquire_metadata_reports_malformed_url_sanitization_without_raw_data(
    tmp_path, monkeypatch, capsys
) -> None:
    output_path = tmp_path / "source" / "metadata.json"

    def fake_run(command, *, check, capture_output, text, **kwargs):
        return subprocess.CompletedProcess(
            command,
            0,
            stdout='{"webpage_url":"https://[malformed"}',
            stderr="",
        )

    monkeypatch.setattr("vka_cli.subprocess.run", fake_run)

    assert (
        main(
            [
                "acquire-metadata",
                "--url",
                "https://www.bilibili.com/video/BV1xx",
                "--output",
                str(output_path),
            ]
        )
        == 1
    )

    captured = capsys.readouterr()
    assert captured.err == "error: failed to sanitize metadata\n"
    assert "malformed" not in captured.err
    assert "Traceback" not in captured.err
    assert not output_path.exists()


def test_acquire_metadata_reports_output_write_failure_without_traceback(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    output_path = tmp_path / "metadata-as-directory"
    output_path.mkdir()

    def fake_run(command, *, check, capture_output, text, **kwargs):
        return subprocess.CompletedProcess(command, 0, stdout='{"title":"demo"}', stderr="")

    monkeypatch.setattr("vka_cli.subprocess.run", fake_run)

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "acquire-metadata",
                "--url",
                "https://www.bilibili.com/video/BV1xx",
                "--output",
                str(output_path),
            ]
        )

    captured = capsys.readouterr()
    assert exc_info.value.code == 1
    assert "error:" in captured.err
    assert "Traceback" not in captured.err


def test_acquire_metadata_reports_yt_dlp_failure_without_detail(monkeypatch, capsys) -> None:
    def fake_run(command, *, check, capture_output, text, **kwargs):
        raise subprocess.CalledProcessError(returncode=1, cmd=command)

    monkeypatch.setattr("vka_cli.subprocess.run", fake_run)

    exit_code = main(
        [
            "acquire-metadata",
            "--url",
            "https://www.bilibili.com/video/BV1xx",
            "--output",
            "source/metadata.json",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "error: failed to acquire metadata with yt-dlp (exit 1)" in captured.err
    assert "Traceback" not in captured.err


def test_acquire_subs_success_calls_expected_command(tmp_path, monkeypatch) -> None:
    calls = []
    output_template = tmp_path / "source" / "video"

    def fake_run(command, *, check, capture_output, text, **kwargs):
        calls.append((command, check, capture_output, text))
        if command[1] == "--dump-single-json":
            return subprocess.CompletedProcess(command, 0, stdout="{}", stderr="")
        srt_path = output_template.parent / "video.zh-Hans.srt"
        srt_path.parent.mkdir(parents=True, exist_ok=True)
        srt_path.write_text(
            "1\n00:00:00,000 --> 00:00:01,000\nx\n",
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("vka_cli.subprocess.run", fake_run)

    exit_code = main(
        [
            "acquire-subs",
            "--url",
            "https://www.bilibili.com/video/BV1xx",
            "--output-template",
            str(output_template),
        ]
    )

    assert exit_code == 0
    assert calls == [
        (
            ["yt-dlp", "--dump-single-json", "https://www.bilibili.com/video/BV1xx"],
            True,
            True,
            True,
        ),
        (
            subtitle_command("https://www.bilibili.com/video/BV1xx", str(output_template)),
            True,
            True,
            True,
        )
    ]


def test_acquire_subs_passes_cookie_file_to_metadata_and_subtitle_commands(
    tmp_path, monkeypatch
) -> None:
    cookie_file = tmp_path / "cookies.txt"
    cookie_file.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")
    output_template = tmp_path / "source" / "video"
    calls = []

    def fake_run(command, *, check, capture_output, text, **kwargs):
        calls.append(command)
        if "--dump-single-json" in command:
            return subprocess.CompletedProcess(command, 0, stdout="{}", stderr="")
        output_template.parent.mkdir(parents=True, exist_ok=True)
        (output_template.parent / "video.zh-Hans.srt").write_text("subtitle", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("vka_cli.subprocess.run", fake_run)

    assert (
        main(
            [
                "acquire-subs",
                "--url",
                "https://www.bilibili.com/video/BV1xx",
                "--cookie-file",
                str(cookie_file),
                "--output-template",
                str(output_template),
            ]
        )
        == 0
    )
    assert calls == [
        metadata_command(
            "https://www.bilibili.com/video/BV1xx", cookie_file=str(cookie_file)
        ),
        subtitle_command(
            "https://www.bilibili.com/video/BV1xx",
            str(output_template),
            cookie_file=str(cookie_file),
        ),
    ]


def test_acquire_subs_reports_no_downloaded_srt(tmp_path, monkeypatch, capsys) -> None:
    def fake_run(command, *, check, capture_output, text, **kwargs):
        if command[1] == "--dump-single-json":
            return subprocess.CompletedProcess(command, 0, stdout="{}", stderr="")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("vka_cli.subprocess.run", fake_run)

    exit_code = main(
        [
            "acquire-subs",
            "--url",
            "https://www.bilibili.com/video/BV1xx",
            "--output-template",
            str(tmp_path / "source" / "video"),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code != 0
    assert "error: no subtitle SRT files were downloaded" in captured.err
    assert "Traceback" not in captured.err


def test_acquire_subs_reports_yt_dlp_failure_without_sensitive_detail(monkeypatch, capsys) -> None:
    def fake_run(command, *, check, capture_output, text, **kwargs):
        if command[1] == "--dump-single-json":
            return subprocess.CompletedProcess(command, 0, stdout="{}", stderr="")
        raise subprocess.CalledProcessError(
            returncode=2,
            cmd=command,
            stderr=(
                "Cookie: session=secret\\n"
                "https://example.test/manifest.m3u8?token=secret\\n"
                "command: yt-dlp --cookies secret.txt"
            ),
        )

    monkeypatch.setattr("vka_cli.subprocess.run", fake_run)

    exit_code = main(
        [
            "acquire-subs",
            "--url",
            "https://www.bilibili.com/video/BV1xx",
            "--output-template",
            "source/video",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "error: failed to acquire subtitles with yt-dlp (exit 2)" in captured.err
    assert "secret" not in captured.err
    assert "Cookie:" not in captured.err
    assert "manifest" not in captured.err
    assert "command:" not in captured.err
    assert "Traceback" not in captured.err


@pytest.mark.parametrize("command", ["acquire-metadata", "acquire-subs"])
def test_acquisition_rejects_non_regular_cookie_file_before_running(
    command, tmp_path, monkeypatch, capsys
) -> None:
    cookie_path = tmp_path / "cookie-directory"
    cookie_path.mkdir()
    called = False

    def fake_run(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("yt-dlp should not run")

    monkeypatch.setattr("vka_cli.subprocess.run", fake_run)
    argv = [
        command,
        "--url",
        "https://www.bilibili.com/video/BV1xx",
        "--cookie-file",
        str(cookie_path),
    ]
    if command == "acquire-metadata":
        argv.extend(["--output", str(tmp_path / "metadata.json")])
    else:
        argv.extend(["--output-template", str(tmp_path / "video")])

    with pytest.raises(SystemExit) as exc_info:
        main(argv)

    assert exc_info.value.code == 1
    assert called is False
    assert capsys.readouterr().err == "error: cookie file must be a regular file\n"


@pytest.mark.parametrize(
    "argv",
    [
        [
            "acquire-metadata",
            "--url",
            "https://www.bilibili.com/video/BV1xx",
            "--output",
            "source/metadata.json",
        ],
        [
            "acquire-subs",
            "--url",
            "https://www.bilibili.com/video/BV1xx",
            "--output-template",
            "source/video",
        ],
    ],
)
def test_acquire_reports_oserror_without_traceback(argv, monkeypatch, capsys) -> None:
    def fake_run(command, *, check, capture_output, text, **kwargs):
        raise FileNotFoundError("yt-dlp")

    monkeypatch.setattr("vka_cli.subprocess.run", fake_run)

    exit_code = main(argv)

    captured = capsys.readouterr()
    assert exit_code != 0
    assert captured.err == "error: failed to run yt-dlp\n"
    assert "Traceback" not in captured.err
