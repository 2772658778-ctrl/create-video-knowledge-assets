# create-video-knowledge-assets

> **给 AI Agent 用的 Skill：把一个视频，变成一份有证据、能直接交付的读者文档。**

[English](./README.en.md) · [快速上手](./docs/getting-started/QUICKSTART.md) · [能力地图](./docs/SKILLS_CATALOG.md) · [架构](./docs/ARCHITECTURE.md)

![create-video-knowledge-assets](assets/banner.svg)

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](./pyproject.toml)
[![Tests](https://img.shields.io/badge/tests-415_passed-green)](#工程质量)

---

## 这是什么

一个可安装到 Codex / Claude Code 等 Agent 里的 Skill。丢给它一个 **Bilibili 链接**或**本地视频**，外加一句你想要什么，它就会走完一整条链路：识别来源 → 取字幕或转录 → 抽帧并**人眼检查画面** → 建立证据与知识层 → 写成读者文档 → 交付**一个双击就能打开的单文件 HTML**（图片、封面、来源时间都在里面）。

它和"视频摘要工具"的区别只有一句话：**每个结论都能回到视频里的某一句话或某一帧**，而且是 Agent 真的看过那一帧，不是猜的。

| | |
| --- | --- |
| 类型 | Agent Skill。`SKILL.md` 是给 Agent 读的入口，本文件是给人的入口 |
| 输入 | 一个 Bilibili URL（单 P）或本地视频文件，加一句你想要什么 |
| 输出 | `summary.html`（正文）+ `notes.html`（边界与来源），各自自包含；PDF 需要你明确要求 |
| 依赖 | Python 3.11+、`pydantic`、`srt`；按路径再用 yt-dlp / ffmpeg / faster-whisper |

**适合谁**

- 想把自己的视频内容做成可复用文档的创作者；
- 需要把长视频拆成学习材料 / 口播脚本 / 长文的团队；
- 想接一个"视频 → 可信文档"能力到自己 Agent 工作流的开发者。

## 什么时候用它

| 你说 | Profile | 你会拿到 |
| --- | --- | --- |
| "深度总结这个视频：`<URL>`" | `deep-summary` | 按论点 / 机制 / 例子 / 关键画面重建视频逻辑 |
| "把这个视频做成课程笔记" | `course-notes` | 学习目标 / 前置知识 / 概念 / 机制 / 例题 / 小结 / 来源导航 |
| "把它改写成一篇长文" | `deep-article` | 可直接发布的公众号 / 知乎式长文，含可执行清单 |
| "做成能直接开拍的短视频脚本" | `short-video-script` | 目标时长 + 节奏假设 + 取舍清单 |

按需启用：`enterprise-knowledge`（团队知识归档）、`research-brief`（研究简报）。`general-deep`、`creator-article` 为兼容别名。

**不适用于**：把视频压成三行摘要；对已有资产做问答或检索（那会是另一个 Skill）；处理你没有权利使用的素材。

## 30 秒上手

**1. 装进你的 Agent**

把 `create-video-knowledge-assets/` 整个目录放进 Agent 能找到 Skill 的目录，例如 Codex 的 `~/.codex/skills/` 或 Claude Code 项目的 `.claude/skills/`；也可以直接在对话里引用这个目录。

```powershell
# 装 Python 依赖（默认 HTML 交付只需要这两个）
python -m pip install "pydantic>=2.7,<3" "srt>=3.5,<4"
```

**2. 用一句话调用**

```text
使用 $create-video-knowledge-assets 深度总结这个视频：<Bilibili URL>。
```

```text
把这个视频做成课程笔记：<本地视频路径>。
保留关键画面和教学结构，交付一个单文件 HTML。
```

```text
用 $create-video-knowledge-assets 总结这个视频：<Bilibili URL>，再给我一份 PDF。
```

**3. 拿结果**

交付物是 `summary.html`（正文）和 `notes.html`（证据边界与来源）两个文件，各自自包含，不依赖仓库里的任何其他文件。需要归档或转发时，同一份底稿可以再出一份 PDF。

> Bilibili 的字幕与元数据通常需要登录态：先用浏览器插件（如 Cookie-Editor）导出 `bilibili.com` 域的 Cookie，再通过 `--cookie-file` 显式传入。Cookie 等同账号凭据，不要上传仓库或贴进公开内容。

## 你会得到什么

三篇 Demo 走完了完整链路（URL → 转录 → 抽帧检查 → 知识建模 → 写作 → 交付），可以直接下载围观：

| Demo | 视频形态 | 成品 |
| --- | --- | --- |
| 为什么除了中国很少有国家吃笋 | 11:48 科普 | [正文](./demos/bili-BV1tHdoYnEGm/summary.html) · [边界与来源](./demos/bili-BV1tHdoYnEGm/notes.html) |
| 3 年少卖 10 亿元：国民凉茶为什么卖不动 | 10:20 财经口播 | [正文](./demos/bili-BV1hwtB6YEzo/summary.html) · [边界与来源](./demos/bili-BV1hwtB6YEzo/notes.html) |
| Harness 实践：把文字编辑成精美的文章 | 20:37 教程 | [正文](./demos/bili-BV1ayLD6uERL/summary.html) · [边界与来源](./demos/bili-BV1ayLD6uERL/notes.html) |

**正文**只讲视频内容，读者不需要知道背后有什么流水线；**边界说明**单独一份，写清楚哪些是视频明确说的、哪些是本文归纳、哪些没有独立核实，以及每条结论对应的时间窗。

## 它是怎么做到可信的

1. **证据优先。** 结论先落证据层（字幕时间窗、直接检查过的画面），再进知识和文档层。证据状态分四档：视频明确表达 / Agent 推断 / 外部补充 / 证据不足——推断不会被写成视频原话。
2. **画面必须真的看过。** 候选帧不算证据；只有 Agent 直接检查过、并在图和图注里如实描述的帧才会进入文档。
3. **一次写作，多种格式。** 正文只写一遍，HTML 与 PDF 由同一份底稿渲染，不存在"换格式内容就对不上"。
4. **一个资产，多种成品。** 同一个视频可以投影成总结、文章、脚本、课程笔记；视图只能读取事实层，不能反向改写原始事实。
5. **质量门 + 人工审阅点。** 多分 P 视频必须显式选范围；缺字幕时降级到 Whisper 转录但保留逐行审校痕迹；发布前保留人工验收。

完整机制见 [架构与数据流](./docs/ARCHITECTURE.md)；技术契约在 [`references/`](./create-video-knowledge-assets/references/)。

## 环境与依赖

| 需求 | 什么时候需要 |
| --- | --- |
| Python 3.11+、`pydantic`、`srt` | 始终（默认 HTML 交付只需要这些） |
| `yt-dlp` | 从 Bilibili 获取元数据 / 字幕 / 媒体 |
| `ffmpeg`、`ffprobe` | 抽帧、抽音频 |
| faster-whisper | 没有可用字幕时的转录（`base` / CPU / int8） |
| XeLaTeX | **只有你要 PDF 时** |

系统盘紧张时，把缓存留在工作区：在仓库根目录点源 `scripts/setup-runtime.ps1`（`. .\scripts\setup-runtime.ps1`），它会把 Whisper / HF / torch / yt-dlp 缓存和临时文件指到 `.cache/` 与 `.tmp/`。

## 工程质量

- **规模**：约 7.6 千行 Python、23 个功能模块、31 个 CLI 子命令、19 份契约文档；
- **测试**：`python -m pytest -q` → 415 passed / 2 skipped（本地 Python 3.11、CI Python 3.12 均全绿）；
- **CI**：[`.github/workflows/ci.yml`](./.github/workflows/ci.yml)，离线阻断式门禁；
- **可复现性**：每个资产用 `manifest.json` 记录阶段产物与 SHA-256，`verify-asset` 校验规范层（`source/`、`evidence/`、`knowledge/`）未被下游改写；
- **安全**：凭据、私有媒体、转录原文不入库；Cookie 只走显式参数。见 [SECURITY.md](./SECURITY.md)。

**当前验证范围**：Codex + 单 P Bilibili + CPU ASR + HTML 交付。GPU、平台字幕、多 P 合集、本地视频尚未被 Demo 覆盖。

## 仓库结构

```text
├── create-video-knowledge-assets/   # Skill 本体
│   ├── SKILL.md                     # Agent 读的入口：什么时候读哪份契约、按什么顺序做
│   ├── references/                  # 19 份数据契约 / 工作流 / profile 规范
│   ├── scripts/                     # vka CLI：获取、证据、知识、视图、渲染、打包
│   └── agents/openai.yaml           # 默认提示词
├── demos/                           # 三篇端到端成品（自包含 HTML）
├── docs/                            # 架构、能力地图、快速上手、作品集一页纸
├── scripts/                         # 本地运行环境准备（缓存 / 临时目录留在工作区）
└── tests/                           # 离线测试
```

## Roadmap

| 阶段 | 目标 | 状态 |
| --- | --- | --- |
| 一：可用 | 单视频、深度总结 / 课程笔记、单文件 HTML 交付、证据追溯 | ✅ 已交付 |
| 二：可复用 | 深度文章、短视频脚本、更多成品形态 | 🧪 初步实现，待更多真实验收 |
| 三：可产品化 | 发布审核、异常恢复、规模化复用 | 🔜 规划中 |

变更记录见 [CHANGELOG.md](./CHANGELOG.md)。

## 隐私、版权与许可

- 只处理你有权访问和使用的视频、字幕、封面与截图；
- 视频封面与截图的版权归原权利人所有，不在 MIT License 覆盖范围内；
- 本项目代码使用 [MIT License](./LICENSE)；安全问题见 [SECURITY.md](./SECURITY.md)，贡献指南见 [CONTRIBUTING.md](./CONTRIBUTING.md)。
