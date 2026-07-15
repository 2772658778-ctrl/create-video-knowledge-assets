# P2 U1 Input, Recovery, And L2 Workflow

Use this route before source acquisition or authoring. It governs a Bilibili
input and a local video input; the evidence and profile contracts remain in
their dedicated references.

## Input And Profile

- Accept one input: a public Bilibili URL or a local video path supplied by
  the user.
- Normalize a Bilibili URL before using it. Reject unsupported hosts and ask
  the user to provide a public canonical URL.
- Describe a local video before using it. Its computed identity is the source
  of truth for later recovery.
- Use `general-deep` unless the user explicitly asks for `course-notes`.
  Read `profile-general-deep.md` for the default profile and
  `profile-course-notes.md` for the explicit teaching profile.

## Minimal Commands

Run these commands with placeholders only after the user has supplied the
input. They inspect or prepare an input; they do not authorize a full render.

```powershell
vka preflight --commands ffmpeg ffprobe
vka normalize-bilibili-url --url "$PUBLIC_URL"
vka describe-local-video --input "$LOCAL_VIDEO"
vka cleanup-l2 --asset "$ASSET_DIR" --dry-run
```

Use only the URL command for a Bilibili input and only the local-video command
for a local input. Add `yt-dlp`, `whisper`, or `xelatex` to preflight only when
the selected work actually requires it. Read `acquisition-recipes.md` before
downloading subtitles, cover images, audio, video, or candidate frames. Its
direct commands write acquisition artifacts into the existing asset structure;
they do not replace input identity, evidence validation, or stage manifests.

## Stop, Degrade, And Recovery

- Stop and ask the user when the input is unreadable, the local path is not
  available, the URL is not public or cannot be normalized, a multipart source
  has no selected part, or required evidence cannot be grounded.
- Degrade only under the evidence and document rules in `p1-workflow.md`.
  Record the limitation, omit unsupported claims, and never convert a degraded
  result into an unqualified fact.
- Recovery starts from the recorded input identity and the verified stage
  manifests. Re-run validation for every stage whose output is missing or
  whose hash does not match; do not trust a filename alone.
- Use L2 only for derived, discardable working data. Run `cleanup-l2 --dry-run`
  before an L2 removal and obtain an explicit decision before `--apply`.

## Outputs And Human Review

Record the selected profile, canonical input identity, validated evidence,
stage results, and requested reader-facing outputs in the asset directory.
For `general-deep`, retain the outline and reader-facing explanation. For
`course-notes`, also retain the validated teaching outline, document contract,
and rendered outputs required by the P1 gates.

Before acceptance, a human review must confirm the intended input and profile,
the claimed limitations, evidence grounding, profile-specific quality, and the
L2 dryrun scope. Do not treat a successful command exit as a substitute for
human review.
