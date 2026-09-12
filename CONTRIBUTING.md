# 贡献指南

感谢参与 create-video-knowledge-assets。项目优先接受能够提高证据可靠性、课程笔记质量、跨格式一致性、安全边界和可复现性的改动。

## 开始之前

提交 Issue 或 Pull Request 前，请确认：

- 改动符合当前发布范围：深度总结与课程笔记是稳定交付面；深度文章与短视频脚本已实现、仍在真实验收；`enterprise-knowledge`、`research-brief` 为按需启用的扩展视图；问答与检索是另一个 Skill 的范围。
- 没有提交 Cookie、Authorization header、私有媒体、签名 URL、绝对路径、原始日志或未经授权的第三方内容。
- 没有把下载器、ASR 或 PDF 编译器的职责混入证据和知识模型。
- 新增文档遵守中英文之间留空格、中文使用全角标点等排版约定。

## 本地开发

项目要求 Python 3.11 或更高版本。

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install "pydantic>=2.7,<3" "srt>=3.5,<4" "pytest>=8,<9" "PyYAML>=6,<7"
```

运行检查：

```powershell
python create-video-knowledge-assets/scripts/vka_cli.py --help
python -m pytest -q
git diff --check
```

测试必须默认离线运行，不得下载视频、Whisper 模型或 TeX 发行版，不得读取浏览器 Cookie。需要真实媒体验收时，请使用自有、授权或许可明确的素材，并把验收记录与普通单元测试分开。

## 修改原则

### Skill 文档

- 保持 `SKILL.md` 简洁，只保留核心选择与执行流程。
- 详细 schema、获取命令和 profile 规则放入 `references/`，并从 `SKILL.md` 直接链接。
- 不在 skill 本体中新增仓库级 README、安装指南或变更日志。
- 修改触发范围后，同步检查 `agents/openai.yaml`。

### CLI 与模型

- CLI 参数、输出路径、错误条件和退出码应可测试。
- schema 变更需要说明兼容策略，并补充正常、非法和边界输入测试。
- 文件写入必须限制在声明的 asset 边界内；涉及覆盖、回滚和清理时增加幂等与失败测试。
- 不要依靠日志字符串或人工约定替代能够结构化验证的安全条件。

### 渲染器

- Markdown、HTML 和 LaTeX 应消费同一份 renderer-neutral document。
- 改动需要验证图片路径、来源时间、表格、公式、代码和特殊字符。
- PDF 页面视觉检查属于发布验收；普通 CI 只做离线单元测试和可选的轻量编译 smoke test。

## Pull Request 要求

Pull Request 描述应包含：

- 解决的问题和业务影响；
- 关键实现选择；
- 新增或修改的测试；
- 是否影响 schema、CLI、资产目录、隐私或版权边界；
- 无法自动验证的人工检查项目。

保持改动范围集中。不要顺带提交下载媒体、测试缓存、验收工作区或无关格式化修改。

## 提交示例与 Demo

公开示例只能包含以下材料：

- 自有、授权或许可明确的短视频及其必要派生物；
- 已脱敏的结构化样例；
- 不含绝对路径、凭据和私人信息的 manifest；
- 明确标注来源、许可、运行环境、处理时间和人工干预点的验收说明。

无法确认授权时，只提交合成 fixture，不提交原始视频、音频、字幕、封面或截图。
