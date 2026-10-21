"""Main staged run over the declared subset. Paid stages need --paid. Resumable.

Work order: cost_100 -> checkpoint_500 -> analysis_10000 -> golden_50 -> rest of subset,
so the 500 / 10,000 milestones are prefixes of one run under one label_config.
"""
import json
import time

from . import common, enrich, group, memo, prepare, rank, state, verify

OUT = common.OUT
SCOPES = {"500": ["cost_100.csv", "checkpoint_500.csv"],
          "10000": ["cost_100.csv", "checkpoint_500.csv", "analysis_10000.csv"],
          "subset": None}


def ordered_ids():
    order, seen = [], set()
    for name in ["cost_100.csv", "checkpoint_500.csv", "analysis_10000.csv", prepare.GOLDEN]:
        for r in common.csv_rows(common.DATA / name):
            if r["review_id"] not in seen:
                seen.add(r["review_id"])
                order.append(r["review_id"])
    for r in common.csv_rows(prepare.SUBSET_CSV):
        if r["review_id"] not in seen:
            seen.add(r["review_id"])
            order.append(r["review_id"])
    return order


def ensure_state(input_csv):
    db = state.connect()
    n = db.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]
    if n == 0 or not prepare.SUBSET_CSV.exists():
        prepare.main()
    if db.execute("SELECT COUNT(*) FROM reviews WHERE work_order IS NOT NULL").fetchone()[0] == 0:
        db.execute("BEGIN")
        for i, rid in enumerate(ordered_ids()):
            db.execute("UPDATE reviews SET work_order=? WHERE review_id=?", (i, rid))
        db.execute("COMMIT")
    return db


def subset_texts():
    return {r["review_id"]: r["review_text"] for r in common.csv_rows(prepare.SUBSET_CSV)}


def scope_ids(scope):
    if SCOPES[scope] is None:
        return None
    ids = set()
    for name in SCOPES[scope]:
        ids |= {r["review_id"] for r in common.csv_rows(common.DATA / name)}
    return ids


def enrich_stage(scope, ledger, requests_per_wave, stop_after_waves=None):
    d = common.decisions()
    db = ensure_state(None)
    enrich.REQUESTS_PER_WAVE = requests_per_wave
    e = enrich.Enricher(db, ledger, OUT / "calls.jsonl", d["enrich_model"], tier="batch",
                        run_id=f"main-{scope}-" + time.strftime("%Y%m%dT%H%M%S"))
    t0 = time.time()
    counts = e.run(subset_texts(), scope_ids(scope), stop_after_waves)
    common.log("run", "enrich_stage_done", scope=scope, wall_s=round(time.time() - t0, 1), **counts)
    if e.meta("checkpoint_before_written") == "1" and e.meta("checkpoint_after_written") != "1":
        ids = state.completed_ids(db)
        common.write_json(OUT / "checkpoint_after.json",
                          {"completed_ids": ids, "taken_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                           "note": f"after resuming and finishing the {scope} stage"})
        e.set_meta("checkpoint_after_written", "1")
        common.log("run", "checkpoint_after_written", completed=len(ids))
    return counts


def completed_records(db):
    return {rid: json.loads(res) for rid, res in
            db.execute("SELECT review_id, result_json FROM reviews WHERE status='completed' AND in_scope=1")}


def downstream(ledger, scope_note):
    """Verify -> group -> rank -> memo over completed subset records."""
    d = common.decisions()
    db = state.connect()
    texts = subset_texts()
    records = completed_records(db)
    cache_dir = OUT / "artifact_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    run_id = "main-downstream-" + time.strftime("%Y%m%dT%H%M%S")
    calls = OUT / "calls.jsonl"
    # Verify: one per distinct text among completed originals (not cache aliases).
    originals = sorted(rid for rid, in db.execute(
        "SELECT review_id FROM reviews WHERE status='completed' AND in_scope=1 AND cache_source_id IS NULL"))
    ids = verify.sample(originals, d["verifier_sample_size"], d["verifier_sample_seed"])
    vdir = common.ROOT / "evals" / "verify"
    vdir.mkdir(parents=True, exist_ok=True)
    cached = cache_dir / "verify_predictions.json"
    if cached.exists() and json.loads(cached.read_text(encoding="utf-8"))["sample_ids"] == ids:
        preds = json.loads(cached.read_text(encoding="utf-8"))["predictions"]
    else:
        res = verify.run(ids, texts, ledger, calls, cache_dir, d["verify_model"], run_id)
        preds = res[0] if res else {}
    vsum = verify.compare(records, preds, vdir)
    pairs = group.build_membership(records, texts)
    group.write_membership(pairs, OUT / "membership.csv")
    pack = group.evidence_pack(pairs, records)
    common.write_json(OUT / "issues_evidence_pack.json", pack)
    names, _ = group.name_issues(pack, ledger, calls, d["group_naming_model"], run_id, cache_dir=cache_dir)
    group.write_issues(pairs, names, OUT / "issues.csv")
    ranking = rank.from_files(OUT / "membership.csv", write_records(db), OUT / "ranking.csv")
    agg = memo.aggregates(records, ranking)
    memo.write_aggregates(agg, OUT / "aggregates.csv")
    mpack = memo.evidence_pack(ranking, pairs, records)
    out, _ = memo.run(ranking, agg, mpack, scope_note, ledger, calls, d["memo_model"], run_id, cache_dir=cache_dir)
    if out:
        memo.write_outputs(out, OUT / "memo.md", OUT / "claims.csv")
        common.write_json(OUT / "memo_inputs.json", out["inputs"])
        common.write_json(OUT / "memo_output.json", {k: v for k, v in out.items() if k != "inputs"})
    return vsum, ranking, out


def write_records(db):
    """enriched.jsonl / quarantine.jsonl / records.jsonl over the subset (contract statuses only)."""
    rec_path = OUT / "records.jsonl"
    enriched, quarantine, allrec = [], [], []
    for rid, sha, status, reason, src, cfg, res, att in db.execute(
            "SELECT review_id, source_sha256, status, reason, cache_source_id, label_config, result_json, attempts"
            " FROM reviews WHERE in_scope=1 ORDER BY work_order"):
        if status == "completed":
            r = {"review_id": rid, "source_sha256": sha, "status": "completed", **json.loads(res), "label_config": cfg}
            if src:
                r["cache_source_id"] = src
            enriched.append(r)
        else:
            r = {"review_id": rid, "source_sha256": sha, "status": "quarantined",
                 "reason": reason or f"unfinished:{status}", "attempts": att}
            quarantine.append(r)
        allrec.append(r)
    for path, rows in ((OUT / "enriched.jsonl", enriched), (OUT / "quarantine.jsonl", quarantine), (rec_path, allrec)):
        path.write_text("".join(json.dumps(x, ensure_ascii=False, separators=(",", ":")) + "\n" for x in rows),
                        encoding="utf-8")
    return rec_path
