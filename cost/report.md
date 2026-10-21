# 100-review cost & runtime calculator — report

Generated offline by `python -m pipeline cost --replay` from `pilot_calls.jsonl` × `rates.csv` (no API key, no model calls). Measured and estimated figures are kept in separate sections.

## Measured: 100-review pilot (`data/cost_100.csv`, sha256 c884ac3b…dd0e)

| Stage | Cold wall s | Cold new calls | Warm wall s | Warm new calls |
|---|---|---|---|---|
| enrich | 619.476 | 3 | 0.005 | 0 |
| verify | 195.129 | 1 | 0.003 | 0 |
| group | 5.508 | 1 | 0.004 | 0 |
| rank | 0.0 | — | 0.001 | — |
| memo | 7.312 | 1 | 0.002 | 0 |

End-to-end wall clock (sum of sequential stage clocks): cold **827.4 s**, warm **0.0 s**. Batch-API queue time dominates enrichment/verification wall clock.

Enrichment status (cold): {'completed': 100}; label_config `claude-haiku-5-5+enrich_v1.044e2ae6+schema_v1+effort-low+thinking-off+short200+qrepair1+lengthgroups`.

### API spend by stage (USD, from usage × rates)

| Mode | enrich | verify | group | memo | Subtotal |
|---|---|---|---|---|---|
| cold | 0.002052 | 0.000616 | 0.000903 | 0.001286 | **0.004857** |
| warm | 0 | 0 | 0 | 0 | **0.0** |
| warm_stale_invalid | 0 | 0 | 0.000919 | 0.001368 | **0.002287** |

Cold cost per 1,000 input rows: $0.0486; per completed record: $4.9e-05.
Requests/attempts (cold enrichment): 3 requests, 0 failed, retry fraction 0.000. Mean billed tokens per review: input 43.4, output 61.2; cached instruction prefix 2774 tokens (cache-read share 0.67).
Provider prompt-cache savings are only what `cache_read_input_tokens` shows; the result cache is separate.

## Estimated: projections (not measurements)

Controls (editable in `cost/assumptions.json`): spend limit $5.0, output-token cap 70/review, max workers 1, fallback fraction 0.0, 50 reviews/request, verification sample 500.

| Scenario | Case | Distinct texts | Requests | Enrich $ | Verify $ | Group+memo $ | **Total API $** | Est. wall s | Over cap? |
|---|---|---|---|---|---|---|---|---|---|
| declared 173,000-review subset (planned run) | base | 132,832 | 2,657 | 2.357494 | 0.006162 | 0.002189 | **2.365845** | 4,336 | no |
| declared 173,000-review subset (planned run) | conservative | 132,832 | 3,322 | 3.98762 | 0.00647 | 0.002189 | **3.99628** | 16,726 | no |
| 100,000 core of the subset | base | 78,309 | 1,567 | 1.389832 | 0.006162 | 0.002189 | **1.398183** | 2,478 | no |
| 100,000 core of the subset | conservative | 78,309 | 1,959 | 2.350921 | 0.00647 | 0.002189 | **2.35958** | 9,292 | no |
| full corpus (estimate only, not executed) | base | 484,189 | 9,684 | 8.593341 | 0.006162 | 0.002189 | **8.601692** | 15,487 | **YES — exceeds cap** |
| full corpus (estimate only, not executed) | conservative | 484,189 | 12,105 | 14.53477 | 0.00647 | 0.002189 | **14.54343** | 57,611 | **YES — exceeds cap** |

No-reuse comparison: the full-corpus rows above use 484,189 distinct texts; without exact-text reuse the work is 660,609 classifications (×1.364). Subset without reuse: 100,000 vs 78,309 (×1.277).
Formulas: item_cost = billed_units × usd_per_mtok / 1e6 per mutually exclusive item (input, cache_write_5m, cache_write_1h, cache_read, output); conservative = higher retries, ×1.5 output, 50% prefix cache misses, ×3 batch wait. Group and memo are fixed one-time overhead, added once. Local compute: not measured; local CPU/SQLite work only, no GPU; shown separately and excluded from API spend.

## Rates used

| Model | Tier | Item | $/MTok | Source | Checked |
|---|---|---|---|---|---|
| claude-haiku-5-5 | standard | input | 0.10 | https://platform.claude.com/docs/en/about-claude/pricing#model-pricing | 2026-10-20 |
| claude-haiku-5-5 | standard | cache_write_5m | 0.125 | https://platform.claude.com/docs/en/about-claude/pricing#model-pricing | 2026-10-20 |
| claude-haiku-5-5 | standard | cache_write_1h | 0.20 | https://platform.claude.com/docs/en/about-claude/pricing#model-pricing | 2026-10-20 |
| claude-haiku-5-5 | standard | cache_read | 0.01 | https://platform.claude.com/docs/en/about-claude/pricing#model-pricing | 2026-10-20 |
| claude-haiku-5-5 | standard | output | 0.50 | https://platform.claude.com/docs/en/about-claude/pricing#model-pricing | 2026-10-20 |
| claude-haiku-5-5 | batch | input | 0.05 | https://platform.claude.com/docs/en/about-claude/pricing#batch-processing | 2026-10-20 |
| claude-haiku-5-5 | batch | cache_write_5m | 0.0625 | https://platform.claude.com/docs/en/about-claude/pricing#prompt-caching (multipliers stack with batch 50% discount) | 2026-10-20 |
| claude-haiku-5-5 | batch | cache_write_1h | 0.10 | https://platform.claude.com/docs/en/about-claude/pricing#prompt-caching (multipliers stack with batch 50% discount) | 2026-10-20 |
| claude-haiku-5-5 | batch | cache_read | 0.005 | https://platform.claude.com/docs/en/about-claude/pricing#prompt-caching (multipliers stack with batch 50% discount) | 2026-10-20 |
| claude-haiku-5-5 | batch | output | 0.25 | https://platform.claude.com/docs/en/about-claude/pricing#batch-processing | 2026-10-20 |
