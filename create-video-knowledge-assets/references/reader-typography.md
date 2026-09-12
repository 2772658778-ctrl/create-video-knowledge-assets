# Reader Delivery Contract

What a delivered reader document should feel like, and the traps we already paid
for. Read this before changing a renderer and before judging a rendered page. It
applies to every reader-facing profile.

## What Ships

HTML is the delivered format. Each part is one self-contained file — the reader
document and the boundary document — with its cover and every figure inlined, so
a reader can open it by double-clicking or hand it to someone else and still see
everything. Nothing is installed and nothing else is copied next to it.

The two parts stay separate files. A reader who wants the video's content opens
one file; nobody scrolls past scope and uncertainty to reach the prose.

PDF is one request away, never a surprise. When the user asks for it, the same
document is compiled with XeLaTeX (`render-document --format tex`, then
`compile-pdf`), and that is the only path that needs an external toolchain. A run
that produced HTML should say so when it finishes, so the reader knows the option
exists.

## What A Reader Should Feel

One column, serif body, sans headings, generous leading, the reading experience
of a long-form article rather than of a report. The reader document carries only
the video's content; scope, uncertainty, and source navigation live in the
boundary document.

## Type Scale

Body is serif, headings are sans, and no two adjacent levels sit within 10% of
each other. A caption is two steps below the body and never competes with it.

| Element | Face | HTML | PDF |
| --- | --- | --- | --- |
| Cover title | sans bold | 2.05rem | 24 / 32pt |
| Section title | sans bold | 1.5rem | `\Large` |
| Body | serif | 19px / 1.85 | 11 / 17.5pt |
| Caption | sans label + serif text | 0.87rem | 9.5 / 13pt |
| Source time | mono | 0.83rem | 8.5 / 12pt |
| Metadata | sans | 0.87rem | 9 / 13.5pt |

## One Accent Colour

Deep green (`#2F6B52` in HTML, `#3B6B4F` in PDF) marks where the reader is in the
document, and nothing else: the section number, the contents number, the `图 N`
caption label, and the `来源时间` heading. Two borrowed uses are deliberate and
stay: the cover theme line, and the rule on a knowledge box, because each already
means "this is the document's own frame, not its content". Body text, captions,
rules, and metadata are ink, grey, or a hairline. If a sixth place wants colour,
it does not get one — the accent works because a reader sees it four or five
times per document, not twenty.

The three teaching boxes are the one exception, and they are semantic rather
than decorative: blue is the core point, green is background knowledge, amber is
a common mistake. They appear only in course notes.

## Cover

Order: title, theme sentence, one-sentence summary, subtitle, cover image, two or
three metadata lines, contents. The cover frame is 0.62 of the text measure in
both renders. A title containing a full-width colon breaks at the colon; a
centred title otherwise breaks wherever the measure runs out, which splits a
word.

`short-video-script` is not an exception. A cover missing its theme and source
metadata reads as an unfinished file, so no profile may have its cover fields
dropped by a renderer.

## Figures

- One size for every figure in a document, with a hairline border and a caption
  whose measure equals the image width.
- Every figure is a directly inspected frame, and its caption describes that
  frame. The renderer never crops, letterboxes, or substitutes a description; if
  a frame's own text is unreadable at delivery width, the asset step chooses a
  better frame. A caption that describes a neighbouring slide is a defect, not a
  wording problem.
- Adjacent windows (within 2 seconds) merge into one citation, and equal
  citations share a number, so the source list stays a reference rather than a
  log.
- Source times are numbered in the body and listed once at the end. They are
  never an entry in the contents.

## When The Two Renders Must Agree

A rule that changes one renderer changes the other in the same commit. The places
where they have drifted before:

| Thing | Rule |
| --- | --- |
| Accent colour | The same slots in both; colour applied in one renderer only is invisible in the other |
| Figure size | The frame fills the text measure in both |
| Cover frame | The same fraction of the text measure in both |
| Source-time list | Numbered from one shared pass, with the same explainer line above it |
| Citation markers | Numbered before the body is written, so no marker points at nothing |

## PDF, When It Is Requested

A fixed-page medium cannot fill every page: a figure that does not fit in the
remaining space moves to the next page and leaves a gap behind it. Expect the
contents page and the last page to be the least full, and treat a 20–30% blank
tail as normal. Do not "fix" it with `\vfill`, with stretched leading, or by
letting figures drift away from the paragraph they illustrate.

| Symptom | Cause | Fix |
| --- | --- | --- |
| Contents page numbers describe the previous layout | Two compile passes, while the contents itself changes how much of the first page is left for prose | Compile three times |
| Caption alone at the top of the next page | Figure and caption emitted as two paragraphs | One unbreakable box |
| Citation number alone on a line | A breakable CJK boundary between the last character and the superscript box | Bind the last character and the marker in one unbreakable box |
| A table jumps whole to the next page | `tabularx` cannot break across pages | `longtable`, which ships in LaTeX's own tools bundle |
| A long citation runs into the next column | No breakpoint inside a monospace run | A breakable space after each separator |
| Near-empty contents page | Contents rendered on a page of its own | Contents opens the content page |
| Boundary PDF looks like a book | It reused the cover template | Compact heading, hairline rule, metadata, body |
| Near-empty last page | `\vfill` plus a footer line pushed the footer onto a fresh page | End the document with the endnote block; no trailing footer |
