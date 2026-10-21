"""Offline cost/runtime calculator. No API key, no network, no model calls.

  python -m pipeline cost --replay            (default)
  python cost/calculator.py --rate-scale 2    (sanity test: API subtotal doubles, time unchanged)

Inputs: cost/pilot_calls.jsonl (real per-attempt usage), cost/rates.csv (editable, dated),
cost/assumptions.json (editable projection controls). Outputs: cost/usage.csv,
cost/replay.json and cost/report.md.
"""
import argparse
import csv
import json
import math
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

COST = Path(__file__).resolve().parent
ITEMS = ("input", "cache_write_5m", "cache_write_1h", "cache_read", "output")
DEFAULT_ASSUMPTIONS = {
    "spend_limit_usd": 5.00,
    "output_token_cap_per_review": 70,
    "max_workers": 1,
    "fallback_fraction": 0.0,
    "reviews_per_request": 50,
    "verification_sample": 500,
    "scenarios": {
        "subset_100000": {"rows": 100000, "classifications": 100000, "quarantines": 0, "distinct_texts": 78309,
                          "label": "declared 100,000-review subset (planned run)"},
        "full_corpus_660609": {"rows": 660622, "classifications": 660609, "quarantines": 13, "distinct_texts": 484189,
                               "label": "full corpus (estimate only, not executed)"},
    },
    "base": {"retry_fraction": None, "output_multiplier": 1.0, "batch_wait_s_per_wave": None},
    "conservative": {"retry_fraction": 0.05, "output_multiplier": 1.5, "batch_wait_s_per_wave_multiplier": 3.0,
                     "cache_miss_fraction": 0.5},
    "requests_per_wave": 100,
}


def load_rates(scale=Decimal(1)):
    rates, meta = {}, []
    with open(COST / "rates.csv", encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            rates[(r["model"], r["tier"], r["item"])] = Decimal(r["usd_per_mtok"]) * scale / Decimal(1_000_000)
            meta.append(r)
    return rates, meta


def load_calls():
    p = COST / "pilot_calls.jsonl"
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()] if p.exists() else []


def mode_of(call):
    if call.get("run_status") == "invalid_stale_warm_state":
        return "warm_stale_invalid"
    return "warm" if call.get("run_id", "").startswith("pilot-warm") else "cold"


def write_usage(calls):
    """usage.csv: one row per (call, billed item); every charged unit maps to a request_id in pilot_calls.jsonl."""
    rows = []
    for c in calls:
        items = c.get("usage_items") or {"input": c.get("input_tokens", 0), "output": c.get("output_tokens", 0)}
        for k in ITEMS:
            rows.append({"request_id": c["request_id"], "run_id": c.get("run_id", ""), "mode": mode_of(c),
                         "role": c["role"], "model": c["model"], "tier": c.get("tier", "standard"),
                         "outcome": c["outcome"], "item": k, "unit": "token", "billed_units": int(items.get(k, 0))})
    with open(COST / "usage.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else ["request_id"], lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    return rows


def priced(usage_rows, rates):
    by = {}
    for u in usage_rows:
        usd = Decimal(u["billed_units"]) * rates[(u["model"], u["tier"], u["item"])]
        key = (u["mode"], u["role"])
        by[key] = by.get(key, Decimal(0)) + usd
    return by


def d6(x):
    return float(Decimal(x).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))


def measure(calls, timings):
    """Per-review and per-request measurements from the cold pilot's enrichment calls."""
    enr = [c for c in calls if c["role"] == "enrich" and mode_of(c) == "cold"]
    ok = [c for c in enr if c["outcome"] == "succeeded"]
    sent = sum(len(c["review_ids"]) for c in enr)
    first = sum(len(c["review_ids"]) for c in enr if c.get("attempt", 1) == 1)
    m = {"enrich_requests": len(enr), "enrich_failed_requests": len(enr) - len(ok), "reviews_sent": sent,
         "reviews_first_attempt": first,
         "retry_fraction": (sent - first) / first if first else 0.0,
         "input_per_review": sum(c["usage_items"]["input"] for c in ok) / max(1, sum(len(c["review_ids"]) for c in ok)),
         "output_per_review": sum(c["usage_items"]["output"] for c in ok) / max(1, sum(len(c["review_ids"]) for c in ok)),
         "prefix_tokens": max([c["usage_items"]["cache_read"] + c["usage_items"]["cache_write_1h"]
                               + c["usage_items"]["cache_write_5m"] for c in ok] or [0]),
         "cache_read_share": (sum(c["usage_items"]["cache_read"] for c in ok) /
                              max(1, sum(c["usage_items"]["cache_read"] + c["usage_items"]["cache_write_1h"]
                                         + c["usage_items"]["cache_write_5m"] for c in ok))),
         "enrich_wall_s": (timings.get("enrich") or {}).get("wall_s")}
    for role in ("verify", "group", "memo"):
        rc = [c for c in calls if c["role"] == role and mode_of(c) == "cold"]
        m[f"{role}_calls"] = len(rc)
        m[f"{role}_reviews"] = sum(len(c["review_ids"]) for c in rc)
    return m


def project(m, a, rates, model, scen, case, calls):
    n_texts = scen["distinct_texts"]
    rpr = a["reviews_per_request"]
    retry = m["retry_fraction"] if case == "base" else max(m["retry_fraction"], a["conservative"]["retry_fraction"])
    out_mult = 1.0 if case == "base" else a["conservative"]["output_multiplier"]
    miss = 0.0 if case == "base" else a["conservative"]["cache_miss_fraction"]
    reviews = n_texts * (1 + retry)
    requests = math.ceil(n_texts / rpr) + math.ceil(n_texts * retry / 10)
    t = "batch"
    r = lambda item: rates[(model, t, item)]
    prefix = Decimal(m["prefix_tokens"])
    prefix_cost = requests * prefix * (Decimal(miss) * r("cache_write_1h") + Decimal(1 - miss) * r("cache_read"))
    enrich = (Decimal(reviews) * Decimal(m["input_per_review"]) * r("input")
              + Decimal(reviews) * Decimal(m["output_per_review"] * out_mult) * r("output") + prefix_cost)
    # Verification, grouping and memo: measured per-call cost from the pilot, applied once / per sample.
    stage_cost = {}
    for role in ("verify", "group", "memo"):
        rc = [c for c in calls if c["role"] == role and mode_of(c) == "cold"]
        stage_cost[role] = sum(Decimal(c["usage_items"][k]) * rates[(c["model"], c.get("tier", "standard"), k)]
                               for c in rc for k in ITEMS) if rc else None
    verify = None
    if stage_cost["verify"] is not None and m["verify_reviews"]:
        verify = stage_cost["verify"] / m["verify_reviews"] * a["verification_sample"] * Decimal(1 + retry)
    fixed = sum(v for k, v in stage_cost.items() if k in ("group", "memo") and v is not None)
    total = enrich + (verify or 0) + fixed
    waves = math.ceil(requests / a["requests_per_wave"])
    wave_s = m["enrich_wall_s"] or 0
    if case == "conservative":
        wave_s *= a["conservative"]["batch_wait_s_per_wave_multiplier"]
    return {"case": case, "distinct_texts": n_texts, "reviews_sent_incl_retries": round(reviews),
            "requests": requests, "retry_fraction": round(retry, 4), "output_multiplier": out_mult,
            "prefix_cache_miss_fraction": miss,
            "enrich_usd": d6(enrich), "verify_usd": d6(verify) if verify is not None else "unknown (not yet measured)",
            "group_memo_fixed_usd": d6(fixed), "total_api_usd": d6(total),
            "waves": waves, "est_wall_s": round(waves * wave_s / max(1, a["max_workers"])),
            "exceeds_cap": float(total) > a["spend_limit_usd"]}


def write_report(out, rate_meta, calls):
    m, a = out["measurements"], out["assumptions"]
    L = ["# 100-review cost & runtime calculator — report", "",
         "Generated offline by `python -m pipeline cost --replay` from `pilot_calls.jsonl` × `rates.csv` "
         "(no API key, no model calls). Measured and estimated figures are kept in separate sections.", "",
         "## Measured: 100-review pilot (`data/cost_100.csv`, sha256 c884ac3b…dd0e)", ""]
    cold_t, warm_t = out["timings"].get("cold", {}), out["timings"].get("warm", {})
    L += ["| Stage | Cold wall s | Cold new calls | Warm wall s | Warm new calls |", "|---|---|---|---|---|"]
    for st in ("enrich", "verify", "group", "rank", "memo"):
        c, w = cold_t.get(st, {}), warm_t.get(st, {})
        L.append(f"| {st} | {c.get('wall_s', '—')} | {c.get('new_calls', '—')} | {w.get('wall_s', '—')} | {w.get('new_calls', '—')} |")
    tot = lambda t: round(sum(v.get("wall_s", 0) for v in t.values()), 1)
    L += ["", f"End-to-end wall clock (sum of sequential stage clocks): cold **{tot(cold_t)} s**, warm **{tot(warm_t)} s**. "
          "Batch-API queue time dominates enrichment/verification wall clock.", ""]
    enr = cold_t.get("enrich", {})
    if enr.get("counts"):
        L.append(f"Enrichment status (cold): {enr['counts']}; label_config `{enr.get('label_config')}`.")
    L += ["", "### API spend by stage (USD, from usage × rates)", "", "| Mode | " + " | ".join(("enrich", "verify", "group", "memo")) + " | Subtotal |",
          "|---|---|---|---|---|---|"]
    for mode in ("cold", "warm", "warm_stale_invalid"):
        r = out["measured"].get(mode, {})
        L.append(f"| {mode} | " + " | ".join(str(r.get(k, 0)) for k in ("enrich", "verify", "group", "memo"))
                 + f" | **{r.get('api_subtotal_usd', 0)}** |")
    cold_usd = out["measured"].get("cold", {}).get("api_subtotal_usd", 0)
    L += ["", f"Cold cost per 1,000 input rows: ${round(cold_usd * 10, 4)}; per completed record: ${round(cold_usd / 100, 6)}.",
          f"Requests/attempts (cold enrichment): {m['enrich_requests']} requests, {m['enrich_failed_requests']} failed, "
          f"retry fraction {m['retry_fraction']:.3f}. Mean billed tokens per review: input {m['input_per_review']:.1f}, "
          f"output {m['output_per_review']:.1f}; cached instruction prefix {m['prefix_tokens']} tokens "
          f"(cache-read share {m['cache_read_share']:.2f}).",
          "Provider prompt-cache savings are only what `cache_read_input_tokens` shows; the result cache is separate.", "",
          "## Estimated: projections (not measurements)", "",
          f"Controls (editable in `cost/assumptions.json`): spend limit ${a['spend_limit_usd']}, output-token cap "
          f"{a['output_token_cap_per_review']}/review, max workers {a['max_workers']}, fallback fraction {a['fallback_fraction']}, "
          f"{a['reviews_per_request']} reviews/request, verification sample {a['verification_sample']}.", "",
          "| Scenario | Case | Distinct texts | Requests | Enrich $ | Verify $ | Group+memo $ | **Total API $** | Est. wall s | Over cap? |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for name, cases in out["projections"].items():
        for case, p in cases.items():
            L.append(f"| {a['scenarios'][name]['label']} | {case} | {p['distinct_texts']:,} | {p['requests']:,} | {p['enrich_usd']} | "
                     f"{p['verify_usd']} | {p['group_memo_fixed_usd']} | **{p['total_api_usd']}** | {p['est_wall_s']:,} | "
                     f"{'**YES — exceeds cap**' if p['exceeds_cap'] else 'no'} |")
    L += ["", "No-reuse comparison: the full-corpus rows above use 484,189 distinct texts; without exact-text reuse the "
          "work is 660,609 classifications (×1.364). Subset without reuse: 100,000 vs 78,309 (×1.277).",
          "Formulas: item_cost = billed_units × usd_per_mtok / 1e6 per mutually exclusive item (input, cache_write_5m, "
          "cache_write_1h, cache_read, output); conservative = higher retries, ×1.5 output, 50% prefix cache misses, ×3 batch wait. "
          "Group and memo are fixed one-time overhead, added once. Local compute: " + out["local_compute"] + ".", "",
          "## Rates used", "", "| Model | Tier | Item | $/MTok | Source | Checked |", "|---|---|---|---|---|---|"]
    for r in rate_meta:
        L.append(f"| {r['model']} | {r['tier']} | {r['item']} | {r['usd_per_mtok']} | {r['source']} | {r['checked']} |")
    (COST / "report.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--rate-scale", default="1", help="multiply every API rate (sanity test)")
    ap.add_argument("--assumptions", default=str(COST / "assumptions.json"))
    args = ap.parse_args(argv or [])
    ap_path = Path(args.assumptions)
    if not ap_path.exists():
        ap_path.write_text(json.dumps(DEFAULT_ASSUMPTIONS, indent=2) + "\n", encoding="utf-8")
    a = json.loads(ap_path.read_text(encoding="utf-8"))
    rates, rate_meta = load_rates(Decimal(args.rate_scale))
    calls = load_calls()
    usage = write_usage(calls)
    by = priced(usage, rates)
    timings = {m: json.loads((COST / f"pilot_{m}_timings.json").read_text())
               for m in ("cold", "warm") if (COST / f"pilot_{m}_timings.json").exists()}
    measured = {mode: {role: d6(v) for (md, role), v in by.items() if md == mode} for mode in ("cold", "warm", "warm_stale_invalid")}
    for mode in measured:
        measured[mode]["api_subtotal_usd"] = d6(sum(Decimal(str(v)) for v in measured[mode].values()))
        measured[mode]["new_enrich_calls"] = sum(1 for c in calls if c["role"] == "enrich" and mode_of(c) == mode)
    m = measure(calls, timings.get("cold", {}))
    model = calls[0]["model"] if calls else "claude-haiku-5-5"
    proj = {name: {case: project(m, a, rates, model, scen, case, calls) for case in ("base", "conservative")}
            for name, scen in a["scenarios"].items()}
    out = {"rate_scale": args.rate_scale, "measured": measured, "timings": timings, "measurements": m,
           "projections": proj, "assumptions": a,
           "local_compute": "not measured; local CPU/SQLite work only, no GPU; shown separately and excluded from API spend"}
    if args.rate_scale == "1":
        (COST / "replay.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
        write_report(out, rate_meta, calls)
    print(json.dumps({"measured": measured, "projections": {k: {c: {x: v[x] for x in ("total_api_usd", "requests", "exceeds_cap", "est_wall_s")}
                                                               for c, v in p.items()} for k, p in proj.items()}}, indent=2))
    return out


if __name__ == "__main__":
    import sys
    main(sys.argv[1:])
