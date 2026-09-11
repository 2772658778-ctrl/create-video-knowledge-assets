# create-video-knowledge-assets

> **Turn a knowledge video into a shippable, reusable, and traceable video content artifact.**

[简体中文](./README.md) · [Quick start](./docs/getting-started/QUICKSTART.md)

![create-video-knowledge-assets](assets/banner.svg)

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](./pyproject.toml)
[![Tests](https://img.shields.io/badge/tests-414_passed-green)](#engineering-quality)

---

`create-video-knowledge-assets` is an AI-driven video content reproduction engine. Give it a **Bilibili URL** or a **local knowledge video**, and it handles source identification, subtitle acquisition or speech transcription, key-frame inspection, evidence organization, knowledge modeling, and business-oriented writing — delivering a clean artifact you can use directly (**a PDF**).

It is not a "video summarizer." A summary compresses information; it turns a one-time viewing into a **traceable, reviewable, reusable** knowledge asset.

## Why this exists

A lot of high-value knowledge lives in videos, but videos are naturally bad for quick review, remixing, and team sharing. Viewers re-watch, hand-write notes, and reorganize them into documents — expensive, and easy to miss the key logic, examples, and boundary conditions.

| Pain point | What it looks like |
| --- | --- |
| Understood but hard to reuse | After watching, you still need to rebuild notes, structure, and citations |
| Key information scattered | Conclusions are spread across subtitles, frames, and context; manual assembly is costly |
| Ordinary summaries are too thin | Only conclusions remain — no structure, evidence, examples, or limits |
| Scenarios demand different outputs | Learning, creation, archival, and research each need a different depth and format |

The goal is not "compress a video into a short summary" but **"turn one viewing into a sustainable knowledge result."**

## What it produces

One video asset, processed once, serving four production profiles.

| Scenario | Audience | Status | What it does |
| --- | --- | --- | --- |
| Deep summary | Learners | Core ✅ | `deep-summary`, rebuilds the video's logic from claims, mechanisms, examples, key frames, and limits |
| Deep article | Creators / analysts | Core ✅ | `deep-article`, turns video material into a clean long-form article |
| Short video script | Content creators | Core ✅ | `short-video-script`, extracts reusable hooks, turns, and closes |
| Course notes | Learners / teachers | Core ✅ | `course-notes`, keeps learning objectives, prerequisites, concepts, mechanisms, examples, summaries, and source navigation |

`general-deep` and `creator-article` remain as compatibility aliases.

Three formats, one underlying source document:

- **PDF** — primary deliverable, for reading and archiving;
- **HTML** — for browsing and sharing online;
- **Markdown** — for editing and remixing.

## Core design decisions

This project is worth explaining not just for what it does, but for **why it is designed this way**.

### 1. Evidence-first: evidence before conclusions

Every knowledge claim lands in an evidence layer first — subtitle time windows, key frames, visual observations — before entering the knowledge and document layers. **The agent cannot treat unchecked candidate frames as evidence, and cannot disguise inference as something the video explicitly said.** Epistemic status explicitly distinguishes: explicitly stated in video / agent inference / external supplement / insufficient evidence.

> Effect: a reader can follow source-time footnotes back to the video to verify any key claim.

### 2. Content–format separation: knowledge to content, then formats

The system builds a renderer-neutral draft and compiles it to PDF. **Prose, figures, and provenance are written once**, so the deliverable cannot drift.

### 3. One asset, many views: reusable content units

`source/`, `evidence/`, and `knowledge/` form the canonical fact base. Course notes, deep articles, short video scripts, and other product views are **different finished outputs from the same asset**. Views may read the lower layers and write only to their own `views/` and `outputs/` — they cannot pollute the underlying facts.

> Effect: a video is not re-understood once per scenario; it is processed once and reused many times.

### 4. Quality gates and human checkpoints: not a black box

Staged contracts, quality gates, and human review points govern the process: multi-part videos must explicitly select a range; when subtitles are missing, it degrades to Whisper transcription while preserving a repair trail; when evidence is insufficient, it downgrades and annotates rather than fabricating; **a human review point remains before publication.**

## Real results

### End-to-end demos (Bilibili URL → deliverables)

| Demo | Scenario | View directly |
| --- | --- | --- |
| Why so few countries eat bamboo shoots (11:48 explainer) | Deep summary: three eating thresholds, line-by-line reviewed transcript, 6 inspected frames | [PDF](./demos/bili-BV1tHdoYnEGm/summary.pdf) · [boundary notes](./demos/bili-BV1tHdoYnEGm/notes.pdf) |
| Why the national herbal tea stopped selling (10:20 finance short) | Short-video script: ~2-minute cut, with pacing assumptions and a cut list | [PDF](./demos/bili-BV1hwtB6YEzo/summary.pdf) · [boundary notes](./demos/bili-BV1hwtB6YEzo/notes.pdf) |
| Harness in practice: turning any text into a polished article (20:37 tutorial) | Long-form article: all nine steps covered, with checkpoints and process evidence | [PDF](./demos/bili-BV1ayLD6uERL/summary.pdf) · [boundary notes](./demos/bili-BV1ayLD6uERL/notes.pdf) |

The three demos cover three different source forms — a dense 12-minute explainer, a 10-minute data commentary, and a 20-minute tutorial — and their length and structure follow the source rather than a template. All of them ran the full pipeline: URL → subtitles/transcription → frame extraction and inspection → knowledge modeling → writing → PDF. Each also ships a separate boundary document, so the reader copy stays about the video while scope, uncertainty, and claim-to-source navigation live in their own PDF.

**Current verification scope**: these demos validate the Codex, single-part Bilibili, CPU ASR, and the PDF delivery path. GPU, platform subtitles, full multi-part handling, and local videos are not yet covered by demos.

## Architecture at a glance

```text
Bilibili URL or local video
        │
        ▼
Input identification & tool preflight ────► Subtitles / audio / video / candidate frames
        │                                        │
        ▼                                        ▼
  Evidence layer (repaired timeline + inspected frames) ──► Knowledge layer (units / relations / synthesis / limits)
        │                                                    │
        ▼                                                    ▼
        │
        ▼
 Renderer-neutral document ──► content PDF + boundary-notes PDF
        │
        ▼
 Learning · Creation · Archival · Publishing
```

Full architecture, asset layout, and data contracts: [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md).

## Quick start

Regular users only provide the video and the goal — no hand-built outlines, evidence JSON, or render commands.

**Default deep summary:**

```text
Use $create-video-knowledge-assets to deeply summarize this video: <Bilibili URL>.
Organize the core question, mechanisms, examples, key frames, limits, and source navigation, and produce PDF, HTML, and Markdown.
```

**Course notes:**

```text
Use $create-video-knowledge-assets to turn this video into Chinese course notes suitable for learning and review: <Bilibili URL>.
Keep key frames, teaching structure, and source-time footnotes, and produce PDF, HTML, and Markdown.
```

**Local video:**

```text
Use $create-video-knowledge-assets to deeply summarize this local knowledge video: <local video path>.
Check video identity and tool conditions first, then build evidence, knowledge, and the final documents.
```

**Bilibili videos require an explicit cookie.** Bilibili's public endpoints generally need a login session for reliable subtitle and metadata acquisition. Sign in to Bilibili in your browser, then use the **Cookie-Editor** browser extension to export `bilibili.com` cookies (Netscape format), and pass them explicitly via `--cookie-file <path>` or `yt-dlp --cookies <file>`. Cookies are account credentials: export only Bilibili-related domains and never commit them to the repository or paste them into public content.

Installation and full examples: [docs/getting-started/QUICKSTART.md](./docs/getting-started/QUICKSTART.md).

## Engineering quality

- **Language / environment**: Python 3.12+, `pydantic`, `srt`; external tools yt-dlp / ffmpeg / Whisper / XeLaTeX invoked as needed;
- **Scale**: ~11k lines of Python, 28 modules, 31 test files;
- **Tests**: `python -m pytest -q` (414 passing, reproducible on Python 3.11 / 3.12 / 3.13);
- **CLI**: `vka` exposes 31 stage commands covering acquisition, evidence, knowledge, content, views, and rendering;
- **Contracts**: 23 schema / workflow / security contract documents in [`references/`](./create-video-knowledge-assets/references/);
- **CI**: [`.github/workflows/ci.yml`](./.github/workflows/ci.yml), stable (blocking) + experimental (non-blocking);
- **Security**: Bilibili content requires an explicit cookie (exported via Cookie-Editor); credentials, private media, and logs never enter the repo. See [SECURITY.md](./SECURITY.md).

## Repository structure

```text
├── create-video-knowledge-assets/   # The skill itself (SKILL.md, scripts/, references/, assets/)
├── docs/                            # Product and engineering docs (architecture, capability map, quick start)
├── demos/                           # End-to-end demos (content PDF + boundary PDF)
├── tests/                           # Stable tests + experimental tests
└── CHANGELOG.md / LICENSE / SECURITY.md / CONTRIBUTING.md
```

## Evolution & roadmap

This project began with a product requirements document that defined one guiding thread: **evidence before conclusions; structure before rhetoric; traceability before publication; go deep on one scenario before expanding.** v0.1 delivers the core engineering chain of that thread.

| Phase | Goal | Status |
| --- | --- | --- |
| Phase 1: Usable | Single video, deep summary / course notes, PDF delivery, evidence traceability | ✅ shipped in v0.1 |
| Phase 2: Reusable | Deep articles, short video scripts, broader content profiles | 🧪 implemented early, awaiting more real-business validation |
| Phase 3: Productizable | Quality gates, release review, exception recovery, scaled reuse | 🔜 planned |

Changes: [CHANGELOG.md](./CHANGELOG.md).

## Documentation map

| Document | Content | For |
| --- | --- | --- |
| [Quick start](./docs/getting-started/QUICKSTART.md) | Start in 30 seconds + scenario examples | Regular users |
| [Architecture](./docs/ARCHITECTURE.md) | Asset layout, pipeline, data contracts, product views | Engineers |
| [Capability map](./docs/SKILLS_CATALOG.md) | 4 production profiles + the P1–P3 pipeline + contract index | Anyone exploring boundaries |

## Privacy, copyright & license

- Only processes videos, subtitles, covers, and screenshots the user has the right to access.
- Cookies are account credentials — export only Bilibili-related domains and never commit them to the repo.
- Video covers and screenshots remain the property of their rights holders and are not covered by this project's MIT License.
- Project code is under the [MIT License](./LICENSE).

See [SECURITY.md](./SECURITY.md) for security. Contributions are welcome — please read [CONTRIBUTING.md](./CONTRIBUTING.md) before changing workflows, data contracts, or security boundaries.
