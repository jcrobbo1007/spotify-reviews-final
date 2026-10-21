"""Grading export (GRADING_CONTRACT.md) + run_summary. Code only, no model calls.

The checker's --analysis input is the declared subset CSV, so grading/records.jsonl.gz
holds exactly those IDs with contract statuses. Full-corpus accounting (including
not_in_model_scope rows) is written separately to outputs/full_corpus_accounting.jsonl.gz.
"""
import gzip
import json
import shutil
import subprocess
import sys

from . import common, prepare, state

GRADING = common.ROOT / "grading"


def gz_copy(src, dst):
    with open(src, "rb") as f, open(dst, "wb") as raw, \
            gzip.GzipFile(fileobj=raw, mode="wb", compresslevel=9, mtime=0) as g:
        shutil.copyfileobj(f, g)


def main():
    OUT = common.OUT
    GRADING.mkdir(exist_ok=True)
    d = common.decisions()
    run = {"version": "a5-audit-v1", "analysis_count": d["scope"]["subset_size"],
           "analysis_sha256": common.file_sha(prepare.SUBSET_CSV), "classification_input_fields": ["review_text"],
           "allow_multi_issue": False,
           "scope_note": d["scope"]["label"], "analysis_file": str(prepare.SUBSET_CSV.relative_to(common.ROOT).as_posix()),
           "full_input_sha256": common.file_sha(prepare.FULL_CSV), "full_input_rows": 660622}
    common.write_json(GRADING / "run.json", run)
    profile = common.checker.profile(prepare.FULL_CSV)
    common.checker.write_json(GRADING / "ingestion.json", profile)
    for name in ("records.jsonl", "calls.jsonl"):
        gz_copy(OUT / name, GRADING / (name + ".gz"))
        (GRADING / name).unlink(missing_ok=True)
    for name in ("membership.csv", "ranking.csv", "claims.csv"):
        shutil.copyfile(OUT / name, GRADING / name)
    for name in ("checkpoint_before.json", "checkpoint_after.json"):
        if (OUT / name).exists():
            shutil.copyfile(OUT / name, GRADING / name)
    # Full-corpus accounting: every one of the 660,622 IDs with its status.
    db = state.connect()
    acc = OUT / "full_corpus_accounting.jsonl.gz"
    with gzip.open(acc, "wt", encoding="utf-8", compresslevel=9) as f:
        for rid, sha, status, reason, att in db.execute(
                "SELECT review_id, source_sha256, status, reason, attempts FROM reviews ORDER BY review_id"):
            f.write(json.dumps({"review_id": rid, "source_sha256": sha, "status": status,
                                **({"reason": reason} if reason and status != "completed" else {}),
                                "attempts": att}, separators=(",", ":")) + "\n")
    return run


def run_summary():
    """All figures recomputed from saved state/files; written to outputs/run_summary.json."""
    import sqlite3
    d = common.decisions()
    db = state.connect()
    q = lambda sql: db.execute(sql).fetchone()[0]
    counts = {
        "source_rows": q("SELECT COUNT(*) FROM reviews"),
        "subset_rows": q("SELECT COUNT(*) FROM reviews WHERE in_scope=1"),
        "completed": q("SELECT COUNT(*) FROM reviews WHERE status='completed'"),
        "quarantined_subset": q("SELECT COUNT(*) FROM reviews WHERE status='quarantined' AND in_scope=1"),
        "empty_text_quarantines": q("SELECT COUNT(*) FROM reviews WHERE reason='empty_review_text'"),
        "not_in_model_scope": q("SELECT COUNT(*) FROM reviews WHERE status='not_in_model_scope'"),
        "pending": q("SELECT COUNT(*) FROM reviews WHERE status='pending'"),
        "cache_reused_rows": q("SELECT COUNT(*) FROM reviews WHERE status='completed' AND cache_source_id IS NOT NULL"),
        "model_classified_distinct_texts": q("SELECT COUNT(*) FROM reviews WHERE status='completed' AND cache_source_id IS NULL"),
        "needs_review": q("SELECT COUNT(*) FROM reviews WHERE status='completed' AND json_extract(result_json,'$.needs_review')=1"),
    }
    quarantine_reasons = dict(db.execute("SELECT reason, COUNT(*) FROM reviews WHERE status='quarantined' GROUP BY reason"))
    quote_sources = dict(db.execute("SELECT json_extract(result_json,'$.quote_source'), COUNT(*) FROM reviews"
                                    " WHERE status='completed' GROUP BY 1"))
    led = sqlite3.connect(common.STATE / "ledger.sqlite")
    by_exp = {e: round(u, 6) for e, u in led.execute("SELECT experiment, SUM(usd) FROM spend GROUP BY experiment")}
    by_role = {r: round(u, 6) for r, u in led.execute("SELECT role, SUM(usd) FROM spend GROUP BY role")}
    total = round(led.execute("SELECT SUM(usd) FROM spend").fetchone()[0], 6)
    calls = common.read_jsonl(common.OUT / "calls.jsonl")
    vs = common.ROOT / "evals" / "verify" / "verify_summary.json"
    summary = {
        "scope_label": d["scope"]["label"],
        "scope_detail": f"All 660,622 source rows accounted for; {d['scope']['subset_size']:,} classified (seeded subset). "
                        "Not a full-corpus model run; counts are subset counts.",
        "counts": counts, "quarantine_reasons": quarantine_reasons, "quote_sources": quote_sources,
        "cost": {"api_spend_usd": total, "cap_usd": d["spend_cap_usd"], "by_experiment": by_exp, "by_role": by_role,
                 "measured": "ledger of actual usage x rates.csv; includes all pilot attempts and tests"},
        "main_run_calls": {"total": len(calls), "by_role": dict(__import__("collections").Counter(c["role"] for c in calls)),
                           "failed": sum(c["outcome"] == "failed" for c in calls)},
        "verification": json.loads(vs.read_text()) if vs.exists() else None,
        "model": d["enrich_model"], "label_config": calls[0]["label_config"] if calls else None,
    }
    common.write_json(common.OUT / "run_summary.json", summary)
    return summary


def checker(out_path=None):
    """Run the provided zero-API self-check; reports stay outside grading/."""
    ev = common.ROOT / "evals" / "checker"
    ev.mkdir(parents=True, exist_ok=True)
    py, chk = sys.executable, str(common.ROOT / "vendor" / "check_submission.py")
    ref = ev / "local-reference.json"
    cmds = [[py, chk, "reference", "--full", str(prepare.FULL_CSV), "--analysis", str(prepare.SUBSET_CSV), "--out", str(ref)],
            [py, chk, "check", "--reference", str(ref), "--submission", str(GRADING), "--out", str(ev / "self-check.json")]]
    log = []
    for c in cmds:
        p = subprocess.run(c, capture_output=True, text=True, encoding="utf-8")
        log.append({"cmd": " ".join(x.replace(str(common.ROOT), ".") for x in c), "returncode": p.returncode,
                    "stdout": p.stdout[-4000:], "stderr": p.stderr[-4000:]})
    (ev / "checker_output.txt").write_text("\n\n".join(f"$ {x['cmd']}\n{x['stdout']}{x['stderr']}" for x in log),
                                          encoding="utf-8")
    ref.unlink(missing_ok=True)  # large; regenerable from the CSVs
    return json.loads((ev / "self-check.json").read_text(encoding="utf-8"))
