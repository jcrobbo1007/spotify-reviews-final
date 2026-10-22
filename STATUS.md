# STATUS — read first

_Last updated: 2026-10-21. Golden workbook rebuilt with your draft carried over; nothing is running._

## Waiting on Jack (blocking items first)
1. **Finish the golden 50 in `evals/golden_50_labels.xlsx`.** Your first draft (made in `data/golden_50_to_label.csv`,
   now saved as `evals/golden/jack_draft_freeform_labels.csv`) used free-form labels outside the contract sets (1/50 topics,
   0/50 severities valid). The workbook carries over your evidence_quote, entities and needs_review (green cells) and
   shows your draft topic/intent/severity/sentiment in locked grey columns. Pick topic, intent, severity and sentiment
   from the dropdowns (yellow), fix the one quote flagged "NOT an exact substring", save, then
   `python -m pipeline eval golden`. `data/golden_50_to_label.csv` was restored byte-exact to the course original.
2. ~~Repo history has two 83 MB files~~ **Done (your request):** history rewritten with `git filter-repo` and
   force-pushed. Removed from every commit: the plain `outputs/records.jsonl` / `outputs/enriched.jsonl`, their
   `outputs/*.jsonl.gz` copies, the plain `outputs/calls_raw_responses.jsonl`, and the superseded pre-recovery blob of
   `outputs/full_corpus_accounting.jsonl.gz`. The two record files are release assets
   ([data-v1](https://github.com/jcrobbo1007/spotify-reviews-final/releases/tag/data-v1)). Commit hashes after milestone 1
   changed; the table below uses the new ones. Backup bundle of the old history: kept locally outside the repo.
3. **Drive link for the raw CSV:** paste it at the `TODO(Jack)` line in the README "Dataset" section (the course ZIP
   link is already there).
4. ~~40 quarantined subset reviews~~ **Done (recovery pass, your request):** 30 salvaged from saved truncated responses
   (no new calls), 9 of 10 refusals completed with single-review requests. **1 remains quarantined** (refused again; text
   in look-alike Cherokee letters). It is the checker's only flag. Details: `evals/recovery/`, README "Recovery pass".
5. ~~Rubric map~~ **Done:** 10 rows, one per criterion, with evidence links; criterion 5 stays "Pending" until the golden
   50 are labelled. Coverage under the full-file checker is 0.4095 (README "Coverage under the course checker").
6. Optional: rotate nothing. No secret was printed, logged or committed (staged diffs scanned before every push;
   `.env` ignored).

## Scope (declared)
**Declared 173,000-review subset — not a full-corpus model run.** All 660,622 rows are accounted for: 172,999 completed,
1 quarantined in the subset, 13 `empty_review_text`, 487,609 `not_in_model_scope`. Sizing rule: the largest N whose
conservative enrichment projection fits $4.00 → 173,000 (`config/run_decisions.json`).

## Done (all pushed to main)
| Milestone | Commit | Result |
|---|---|---|
| 1 Ingest + calculator + 100 pilot | c6cfb11 | brief counts match; final pilot: 100/100 cold, warm 0 calls |
| 2 500 run + refresh | 797ecf5 | 500/500, $0.008424 |
| 3 10,000 run + refresh | 7a0e9b5 | 10,000/10,000, +$0.137564 |
| 4 Full subset + resume demo | fbba714 | 172,960 completed; kill mid-batch, resume, 0 completed IDs resent |
| 5 Verify/group/rank/memo/export/checker | b1c8526 | verifier 0.900/0.942/0.888; planted 40/40; injection 6/6; checker: only the 40 quarantines |
| 6 DB + dashboard + README | 36c8e11 | Supabase loaded, RLS anon read-only; https://spotify-reviews-final-energy-43a6.vercel.app (public); dashboard ranking = ranking.csv (35/35) |
| 7 Recovery pass + memo regenerated at effort high | bce05c3 | 172,999 completed, 1 quarantined; memo passed first try at high; DB reloaded; live API = ranking.csv |

## Deviations (all disclosed in README / run_decisions.json)
- Recovery pass on the 40 quarantines (your request) and one memo regeneration at effort high (your approval), after
  three medium-effort runs failed the checks on the post-recovery numbers.
- Resume demo ran in the subset stage, not the 10,000 stage (wave-size bug; fixed).
- Memo call runs at effort high (was medium overnight) with adaptive thinking; enrichment and verify stay at low with
  thinking off. Two low-effort drafts were rejected for wrong comparisons; comparisons are now code-computed and checked verbatim. The
  overnight memo was blocked at generation only by a checker bug (missing backticks), then re-checked offline with 0
  problems and annotated in `calls.jsonl`; it was superseded by the post-recovery memo.
- Pilot took 4 attempts (quote-quality fixes) plus one invalid stale warm run, all kept in `cost/`.
- Issue map refined once (v2) after reading unmatched samples, before ranking and the memo.

## Quote fallback (code-filled evidence_quote), final
| whole short text (≤200 chars) | model exact quote | code span repair | code head fallback |
|---|---|---|---|
| 154,730 | 17,613 | 467 | 189 |

## Spend vs cap
**$2.449436 / $5.00** (all stages incl. pilots, tests and the recovery pass). Enrichment $2.382955 (main run $2.375282
incl. recovery $0.00069); verify $0.008141; naming $0.005912; memo $0.052428 (19 attempts across pilot, drafts and
recovery). Enrichment wall clock ≈ 6,550 s plus a 497 s recovery batch.
