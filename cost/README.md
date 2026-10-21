# Cost & runtime calculator

**Offline replay (default, no API key, no model calls):**

```
python -m pipeline cost --replay
```

Reads `pilot_calls.jsonl` (real per-attempt usage) × `rates.csv` (editable, dated, with source links) ×
`assumptions.json` (editable controls: spend limit, output-token cap, max workers, fallback fraction, scenarios),
and writes `usage.csv`, `replay.json` and `report.md`.

Sanity test (doubling rates doubles API spend; measured time unchanged):

```
python cost/calculator.py --rate-scale 2
```

**Explicit paid pilot** (needs `ANTHROPIC_API_KEY` in `.env`; makes real calls):

```
python -m pipeline cost --pilot --paid --mode cold   # empty result cache, cost_100.csv unchanged
python -m pipeline cost --pilot --paid --mode warm   # same settings, saved result cache
```

Files: `pilot_records.jsonl` (one record per pilot ID, contract hash + labels), `pilot_calls.jsonl` (every attempt,
cold and warm, with run/request IDs), `usage.csv` (every billed unit → request_id), `rates.csv`, `report.md`,
`pilot_cold/` (verify/group/rank/memo outputs), `pilot_*_timings.json`, terminal logs.

## Pilot history (all attempts kept; all spend counts against the $5.00 cap)

| Attempt | Folder | What happened | Fix before next attempt |
|---|---|---|---|
| 1 | `pilot_attempt1/` | enrich only; 99/100 completed, 1 quarantined (model quote not an exact substring of a gibberish review; 3 others needed a retry round trip) | deterministic code quote repair (`qrepair1`) |
| 2 | `pilot_attempt2/` | all stages passed; 4 of 9 long reviews fell back to the opening as quote; cold naming call hit its output cap so the warm run repeated it | raw responses saved; naming cap raised |
| 3 | `pilot_attempt3/` | raw responses showed the model returns `q:""` for long reviews (copies the pattern of the 91% short ones); stopped mid-verify, verify batch reconciled into the ledger | long reviews grouped into their own requests with an explicit `qn=1` flag |
| **4 (final)** | `pilot_cold/`, `pilot_warm/` | **cold: 100/100 completed, 0 retries, 8/9 long reviews quoted exactly (1 gibberish review uses the code fallback); warm: 0 calls in every stage, $0** | — |

One disclosed invalid run: `pilot_warm_stale/` (run `pilot-warm-20261021T004102`). The warm run's SQLite state had not
been reset since attempt 2, so its "0 enrichment calls" proved nothing, and its group/memo inputs differed, causing 2 real
calls ($0.002287). Those calls stay in `pilot_calls.jsonl`, tagged `run_status: invalid_stale_warm_state`, and the
calculator reports them separately (`warm_stale_invalid`). The warm run now always starts from fresh run state with only
the saved result cache copied in; the rerun (`pilot_warm/`) made zero calls.
