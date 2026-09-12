# create-video-knowledge-assets

> **A Skill for AI agents: turn one video into an evidence-backed reader document you can ship as it is.**

[简体中文](./README.md) · [Quick start](./docs/getting-started/QUICKSTART.md) · [Capability map](./docs/SKILLS_CATALOG.md) · [Architecture](./docs/ARCHITECTURE.md)

![create-video-knowledge-assets](assets/banner.svg)

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](./pyproject.toml)
[![Tests](https://img.shields.io/badge/tests-415_passed-green)](#engineering-quality)

---

## What it is

A Skill you can install into Codex / Claude Code and other agents. Hand it a **Bilibili URL** or a **local video** plus one sentence about what you want, and it walks the whole chain: identify the source → fetch subtitles or transcribe → extract frames and **inspect the picture with real eyes** → build the evidence and knowledge layers → write the reader document → deliver **one self-contained HTML file that opens with a double click** (figures, cover, and source times all inside it).

The difference from a "video summarizer" is one sentence: **every conclusion traces back to a sentence or a frame in the video** — and the agent actually looked at that frame rather than guessing.

| | |
| --- | --- |
| Type | An Agent Skill. `SKILL.md` is the entry point for the agent; this file is the entry point for people |
| Input | One Bilibili URL (single part) or a local video file, plus one sentence about what you want |
| Output | `summary.html` (the reader copy) + `notes.html` (boundaries and sources), each self-contained; a PDF only when you explicitly ask for one |
| Dependencies | Python 3.11+, `pydantic`, `srt`; yt-dlp / ffmpeg / faster-whisper depending on the path |

**Who it is for**

- Creators who want their video content turned into reusable documents;
- Teams that need long videos split into learning material / narration scripts / long-form articles;
- Developers who want a "video → trustworthy document" capability inside their own agent workflow.

## When to use it

| You say | Profile | You get |
| --- | --- | --- |
| "Deeply summarize this video: `<URL>`" | `deep-summary` | The video's logic rebuilt from claims / mechanisms / examples / key frames |
| "Turn this video into course notes" | `course-notes` | Learning objectives / prerequisites / concepts / mechanisms / worked examples / summary / source navigation |
| "Rewrite it as a long-form article" | `deep-article` | A publish-ready WeChat / Zhihu style article with an actionable checklist |
| "Make it a script I can shoot straight away" | `short-video-script` | Target duration + pacing assumptions + a cut list |

On request: `enterprise-knowledge` (team knowledge archival), `research-brief` (research briefs). `general-deep` and `creator-article` are compatibility aliases.

**Not for**: compressing a video into three lines; Q&A or retrieval over existing assets (that would be a different Skill); processing material you have no right to use.

## 30-second start

**1. Install it into your agent**

Drop the whole `create-video-knowledge-assets/` directory into a directory your agent discovers Skills in — Codex's `~/.codex/skills/`, for example, or a Claude Code project's `.claude/skills/`. You can also reference the directory directly in the conversation.

```powershell
# Install the Python dependencies (default HTML delivery needs only these two)
python -m pip install "pydantic>=2.7,<3" "srt>=3.5,<4"
```

**2. Ask in one sentence**

```text
Use $create-video-knowledge-assets to deeply summarize this video: <Bilibili URL>.
```

```text
Turn this video into course notes: <local video path>.
Keep the key frames and the teaching structure, and deliver one self-contained HTML file.
```

```text
Use $create-video-knowledge-assets to summarize this video: <Bilibili URL>, and give me a PDF as well.
```

**3. Take the result**

You get two files — `summary.html` (the reader copy) and `notes.html` (evidence boundaries and sources) — each self-contained and dependent on nothing else in the repository. When you need an archive copy to forward, the same draft can render a PDF as well.

> Bilibili subtitles and metadata usually need a login session: export `bilibili.com` cookies with a browser extension such as Cookie-Editor, then pass them explicitly with `--cookie-file`. Cookies are account credentials — do not commit them to the repository or paste them into public content.

## What you get

Three demos ran the full chain (URL → transcription → frame extraction and inspection → knowledge modeling → writing → delivery); open them directly to see the result:

| Demo | Source form | Deliverable |
| --- | --- | --- |
| Why so few countries outside China eat bamboo shoots | 11:48 explainer | [article](./demos/bili-BV1tHdoYnEGm/summary.html) · [boundary notes](./demos/bili-BV1tHdoYnEGm/notes.html) |
| Three years, a billion fewer: who pushed the national herbal tea off the shelf | 10:20 finance narration | [script](./demos/bili-BV1hwtB6YEzo/summary.html) · [boundary notes](./demos/bili-BV1hwtB6YEzo/notes.html) |
| Turning any text into a polished article: a reusable production pipeline | 20:37 tutorial | [article](./demos/bili-BV1ayLD6uERL/summary.html) · [boundary notes](./demos/bili-BV1ayLD6uERL/notes.html) |

The **reader copy** talks only about the video; readers never need to know what pipeline sits behind it. The **boundary notes** are a file of their own, spelling out what the video explicitly states, what this document inferred, what was not independently verified, and the time window behind each conclusion.

## Why it is trustworthy

1. **Evidence first.** Conclusions land in the evidence layer first (subtitle time windows, frames the agent inspected directly) and only then enter the knowledge and document layers. Epistemic status has four levels — explicitly stated in the video / agent inference / external supplement / insufficient evidence — and an inference is never written as the video's own words.
2. **The picture has really been looked at.** Candidate frames are not evidence; only frames the agent inspected directly, and described honestly in the figure and its caption, enter the document.
3. **Written once, rendered in several formats.** The reader copy is written once; HTML and PDF render from the same draft, so "the content no longer matches after a format change" cannot happen.
4. **One asset, many finished outputs.** The same video projects into a summary, an article, a script, or course notes; views may only read the fact layers and cannot rewrite the original facts.
5. **Quality gates + human checkpoints.** Multi-part videos must select an explicit range; when subtitles are missing it degrades to Whisper transcription while keeping a line-by-line review trail; a human acceptance step remains before publication.

Full mechanism: [architecture and data flow](./docs/ARCHITECTURE.md); technical contracts live in [`references/`](./create-video-knowledge-assets/references/).

## Environment and dependencies

| Requirement | When you need it |
| --- | --- |
| Python 3.11+, `pydantic`, `srt` | Always (default HTML delivery needs only these) |
| `yt-dlp` | Metadata / subtitles / media from Bilibili |
| `ffmpeg`, `ffprobe` | Frame and audio extraction |
| faster-whisper | Transcription when no usable subtitles exist (`base` / CPU / int8) |
| XeLaTeX | **Only when you want a PDF** |

When the system drive is tight, keep the caches in the workspace: dot-source `scripts/setup-runtime.ps1` from the repository root (`. .\scripts\setup-runtime.ps1`) and it points Whisper / HF / torch / yt-dlp caches and temporary files at `.cache/` and `.tmp/`.

## Engineering quality

- **Scale**: ~7.6k lines of Python, 23 modules, 31 CLI subcommands, 19 contract documents;
- **Tests**: `python -m pytest -q` → 415 passed / 2 skipped (green on local Python 3.11 and on CI Python 3.12);
- **CI**: [`.github/workflows/ci.yml`](./.github/workflows/ci.yml), an offline blocking gate;
- **Reproducibility**: every asset records stage outputs and SHA-256 in `manifest.json`, and `verify-asset` checks that the canonical layers (`source/`, `evidence/`, `knowledge/`) were not rewritten downstream;
- **Security**: credentials, private media, and raw transcripts never enter the repo; cookies travel only as explicit arguments. See [SECURITY.md](./SECURITY.md).

**Current verification scope**: Codex + single-part Bilibili + CPU ASR + HTML delivery. GPU, platform subtitles, multi-part collections, and local videos are not yet covered by demos.

## Repository structure

```text
├── create-video-knowledge-assets/   # The Skill itself
│   ├── SKILL.md                     # The agent's entry point: which contract to read when, in what order
│   ├── references/                  # 19 data contracts / workflows / profile specs
│   ├── scripts/                     # The vka CLI: acquisition, evidence, knowledge, views, rendering, packaging
│   └── agents/openai.yaml           # Default prompt
├── demos/                           # Three end-to-end deliverables (self-contained HTML)
├── docs/                            # Architecture, capability map, quick start, portfolio one-pager
├── scripts/                         # Local runtime setup (caches / temp files kept in the workspace)
└── tests/                           # Offline tests
```

## Roadmap

| Phase | Goal | Status |
| --- | --- | --- |
| One: usable | Single video, deep summary / course notes, self-contained HTML delivery, evidence traceability | ✅ shipped |
| Two: reusable | Deep articles, short-video scripts, more finished forms | 🧪 implemented early, awaiting more real-world acceptance |
| Three: productizable | Release review, exception recovery, reuse at scale | 🔜 planned |

Changes: [CHANGELOG.md](./CHANGELOG.md).

## Privacy, copyright & license

- Only processes videos, subtitles, covers, and screenshots you have the right to access and use;
- Video covers and screenshots remain the property of their rights holders and are outside the scope of the MIT License;
- Project code is under the [MIT License](./LICENSE). For security see [SECURITY.md](./SECURITY.md); for contribution guidance see [CONTRIBUTING.md](./CONTRIBUTING.md).
