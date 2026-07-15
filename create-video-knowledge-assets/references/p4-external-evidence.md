# P4 External Evidence

P4.2 external context is local, explicit, and separate from the video's canonical evidence. Register only user-provided structured JSON or JSONL:

```powershell
vka register-external-evidence --asset <asset> --input <external.jsonl>
vka validate-external-evidence --asset <asset>
```

Records are written to `evidence/external.jsonl`. Each record needs an `external:` ID, source title and type, stable HTTP(S) URL without credentials, query, or fragment, acquisition time, optional publication date/version, and a quote or extracted content. Prefer official documentation, primary papers, and project repositories. Do not put Cookies, headers, sensitive URLs, manifests, or search queries in the record.

This workflow does not fetch the network. Model knowledge can suggest a search query or draft prose, but it is not evidence. Show model background only when the user explicitly asks, with its visible unverified label. The caller must retain that request in `model_background_request` with `request_source: "user_explicit"` and the request text; a Boolean payload flag is not authorization.

As a conservative artifact-safety rule, registration rejects source title/type, date/version, and extracted content that contain `cookie`, `header`, or `authorization` (case-insensitive), or a `manifest:`/`log:` label. It also rejects any HTTP(S) URL embedded in those fields when that URL has credentials, a query, or a fragment; ordinary prose and clean stable URLs remain valid. The `log` rule deliberately matches labels rather than ordinary prose using that word.
