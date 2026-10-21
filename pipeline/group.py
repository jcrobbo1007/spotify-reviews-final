"""Stage 4 - Group (code; one small-model call only names the frozen issues).

Issue = topic x subtopic. Subtopic comes from a deterministic, ordered keyword map over
the review text and extracted entities, so membership is reproducible without a model.
Each complaint/cancellation record belongs to exactly one issue.
"""
import csv
import hashlib
import json
import re
import time

from . import common, llm

MAP_VERSION = "issue_map_v1"
# Ordered: first match wins inside a topic. Patterns are matched case-insensitively.
SUBTOPICS = {
    "access": [("login_failure", r"log ?in|sign ?in|can'?t (get )?in|password|verif|code"),
               ("logged_out", r"log(ged|s)? (me )?out|sign(ed|s)? (me )?out"),
               ("account_lost", r"account (was )?(hack|delet|gone|lost|disabl|suspend|ban)|hack")],
    "usability": [("ads", r"\bads?\b|advert|commercial"),
                  ("shuffle_queue", r"shuffle|queue|repeat|skip"),
                  ("playlist_library", r"playlist|library|liked songs|like button"),
                  ("ui_layout", r"\bui\b|interface|layout|design|update|navigat|button|home ?(page|screen)|swipe")],
    "playback": [("crash_freeze", r"crash|freez|clos(e|es|ing) (itself|by itself|on)|force|not open|won'?t open"),
                 ("stops_pauses", r"stop|paus|cut(s|ting)? (out|off)|interrupt"),
                 ("connectivity", r"connect|internet|wifi|network|offline|bluetooth|cast|car|android auto"),
                 ("lag_loading", r"lag|load|buffer|slow|delay"),
                 ("audio_quality", r"quality|sound|audio|volume|equali"),
                 ("battery_resource", r"battery|storage|memory|data usage|ram")],
    "downloads": [("downloads_lost", r"disappear|gone|deleted|lost|remov|re-?download"),
                  ("offline_play", r"offline|internet|connection"),
                  ("download_failure", r"download")],
    "catalog": [("missing_content", r"missing|not available|unavailable|removed|grey|gray|can'?t find|region"),
                ("lyrics", r"lyric"),
                ("search", r"search"),
                ("recommendations", r"recommend|algorithm|suggest|discover|smart shuffle|dj")],
    "billing": [("premium_paywall", r"skip|shuffle|lyric|choose|pick|order|seek|rewind|free (version|users|tier)|without premium|pay(ing)? for"),
                ("price", r"price|expensive|cost|increase|afford"),
                ("charges_refund", r"charg|refund|bill|money|deduct|payment|card"),
                ("subscription_entitlement", r"premium|subscri|plan|trial|family|student")],
    "support": [("support_response", r"support|customer service|help|contact|chat|email")],
    "other": [("general_dislike", r"")],
}


def assign(record, text):
    topic = record["topic"]
    hay = (text + " " + " ".join(record.get("entities", []))).lower()
    for sub, pat in SUBTOPICS[topic]:
        if pat == "" or re.search(pat, hay, re.I):
            return f"{topic}.{sub}"
    return f"{topic}.general"


def map_digest():
    return hashlib.sha256(json.dumps(SUBTOPICS, sort_keys=True).encode()).hexdigest()[:8]


def build_membership(records, texts):
    """records: {rid: fields}. Returns sorted [(issue_id, review_id)] for complaint/cancellation only."""
    pairs = []
    for rid, r in records.items():
        if r["intent"] in ("complaint", "cancellation"):
            pairs.append((assign(r, texts[rid]), rid))
    pairs.sort()
    return pairs


def write_membership(pairs, path):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["issue_id", "review_id"])
        w.writerows(pairs)


NAME_SCHEMA = {"type": "object", "properties": {"issues": {"type": "array", "items": {
    "type": "object", "properties": {"issue_id": {"type": "string"}, "name": {"type": "string"},
                                     "description": {"type": "string"}},
    "required": ["issue_id", "name", "description"], "additionalProperties": False}}},
    "required": ["issues"], "additionalProperties": False}
NAME_PROMPT_PATH = common.PROMPTS / "group_names_v1.md"


def evidence_pack(pairs, records, per_issue=4):
    """Bounded: up to `per_issue` ID'd quotes per issue, deterministic order (lowest review_id hash)."""
    by = {}
    for iid, rid in pairs:
        by.setdefault(iid, []).append(rid)
    pack = []
    for iid in sorted(by):
        ids = sorted(by[iid], key=lambda r: hashlib.sha256(r.encode()).hexdigest())[:per_issue]
        pack.append({"issue_id": iid, "members": len(by[iid]),
                     "examples": [{"review_id": r, "quote": records[r]["evidence_quote"][:240]} for r in ids]})
    return pack


def name_issues(pack, ledger, calls_path, model, run_id, log_path=None, cache_dir=None):
    """One sync call. Cached by input hash so a warm rerun makes no call."""
    prompt = NAME_PROMPT_PATH.read_text(encoding="utf-8")
    user = json.dumps(pack, ensure_ascii=False, separators=(",", ":"))
    key = hashlib.sha256((model + prompt + user).encode()).hexdigest()
    cache = (cache_dir / f"group_names_{key[:16]}.json") if cache_dir else None
    if cache and cache.exists():
        common.log("group", "names_cache_hit", log_path, cache=cache.name)
        return json.loads(cache.read_text(encoding="utf-8")), 0
    rates = llm.load_rates()
    mt = 300 + 110 * len(pack)  # pilot: 1,200 for 18 issues truncated (~64 tokens/issue used)
    params = llm.request_params(model, prompt, user, NAME_SCHEMA, mt)
    wc = llm.worst_case(model, "standard", rates, len(prompt), len(user), mt)
    rkey = f"group:{run_id}"
    if not ledger.try_reserve(rkey, wc):
        common.log("group", "stopped_at_cap", log_path, **ledger.summary())
        return None, 0
    c = llm.client()
    msg, dt = llm.sync_call(c, params)
    items = llm.usage_items(msg.usage)
    usd = float(llm.cost(items, model, "standard", rates))
    names, outcome = {}, "failed"
    try:
        valid_ids = {p["issue_id"] for p in pack}
        for it in json.loads(llm.message_text(msg))["issues"]:
            if it["issue_id"] in valid_ids:
                names[it["issue_id"]] = {"name": it["name"][:80], "description": it["description"][:240]}
        outcome = "succeeded" if names else "failed"
    except Exception:
        pass
    common.append_jsonl(calls_path, [{
        "request_id": msg.id, "run_id": run_id, "role": "group", "review_ids": [], "model": model, "tier": "standard",
        "effort": "low", "thinking": "disabled", "phase": "initial", "outcome": outcome,
        "inputs": "bounded evidence pack: issue ids + <=4 ID'd quotes each (see issues_evidence_pack.json)",
        "input_tokens": items["input"], "output_tokens": items["output"],
        "cache_read_input_tokens": items["cache_read"],
        "cache_creation_input_tokens": items["cache_write_5m"] + items["cache_write_1h"],
        "usage_items": items, "usd": round(usd, 8), "duration_s": round(dt, 3), "stop_reason": msg.stop_reason}])
    ledger.settle(rkey, [(msg.id, "group", usd)])
    if cache and names:
        cache.write_text(json.dumps(names, indent=2, ensure_ascii=False), encoding="utf-8")
    return names, 1


def write_issues(pairs, names, path):
    counts = {}
    for iid, _ in pairs:
        counts[iid] = counts.get(iid, 0) + 1
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["issue_id", "topic", "subtopic", "name", "description", "member_count", "map_version"])
        for iid in sorted(counts):
            topic, sub = iid.split(".", 1)
            n = (names or {}).get(iid) or {"name": sub.replace("_", " "), "description": "(default name; naming call unavailable)"}
            w.writerow([iid, topic, sub, n["name"], n["description"], counts[iid], f"{MAP_VERSION}.{map_digest()}"])
