"""Stage 3 - Verify. A separate, blind prompt re-labels a declared seeded sample from
source text + rubric only (never stage-2 output). Code compares and reports disagreements.
"""
import csv
import hashlib
import json
import time

from . import common, llm

PROMPT_PATH = common.PROMPTS / "verify_v1.md"
ITEM = {
    "type": "object",
    "properties": {"id": {"type": "string"},
                   "tp": {"type": "string", "enum": list(common.TOPICS)},
                   "in": {"type": "string", "enum": list(common.INTENTS)},
                   "sv": {"type": "integer", "enum": [1, 2, 3, 4, 5]},
                   "se": {"type": "number"}, "nr": {"type": "boolean"}},
    "required": ["id", "tp", "in", "sv", "se", "nr"], "additionalProperties": False}
SCHEMA = {"type": "object", "properties": {"r": {"type": "array", "items": ITEM}},
          "required": ["r"], "additionalProperties": False}
PER_REQUEST = 50


def sample(completed, n, seed):
    """Seeded, declared random sample over completed records (one per distinct text)."""
    ranked = sorted(completed, key=lambda rid: hashlib.sha256(f"{seed}:{rid}".encode()).hexdigest())
    return ranked[:n]


def run(ids, texts, ledger, calls_path, out_dir, model, run_id, log_path=None, tier="batch", tag="verify"):
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    cfg = f"{model}+verify_v1.{hashlib.sha256(prompt.encode()).hexdigest()[:8]}+effort-low+thinking-off"
    rates = llm.load_rates()
    groups = [ids[i:i + PER_REQUEST] for i in range(0, len(ids), PER_REQUEST)]
    reqs, meta, reserve = [], {}, 0.0
    for gi, g in enumerate(groups):
        cid = f"{tag}-{gi:03d}"
        user = json.dumps([{"id": f"r{j + 1}", "t": texts[rid]} for j, rid in enumerate(g)],
                          ensure_ascii=False, separators=(",", ":"))
        mt = 100 + 40 * len(g)
        reqs.append((cid, llm.request_params(model, prompt, user, SCHEMA, mt)))
        meta[cid] = {"ids": g, "local": {f"r{j + 1}": rid for j, rid in enumerate(g)}, "max_tokens": mt}
        reserve += llm.worst_case(model, tier, rates, len(prompt), len(user), mt)
    key = f"{tag}:{run_id}"
    if not ledger.try_reserve(key, reserve):
        common.log("verify", "stopped_at_cap", log_path, **ledger.summary())
        return None
    c = llm.client()
    t0 = time.time()
    batch = llm.submit_batch(c, reqs)
    common.log("verify", "batch_submitted", log_path, batch_id=batch.id, requests=len(reqs), reviews=len(ids))
    submitted = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    llm.wait_batch(c, batch.id)
    preds, calls, charges = {}, [], []
    for cid, kind, obj in llm.batch_results(c, batch.id):
        m = meta[cid]
        base = {"request_id": f"{batch.id}:{cid}", "batch_id": batch.id, "run_id": run_id, "role": "verify",
                "review_ids": m["ids"], "model": model, "tier": tier, "effort": "low", "thinking": "disabled",
                "phase": "initial", "label_config": cfg, "submitted_at": submitted,
                "ended_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "max_tokens": m["max_tokens"]}
        if kind != "succeeded":
            calls.append({**base, "outcome": "failed", "error": kind, "input_tokens": 0, "output_tokens": 0})
            continue
        items = llm.usage_items(obj.usage)
        usd = float(llm.cost(items, model, tier, rates))
        charges.append((base["request_id"], "verify", usd))
        got = 0
        try:
            for it in json.loads(llm.message_text(obj))["r"]:
                rid = m["local"].get(it.get("id"))
                if rid and rid not in preds and -1 <= it["se"] <= 1:
                    preds[rid] = {"topic": it["tp"], "intent": it["in"], "severity": it["sv"],
                                  "sentiment": round(float(it["se"]), 2), "needs_review": it["nr"]}
                    got += 1
        except Exception:
            pass
        calls.append({**base, "outcome": "succeeded" if got else "failed", "message_id": obj.id,
                      "stop_reason": obj.stop_reason, "input_tokens": items["input"], "output_tokens": items["output"],
                      "cache_read_input_tokens": items["cache_read"],
                      "cache_creation_input_tokens": items["cache_write_5m"] + items["cache_write_1h"],
                      "usage_items": items, "usd": round(usd, 8), "valid_items": got})
    common.append_jsonl(calls_path, calls)
    ledger.settle(key, charges)
    common.write_json(out_dir / f"{tag}_predictions.json",
                      {"label_config": cfg, "sample_ids": ids, "predictions": preds,
                       "wall_s": round(time.time() - t0, 2)})
    common.log("verify", "done", log_path, predicted=len(preds), of=len(ids), usd=round(sum(x[2] for x in charges), 6))
    return preds, cfg, round(time.time() - t0, 2)


def compare(records, preds, out_dir, tag="verify"):
    """records: {rid: stage-2 fields}. Writes disagreement CSV + summary."""
    rows, n = [], 0
    agree = {"topic": 0, "intent": 0, "severity": 0}
    sev_err = sent_err = 0.0
    for rid, p in preds.items():
        r = records.get(rid)
        if not r:
            continue
        n += 1
        for k in agree:
            agree[k] += r[k] == p[k]
        sev_err += abs(r["severity"] - p["severity"])
        sent_err += abs(r["sentiment"] - p["sentiment"])
        diff = [k for k in ("topic", "intent", "severity") if r[k] != p[k]]
        if diff:
            rows.append({"review_id": rid, "fields": "|".join(diff),
                         **{f"enrich_{k}": r[k] for k in ("topic", "intent", "severity")},
                         **{f"verify_{k}": p[k] for k in ("topic", "intent", "severity")},
                         "enrich_needs_review": r["needs_review"], "evidence_quote": r["evidence_quote"][:200]})
    with open(out_dir / f"{tag}_disagreements.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else ["review_id"], lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    summary = {"compared": n, **{f"{k}_agreement": round(v / n, 4) if n else None for k, v in agree.items()},
               "severity_mae": round(sev_err / n, 4) if n else None,
               "sentiment_mae": round(sent_err / n, 4) if n else None,
               "records_with_any_disagreement": len(rows)}
    common.write_json(out_dir / f"{tag}_summary.json", summary)
    return summary
