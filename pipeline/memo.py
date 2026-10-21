"""Stage 6 - Recommend. The memo model sees only ranking rows, topic aggregates and a
bounded evidence pack. Code checks every cited claim, issue ID and review ID; on a
mismatch it regenerates (at most 2 tries in total) and then fails loudly.
"""
import csv
import hashlib
import json
import re

from . import common, llm

PROMPT_PATH = common.PROMPTS / "memo_v1.md"
FAMILIES = {"access": ["access"], "usability": ["usability"], "playback": ["playback"],
            "billing-support": ["billing", "support"]}
METRICS = ("complaint_count", "severity_sum", "mean_severity", "priority_score")
SCHEMA = {"type": "object", "properties": {
    "recommendation": {"type": "string", "enum": list(FAMILIES)},
    "memo_markdown": {"type": "string"},
    "claims": {"type": "array", "items": {"type": "object", "properties": {
        "claim_id": {"type": "string"}, "issue_id": {"type": "string"},
        "metric": {"type": "string", "enum": list(METRICS)}, "value": {"type": "string"}},
        "required": ["claim_id", "issue_id", "metric", "value"], "additionalProperties": False}},
    "cited_review_ids": {"type": "array", "items": {"type": "string"}}},
    "required": ["recommendation", "memo_markdown", "claims", "cited_review_ids"], "additionalProperties": False}


def aggregates(records, ranking):
    """Topic-level aggregates over completed records (code-computed, for the memo and dashboard)."""
    rows = []
    for topic in common.TOPICS:
        recs = [r for r in records.values() if r["topic"] == topic]
        comp = [r for r in recs if r["intent"] in ("complaint", "cancellation")]
        rows.append({"topic": topic, "records": len(recs), "complaint_or_cancellation": len(comp),
                     "cancellation": sum(r["intent"] == "cancellation" for r in recs),
                     "severity_sum": sum(r["severity"] for r in comp),
                     "severity_4_plus": sum(r["severity"] >= 4 for r in comp),
                     "needs_review": sum(r["needs_review"] for r in recs)})
    return rows


def write_aggregates(rows, path):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def evidence_pack(ranking, membership, records, top=6, per_issue=3):
    by = {}
    for iid, rid in membership:
        by.setdefault(iid, []).append(rid)
    pack = []
    for row in ranking[:top]:
        ids = sorted(by[row["issue_id"]], key=lambda r: (-records[r]["severity"], hashlib.sha256(r.encode()).hexdigest()))
        pack.append({"issue_id": row["issue_id"],
                     "examples": [{"review_id": r, "quote": records[r]["evidence_quote"][:240]} for r in ids[:per_issue]]})
    return pack


def check(out, ranking, pack):
    problems = []
    by_id = {r["issue_id"]: r for r in ranking}
    seen = set()
    for c in out["claims"]:
        if c["claim_id"] in seen:
            problems.append(f"duplicate claim {c['claim_id']}")
        seen.add(c["claim_id"])
        row = by_id.get(c["issue_id"])
        if not row:
            problems.append(f"{c['claim_id']}: unknown issue {c['issue_id']}")
        elif str(row[c["metric"]]) != c["value"]:
            problems.append(f"{c['claim_id']}: {c['metric']} is {row[c['metric']]}, memo says {c['value']}")
        if f"[{c['claim_id']}]" not in out["memo_markdown"]:
            problems.append(f"{c['claim_id']} not cited in memo text")
    for cid in set(re.findall(r"\[(C\d+)\]", out["memo_markdown"])) - seen:
        problems.append(f"memo cites undefined claim {cid}")
    pack_ids = {e["review_id"] for p in pack for e in p["examples"]}
    for rid in out["cited_review_ids"]:
        if rid not in pack_ids:
            problems.append(f"cited review {rid} not in evidence pack")
    for iid in set(re.findall(r"`([a-z]+\.[a-z_]+)`", out["memo_markdown"])):
        if iid not in by_id:
            problems.append(f"memo names unknown issue {iid}")
    if not out["claims"]:
        problems.append("no claims")
    return problems


def run(ranking, agg, pack, scope_note, ledger, calls_path, model, run_id, log_path=None, cache_dir=None, top=12):
    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    inputs = {"scope": scope_note, "ranking_top": [{k: str(r[k]) for k in ["rank", "issue_id", *METRICS]} for r in ranking[:top]],
              "issues_total": len(ranking), "topic_aggregates": agg, "evidence": pack}
    user = json.dumps(inputs, ensure_ascii=False, separators=(",", ":"))
    key = hashlib.sha256((model + prompt + user).encode()).hexdigest()[:16]
    cache = cache_dir / f"memo_{key}.json" if cache_dir else None
    if cache and cache.exists():
        common.log("memo", "cache_hit", log_path, cache=cache.name)
        return json.loads(cache.read_text(encoding="utf-8")), 0
    rates = llm.load_rates()
    c = llm.client()
    feedback, n_calls = "", 0
    for attempt in (1, 2):
        mt = 2500
        params = llm.request_params(model, prompt, user + feedback, SCHEMA, mt)
        rkey = f"memo:{run_id}:{attempt}"
        if not ledger.try_reserve(rkey, llm.worst_case(model, "standard", rates, len(prompt), len(user) + len(feedback), mt)):
            common.log("memo", "stopped_at_cap", log_path, **ledger.summary())
            return None, n_calls
        msg, dt = llm.sync_call(c, params)
        n_calls += 1
        items = llm.usage_items(msg.usage)
        usd = float(llm.cost(items, model, "standard", rates))
        problems, out = ["unparseable"], None
        try:
            out = json.loads(llm.message_text(msg))
            problems = check(out, ranking, pack)
        except Exception as e:
            problems = [f"unparseable: {e}"]
        common.append_jsonl(calls_path, [{
            "request_id": msg.id, "run_id": run_id, "role": "memo", "review_ids": [], "model": model, "tier": "standard",
            "effort": "low", "thinking": "disabled", "phase": "initial", "attempt": attempt,
            "outcome": "succeeded" if not problems else "failed", "check_problems": problems,
            "inputs": "ranking top rows, topic aggregates, bounded evidence pack (memo_inputs.json)",
            "input_tokens": items["input"], "output_tokens": items["output"],
            "cache_read_input_tokens": items["cache_read"],
            "cache_creation_input_tokens": items["cache_write_5m"] + items["cache_write_1h"],
            "usage_items": items, "usd": round(usd, 8), "duration_s": round(dt, 3), "stop_reason": msg.stop_reason}])
        ledger.settle(rkey, [(msg.id, "memo", usd)])
        common.log("memo", "attempt", log_path, attempt=attempt, problems=len(problems))
        if not problems:
            out["inputs"] = inputs
            if cache:
                cache.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
            return out, n_calls
        feedback = "\n\nYour previous draft failed these code checks; fix them exactly:\n" + "\n".join(problems[:20])
    raise RuntimeError("memo failed code checks twice: " + "; ".join(problems[:5]))


def write_outputs(out, memo_path, claims_path):
    memo_path.write_text(out["memo_markdown"].rstrip() + "\n", encoding="utf-8")
    with open(claims_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["claim_id", "issue_id", "metric", "value"])
        for c in out["claims"]:
            w.writerow([c["claim_id"], c["issue_id"], c["metric"], c["value"]])
