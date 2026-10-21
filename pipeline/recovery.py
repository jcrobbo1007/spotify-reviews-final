"""Disclosed recovery pass for the 40 quarantined subset reviews (requested by Jack, 2026-10-21).

Step 1, salvage (no API call): the 30 `output_token_cap` failures came from responses truncated at the
output cap. Complete item objects before the cut are parsed from the saved raw responses
(outputs/calls_raw_responses.jsonl) and run through the same code validation as any result. The original
call record is annotated (`salvaged_review_ids`, `original_outcome`), and no new call is logged.

Step 2, single-review requests (paid, Batch API): every review still quarantined is sent alone, one review
per request, as attempt 3 under the unchanged label_config. A failure there stays quarantined with its reason.
"""
import json
import time

from . import common, enrich, llm, run, state

DEC = json.JSONDecoder()
LOG = common.ROOT / "evals" / "recovery"


def complete_items(text):
    """Complete item objects from a possibly truncated {"r":[{...},{...},... response."""
    items, i = [], text.find("[")
    if i < 0:
        return items
    i += 1
    while True:
        while i < len(text) and text[i] in " \n\r\t,":
            i += 1
        if i >= len(text) or text[i] != "{":
            break
        try:
            obj, i = DEC.raw_decode(text, i)
        except json.JSONDecodeError:
            break
        items.append(obj)
    return items


def salvage(db, texts, cfg):
    raw = common.read_jsonl(common.OUT / "calls_raw_responses.jsonl")
    targets = {rid: reason for rid, reason in db.execute(
        "SELECT review_id, reason FROM reviews WHERE in_scope=1 AND status='quarantined' AND reason LIKE 'enrich_failed:%'")}
    found = {}
    for r in raw:  # file order = time order, so a later attempt overwrites an earlier one
        inv = {v: k for k, v in r["local_ids"].items()}
        hits = [rid for rid in targets if rid in inv]
        if not hits:
            continue
        items = {it.get("id"): it for it in complete_items(r["text"]) if isinstance(it, dict)}
        for rid in hits:
            it = items.get(inv[rid])
            if it:
                fields, _ = enrich.validate_item(it, texts[rid])
                if fields:
                    found[rid] = (r["request_id"], fields)
    db.execute("BEGIN")
    for rid, (req, fields) in found.items():
        res = json.dumps({**fields, "recovery": "salvaged_from_truncated_response"}, ensure_ascii=False, sort_keys=True)
        tsha = db.execute("SELECT text_sha FROM reviews WHERE review_id=?", (rid,)).fetchone()[0]
        db.execute("INSERT OR IGNORE INTO text_cache VALUES (?,?,?,?)", (tsha, cfg, rid, res))
        db.execute("UPDATE reviews SET status='completed', label_config=?, result_json=?, cache_source_id=NULL,"
                   " completed_phase='resume', completed_at=?, reason=? WHERE review_id=?",
                   (cfg, res, time.strftime("%Y-%m-%dT%H:%M:%S%z"), f"recovered_salvage:{req}", rid))
    db.execute("COMMIT")
    # annotate the original call records (they stay one line per real attempt)
    p = common.OUT / "calls.jsonl"
    calls = common.read_jsonl(p)
    by_req = {}
    for rid, (req, _) in found.items():
        by_req.setdefault(req, []).append(rid)
    for c in calls:
        if c["request_id"] in by_req:
            c["original_outcome"] = c.get("original_outcome", c["outcome"])
            c["outcome"] = "succeeded"
            c["salvaged_review_ids"] = sorted(by_req[c["request_id"]])
            c["post_hoc"] = ("recovery pass 2026-10-21: complete items before the output-cap cut were parsed from the "
                             "saved raw response and passed code validation; no new call")
    p.write_text("".join(json.dumps(c, ensure_ascii=False, separators=(",", ":")) + "\n" for c in calls), encoding="utf-8")
    return found, targets


def single_requests(db, texts, ledger, model, run_id):
    rest = [rid for rid, in db.execute(
        "SELECT review_id FROM reviews WHERE in_scope=1 AND status='quarantined' AND reason LIKE 'enrich_failed:%'")]
    if not rest:
        return {}
    e = enrich.Enricher(db, ledger, common.OUT / "calls.jsonl", model, run_id=run_id,
                        log_path=common.OUT / "run_log.jsonl")
    e._texts = texts
    e.set_meta("phase", "resume")
    work = [(rid, texts[rid], 2) for rid in rest]
    reqs, meta = [], {}
    for gi, (rid, text, att) in enumerate(work):  # one review per request
        r1, m1 = e.build_requests([(rid, text, att)], f"{run_id}-single{gi:03d}")
        reqs += r1
        meta.update(m1)
    for m in meta.values():
        m["attempt"] = 3
    reserve = sum(llm.worst_case(model, "batch", e.rates, len(e.prompt), m["payload_chars"], m["max_tokens"])
                  for m in meta.values())
    key = f"enrich:{run_id}"
    if not ledger.try_reserve(key, reserve):
        common.log("recovery", "stopped_at_cap", **ledger.summary())
        return {}
    db.execute("UPDATE reviews SET status='pending' WHERE review_id IN (%s)" % ",".join("?" * len(rest)), rest)
    batch = llm.submit_batch(e.client, reqs)
    db.execute("INSERT INTO inflight VALUES (?,?,?,?,?,?)",
               (batch.id, "enrich", "resume", time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                json.dumps({**meta, "_key": key}), reserve))
    common.log("recovery", "single_review_batch_submitted", batch_id=batch.id, requests=len(reqs))
    e.collect(batch.id)
    return {rid: db.execute("SELECT status, reason FROM reviews WHERE review_id=?", (rid,)).fetchone() for rid in rest}


def main(ledger):
    d = common.decisions()
    db = state.connect()
    texts = run.subset_texts()
    cfg = enrich.label_config(d["enrich_model"])
    before = state.status_counts(db)
    found, targets = salvage(db, texts, cfg)
    common.log("recovery", "salvaged", salvaged=len(found), of=len(targets))
    single = single_requests(db, texts, ledger, d["enrich_model"], "recovery-" + time.strftime("%Y%m%dT%H%M%S"))
    after = state.status_counts(db)
    LOG.mkdir(parents=True, exist_ok=True)
    report = {"before": before, "after": after, "salvaged": {rid: req for rid, (req, _) in found.items()},
              "single_review_results": {rid: {"status": s, "reason": r} for rid, (s, r) in single.items()},
              "ledger": ledger.summary()}
    common.write_json(LOG / "recovery_report.json", report)
    return report
