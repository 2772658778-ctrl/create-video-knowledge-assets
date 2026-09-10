import pytest

from vka.preflight import inspect_commands, require_command


def test_preflight_reports_missing_commands_without_throwing(monkeypatch) -> None:
    def fake_which(command: str) -> str | None:
        if command == "available-command":
            return "/usr/bin/available-command"
        return None

    monkeypatch.setattr("vka.preflight.shutil.which", fake_which)

    report = inspect_commands(["available-command", "definitely-not-a-command"])
    assert report["available-command"]["available"] is True
    assert report["definitely-not-a-command"]["available"] is False


def test_require_command_reports_missing_ffprobe_without_traceback(monkeypatch) -> None:
    monkeypatch.setattr("vka.preflight.find_command", lambda _: None)

    with pytest.raises(ValueError, match="ffprobe is required"):
        require_command("ffprobe")


def test_require_command_uses_existing_command_discovery(monkeypatch, tmp_path) -> None:
    expected = tmp_path / "Library" / "bin" / "ffprobe.exe"
    monkeypatch.setattr("vka.preflight.find_command", lambda _: expected)

    assert require_command("ffprobe") == expected
