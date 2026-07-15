from __future__ import annotations


def metadata_command(url: str, cookie_file: str | None = None) -> list[str]:
    command = ["yt-dlp"]
    if cookie_file is not None:
        command.extend(["--cookies", cookie_file])
    command.extend(["--dump-single-json", url])
    return command


def subtitle_command(
    url: str, output_template: str, cookie_file: str | None = None
) -> list[str]:
    command = ["yt-dlp"]
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
