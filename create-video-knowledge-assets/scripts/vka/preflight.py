from __future__ import annotations

import shutil
import sys
from pathlib import Path


def inspect_commands(commands: list[str]) -> dict[str, dict[str, object]]:
    report: dict[str, dict[str, object]] = {}
    for command in commands:
        resolved = find_command(command)
        item: dict[str, bool | str] = {"available": resolved is not None}
        if resolved is not None:
            item["path"] = str(resolved)
        report[command] = item
    return report


def find_command(command: str) -> Path | None:
    found = shutil.which(command)
    if found:
        return Path(found)

    exe_name = command if command.lower().endswith(".exe") else f"{command}.exe"
    prefixes = [Path(sys.prefix), Path(sys.base_prefix)]
    candidates: list[Path] = []
    for prefix in prefixes:
        candidates.extend(
            [
                prefix / "Scripts" / exe_name,
                prefix / "Library" / "bin" / exe_name,
                prefix / "Library" / "miktex" / "texmfs" / "install" / "miktex" / "bin" / "x64" / exe_name,
            ]
        )

    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def require_command(command: str) -> Path:
    resolved = find_command(command)
    if resolved is None:
        raise ValueError(f"{command} is required but was not found on PATH")
    return resolved
