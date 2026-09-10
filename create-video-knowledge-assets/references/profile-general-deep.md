# General-Deep Profile

Use this profile for a reader who wants a rigorous explanation of a video
without turning every source into course notes. The authoring plan is stored at
`knowledge/outline.json`; it is separate from the course-notes-only
`knowledge/teaching_outline.json` bridge.

`general-deep` remains the compatibility profile and the default route.
`deep-summary` is the explicit safe-default alias for the same source-faithful
artifact shape; selecting it does not change the section contract below.

## Required Outline

A valid general outline has:

- an `overview` section that states the central subject and scope;
- at least two `logical_body` sections that develop the source's actual
  reasoning, chronology, or practical flow;
- a `limitations` or `uncertainty` section that distinguishes unresolved,
  contested, conditional, or missing evidence from settled claims; and
- a `source_navigation` section that tells readers where the main claims,
  demonstrations, quotations, or disagreements came from.

Each section has a natural reader-facing title. The internal `kind` remains in
the outline only and must not be exposed as a visible heading.

## Source-Sensitive Shapes

Choose the shape that fits the source rather than mechanically applying a
course-summary template.

- An interview follows `观点—理由—分歧/边界` (point, reasons,
  disagreement/boundaries). Preserve who holds each view and make a genuine
  disagreement or qualification visible instead of forcing a lesson recap.
- A tutorial follows `问题—机制/步骤—例子—注意事项` (problem,
  mechanism/steps, example, cautions). Keep the order close to the task a
  reader would perform and state conditions that make a step fail or change.

The profile may use a different structure when the video requires it, but it
must still provide the required overview, two logical-body sections,
limitations or uncertainty, and source navigation.
