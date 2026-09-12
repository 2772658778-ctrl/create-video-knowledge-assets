# P3 Profile Projection Workflow

Use this workflow only after a completed asset has passed its canonical stages.
It projects supplied authored documents into reader views; it does not acquire
sources, infer new facts, or generate prose from canonical records.

## Verify And Route

1. Run `vka verify-asset --asset <asset>` before R3. Stop if source, evidence,
   or knowledge verification fails.
2. Read `profile-routing.md`, the selected profile reference, and
   `document-schema.md`. Use `vka select-profile` to record the selected
   profile, route reason, and requested formats.
3. Snapshot `canonical_hash_tree(asset)`. Its scope is exactly `source/`,
   `evidence/`, and `knowledge/`.

## Author And Project

1. Read `p3-profile-authoring.md` and `projection-plan.md`. Build, validate,
   and persist `views/<profile_id>/projection-plan.json` before accepting a
   supplied authored document. The document must be grounded in canonical
   knowledge and evidence records; do not invent facts, quotes, roles,
   decisions, external materials, or research findings. It must be a
   profile-specific explanation, procedure record, or evidence brief rather
   than a renamed general summary.
2. Call `reproject_profile_documents(asset, {profile_id: document})`. It
   validates canonical references and profile quality before writing a view.
3. R3 may write only `views/<profile_id>` and, after rendering,
   `outputs/<profile_id>`. It must never write to `source/`, `evidence/`, or
   `knowledge/`.
4. Compare the post-projection `canonical_hash_tree(asset)` with the snapshot.
   They must be identical. Record every selected profile and route reason.

## Render And Inspect

Render only the formats registered in the profile selection. Validate the
document before rendering, retain renderer paths in the profile output stage,
and compile a PDF whenever `pdf` is selected. Inspect every PDF page for
readability, source navigation, visual fit, overflow, and missing glyphs, then
open the HTML to confirm the same document reads correctly on screen. Publish a
shareable copy with
`vka package-demo --asset <asset> --profile <profile> --demo-root demos`; it
writes the PDF and HTML for both parts and copies the cover and the cited
inspected frames next to the document so the HTML opens without the asset.
Keep the acceptance record free of cookies, raw media, and private transcript
content.
