# Short-Video Script Profile

Use `short-video-script` for a concise, source-faithful script intended for
short-form video production. The script is spoken copy, not a summary that
someone will read aloud — write the way a person talks.

## Sections

Author these sections in this order. The `kind` values are authoring metadata
and must not appear as visible headings.

1. `hook` — the opening attention and promise.
2. `context` — the minimum setup needed to understand the subject.
3. `core_point` — the source-backed central idea.
4. `evidence` — concrete demonstrations, examples, or quotations.
5. `payoff` — the useful implication or takeaway.
6. `closing` — a concise ending that completes the script.

Keep visible copy focused on the script. Do not add source navigation
boilerplate, audit timestamps, or renderer instructions; the profile sets
`source_navigation: false`, so the rendered deliverable carries no source-time
footnotes even though the document keeps every `source_spans`.

## Spoken, Not Written

These rules are enforced by the quality gate, not left to taste:

- **The hook starts mid-conversation.** `大家好` / `今天我们来讲` / `本期视频`
  openers are rejected: a viewer scrolled in halfway, and an announcement
  spends the only seconds that could have stopped them.
- **The closing ends on the thought.** Lesson endings (`希望对你有所帮助`,
  `最后想说的是`, `共勉`) are rejected. Landing on a moral is what makes a
  script sound like an advertisement.
- **Written connectives are rejected.** `因此` / `综上所述` / `总而言之` /
  `由此可见` belong to prose. Say the relation instead of labelling it.
- **Concrete beats abstract.** The gate already rejects text that is mostly
  abstract phrasing; keep a number, a scene, an object, or a named step in
  every section.

A good check before projection: read the finished script aloud. Anything that
sounds like copy rather than speech gets rewritten as speech.
