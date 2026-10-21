"""Load saved pipeline outputs into Postgres (Supabase). Reads DATABASE_URL from .env.

  python db/load.py            # schema + truncate + load from outputs/
No model calls. The connection string is never printed.
"""
import csv
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "outputs"


def rows_csv(name):
    with open(OUT / name, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def main():
    from dotenv import load_dotenv
    import psycopg
    load_dotenv(ROOT / ".env")
    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("DATABASE_URL missing in .env")
    src = {}
    subset = OUT / "scope" / "subset_100000.csv"
    for p in sorted((OUT / "scope").glob("subset_*.csv")):
        subset = p
    with open(subset, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            src[r["review_id"]] = (r["review_rating"], r["review_timestamp"], r["app_version"])
    with psycopg.connect(url) as conn, conn.cursor() as cur:
        cur.execute((ROOT / "db" / "schema.sql").read_text(encoding="utf-8"))
        cur.execute("truncate records, issues, membership, ranking, aggregates, claims, memo, run_summary")
        with cur.copy("copy records (review_id, source_sha256, status, reason, topic, intent, severity, sentiment,"
                      " entities, evidence_quote, needs_review, label_config, cache_source_id, review_rating,"
                      " review_timestamp, app_version) from stdin") as cp:
            for line in open(OUT / "records.jsonl", encoding="utf-8"):
                r = json.loads(line)
                rating, ts, ver = src.get(r["review_id"], (None, None, None))
                cp.write_row([r["review_id"], r["source_sha256"], r["status"], r.get("reason"), r.get("topic"),
                              r.get("intent"), r.get("severity"), r.get("sentiment"),
                              json.dumps(r.get("entities")) if "entities" in r else None, r.get("evidence_quote"),
                              r.get("needs_review"), r.get("label_config"), r.get("cache_source_id"), rating, ts, ver])
        for table, name, cols in [
            ("issues", "issues.csv", ["issue_id", "topic", "subtopic", "name", "description", "member_count", "map_version"]),
            ("membership", "membership.csv", ["issue_id", "review_id"]),
            ("ranking", "ranking.csv", ["rank", "issue_id", "complaint_count", "severity_sum", "mean_severity", "priority_score"]),
            ("aggregates", "aggregates.csv", ["topic", "records", "complaint_or_cancellation", "cancellation", "severity_sum", "severity_4_plus", "needs_review"]),
            ("claims", "claims.csv", ["claim_id", "issue_id", "metric", "value"])]:
            with cur.copy(f"copy {table} ({', '.join(cols)}) from stdin") as cp:
                for r in rows_csv(name):
                    cp.write_row([r[c] for c in cols])
        m = json.loads((OUT / "memo_output.json").read_text(encoding="utf-8"))
        cur.execute("insert into memo values (1, %s, %s, %s)",
                    (m["recommendation"], m["memo_markdown"], json.dumps(m["cited_review_ids"])))
        summary = json.loads((OUT / "run_summary.json").read_text(encoding="utf-8"))
        for k, v in summary.items():
            cur.execute("insert into run_summary values (%s, %s)", (k, json.dumps(v)))
        for t in ("records", "issues", "membership", "ranking", "claims"):
            cur.execute(f"select count(*) from {t}")
            print(t, cur.fetchone()[0])


if __name__ == "__main__":
    main()
