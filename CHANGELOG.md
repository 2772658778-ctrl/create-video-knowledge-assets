# Changelog

本文件记录本项目（`create-video-knowledge-assets`）对外可感知的变更。语义化版本见 [`pyproject.toml`](./pyproject.toml)。

## [Unreleased]

### 文档与作品集呈现

- 重写 README，转为产品叙事：以"把视频变成可学习、可追问、可复用、可归档的知识资产"为定位主线。
- 新增 `docs/` 文档体系：作品集一页纸、快速上手、架构与数据流、能力地图、开发指南、质量与基准。
- 新增英文版 README（`README.en.md`）与仓库 banner。

### 待办（open items）

- 补充 benchmark 真实运行数据（质量门通过率、耗时、成本、grounding 抽查）。
- 沉淀真实视频 / ASR / PDF 的人工验收记录。

### Q&A 契约与测试对齐（本次改动）

- 将 QA 测试夹具与 v1.1 回答契约对齐（`answer_plan.mode` 必须匹配、`answer_plan` 块必须携带 `expected_claim_ids`、上下文模式需 schema 1.2、扩展标签收敛到固定文案）。
- 实现 revision 感知的答案校验：`GroundedAnswer` 支持 `knowledge_revision` / `knowledge_revision_sha256`，plan 允许 revision 元数据，`validate_grounded_answer` 对 revision 答案按 revision 单元/关系复核并校验 revision 身份与保留窗口/拓扑一致性。
- 结果：全套测试 477 passed / 6 skipped（Python 3.11 / 3.13 均可复现）。

## [0.1.0] — 2026-08

开源发布包。核心工程链可用：

- **P1 获取与取证**：Bilibili / 本地视频输入识别、预检、字幕或 Whisper 转录、ASR 修订链、候选帧规划与人工检查。
- **P2 知识建模**：知识单元、关系、综合结论，携带证据引用与 epistemic status。
- **P3 业务视图**：深度总结、课程笔记、创作者文章、企业归档、研究简报，基于投影计划与视图质量门。
- **渲染**：渲染器无关文档 → PDF / HTML / Markdown，质量校验（quality floor）。
- **P4 证据约束问答（实验性）**：词法索引、知识拓扑、有界证据窗口、检索、回答计划、声明校验。
- **工程**：约 1.1 万行 Python，28 个模块，31 个测试文件，稳定测试 345 通过；CI stable（阻断）+ experimental-qa（不阻断）。
- **文档**：README、SKILL.md 契约、23 份 references 契约、CONTRIBUTING、SECURITY。

[Unreleased]: https://github.com/2772658778-ctrl/create-video-knowledge-assets/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/2772658778-ctrl/create-video-knowledge-assets/releases/tag/v0.1.0
