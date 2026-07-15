# P4 Answer Presentation

Use the selected mode deliberately:

- `video_only`: video claims, video inferences, and video limitations only.
- `video_plus_context`: the video answer plus separate non-video **background** blocks backed by `external:` evidence.
- `explore`: the same separation, with at least one non-video block visibly labelled as broader **comparison** or **research**.

Author and validate in this order: retrieve video grounding, plan the video answer, author video claims, add separately cited external claims only for a context mode, then run `validate-answer`.

Keep the presentation visibly partitioned: video-grounded answer; video inference and limitations; non-video background with external citations; then version differences or source conflicts when externally evidenced. The delivered `answer` is the exact rendering of those ordered sections, including every external block, conflict, limitation, and model-background extension. Never put external IDs in video claims. When an external source differs from the video, bind the conflict to its video claim IDs and external refs, then describe what the video did, the external version or conditions, and the disagreement; do not silently select one.
