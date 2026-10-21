"""Shared paths, CSV/hash helpers and the run log. No network access here."""
import importlib.util
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "outputs"
STATE = ROOT / "state"
CONFIG = ROOT / "config"
PROMPTS = ROOT / "prompts"

_spec = importlib.util.spec_from_file_location("check_submission", ROOT / "vendor" / "check_submission.py")
checker = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(checker)

FIELDS = checker.FIELDS
TOPICS = checker.TOPICS
INTENTS = checker.INTENTS
csv_rows = checker.csv_rows
row_sha = checker.row_sha
file_sha = checker.sha


def decisions():
    return json.loads((CONFIG / "run_decisions.json").read_text(encoding="utf-8"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def append_jsonl(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
        f.flush()


def read_jsonl(path):
    path = Path(path)
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def log(stage, event, run_log=None, **fields):
    entry = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "stage": stage, "event": event, **fields}
    append_jsonl(run_log or (OUT / "run_log.jsonl"), [entry])
    print(f"[{stage}] {event} " + " ".join(f"{k}={v}" for k, v in fields.items() if not isinstance(v, (list, dict))))
    return entry
