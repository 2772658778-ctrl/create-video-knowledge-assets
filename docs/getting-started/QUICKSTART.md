# 快速上手

> 30 秒开始使用 create-video-knowledge-assets：把一段知识视频变成一套知识资产。

## 前置条件

- Python 3.12+
- 一个可发现本 Skill 的 Agent 环境（默认按 Codex 适配）
- 按需安装外部工具：yt-dlp（获取）、ffmpeg / ffprobe（媒体）、Whisper（无字幕转录）、XeLaTeX（PDF）

安装 Python 依赖：

```powershell
python -m pip install "pydantic>=2.7,<3" "srt>=3.5,<4"
```

## 30 秒开始

将 `create-video-knowledge-assets/` 放入 Agent 可发现的 Skill 目录，或在请求中明确引用该目录。普通用户只需要提供视频和目标，不需要手工构造大纲、证据 JSON 或渲染命令。

### 默认深度总结

```text
使用 $create-video-knowledge-assets 深度总结这个视频：<Bilibili URL>。
整理核心问题、机制、例子、关键画面、限制和来源导航，并生成 PDF、HTML 和 Markdown。
```

### 课程笔记

```text
使用 $create-video-knowledge-assets，把这个视频制作成适合学习和复习的中文课程笔记：<Bilibili URL>。
保留关键画面、教学结构和来源时间脚注，并生成 PDF、HTML 和 Markdown。
```

### 本地视频

```text
使用 $create-video-knowledge-assets 深度总结这个本地知识视频：<本地视频路径>。
先检查视频身份和工具条件，再建立证据、知识和最终文档。
```

**输入 Bilibili URL 时需要显式提供 Cookie。** Bilibili 的公开接口普遍需要登录态才能稳定获取字幕与元数据。先在浏览器中登录 Bilibili，再用浏览器插件 **Cookie-Editor** 导出 `bilibili.com` 相关域的 Cookie（Netscape 格式），通过 `--cookie-file <path>` 或 `yt-dlp --cookies <file>` 显式传入。Cookie 等同于账户登录凭据：只导出 Bilibili 相关域，不要上传仓库或粘贴到公开内容中。

本地跑视频时，建议先执行仓库里的 `create-video-knowledge-assets/scripts/setup-runtime.ps1`。它会把 Whisper、`yt-dlp`、HF/torch 缓存和临时文件都留在工作区的 `.cache/` 和 `.tmp/`，避免默认落到 C 盘。

## 看真实结果

不用跑代码也能看效果。`demos/` 下有两份走完完整链路的成果：

| Demo | 直接查看 |
| --- | --- |
| Transformer 的 QKV（课程笔记） | [PDF](../../demos/BV1uPMA62E8e/summary.pdf) · [HTML](../../demos/BV1uPMA62E8e/summary.html) · [Markdown](../../demos/BV1uPMA62E8e/summary.md) |
| 猫为什么把幼崽叼给主人（深度总结） | [PDF](../../demos/BV1idEL6REd3/summary.pdf) · [HTML](../../demos/BV1idEL6REd3/summary.html) · [Markdown](../../demos/BV1idEL6REd3/summary.md) |
| 国民凉茶为什么卖不动了（短视频脚本） | [PDF](../../demos/bili-BV1hwtB6YEzo/summary.pdf) · [HTML](../../demos/bili-BV1hwtB6YEzo/summary.html) · [Markdown](../../demos/bili-BV1hwtB6YEzo/summary.md) |
| 为什么很少有国家吃笋（深度总结） | [PDF](../../demos/bili-BV1tHdoYnEGm/summary.pdf) · [HTML](../../demos/bili-BV1tHdoYnEGm/summary.html) · [Markdown](../../demos/bili-BV1tHdoYnEGm/summary.md) |

## 验证环境

```powershell
python create-video-knowledge-assets/scripts/vka_cli.py --help
python create-video-knowledge-assets/scripts/vka_cli.py preflight --commands yt-dlp ffmpeg ffprobe xelatex
```

## 下一步

- 想理解内部机制：看 [架构与数据流](../ARCHITECTURE.md)
- 想了解能力边界：看 [能力地图](../SKILLS_CATALOG.md)
