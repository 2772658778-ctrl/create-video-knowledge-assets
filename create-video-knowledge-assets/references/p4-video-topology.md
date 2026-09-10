# P4 Video Topology

Use topology only for completed `course-notes` assets. Build it with:

```text
vka build-qa-topology --asset <asset> --profile course-notes
```

The topology is a reference-only map of eligible video-backed atomic knowledge facets, the capabilities those facets can support in an answer, their canonical evidence references, source spans, directly inspected frame references, and relation IDs. It does not contain transcript, knowledge-unit, course-note prose, or a tutorial taxonomy. Relations provide context only and never authorize a claim on their own. Rebuild it after canonical evidence or knowledge changes; do not edit the generated topology by hand.

Retrieval selects a bounded topology subset for the question. Treat selected facets and their relation IDs as scope, not as answer text.
