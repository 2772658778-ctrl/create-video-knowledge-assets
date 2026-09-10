from __future__ import annotations

import os
from pathlib import Path


def _cache_dir_flag() -> list[str]:
    cache_dir = os.environ.get("VKA_YTDLP_CACHE_DIR")
    if cache_dir:
        Path(cache_dir).mkdir(parents=True, exist_ok=True)
        return ["--cache-dir", cache_dir]
    return []


def metadata_command(url: str, cookie_file: str | None = None) -> list[str]:
    command = ["yt-dlp"]
    command.extend(_cache_dir_flag())
    if cookie_file is not None:
        command.extend(["--cookies", cookie_file])
    command.extend(["--dump-single-json", url])
    return command


def subtitle_command(
    url: str, output_template: str, cookie_file: str | None = None
) -> list[str]:
    command = ["yt-dlp"]
    command.extend(_cache_dir_flag())
    if cookie_file is not None:
        command.extend(["--cookies", cookie_file])
    command.extend(
        [
            "--write-subs",
            "--sub-langs",
            "zh-Hans,zh-CN,zh,ai-zh",
            "--convert-subs",
            "srt",
            "--skip-download",
            "-o",
            output_template,
            url,
        ]
    )
    return command
