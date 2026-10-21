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
    with open(src, "rb") as f, gzip.open(dst, "wb", compresslevel=9, mtime=0) as g:
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
