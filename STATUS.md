# STATUS — read first

_Last updated: 2026-10-21 03:20 PDT. Overnight run finished; nothing is running._

## Waiting on Jack (blocking items first)
1. **Label the golden 50** in `evals/golden_50_labels.csv` (blank columns; definitions in `evals/golden_50_DEFINITIONS.md`).
   Then run `python -m pipeline eval golden` and add the results to the README "Results summary" (currently says pending).
2. **Repo history has two 83 MB files** (`outputs/records.jsonl`, `outputs/enriched.jsonl`) from commit 45f8cd2. They hold no
   secrets (labels, IDs, quotes from the CC0 dataset) and are no longer tracked; gzipped copies are. Removing them from
   history needs a rewrite and force-push of the public repo, so I left it for you. `.git` is 154 MB. Your call.
3. **Drive link for the raw CSV:** CLAUDE.md asks the README to link the Drive source. I don't have it; the README links
   the Kaggle source and records the SHA-256. Paste the Drive link if you want it added.
4. **40 quarantined subset reviews** (30 output-token cap, 10 refusals) are the checker's only flag
   (`unfinished_classification`). That follows the "retry once → quarantine" rule. Option: a disclosed recovery pass,
   such as salvaging complete items from the saved truncated responses (no new calls) or single-review requests (about
   $0.001). Not done without your OK.
5. **Rubric map:** the brief's itemised criteria aren't in the repo, so the README maps evidence to the 4/3/3 areas. Check
   it against the brief.
6. Optional: rotate nothing. No secret was printed, logged or committed (staged diffs scanned before every push;
   `.env` ignored).

## Scope (declared)
**Declared 173,000-review subset — not a full-corpus model run.** All 660,622 rows are accounted for: 172,960 completed,
40 quarantined in the subset, 13 `empty_review_text`, 487,609 `not_in_model_scope`. Sizing rule: the largest N whose
conservative enrichment projection fits $4.00 → 173,000 (`config/run_decisions.json`).

## Done (all pushed to main)
| Milestone | Commit | Result |
|---|---|---|
| 1 Ingest + calculator + 100 pilot | c6cfb11 | brief counts match; final pilot: 100/100 cold, warm 0 calls |
| 2 500 run + refresh | 4a18dc4 | 500/500, $0.008424 |
| 3 10,000 run + refresh | 61bb629 | 10,000/10,000, +$0.137564 |
| 4 Full subset + resume demo | 06ec5ea | 172,960 completed; kill mid-batch, resume, 0 completed IDs resent |
| 5 Verify/group/rank/memo/export/checker | 45f8cd2 (+0749fcc gz) | verifier 0.900/0.942/0.888; planted 40/40; injection 6/6; checker: only the 40 quarantines |
| 6 DB + dashboard + README | (this commit) | Supabase loaded, RLS anon read-only; https://spotify-reviews-final-energy-43a6.vercel.app (public); dashboard ranking = ranking.csv (35/35) |

## Deviations (all disclosed in README / run_decisions.json)
- Resume demo ran in the subset stage, not the 10,000 stage (wave-size bug; fixed).
- Memo call runs at effort medium with adaptive thinking; enrichment and verify stay at low with thinking off. Two
  low-effort drafts were rejected for wrong comparisons; comparisons are now code-computed and checked verbatim. The
  accepted memo was blocked at generation only by a checker bug (missing backticks), then re-checked offline with 0
  problems and annotated in `calls.jsonl`.
- Pilot took 4 attempts (quote-quality fixes) plus one invalid stale warm run, all kept in `cost/`.
- Issue map refined once (v2) after reading unmatched samples, before ranking and the memo.

## Quote fallback (code-filled evidence_quote), final
| whole short text (≤200 chars) | model exact quote | code span repair | code head fallback |
|---|---|---|---|
| 154,700 | 17,604 | 467 | 189 |

## Spend vs cap
**$2.42537 / $5.00** (all stages incl. pilots and tests). Main-run enrichment $2.374592; verify $0.006182; naming $0.002253;
memo $0.025011 (10 calls across drafts). Enrichment wall clock ≈ 6,550 s (500 → 10k → subset incl. kill/restart).
