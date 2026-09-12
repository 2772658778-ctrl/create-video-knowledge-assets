# Profile Routing

R3 selects a registered reader-facing profile before a view is authored. The
selection is deterministic and records its explanation in both the asset
manifest and `views/<profile_id>/view-manifest.json`.

## Registered Profiles

| Profile | Use when | Reference |
| --- | --- | --- |
| `general-deep` | no specialized profile is requested | `profile-general-deep.md` |
| `deep-summary` | an explicit deep summary is requested | `profile-general-deep.md` |
| `course-notes` | the requested output is a teachable lesson | `profile-course-notes.md` |
| `creator-article` | a reader-facing article is explicitly requested | `profile-creator-article.md` |
| `deep-article` | an explicit long-form article is requested | `profile-creator-article.md` |
| `short-video-script` | a concise short-form script is explicitly requested | `profile-short-video-script.md` |
| `enterprise-knowledge` | an internal decision or operational knowledge view is explicitly requested | this routing contract |
| `research-brief` | a compact research-oriented brief is explicitly requested | this routing contract |

## Selection Order

1. A registered explicit `--profile` always wins.
2. With no explicit profile, only these exact intent labels may route a view:
   `课程笔记`/`写成课程笔记`, `公众号长文`/`写成公众号长文`,
   `企业知识库`/`写成企业知识库`, `研究简报`/`写成研究简报`,
   and `短视频脚本`/`写成短视频脚本`.
3. Any absent or unregistered intent defaults to `general-deep`.

Do not classify arbitrary prompt prose, infer an audience from a source, or
record a free-text request as a fact about the video. `selection_source`,
`reason`, and the requested explicit profile/intent stay in the manifests so a
reviewer can reproduce the route.

Use `vka select-profile --asset <asset> [--profile <registered-id>]
[--intent <exact-label>] [--format <md|html|tex|pdf>]` before authoring
`document.json`. Without `--format`, a view is delivered as HTML; `pdf` is the
one other format a reader can ask for, and it is selected explicitly. Repeat
`--format` for a deliberate subset. The command creates the profile view
manifest but does not complete its `views/<profile_id>` stage. Authoring later
hashes the view manifest and `document.json` together.
