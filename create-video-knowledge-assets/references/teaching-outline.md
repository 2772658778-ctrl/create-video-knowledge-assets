# Teaching Outline Contract

Use `knowledge/teaching_outline.json` as the mandatory bridge between normalized
knowledge units and reader-facing course notes.

The outline is not a summary and not a rendering format. It is the teacher's
plan for how the reader will understand the video.

## Required Shape

```json
{
  "title": "Course title",
  "sections": [
    {
      "title": "Section title",
      "moves": [
        {
          "kind": "motivation",
          "text": "Why this idea appears and what problem it solves.",
          "evidence_refs": ["tw-001"]
        }
      ]
    }
  ]
}
```

Supported move kinds:

- `motivation`: why the section matters.
- `wrong_intuition`: a tempting but insufficient idea.
- `mechanism`: how the idea works.
- `worked_example`: a concrete example, calculation, code path, or analogy.
- `formula_or_visual`: the formula, frame, diagram, or visual state that anchors the explanation.
- `misconception`: what readers commonly confuse and how to avoid it.
- `takeaway`: what the reader should retain before moving on.
- `transition`: why the next section follows.
- `synthesis`: final integration across sections.
- `practice`: practice prompts or next steps.

## Quality Rules

For every non-final teaching section, include:

- `motivation` or `wrong_intuition`;
- `mechanism`;
- `worked_example` or `formula_or_visual`;
- `takeaway`.

The final section must include `synthesis`, `practice`, and `takeaway`.

Each move needs enough prose to guide a reader, not just restate a knowledge
unit. Every move must cite `evidence_refs`. The generated PDF should render
compact source-time footnotes from `source_spans`; Markdown/HTML can remain
clean while preserving provenance in JSON.

The first section should act as a golden prelude: make the core question,
stakes, or main thesis easy to grasp before detailed chronology or formulas.
Do this with subject-appropriate language and examples; do not hard-code a
technical-video pattern.

## Generation Rule

Generate `views/course-notes/document.json` from this teaching outline, not
directly from `knowledge/units.jsonl`. The document may reorganize, merge, or
expand normalized knowledge units into teacher-style prose as long as every
claim remains grounded through evidence references.
