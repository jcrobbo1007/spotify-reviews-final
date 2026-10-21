"""SQLite state: per-ID status, exact-text result cache, and the shared spend ledger.

Every write that completes a batch happens in one transaction, so a crash leaves
either the whole batch committed or none of it.
"""
import hashlib
import json
import sqlite3
import time
from pathlib import Path

from . import common

SCHEMA = """
CREATE TABLE IF NOT EXISTS reviews (
  review_id TEXT PRIMARY KEY, source_sha256 TEXT NOT NULL, text_sha TEXT NOT NULL,
  in_scope INTEGER NOT NULL, work_order INTEGER, status TEXT NOT NULL,
  attempts INTEGER NOT NULL DEFAULT 0, reason TEXT, cache_source_id TEXT,
  label_config TEXT, result_json TEXT, completed_phase TEXT, completed_at TEXT);
CREATE INDEX IF NOT EXISTS reviews_status ON reviews(status, work_order);
CREATE TABLE IF NOT EXISTS text_cache (
  text_sha TEXT NOT NULL, label_config TEXT NOT NULL, source_id TEXT NOT NULL, result_json TEXT NOT NULL,
  PRIMARY KEY (text_sha, label_config));
CREATE TABLE IF NOT EXISTS inflight (
  batch_id TEXT PRIMARY KEY, role TEXT NOT NULL, phase TEXT NOT NULL, submitted_at TEXT NOT NULL,
  requests_json TEXT NOT NULL, reserved_usd REAL NOT NULL);
"""

LEDGER_SCHEMA = """
CREATE TABLE IF NOT EXISTS spend (
  request_id TEXT PRIMARY KEY, experiment TEXT NOT NULL, role TEXT NOT NULL, usd REAL NOT NULL, ts TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS reservations (
  key TEXT PRIMARY KEY, experiment TEXT NOT NULL, usd REAL NOT NULL, ts TEXT NOT NULL);
"""


def text_sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def connect(path=None):
    path = Path(path or common.STATE / "pipeline.sqlite")
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, isolation_level=None)
    db.execute("PRAGMA journal_mode=WAL")
    db.executescript(SCHEMA)
    return db


def seed(db, rows, in_scope_ids, work_order=None):
    """Insert every source row once. Out-of-scope rows are recorded, never dropped."""
    order = work_order or {}
    db.execute("BEGIN")
    for r in rows:
        empty = not r["review_text"].strip()
        scope = r["review_id"] in in_scope_ids
        if empty:
            status, reason = "quarantined", "empty_review_text"
        elif scope:
            status, reason = "pending", None
        else:
            status, reason = "not_in_model_scope", "sampled_out_of_declared_subset"
        db.execute("INSERT OR IGNORE INTO reviews(review_id, source_sha256, text_sha, in_scope, work_order, status, reason)"
                   " VALUES (?,?,?,?,?,?,?)",
                   (r["review_id"], common.row_sha(r), text_sha(r["review_text"]), int(scope),
                    order.get(r["review_id"]), status, reason))
    db.execute("COMMIT")


def status_counts(db):
    return {s: n for s, n in db.execute("SELECT status, COUNT(*) FROM reviews GROUP BY status")}


def completed_ids(db):
    return [r[0] for r in db.execute("SELECT review_id FROM reviews WHERE status='completed' ORDER BY review_id")]


class Ledger:
    """One spend ledger shared by every experiment and worker (state/ledger.sqlite)."""

    def __init__(self, cap_usd, experiment, path=None):
        self.cap = cap_usd
        self.experiment = experiment
        p = Path(path or common.STATE / "ledger.sqlite")
        p.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(p, isolation_level=None)
        self.db.executescript(LEDGER_SCHEMA)

    def spent(self):
        return self.db.execute("SELECT COALESCE(SUM(usd),0) FROM spend").fetchone()[0]

    def reserved(self):
        return self.db.execute("SELECT COALESCE(SUM(usd),0) FROM reservations").fetchone()[0]

    def try_reserve(self, key, usd):
        """Admit work only if spent + reserved + this reservation stays within the cap."""
        self.db.execute("BEGIN IMMEDIATE")
        total = self.spent() + self.reserved() + usd
        if total > self.cap:
            self.db.execute("ROLLBACK")
            return False
        self.db.execute("INSERT INTO reservations VALUES (?,?,?,?)", (key, self.experiment, usd, _now()))
        self.db.execute("COMMIT")
        return True

    def settle(self, key, charges):
        """Replace a reservation with actual charges [(request_id, role, usd), ...]."""
        self.db.execute("BEGIN IMMEDIATE")
        self.db.execute("DELETE FROM reservations WHERE key=?", (key,))
        for request_id, role, usd in charges:
            self.db.execute("INSERT OR REPLACE INTO spend VALUES (?,?,?,?,?)",
                            (request_id, self.experiment, role, usd, _now()))
        self.db.execute("COMMIT")

    def summary(self):
        return {"cap_usd": self.cap, "spent_usd": round(self.spent(), 6), "reserved_usd": round(self.reserved(), 6)}


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")
