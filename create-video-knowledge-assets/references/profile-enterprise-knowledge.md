# Enterprise Knowledge Profile

Use `enterprise-knowledge` for a source-backed internal knowledge view. It
projects only the canonical knowledge layer into
`views/enterprise-knowledge/document.json`; the renderer is presentation-only.

## Source Boundary

Read `knowledge/units.jsonl`, `knowledge/relations.jsonl`,
`knowledge/synthesis.json`, and the evidence records referenced by those
units. Operational prose must retain video evidence and `source_spans`. Do not
supplement the view with a meeting decision, owner, deadline, or action item
that the video did not express.

The document must contain these semantic sections:

1. `purpose_scope`: purpose, scope, and applicability.
2. `terminology`: terms used consistently by the view.
3. `process_practice`: the source-backed process or practice.
4. `roles_inputs_outputs`: explicit roles, inputs, and outputs.
5. `risks`: risks or failure modes supported by the source.
6. `limitations_sources`: uncertainty, limits, and source navigation.

Before drafting, follow `p3-profile-authoring.md`. Keep the view operational:
make the applicability and preconditions explicit, turn a source-supported
process, input/output boundary, or risk register into a compact table where it
improves scanability, and place a directly inspected process or interface frame
next to the step it verifies when such a frame exists. The figure is evidence,
not decoration. A missing role, owner, deadline, or acceptance criterion is an
open question, not a field to invent.

When a potential decision, owner, due date, or action cannot be traced to the
video, mark that same content block and sentence as insufficient evidence or an
open question. Never let an unrelated limitations note waive a commitment.
This profile records operational knowledge; it does not create an
implementation plan.
