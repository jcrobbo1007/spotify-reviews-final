# Verifier disagreements — hand-read write-up

**Setup.** The blind verifier (`prompts/verify_v1.md`, same model `claude-haiku-5-5`, effort low, separate prompt, no
worked examples, never shown stage-2 output) re-labelled a seeded random sample of **500** originals
(seed `spotify-reviews-final-verify-v1`, one per distinct text). Code compared the two
(`verify_summary.json`, `verify_disagreements.csv`).

| Metric (n = 500) | Value |
|---|---|
| Topic agreement | 0.900 |
| Intent agreement | 0.942 |
| Severity exact agreement | 0.888 |
| Severity MAE | 0.114 |
| Sentiment MAE | 0.0768 |
| Records with any disagreement on topic/intent/severity | 109 |

Disagreement fields: topic only 41, severity only 32, intent+severity 17, intent only 10, topic+severity 7, topic+intent 2.

Agreement between two passes of the same model family is **not accuracy**: shared blind spots agree. Jack's golden-50
labels are the human check; they are pending.

## 16 disagreements, read by hand against the shared rubric

I judged each one by the GRADING_CONTRACT definitions. E = enrichment label, V = verifier label.

| # | Review (abridged) | E | V | Who is right, and why |
|---|---|---|---|---|
| 1 | "It was good until THEY REMOVED SHUFFLE! … ruined the whole app" (`7dfbc802`) | usability/complaint/3 | usability/complaint/2 | **E.** A removed control is a restricted function (3), not just dislike. |
| 2 | "can't see the album pics and I can't play short peek … don't tell me it needs premium" (`774450cc`) | billing/3 | usability/3 | **E.** Explicitly premium-only controls are `billing` by rule. |
| 3 | "Life🫀" (`acab7700`) | other/praise/1 | other/unclear/1 | **V.** No product content → `unclear`. |
| 4 | "problems … go back to an already skipped song … move forward on the song bar" (`929a1adf`) | playback/2 | playback/3 | **V** on severity: a restricted seek function is 3. Topic arguably `usability` (controls) for both. |
| 5 | "Boring update … Forward & Backward … purchase premium" (`9abdd385`) | billing/2 | billing/3 | **V.** Premium-gated controls = restricted function (3). |
| 6 | "might delete this app … I can't even play the song I want to anymore" (`698a056a`) | usability/cancellation/4 | usability/cancellation/3 | **V.** Music still plays; song choice is restricted (3), not blocked (4). Cancellation must not raise severity. |
| 7 | "There's never been a better music/podcast provider" (`d797ae88`) | catalog/praise | other/praise | **V.** General praise → `other`. |
| 8 | "fantastic but … Does this app work when you are offline" (`4862acac`) | downloads/unclear | downloads/request | **Ambiguous.** A question, not a desired change; `unclear` is defensible, `request` is a stretch. |
| 9 | "collection … very good except the advertisement which are turn on too loud" (`c6148f24`) | catalog/complaint | usability/complaint | **V.** The only problem is ads → `usability`. |
| 10 | "Stupid decision … No freedom on listening music" (`ccb1fd14`) | other/complaint | usability/complaint | **E.** No specific defect is supported; rule says do not infer one. |
| 11 | "People who don't have premium can't queue songs … can't go back" (`efc4bc12`) | billing/3 | usability/3 | **E.** Premium-only controls → `billing`. |
| 12 | "Good choices reconmend to anyone" (`b798e4c0`) | catalog/praise | other/praise | **V (lean).** Reads as general praise of the app; "good choices" could be catalog. |
| 13 | "adds are coming frequently … please enable … favourite part … without the premium" (`d803c9fe`) | billing/complaint/3 | billing/request/2 | **E.** Frequent ads is a reported negative experience → complaint; paywalled seek (3) outranks ads (2). |
| 14 | "Why does the swipe to add to queue feature keeps going away on Android?" (`121594ff`) | usability/request/2 | usability/complaint/2 | **V.** A feature disappearing is a reported failure → complaint. |
| 15 | "The best music app is now bad because all features are changed to premium" (`f2a275ce`) | billing/3 | billing/2 | **E (lean).** Paywalled features = restricted function. |
| 16 | "Very impressed to listen musics" (`a57edeb7`) | other/praise | playback/praise | **E.** No specific praised feature → `other`. |

**Tally:** enrichment better in 7 (1, 2, 10, 11, 13, 15, 16), verifier better in 8 (3, 4, 5, 6, 7, 9, 12, 14), 1 ambiguous (8).

## Patterns
- **Enrichment over-assigns `catalog` to general praise** (7, 12) and sometimes misses ad complaints hidden after praise (9).
  Impact on ranking: small. Praise is excluded from the baseline, and case 9 moves one record between issues.
- **The verifier misses the "premium-only controls → billing" rule** (2, 11). Enrichment applies it consistently because its
  prompt carries worked examples for it. That is a prompt-coverage difference, not a model difference.
- **Severity 2 vs 3 for premium-gated controls is the most common disagreement** (1, 4, 5, 15), and the two passes err in
  both directions. The shared rubric's line between "dislike" (2) and "restricted function" (3) is hard to apply to
  paywall complaints. `billing.premium_paywall` and `usability.shuffle_queue` means (2.92, 2.63) should be read with that
  ±1 uncertainty.
- **Cancellation is not raising severity** in the enrichment labels except case 6, where the verifier is right.
