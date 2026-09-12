# 架构与数据流

> 面向想理解本项目内部如何工作的读者。产品层面的"为什么"见 [README](../README.md)，这一步讲"是什么"和"怎么流动"。

## 总览

本项目是一条证据优先的视频内容再生产流水线：从视频输入到可交付成品，信息按 `source → evidence → knowledge → views → outputs` 逐级沉淀。层级之间用明确的数据契约（schema）约束，业务视图只能读取底层，不能反向修改来源事实。

```text
Bilibili URL 或本地视频
        │
        ▼
输入识别与工具预检（P1）
        │
        ▼
字幕 / 音频 / 视频 / 候选帧 ──► 证据层（修复后时间线 + 已检查画面）──► 知识层（单元 / 关系 / 综合 / 限制）
        │                                              │                      │
        │                                              ▼                      ▼
                                               │
                                               ▼
                               业务视图（`views/<profile>/`）
                                               │
                                               ▼
                              与渲染器无关的文档（document.json）
                                               │
                                               ▼
              正文与边界说明（同一底稿，各出 PDF + HTML）
```

## 规范资产布局

一次处理产生一个资产目录（asset）：

```text
<asset>/
├── manifest.json                 # 资产清单
├── source/                       # metadata、原始字幕、媒体、封面和 ASR 输入
├── evidence/                     # raw/repaired timeline、证据记录、候选与已检查帧
├── knowledge/
│   ├── units.jsonl               # 原子知识单元与证据状态
│   ├── relations.jsonl           # 知识关系（prerequisite / explains / supports / contradicts …）
│   ├── synthesis.json            # 全片综合与明确的 Agent 延伸
│   ├── outline.json              # deep-summary 写作中转层
│   ├── teaching_outline.json     # course-notes 教学中转层
│   └── revisions/                # 可选、带哈希绑定的知识修订
├── views/<profile>/              # 视图级投影计划、文档与格式产物
│   ├── view-manifest.json        # 业务视图选择原因与格式范围
│   ├── projection-plan.json      # P3 业务场景的知识到文档桥梁
│   └── document.json             # 渲染器无关文档
├── outputs/<profile>/            # 正文与边界说明的 TeX/PDF 产物
└── logs/                         # 本地运行信息，不得作为公开 Demo 提交
```

`source/`、`evidence/` 和 `knowledge/` 构成**规范事实层**。业务视图（`views/`）和输出（`outputs/`）是派生品。

## 流水线阶段

### P1 · 获取、转录与视觉取证

1. **输入识别与预检**：`vka preflight` 检查 yt-dlp / ffmpeg / ffprobe / whisper / xelatex 是否就绪；`vka normalize-bilibili-url` 规范化 URL；本地视频走 `describe-local-video`。
2. **获取**：优先匿名访问公开 Bilibili。字幕优先采用可靠 CC；无可靠字幕时使用 Whisper ASR，再经 `build-repair-prompt` / `apply-reviewed-transcript` 完成人工可复核的修订。
3. **证据落地**：原始 SRT 归一化为 `timeline.raw.jsonl`，修订后写 `timeline.jsonl`；`plan-frames` 按章节时间窗密集采样候选帧，最终画面必须人工直接检查后才登记为证据。

### P2 · 知识建模

从证据层构建三层知识：

- **知识单元**（`units.jsonl`）：概念、机制、例子、公式、视觉状态、误区、转折、要点；
- **知识关系**（`relations.jsonl`）：单元之间的前置、解释、支持、矛盾、因果等关系；
- **综合结论**（`synthesis.json`）：全片主线 + 明确标注的 Agent 延伸。

每个单元都携带 `evidence_refs` 和 `epistemic_status`（video / inference / external / insufficient），这是"证据优先"的落点。

### P3 · 业务视图（多场景投影）

主成品视图（deep-summary、deep-article、short-video-script、course-notes）通过**投影计划**（projection-plan）把知识层映射为读者文档；enterprise-knowledge、research-brief 属于按需启用的扩展业务视图：

- `select-profile` / `route-profile` 记录选择原因；
- `write-projection-plan` + `validate-projection-plan` 生成并校验知识到内容再到文档的桥梁；
- Agent 只允许写 `views/<profile>/` 和 `outputs/<profile>/`，禁止改动 `source/`、`evidence/`、`knowledge/`（`verify-asset` 校验哈希前后一致）。

## 关键工具边界

| 工具 | 职责 | 边界 |
| --- | --- | --- |
| `vka` CLI | 输入身份、URL 规范化、元数据清洗、字幕规范化、资产边界、证据记录、质量验证、业务视图、渲染 | 项目自身逻辑 |
| yt-dlp | 公开平台的元数据、字幕、封面、音频和视频获取 | 只写入当前资产 `source/` |
| ffmpeg / ffprobe | 媒体探测、音频转换和候选帧抽取 | 只写入候选区 |
| Whisper | 仅在可靠字幕缺失时做 ASR | ASR 结果仍需修复和审核 |
| XeLaTeX | 把通过质量门的 LaTeX 编译为 PDF | 最终交付前人工检查 |

## 质量门与校验

- `preflight`：阶段前工具检查；
- `validate-teaching-outline`：教学大纲结构校验；
- `validate-document`：渲染器无关文档与 profile 质量门；
- `validate-projection-plan`：P3 投影契约校验；
- `verify-asset`：规范资产哈希一致性。

自动校验不能替代人工内容验收；发布前至少抽查关键事实、视觉结论、课程结构，以及 PDF 逐页效果和 HTML 在浏览器里的观感。

## 明确不做什么（边界）

- 不做通用联网搜索（外部背景必须显式注册并分区展示）；
- 不做向量 embedding / 向量库 / 跨资产 RAG 知识库；
- 不做独立模型 API 编排层；
- 多分 P 视频必须显式选择范围，不静默处理整个合集。

更多细节见 [`references/`](../create-video-knowledge-assets/references/) 中对应的契约文档。
