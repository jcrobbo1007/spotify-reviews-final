# 100-review cost & runtime calculator — report

Generated offline by `python -m pipeline cost --replay` from `pilot_calls.jsonl` × `rates.csv` (no API key, no model calls). Measured and estimated figures are kept in separate sections.

## Measured: 100-review pilot (`data/cost_100.csv`, sha256 c884ac3b…dd0e)

| Stage | Cold wall s | Cold new calls | Warm wall s | Warm new calls |
|---|---|---|---|---|
| enrich | 437.976 | 2 | 0.005 | 0 |
| verify | 195.094 | 1 | 0.003 | 0 |
| group | 7.5 | 1 | 8.986 | 1 |
| rank | 0.001 | — | 0.001 | — |
| memo | 9.886 | 1 | 0.007 | 0 |

End-to-end wall clock (sum of sequential stage clocks): cold **650.5 s**, warm **9.0 s**. Batch-API queue time dominates enrichment/verification wall clock.

Enrichment status (cold): {'completed': 100}; label_config `claude-haiku-5-5+enrich_v1.1ab080f4+schema_v1+effort-low+thinking-off+short200+qrepair1`.

### API spend by stage (USD, from usage × rates)

| Mode | enrich | verify | group | memo | Subtotal |
|---|---|---|---|---|---|
| cold | 0.001648 | 0.000726 | 0.000929 | 0.001387 | **0.00469** |
| warm | 0 | 0 | 0.000908 | 0 | **0.000908** |

Cold cost per 1,000 input rows: $0.0469; per completed record: $4.7e-05.
Requests/attempts (cold enrichment): 2 requests, 0 failed, retry fraction 0.000. Mean billed tokens per review: input 45.8, output 55.7; cached instruction prefix 2726 tokens (cache-read share 1.00).
Provider prompt-cache savings are only what `cache_read_input_tokens` shows; the result cache is separate.

## Estimated: projections (not measurements)

Controls (editable in `cost/assumptions.json`): spend limit $5.0, output-token cap 70/review, max workers 1, fallback fraction 0.0, 50 reviews/request, verification sample 500.

| Scenario | Case | Distinct texts | Requests | Enrich $ | Verify $ | Group+memo $ | **Total API $** | Est. wall s | Over cap? |
|---|---|---|---|---|---|---|---|---|---|
| declared 187,000-review subset (planned run) | base | 143,114 | 2,863 | 2.358328 | 0.007264 | 0.002316 | **2.367908** | 3,504 | no |
| declared 187,000-review subset (planned run) | conservative | 143,114 | 3,579 | 3.992981 | 0.007627 | 0.002316 | **4.002924** | 11,825 | no |
| 100,000 core of the subset | base | 78,309 | 1,567 | 1.290434 | 0.007264 | 0.002316 | **1.300014** | 1,752 | no |
| 100,000 core of the subset | conservative | 78,309 | 1,959 | 2.184968 | 0.007627 | 0.002316 | **2.194911** | 6,570 | no |
| full corpus (estimate only, not executed) | base | 484,189 | 9,684 | 7.97876 | 0.007264 | 0.002316 | **7.98834** | 10,949 | **YES — exceeds cap** |
| full corpus (estimate only, not executed) | conservative | 484,189 | 12,105 | 13.508695 | 0.007627 | 0.002316 | **13.518638** | 40,732 | **YES — exceeds cap** |

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
