"""Projection refresh from the main run's real calls (after 500 and 10,000). Offline, no API.

  python cost/refresh.py 500
Appends a dated section to cost/refresh.md and cost/refresh.json.
"""
import json
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from cost.calculator import load_rates, ITEMS  # noqa: E402


def main(label):
    rates, _ = load_rates()
    calls = [json.loads(l) for l in open(ROOT / "outputs" / "calls.jsonl", encoding="utf-8")]
    enr = [c for c in calls if c["role"] == "enrich"]
    usd = sum(Decimal(c["usage_items"][k]) * rates[(c["model"], c["tier"], k)] for c in enr if c.get("usage_items") for k in ITEMS)
    sent = sum(len(c["review_ids"]) for c in enr)
    first = sum(len(c["review_ids"]) for c in enr if c.get("attempt", 1) == 1)
    fails = sum(c["outcome"] == "failed" for c in enr)
    per = usd / first if first else Decimal(0)
    a = json.loads((ROOT / "cost" / "assumptions.json").read_text())
    scen = next(v for k, v in a["scenarios"].items() if k.startswith("subset_") and "planned" in v["label"])
    full = a["scenarios"]["full_corpus_660609"]
    spent_total = Decimal(0)
    import sqlite3
    led = sqlite3.connect(ROOT / "state" / "ledger.sqlite")
    spent_total = Decimal(str(led.execute("select coalesce(sum(usd),0) from spend").fetchone()[0]))
    out = {"checkpoint": label, "enrich_requests": len(enr), "failed_requests": fails, "distinct_texts_classified": first,
           "reviews_sent_incl_retries": sent, "retry_fraction": round((sent - first) / first, 4) if first else None,
           "measured_enrich_usd": float(round(usd, 6)), "usd_per_distinct_text": float(round(per, 10)),
           "projected_subset_enrich_base_usd": float(round(per * scen["distinct_texts"], 4)),
           "projected_subset_enrich_conservative_usd": float(round(per * scen["distinct_texts"] * Decimal("1.5"), 4)),
           "projected_full_corpus_enrich_base_usd": float(round(per * full["distinct_texts"], 4)),
           "ledger_spent_all_stages_usd": float(round(spent_total, 6)), "cap_usd": a["spend_limit_usd"]}
    out["fits_cap_conservative"] = out["projected_subset_enrich_conservative_usd"] + 0.05 <= a["spend_limit_usd"]
    hist_p = ROOT / "cost" / "refresh.json"
    hist = json.loads(hist_p.read_text()) if hist_p.exists() else []
    hist = [h for h in hist if h["checkpoint"] != label] + [out]
    hist_p.write_text(json.dumps(hist, indent=2) + "\n")
    md = ["# Projection refreshes (measured on the main run; estimates are labelled)", "",
          "Conservative = measured $/distinct text × 1.5. Subset = " + scen["label"] + f" ({scen['distinct_texts']:,} distinct texts).", "",
          "| Checkpoint | Distinct texts classified | Requests (failed) | Retry frac | Measured enrich $ | $/distinct text | Subset base $ (est.) | Subset conservative $ (est.) | Full corpus base $ (est.) | Ledger spent, all stages $ | Fits cap? |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for h in hist:
        md.append(f"| {h['checkpoint']} | {h['distinct_texts_classified']:,} | {h['enrich_requests']} ({h['failed_requests']}) | {h['retry_fraction']} | "
                  f"{h['measured_enrich_usd']} | {h['usd_per_distinct_text']:.10f} | {h['projected_subset_enrich_base_usd']} | "
                  f"{h['projected_subset_enrich_conservative_usd']} | {h['projected_full_corpus_enrich_base_usd']} | {h['ledger_spent_all_stages_usd']} | "
                  f"{'yes' if h['fits_cap_conservative'] else '**NO**'} |")
    (ROOT / "cost" / "refresh.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main(sys.argv[1])
