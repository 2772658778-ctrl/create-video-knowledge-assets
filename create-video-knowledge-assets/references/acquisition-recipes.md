# Multimedia Acquisition Recipes

Use these recipes after input normalization and before evidence authoring. Keep
the current architecture boundary: acquisition writes raw or reproducible media
under `source/`; normalization, inspected-frame promotion, and grounding write
formal records under `evidence/`.

## Command Boundary

Set the CLI path once. In installed environments, replace `python $VKA` with
the equivalent `vka` command.

```powershell
$SKILL_DIR = Resolve-Path "<create-video-knowledge-assets-directory>"
$VKA = Join-Path $SKILL_DIR "scripts/vka_cli.py"
$ASSET = Resolve-Path "<asset-directory>"
```

Do not run acquisition before the asset identity and selected Bilibili part are
known. Use only a public canonical URL or a local path explicitly supplied by
the user.

## Preflight And Canonical URL

```powershell
python $VKA preflight --commands yt-dlp ffmpeg ffprobe
$source = python $VKA normalize-bilibili-url --url "$PUBLIC_URL" | ConvertFrom-Json
$URL = $source.canonical_url
python $VKA acquire-metadata --url "$URL" --output "$ASSET/source/metadata.json"
```

Stop when metadata reports multiple parts and the user has not selected one.
Do not guess a part or silently process an entire multipart collection.

## Reliable CC Subtitles

Prefer platform subtitles and preserve the original SRT.

```powershell
python $VKA acquire-subs `
  --url "$URL" `
  --output-template "$ASSET/source/subtitles/%(id)s.%(ext)s"

python $VKA normalize-srt `
  --input "$SRT" `
  --output "$ASSET/evidence/timeline.raw.jsonl" `
  --acquisition cc
```

When review finds no repair is necessary, retain identical content as
`evidence/timeline.jsonl`. When repair is necessary, use the transcript-repair
workflow rather than editing normalized evidence in place.

## ASR Fallback

For Bilibili, extract audio into the asset before transcription:

```powershell
yt-dlp -x --audio-format wav `
  -o "$ASSET/source/asr/audio.%(ext)s" `
  "$URL"

ffmpeg -y -i "$ASSET/source/asr/audio.wav" -vn -ac 1 -ar 16000 `
  "$ASSET/source/asr/audio.16k.wav"

python $VKA transcribe-asr `
  --audio "$ASSET/source/asr/audio.16k.wav" `
  --output "$ASSET/source/asr/audio-faster-base.srt" `
  --model base --device cpu --compute-type int8 --language zh `
  --download-root "$REPO/.cache/hf/faster-whisper"
```

`faster-whisper base` on CPU is the ASR of record for this pipeline: it fits a
CPU-only machine, and its SRT is still a raw artifact that must go through the
repair workflow. The OpenAI `whisper` CLI (`--model medium`) remains an option
only when a GPU or a very long CPU budget is available; record which backend
produced the SRT in the manifest `config.selected_asr` either way.

For a local video, use the supplied file without copying it unless L1 retention
was explicitly requested:

```powershell
ffmpeg -y -i "$LOCAL_VIDEO" -vn -ac 1 -ar 16000 "$ASSET/source/asr/audio.wav"
```

Normalize the SRT into the raw timeline with a raw id prefix, then repair:

```powershell
python $VKA normalize-srt `
  --input "$ASSET/source/asr/audio-faster-base.srt" `
  --output "$ASSET/evidence/timeline.raw.jsonl" `
  --acquisition asr --id-prefix raw-

python $VKA build-repair-prompt `
  --timeline "$ASSET/evidence/timeline.raw.jsonl" `
  --output "$ASSET/evidence/asr-repair-prompt.md" `
  --title "$VIDEO_TITLE"

python $VKA apply-transcript-repairs `
  --timeline "$ASSET/evidence/timeline.raw.jsonl" `
  --repairs "$ASSET/evidence/asr-repairs.json" `
  --parent-prefix raw- `
  --output "$ASSET/evidence/timeline.jsonl"

python $VKA timeline-digest `
  --timeline "$ASSET/evidence/timeline.jsonl" `
  --output "$ASSET/logs/timeline-digest.md"
```

Use visual-only acquisition only as a last resort for inherently visual
material. Stop when frames cannot ground the speaker's reasoning or the main
requested claims.

## Cover And Video For Figures

Keep the cover and downloaded video in `source/`; never register an uninspected
downloaded frame as formal evidence.

```powershell
yt-dlp --skip-download --write-thumbnail --convert-thumbnails jpg `
  -o "$ASSET/source/cover/%(id)s.%(ext)s" `
  "$URL"

yt-dlp -f "bv*+ba/b" --merge-output-format mp4 `
  -o "$ASSET/source/video/%(id)s.%(ext)s" `
  "$URL"
```

Probe available formats first when the best format is not downloadable. Prefer
the highest usable source, not a nominal resolution that requires unavailable
authorization.

## Dense Candidate Frames

Use transcript windows to choose a bounded interval, oversample candidates, and
inspect them directly before selection.

```powershell
python $VKA plan-frames --start-ms 740000 --end-ms 770000 --interval-ms 2000

ffmpeg -y -ss 00:12:20 -i "$VIDEO" -t 30 `
  -vf "fps=1/2" `
  "$ASSET/evidence/frames/candidates/frame-%06d.jpg"

ffmpeg -y -ss 00:12:31.000 -i "$VIDEO" -frames:v 1 `
  "$ASSET/evidence/frames/candidates/frame-000751000.jpg"
```

Use image inspection to select the fully revealed readable state. Promote only
reviewed frames into formal evidence, preserve their exact source spans and
artifact paths, and mark review state as `directly_inspected`.

## Cookie And Retention Rules

- Prefer public acquisition without Cookie data.
- Use `--cookie-file` or yt-dlp `--cookies <file>` only after explicit user
  authorization. Do not use `--cookies-from-browser` in the default workflow.
- Never copy Cookie contents into prompts, manifests, logs, acceptance records,
  demo assets, or version control.
- Keep downloaded remote video and ASR audio as discardable working data unless
  the user explicitly requests retention. Run `cleanup-l2 --dry-run` before
  removal.
- Do not mark a source or evidence stage complete until its declared outputs are
  present, schema-valid where applicable, and bound into the asset manifest by
  the current U1 workflow.
