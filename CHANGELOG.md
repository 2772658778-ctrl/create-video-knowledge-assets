# Changelog

本文件记录本项目（`create-video-knowledge-assets`）对外可感知的变更。语义化版本见 [`pyproject.toml`](./pyproject.toml)。

## [Unreleased]

### 交付形态：默认单文件 HTML，PDF 按需

- 默认交付收敛为 HTML：正文与边界说明各是一个自包含文件（`summary.html`、`notes.html`），封面与引用画面内联在同一份文件里，双击即可阅读，不需要安装任何东西。
- 两个部分保持独立文件：读者看正文时不会滚过范围说明，`notes.html` 仍单独交付。
- PDF 改为按需能力：只有用户明确要求时才渲染与编译，也是唯一需要 LaTeX 工具链（XeLaTeX）的路径；交付 HTML 的运行在结束时提示同一份底稿可以出 PDF。
- 相应收敛：`reader-typography.md`（原 `pdf-typography.md`）改成"默认交付什么 + PDF 何时产出"，固定分页相关规则（目录页码、空白尾巴、两栏来源时间、编译三遍）收进 PDF 小节；`.gitignore` 与 README/QUICKSTART/一页纸/架构文档的口径同步；`package-demo` 不再复制图片目录，改为把图片内联进交付件。
- 重做两套渲染器的排版：正文宋体 + 黑体标题的字号梯度、封面（标题／主题句／一句话摘要／副标题／封面图／三行元数据）、目录并入正文第一页、图片统一宽度与细边框、来源时间改为文末两栏列表；HTML 排版与之对齐。
- 来源时间在渲染前统一合并（间隔 2 秒内的窗口视为一段）并去重，正文上标编号与文末列表共用一次编号。
- 三篇 Demo 发布单文件 HTML；README、快速上手、一页纸与架构文档的链接与口径同步更新。

### 写作规则从"格式"转向"源形态"

- 投影计划新增必填的 `source_form`（类型／时长带／密度／章节形态）与 `granularity`（计划承载的核心判断数与理由），写作粒度由视频形态决定，不设固定配额。
- 重申三条硬规则：教程按覆盖度计量（每个步骤落在完整讲述／合并／明确省略三态之一，覆盖清单写进 notes）、一段一判断、每个判断只引用 1–3 个连续时间窗（更多则标为综合并在 notes 给证据表）。
- 三篇 Demo 按上述规则重写：竹子科普补齐了遗漏的风味营养与日本案例，20 分钟教程逐条覆盖九个步骤与三个检查点，短视频脚本补上目标时长、取舍清单与拍摄备注。

### 架构

- 移除 P4 证据约束问答子系统（10 个模块、索引层、CLI 命令与 CI 实验作业）；`content/` 中间层已删除，资产层收敛为 `source/`、`evidence/`、`knowledge/`、`views/`、`outputs/`。
- 结果：约 7.6 千行 Python、23 个模块、27 个测试文件，`pytest` 415 passed / 2 skipped。

### 文档与作品集呈现

- README（中英）改为 AI 产品导向：开头就回答"这是什么 / 什么时候用它 / 怎么装 / 怎么调用 / 会拿到什么"，新增"你说什么 → 它做什么"的 profile 触发映射与"不适用于"，工程规模与测试数字后置；英文版与中文版逐节对齐，能力地图的成熟度标注与 Roadmap 统一。
- 校对文档事实与链接：`setup-runtime.ps1` 实际位于仓库根 `scripts/`（且需点源才作用于当前会话）、一页纸的 README 锚点、`CONTRIBUTING.md` 中残留的 Q&A 子系统说明，以及文档中的 Python 版本下限，全部改为与 `pyproject.toml` 和当前代码一致。
- 删除孤儿文件 `create-video-knowledge-assets/assets/notes-template.tex`：自基线提交起没有任何引用，LaTeX 渲染器自带 preamble。
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
