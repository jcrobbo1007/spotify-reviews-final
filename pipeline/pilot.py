"""The 100-review cold/warm pilot (COST_CALCULATOR.md section 2). Paid only with --paid.

Cold: empty result cache, one worker, cost_100.csv unchanged. Warm: fresh run state,
same saved result cache and settings -> expect zero new enrichment calls.
"""
import json
import shutil
import time

from . import common, enrich, group, memo, rank, state, verify

COST = common.ROOT / "cost"
PILOT_CSV = common.DATA / "cost_100.csv"
EXPECTED_SHA = "c884ac3b9be5066995d5063f96ad9af6e5e082975788c1684c4f6b6ea661dd0e"


def _setup(db_path, fresh):
    if fresh and db_path.exists():
        for suffix in ("", "-wal", "-shm"):
            p = db_path.with_name(db_path.name + suffix)
            if p.exists():
                p.unlink()
    rows = list(common.csv_rows(PILOT_CSV))
    db = state.connect(db_path)
    state.seed(db, rows, {r["review_id"] for r in rows}, {r["review_id"]: i for i, r in enumerate(rows)})
    return db, rows


def stage_timer(timings, name):
    class T:
        def __enter__(self):
            self.t = time.time()
            self.wall_start = time.strftime("%Y-%m-%dT%H:%M:%S%z")

        def __exit__(self, *a):
            timings[name] = {"wall_s": round(time.time() - self.t, 3), "started": self.wall_start,
                             "ended": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    return T()


def run(mode, stages, ledger):
    assert common.file_sha(PILOT_CSV) == EXPECTED_SHA, "cost_100.csv checksum mismatch"
    d = common.decisions()
    model = d["enrich_model"]
    db_path = common.STATE / f"pilot_{mode}.sqlite"
    # warm always starts from fresh run state (only the saved result cache is copied in)
    fresh = mode == "warm" or ("enrich" in stages and not (COST / "pilot_cold_timings.json").exists())
    db, rows = _setup(db_path, fresh=fresh)
    texts = {r["review_id"]: r["review_text"] for r in rows}
    run_log = COST / f"pilot_{mode}_run_log.jsonl"
    calls = COST / "pilot_calls.jsonl"
    timings_path = COST / f"pilot_{mode}_timings.json"
    timings = json.loads(timings_path.read_text()) if timings_path.exists() and mode == "cold" else {}
    if mode == "warm":
        cold = state.connect(common.STATE / "pilot_cold.sqlite")
        db.execute("BEGIN")
        for row in cold.execute("SELECT * FROM text_cache"):
            db.execute("INSERT OR IGNORE INTO text_cache VALUES (?,?,?,?)", row)
        db.execute("COMMIT")
    run_id = f"pilot-{mode}-" + time.strftime("%Y%m%dT%H%M%S")
    if "enrich" in stages:
        e = enrich.Enricher(db, ledger, calls, model, tier="batch", run_id=run_id, log_path=run_log)
        before_calls = len(common.read_jsonl(calls))
        with stage_timer(timings, "enrich"):
            counts = e.run(texts)
        new_calls = len(common.read_jsonl(calls)) - before_calls
        timings["enrich"].update({"new_calls": new_calls, "counts": counts, "label_config": e.cfg,
                                  "run_id": run_id})
        common.log("pilot", f"{mode}_enrich_done", run_log, new_calls=new_calls, **counts)
    if mode == "cold" and "enrich" in stages:
        export_records(db, rows)
    records = {r[0]: json.loads(r[1]) for r in db.execute(
        "SELECT review_id, result_json FROM reviews WHERE status='completed'")}
    work = COST / f"pilot_{mode}"
    work.mkdir(exist_ok=True)
    cache_dir = COST / "pilot_artifact_cache"
    cache_dir.mkdir(exist_ok=True)
    if "verify" in stages:
        with stage_timer(timings, "verify"):
            ids = verify.sample(sorted(records), PILOT_VERIFY_N, d["verifier_sample_seed"])
            cached = cache_dir / "verify_predictions.json"
            if cached.exists() and json.loads(cached.read_text())["sample_ids"] == ids:
                preds = json.loads(cached.read_text())["predictions"]
                common.log("verify", "cache_hit", run_log, sample=len(ids))
                timings_calls = 0
            else:
                preds, cfg, _ = verify.run(ids, texts, ledger, calls, cache_dir, d["verify_model"], run_id, run_log)
                timings_calls = 1
            summary = verify.compare(records, preds, work)
        timings["verify"].update({"sample": len(ids), "new_calls": timings_calls, **summary})
    pairs = group.build_membership(records, texts)
    if "group" in stages:
        with stage_timer(timings, "group"):
            group.write_membership(pairs, work / "membership.csv")
            pack = group.evidence_pack(pairs, records)
            common.write_json(work / "issues_evidence_pack.json", pack)
            names, n = group.name_issues(pack, ledger, calls, d["group_naming_model"], run_id, run_log, cache_dir)
            group.write_issues(pairs, names, work / "issues.csv")
        timings["group"].update({"issues": len({i for i, _ in pairs}), "members": len(pairs), "new_calls": n})
    ranking = rank.compute(pairs, {rid: r["severity"] for rid, r in records.items()})
    if "rank" in stages:
        with stage_timer(timings, "rank"):
            rank.write(ranking, work / "ranking.csv")
        timings["rank"]["issues"] = len(ranking)
    if "memo" in stages:
        with stage_timer(timings, "memo"):
            agg = memo.aggregates(records, ranking)
            memo.write_aggregates(agg, work / "aggregates.csv")
            mpack = memo.evidence_pack(ranking, pairs, records)
            out, n = memo.run(ranking, agg, mpack, "100-review cost pilot (cost_100.csv); counts are pilot counts",
                              ledger, calls, d["memo_model"], run_id, run_log, cache_dir)
            if out:
                memo.write_outputs(out, work / "memo.md", work / "claims.csv")
        timings["memo"]["new_calls"] = n
    common.write_json(timings_path, timings)
    return timings


PILOT_VERIFY_N = 50


def export_records(db, rows):
    out = []
    by_id = {r[0]: r for r in db.execute(
        "SELECT review_id, source_sha256, status, reason, cache_source_id, label_config, result_json, attempts FROM reviews")}
    for r in rows:
        rid, sha, status, reason, src, cfg, res, att = by_id[r["review_id"]]
        if status == "completed":
            rec = {"review_id": rid, "source_sha256": sha, "status": "completed", **json.loads(res),
                   "label_config": cfg, "attempts": att}
            if src:
                rec["cache_source_id"] = src
        else:
            rec = {"review_id": rid, "source_sha256": sha, "status": "quarantined" if status == "quarantined" else status,
                   "reason": reason or status, "attempts": att}
        out.append(rec)
    p = COST / "pilot_records.jsonl"
    p.write_text("".join(json.dumps(x, ensure_ascii=False, separators=(",", ":")) + "\n" for x in out), encoding="utf-8")
