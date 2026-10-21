# Golden 50 — labelling sheet (Jack fills `golden_50_labels.xlsx`, which has dropdowns, or the same rows in `golden_50_labels.csv`; all label columns start blank)

Nothing here was pre-filled, drafted or suggested by a model. The pipeline classifies these 50 texts as part of the
declared subset, but these human labels are never used as prompts, examples, thresholds or grouping inputs.

Columns to fill:
- `topic` — one of: access, usability, playback, downloads, catalog, billing, support, other
- `intent` — cancellation > complaint > request > praise > unclear (precedence)
- `severity` — integer 1–5
- `sentiment` — −1.0 to 1.0
- `entities` — `;`-separated feature terms explicitly named (blank if none)
- `evidence_quote` — exact substring of `review_text`
- `needs_review` — true/false
- `ambiguous` — true if more than one label is defensible
- `accepted_alternatives` — optional, e.g. `topic=billing|usability; severity=2|3`
- `notes` — free text

## Shared definitions (GRADING_CONTRACT.md)

| topic | Definition |
|---|---|
| access | Login, signup, password or account access |
| usability | Navigation, controls, layout, queue/playlist management, ad interruptions |
| playback | Playback failure, crashes, lag, connection failures, audio quality, resource use |
| downloads | Downloading, saved music, offline listening, disappearing downloads |
| catalog | Missing songs/artists, search/discovery, recommendations, lyrics availability |
| billing | Price, charges, subscriptions, paywalls, premium entitlement; explicitly premium-only controls go here |
| support | Contacting support and the support response |
| other | General praise/criticism, unrelated content, or no supported specific topic |

Choose the problem with the highest supported severity; on a tie, the first specific problem mentioned. For a positive
review, the first specific praised feature; general praise is `other`. A paid-plan mention alone is not `billing`;
a subscription failing to activate is; music crashing for a paying customer is `playback`.

Intent: `cancellation` (explicitly leaving, uninstalling, cancelling, or threatening to) → `complaint` (negative
experience, incl. mixed) → `request` (desired change, no reported failure) → `praise` → `unclear`. Bare boycott slogans
and unrelated/meaningless text are `unclear` unless there is a product complaint or explicit personal departure.
General "bad app" is a complaint; do not infer a specific defect.

| severity | Meaning |
|---|---|
| 1 | No reported problem: praise, neutral/unclear content, or a pure feature request |
| 2 | Dislike, generic criticism, minor annoyance, or cosmetic issue; no supported functional loss |
| 3 | A degraded or restricted function; some use or workaround remains |
| 4 | A clearly blocked core task, such as inability to log in or play music |
| 5 | Explicit serious financial, privacy, or data harm; an expensive plan, a crash, or angry language alone is insufficient |

Cancellation intent does not automatically raise severity. Missing context → `needs_review`; do not invent impact.

Run the comparison after labelling: `python -m pipeline eval golden` (reads the .xlsx if any row is filled there, otherwise the .csv)
