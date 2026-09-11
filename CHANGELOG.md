# Changelog

本文件记录本项目（`create-video-knowledge-assets`）对外可感知的变更。语义化版本见 [`pyproject.toml`](./pyproject.toml)。

## [Unreleased]

### 交付形态收敛为 PDF

- 正文与证据边界仍然分成两份 PDF，但 HTML、Markdown 降级为同一份文档视图的审阅输出，不再作为对外的第二种交付物；三篇 Demo 只发布 `summary.pdf` 与 `notes.pdf`。
- 重做两套渲染器的排版：正文宋体 + 黑体标题的字号梯度、封面（标题／主题句／一句话摘要／副标题／封面图／三行元数据）、目录并入正文第一页、图片统一宽度与细边框、来源时间改为文末两栏列表；HTML 排版与之对齐。
- 来源时间在渲染前统一合并（间隔 2 秒内的窗口视为一段）并去重，正文上标编号与文末列表共用一次编号。

### 写作规则从"格式"转向"源形态"

- 投影计划新增必填的 `source_form`（类型／时长带／密度／章节形态）与 `granularity`（计划承载的核心判断数与理由），写作粒度由视频形态决定，不设固定配额。
- 重申三条硬规则：教程按覆盖度计量（每个步骤落在完整讲述／合并／明确省略三态之一，覆盖清单写进 notes）、一段一判断、每个判断只引用 1–3 个连续时间窗（更多则标为综合并在 notes 给证据表）。
- 三篇 Demo 按上述规则重写：竹子科普补齐了遗漏的风味营养与日本案例，20 分钟教程逐条覆盖九个步骤与三个检查点，短视频脚本补上目标时长、取舍清单与拍摄备注。

### 架构

- 移除 P4 证据约束问答子系统（10 个模块、索引层、CLI 命令与 CI 实验作业）；`content/` 中间层已删除，资产层收敛为 `source/`、`evidence/`、`knowledge/`、`views/`、`outputs/`。
- 结果：约 7.3 千行 Python、23 个模块、27 个测试文件，`pytest` 414 passed / 2 skipped。

### 文档与作品集呈现

- 重写 README，转为产品叙事：以"把视频变成可学习、可追问、可复用、可归档的知识资产"为定位主线。
- 新增 `docs/` 文档体系：作品集一页纸、快速上手、架构与数据流、能力地图、开发指南、质量与基准。
- 新增英文版 README（`README.en.md`）与仓库 banner。

### 待办（open items）

- 补充 benchmark 真实运行数据（质量门通过率、耗时、成本、grounding 抽查）。
- 沉淀真实视频 / ASR / PDF 的人工验收记录。

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
