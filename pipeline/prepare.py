"""Stage 1 - Prepare (code only).

Reads the full CSV with the checker's multiline-safe reader, verifies counts against
the brief, writes data_manifest.json / ingestion_report.json, builds the declared
100,000-review subset CSV, and seeds the SQLite state with every source ID.
"""
import csv
import hashlib
import io
from collections import Counter

from . import common, state

BRIEF = {"records": 660622, "empty_review_text": 13, "missing_app_version": 159701,
         "duplicate_review_ids": 0, "distinct_nonempty_texts": 484189}
FULL_CSV = common.DATA / "spotify_reviews_18months.csv"
SUBSET_CSV = common.OUT / "scope" / f"subset_{common.decisions()['scope']['subset_size']}.csv"
DEV_FILES = ["analysis_10000.csv", "checkpoint_500.csv", "cost_100.csv"]
GOLDEN = "golden_50_to_label.csv"


def load_full():
    return list(common.csv_rows(FULL_CSV))


def ingest():
    rows = load_full()
    ids = Counter(r["review_id"] for r in rows)
    texts = Counter(r["review_text"] for r in rows if r["review_text"].strip())
    dup_text_rows = sum(c for c in texts.values() if c > 1)
    profile = {
        "records": len(rows),
        "duplicate_review_ids": sum(c - 1 for c in ids.values() if c > 1),
        "empty_review_text": sum(1 for r in rows if not r["review_text"].strip()),
        "missing_app_version": sum(1 for r in rows if not r["app_version"].strip()),
        "distinct_nonempty_texts": len(texts),
        "rows_with_exact_duplicate_text": dup_text_rows,
        "first_review": min(r["review_timestamp"] for r in rows),
        "last_review": max(r["review_timestamp"] for r in rows),
        "reviews_by_rating": dict(sorted(Counter(r["review_rating"] for r in rows).items())),
        "reviews_by_month": dict(sorted(Counter(r["review_timestamp"][:7] for r in rows).items())),
        "missing_by_field": {f: sum(1 for r in rows if not r[f].strip()) for f in common.FIELDS},
    }
    checks = {k: {"brief": v, "actual": profile[k], "match": profile[k] == v} for k, v in BRIEF.items()}
    report = {"input": str(FULL_CSV.relative_to(common.ROOT)), "sha256": common.file_sha(FULL_CSV),
              "profile": profile, "brief_checks": checks, "all_match": all(c["match"] for c in checks.values())}
    common.write_json(common.OUT / "ingestion_report.json", report)
    manifest = {"files": {}}
    for name in ["spotify_reviews_18months.csv", GOLDEN, *DEV_FILES]:
        p = common.DATA / name
        manifest["files"][name] = {"bytes": p.stat().st_size, "sha256": common.file_sha(p)}
    manifest["source_manifest_sha256"] = common.file_sha(common.DATA / "manifest.json")
    common.write_json(common.OUT / "data_manifest.json", manifest)
    common.log("prepare", "ingested", records=len(rows), all_match=report["all_match"])
    return rows, report


def build_subset(rows):
    d = common.decisions()["scope"]
    size, seed = d["subset_size"], d["subset_seed"]
    fixed = []
    for name in [GOLDEN, "analysis_10000.csv"]:
        fixed += [r["review_id"] for r in common.csv_rows(common.DATA / name)]
    fixed_set = set(fixed)
    pool = [r for r in rows if r["review_text"].strip() and r["review_id"] not in fixed_set]
    pool.sort(key=lambda r: hashlib.sha256(f"{seed}:{r['review_id']}".encode()).hexdigest())
    chosen = fixed_set | {r["review_id"] for r in pool[: size - len(fixed_set)]}
    subset = [r for r in rows if r["review_id"] in chosen]  # keep source order
    assert len(subset) == size, len(subset)
    SUBSET_CSV.parent.mkdir(parents=True, exist_ok=True)
    buf = io.StringIO(newline="")
    w = csv.DictWriter(buf, fieldnames=list(common.FIELDS), lineterminator="\n")
    w.writeheader()
    w.writerows(subset)
    SUBSET_CSV.write_bytes(buf.getvalue().encode("utf-8"))
    info = {"path": str(SUBSET_CSV.relative_to(common.ROOT)), "rows": len(subset), "seed": seed,
            "sha256": common.file_sha(SUBSET_CSV), "fixed_members": len(fixed_set),
            "random_members": len(subset) - len(fixed_set),
            "distinct_texts": len({r["review_text"] for r in subset})}
    common.write_json(common.OUT / "scope" / "subset_manifest.json", info)
    common.log("prepare", "subset_built", **info)
    return subset, info


def main():
    rows, report = ingest()
    subset, info = build_subset(rows)
    db = state.connect()
    state.seed(db, rows, {r["review_id"] for r in subset})
    counts = state.status_counts(db)
    common.log("prepare", "state_seeded", **counts)
    return report, info, counts
