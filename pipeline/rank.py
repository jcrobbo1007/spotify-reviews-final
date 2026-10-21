"""Stage 5 - Rank (code only, no model, no key). Byte-identical on rerun.

priority_score = severity_sum = complaint_count x mean_severity (integer arithmetic).
Order: descending score, then ascending issue_id. Mean: six decimals, half-up.
"""
import csv
import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

COLUMNS = ["rank", "issue_id", "complaint_count", "severity_sum", "mean_severity", "priority_score"]


def mean_string(total, count):
    return str((Decimal(total) / Decimal(count)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))


def compute(membership_rows, severity):
    """membership_rows: [(issue_id, review_id)]; severity: {review_id: int}."""
    agg = {}
    for iid, rid in membership_rows:
        a = agg.setdefault(iid, [0, 0])
        a[0] += 1
        a[1] += severity[rid]
    rows = [{"issue_id": iid, "complaint_count": n, "severity_sum": s, "mean_severity": mean_string(s, n),
             "priority_score": s} for iid, (n, s) in agg.items()]
    rows.sort(key=lambda r: (-r["priority_score"], r["issue_id"]))
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return rows


def write(rows, path):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(COLUMNS)
        for r in rows:
            w.writerow([str(r[c]) for c in COLUMNS])


def read_membership(path):
    with open(path, encoding="utf-8", newline="") as f:
        return [(r["issue_id"], r["review_id"]) for r in csv.DictReader(f)]


def read_severity(records_path):
    import gzip
    sev = {}
    opener = gzip.open if str(records_path).endswith(".gz") else open
    with opener(records_path, "rt", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r.get("status") == "completed":
                sev[r["review_id"]] = r["severity"]
    return sev


def from_files(membership_path, records_path, out_path):
    rows = compute(read_membership(membership_path), read_severity(records_path))
    write(rows, out_path)
    return rows
