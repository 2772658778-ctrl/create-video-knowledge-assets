# Reader Delivery Contract

Why the delivered document looks the way it does, and the traps that already
cost us iterations. Read this before changing any renderer, and before judging
a rendered document. It applies to every reader-facing profile, in both
delivered formats.

## What A Reader Should Feel

One column, serif body, sans headings, generous leading — the reading
experience of a long-form article, not of a report. Two documents per view: the
reader document carries only the video's content; scope, uncertainty, and
source navigation live in the boundary document. Each ships as a PDF and as a
standalone HTML file; the HTML is the same document without page breaks, so it
shows what the prose really looks like and the PDF is the paginated counterpart.

## Type Scale

Body is serif, headings are sans, and no two adjacent levels sit within 10%
of each other. A caption is two steps below the body and never competes with it.

| Element | Face | LaTeX | HTML |
| --- | --- | --- | --- |
| Cover title | sans bold | 24 / 32pt | 2.05rem |
| Section title | sans bold | `\Large` | 1.5rem |
| Body | serif (SimSun) | 11 / 17.5pt | 19px / 1.85 |
| Caption | sans label + serif text | 9.5 / 13pt | 0.87rem |
| Source time | mono | 8.5 / 12pt | 0.83rem |
| Metadata | sans | 9 / 13.5pt | 0.87rem |

## One Accent Colour

Deep green (`#3B6B4F` in LaTeX, `#2F6B52` in HTML) marks where the reader is in
the document, and nothing else: the section number, the contents number, the
`图 N` caption label, and the `来源时间` heading. Two borrowed uses are
deliberate and stay: the cover theme line, and the rule on a knowledge box,
because each already means "this is the document's own frame, not its content".
Body text, captions, rules, and metadata are ink, grey, or a hairline. If a
sixth place wants colour, it does not get one — the accent works because a
reader sees it four or five times per document, not twenty.

The three teaching boxes are the one exception, and they are semantic rather
than decorative: blue is the core point, green is background knowledge, amber
is a common mistake. They appear only in course notes.

## Cover

Order: title → theme sentence → one-sentence summary → subtitle → cover image
(0.62 of the text width) → three metadata lines → contents. A title containing
a full-width colon breaks at the colon; a centred title otherwise breaks
wherever the measure runs out, which splits a word.

`short-video-script` is not an exception. A cover missing its theme and source
metadata reads as an unfinished file, so no profile may have its cover fields
dropped by a renderer.

## Figures

- One size for every figure in a document, with a hairline border and a caption
  whose measure equals the image width.
- A figure fills the text measure, capped so its height stays near a third of
  the page. That keeps a 16:9 frame about the same size in the PDF and in the
  HTML, where the same frame spans the column.
- A figure and its caption form one unbreakable box. As two paragraphs they can
  be split, and the caption then sits alone at the top of the next page.
- Every figure is a directly inspected frame. The renderer never crops,
  letterboxes, or substitutes a description; if a frame's own text is
  unreadable at delivery width, the asset step must choose a better frame.

## Contents And Source Times

- The contents opens the first content page. A contents page that is 80% empty
  reads as a missing file rather than as a section marker.
- Source times are numbered in the body and listed once at the end. They are
  never an entry in the contents.
- Adjacent windows (≤2s) merge into one citation and equal citations share a
  number, so the list stays a reference rather than a log.
- Source times list in two columns. A third column looks tempting for long
  lists, but a wrapped entry then runs across the column break.

## Traps We Already Paid For

| Symptom | Cause | Fix |
| --- | --- | --- |
| Contents page numbers describe the previous layout | Two compile passes, while the contents itself changes how much of the first page is left for prose | Compile three times |
| Caption alone at the top of the next page | Figure and caption emitted as two paragraphs | One unbreakable box |
| A table jumps whole to the next page | `tabularx` cannot break across pages | `longtable`, which ships in LaTeX's own tools bundle |
| A long citation runs into the next column | No breakpoint inside a monospace run | A breakable space after each separator |
| Near-empty contents page | Contents rendered on a page of its own | Contents opens the content page |
| Boundary PDF looks like a book | It reused the cover template | Compact heading, hairline rule, metadata, body |
| Citation number alone on a line | A breakable CJK boundary between the last character and the superscript box | Bind the last character and the marker in one unbreakable box |
| Near-empty last page | `\vfill` plus a footer line pushed the footer onto a fresh page | End the document with the endnote block; no trailing footer |
| The web view shows source times nothing points at | Citations numbered after the body was written | Number every citation before rendering the body |
| Emphasis invisible in the PDF | Colour applied in one renderer only | Apply the same four accent slots in both |
| `verify-asset` fails after an intentional re-render | Stage hashes still describe the old artifact | Re-run `complete-stage` for `views/<profile>` and `outputs/<profile>` |

## Page Density

A fixed-page medium cannot fill every page: a figure that does not fit in the
remaining space moves to the next page and leaves a gap behind it. Expect the
contents page and the last page to be the least full, and treat a 20–30% blank
tail as normal. Do not “fix” it with `\vfill`, with stretched leading, or by
letting figures drift away from the paragraph they illustrate.

When a reader wants continuous reading rather than pagination, the HTML render
of the same document is the right answer — it shows what the text looks like
without page breaks. It is a delivered format, not a review view: `package-demo`
copies the cover and every cited frame next to it, so the file opens on its own.
The two formats must not drift, and a rule that changes one renderer changes the
other in the same commit.
