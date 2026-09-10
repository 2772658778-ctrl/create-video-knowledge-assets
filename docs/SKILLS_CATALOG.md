# 能力地图

> 本项目是一个单一、连贯的流水线产品，不是一组彼此独立的 skill 的拼盘。本文用"能力地图"的方式呈现它的内部结构，帮助你理解每一段负责什么、边界在哪。契约细节以 [`references/`](../create-video-knowledge-assets/references/) 为准。

## 两种读法

- **按场景读**：找"我想做 X"，看它对应哪条路径、当前处于什么成熟度；
- **按流水线读**：看 P1–P4 每一段负责什么，数据如何逐层沉淀。

## 按场景：4 类成品输出

| 能力 | 入口 Profile | 成熟度 | 契约 |
| --- | --- | --- | --- |
| 深度总结 | `deep-summary`（兼容 `general-deep`） | 主要能力 ✅ | [profile-general-deep](../create-video-knowledge-assets/references/profile-general-deep.md) |
| 深度文章 | `deep-article`（兼容 `creator-article`） | 主要能力 ✅ | [profile-creator-article](../create-video-knowledge-assets/references/profile-creator-article.md) |
| 短视频脚本 | `short-video-script` | 主要能力 ✅ | [profile-short-video-script](../create-video-knowledge-assets/references/profile-short-video-script.md) |
| 课程笔记 | `course-notes` | 主要能力 ✅ | [profile-course-notes](../create-video-knowledge-assets/references/profile-course-notes.md) · [teaching-outline](../create-video-knowledge-assets/references/teaching-outline.md) |

## 独立实验路径

| 能力 | 入口 Profile | 成熟度 | 契约 |
| --- | --- | --- | --- |
| 证据约束问答 | —（基于 course-notes 资产） | 未来实验 ⚗️ | [p4-qa](../create-video-knowledge-assets/references/p4-qa.md) |

profile 选择与路由逻辑见 [profile-routing](../create-video-knowledge-assets/references/profile-routing.md)。

## 按流水线：P1–P4

| 阶段 | 负责什么 | 关键产物 | 主要契约 |
| --- | --- | --- | --- |
| P1 获取与取证 | 输入识别、字幕 / ASR、抽帧与画面检查 | `source/` · `evidence/` | [acquisition-recipes](../create-video-knowledge-assets/references/acquisition-recipes.md) · [p1-workflow](../create-video-knowledge-assets/references/p1-workflow.md) · [p2-u1-workflow](../create-video-knowledge-assets/references/p2-u1-workflow.md) · [transcript-repair](../create-video-knowledge-assets/references/transcript-repair.md) |
| P2 知识与内容建模 | 知识单元、关系、综合结论、限制、可复用内容单元 | `knowledge/` · `content/` | [evidence-schema](../create-video-knowledge-assets/references/evidence-schema.md) · [knowledge-schema](../create-video-knowledge-assets/references/knowledge-schema.md) · [content-schema](../create-video-knowledge-assets/references/content-schema.md) |
| P3 业务视图 | 投影计划、内容选择、业务写作、视图质量门 | `content/` · `views/<profile>/` · `outputs/<profile>/` | [p3-profile-workflow](../create-video-knowledge-assets/references/p3-profile-workflow.md) · [p3-profile-authoring](../create-video-knowledge-assets/references/p3-profile-authoring.md) · [projection-plan](../create-video-knowledge-assets/references/projection-plan.md) · [document-schema](../create-video-knowledge-assets/references/document-schema.md) |
| P4 证据问答 | 索引、拓扑、检索、回答计划、校验 | `index/` · `views/<profile>/document.json` | [p4-qa](../create-video-knowledge-assets/references/p4-qa.md) · [p4-video-topology](../create-video-knowledge-assets/references/p4-video-topology.md) · [p4-qa-authoring](../create-video-knowledge-assets/references/p4-qa-authoring.md) · [p4-qa-evaluation](../create-video-knowledge-assets/references/p4-qa-evaluation.md) · [p4-external-evidence](../create-video-knowledge-assets/references/p4-external-evidence.md) · [p4-answer-presentation](../create-video-knowledge-assets/references/p4-answer-presentation.md) |

## 完整契约清单（23 份）

见 [`references/`](../create-video-knowledge-assets/references/)，按前缀分组：

- **获取 / 生命周期**：`acquisition-recipes` · `p1-workflow` · `p2-u1-workflow` · `transcript-repair`
- **数据模型**：`evidence-schema` · `knowledge-schema` · `content-schema` · `document-schema`
- **业务视图**：`profile-routing` · `profile-general-deep` · `profile-course-notes` · `profile-creator-article` · `profile-short-video-script` · `profile-enterprise-knowledge` · `profile-research-brief` · `teaching-outline` · `p3-profile-workflow` · `p3-profile-authoring` · `projection-plan`
- **Q&A（未来实验，不在主交付边界）**：`p4-qa` · `p4-video-topology` · `p4-qa-authoring` · `p4-qa-evaluation` · `p4-external-evidence` · `p4-answer-presentation`
