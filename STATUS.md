# STATUS — read first

_Last updated: 2026-10-21 01:10 PDT_

## Blocked / waiting on Jack
- Nothing blocking right now. Golden-50 labelling waits for you: `evals/golden_50_labels.csv` (blank) + `evals/golden_50_DEFINITIONS.md`.
- Optional backup: `vercel login` (the Vercel connector is signed in; the CLI is not).

## Scope (declared)
**Declared 173,000-review subset — not a full-corpus model run.** All 660,622 rows are ingested, hashed and accounted for:
173,000 in the subset, 13 `empty_review_text` quarantines, 487,609 `not_in_model_scope` (sampled out).
Subset = analysis_10000 (contains checkpoint_500 and cost_100) + golden 50 + 162,950 seeded-random nonempty reviews
(seed `spotify-reviews-final-subset-v1`; the 100,000 core is kept). Subset CSV sha256 `f782fb31…a0f19b`; 132,832 distinct texts.
Sizing: largest N whose conservative enrichment projection fits $4.00 → N=173,000 ($3.988); see `config/run_decisions.json`.

## Done
- Pre-flight; decisions in `config/run_decisions.json` (Haiku 5.5, effort low, thinking off, Batch API, prompt caching, no fallback, verifier 500, **$5.00 hard cap**).
- Prices saved 2026-10-20 in `cost/rates.csv`.
- Stage 1: all brief counts match (660,622 / 13 empty / 159,701 missing app_version / 0 dup IDs / 484,189 distinct texts).
- 100-review pilot, final attempt 4: cold 100/100 completed, $0.004857 all stages, wall 619 s enrich (batch queue) + 195 s verify + 13 s group/memo; warm: 0 calls, $0. Doubling-rates test passes. History of attempts 1–3 and one disclosed stale warm run: `cost/README.md`.
- Supabase project `spotify-reviews-final` (created by Jack), schema + RLS applied; `DATABASE_URL` works.

## Running / next
- **Running:** 173,000-subset enrichment (waves of 300 requests) with the kill-and-resume demo (kill during wave 3).
- **Deviation (disclosed):** the demo was planned for the 10,000 stage, but `--requests-per-wave` was bound at import time, so that stage finished in 2 waves before the kill point. Fixed; demo moved to the subset stage. Log of the uninterrupted 10k run: `evals/resume/terminal_10000_no_interrupt.log`.
- Next: verify, group, rank, memo → export + checker → DB load → dashboard deploy → README.

## Milestones
- 500: 500/500 completed, $0.008424, 440 s (commit 4a18dc4)
- 10,000: 10,000/10,000 completed (8,448 model-classified distinct texts + 1,552 cache reuse), +$0.137, 940 s (commit 61bb629)
- Projection refreshes: `cost/refresh.md` (after 10k: subset base $2.30, conservative $3.44 — fits)

## Quote fallback (code-filled evidence_quote)
| Run | short reviews: whole text | model exact quote | code span repair | code head fallback |
|---|---|---|---|---|
| Pilot (final) | 91 | 8 | 0 | 1 (gibberish review) |
| Main run, after 10k | 8,944 | 1,025 | 18 | 13 |

## Counts / spend
| | |
|---|---|
| Completed (main run) | 10,000 of 173,000 |
| Quarantined | 13 (empty text) |
| Spend vs cap | $0.163183 / $5.00 (all stages incl. pilot) |
