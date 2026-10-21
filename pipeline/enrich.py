"""Stage 2 - Enrich (small model + code validation), via the Message Batches API.

Flow per wave: pick pending distinct texts in work order -> chunk (<=50/request) ->
reserve worst-case spend -> submit one batch -> poll -> validate every item in code ->
commit valid results atomically and fan them out to identical texts -> invalid items
retry once in a later wave -> quarantine with reason.
"""
import difflib
import hashlib
import json
import re
import time

from . import common, llm, state

PROMPT_PATH = common.PROMPTS / "enrich_v1.md"
SCHEMA_VERSION = "schema_v1"
SHORT_CHARS = 200          # code uses the whole text as evidence_quote at or below this length
MAX_ATTEMPTS = 2           # first try + one retry, then quarantine
REVIEWS_PER_REQUEST = 50
OUT_TOKENS_PER_REVIEW = 70
REQUESTS_PER_WAVE = 100

ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "tp": {"type": "string", "enum": list(common.TOPICS)},
        "in": {"type": "string", "enum": list(common.INTENTS)},
        "sv": {"type": "integer", "enum": [1, 2, 3, 4, 5]},
        "se": {"type": "number"},
        "en": {"type": "array", "items": {"type": "string"}},
        "q": {"type": "string"},
        "nr": {"type": "boolean"},
    },
    "required": ["id", "tp", "in", "sv", "se", "en", "q", "nr"],
    "additionalProperties": False,
}
SCHEMA = {"type": "object", "properties": {"r": {"type": "array", "items": ITEM_SCHEMA}},
          "required": ["r"], "additionalProperties": False}


def prompt_text():
    return PROMPT_PATH.read_text(encoding="utf-8")


def label_config(model, effort="low"):
    p = hashlib.sha256(prompt_text().encode("utf-8")).hexdigest()[:8]
    return f"{model}+enrich_v1.{p}+{SCHEMA_VERSION}+effort-{effort}+thinking-off+short{SHORT_CHARS}+{QUOTE_RULE}"


QUOTE_RULE = "qrepair1+lengthgroups"
MIN_REPAIR_SPAN = 12


def repair_quote(quote, text):
    """Deterministic code repair when the model's quote is not an exact substring.

    1) the longest exactly matching span between the model quote and the source (>= 12 chars);
    2) otherwise the opening of the source cut at a word boundary (<= 200 chars).
    Either way the result is an exact source substring; the caller marks needs_review.
    """
    if isinstance(quote, str) and quote.strip():
        sm = difflib.SequenceMatcher(None, text, quote, autojunk=False)
        m = sm.find_longest_match(0, len(text), 0, len(quote))
        span = text[m.a:m.a + m.size].strip()
        if len(span) >= MIN_REPAIR_SPAN and span in text:
            return span, "code_repair_span"
    head = text[:SHORT_CHARS]
    if len(text) > SHORT_CHARS and " " in head:
        head = head[:head.rfind(" ")]
    head = head.strip()
    return (head if head else text), "code_repair_head"


def validate_item(item, text):
    """Return (record_fields, None) or (None, reason). Code is the final authority on schema."""
    try:
        if item["tp"] not in common.TOPICS:
            return None, "invalid_topic"
        if item["in"] not in common.INTENTS:
            return None, "invalid_intent"
        sv = item["sv"]
        if type(sv) is not int or not 1 <= sv <= 5:
            return None, "invalid_severity"
        se = item["se"]
        if type(se) not in (int, float) or not -1 <= se <= 1:
            return None, "invalid_sentiment"
        en = item["en"]
        if not isinstance(en, list) or not all(isinstance(x, str) and x.strip() for x in en):
            return None, "invalid_entities"
        if type(item["nr"]) is not bool:
            return None, "invalid_needs_review"
        needs_review = item["nr"]
        if len(text) <= SHORT_CHARS:
            quote, qsrc = text, "code_short_full_text"
        elif isinstance(item["q"], str) and item["q"].strip() and item["q"] in text:
            quote, qsrc = item["q"], "model_exact"
        else:
            quote, qsrc = repair_quote(item["q"], text)
            needs_review = True
        return {"topic": item["tp"], "intent": item["in"], "sentiment": round(float(se), 2), "severity": sv,
                "entities": [x.strip() for x in en][:5], "evidence_quote": quote, "needs_review": needs_review,
                "quote_source": qsrc}, None
    except (KeyError, TypeError):
        return None, "missing_fields"


def parse_response(text, sent):
    """sent: {local_id: review_text}. Returns ({local_id: fields}, {local_id: reason})."""
    good, bad = {}, {}
    try:
        items = json.loads(text)["r"]
        assert isinstance(items, list)
    except Exception:
        return {}, {k: "unparseable_response" for k in sent}
    seen = set()
    for item in items:
        lid = item.get("id") if isinstance(item, dict) else None
        if lid not in sent or lid in seen:
            continue  # unknown or duplicate ids are ignored, never trusted
        seen.add(lid)
        fields, reason = validate_item(item, sent[lid])
        if fields:
            good[lid] = fields
        else:
            bad[lid] = reason
    for lid in sent:
        if lid not in good and lid not in bad:
            bad[lid] = "missing_from_response"
    return good, bad


class Enricher:
    def __init__(self, db, ledger, calls_path, model, tier="batch", run_id=None, log_path=None):
        self.db, self.ledger, self.calls_path = db, ledger, calls_path
        self.model, self.tier = model, tier
        self.rates = llm.load_rates()
        self.cfg = label_config(model)
        self.prompt = prompt_text()
        self.run_id = run_id or time.strftime("run-%Y%m%dT%H%M%S")
        self.log_path = log_path
        self._client = None
        db.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")

    # --- run phase bookkeeping (initial until an unclean stop is detected, then resume) ---
    def meta(self, key, default=None):
        row = self.db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row[0] if row else default

    def set_meta(self, key, value):
        self.db.execute("INSERT OR REPLACE INTO meta VALUES (?,?)", (key, value))

    def begin(self):
        if self.meta("run_active") == "1":
            self.set_meta("phase", "resume")
            if self.meta("checkpoint_before_written") != "1":
                ids = state.completed_ids(self.db)
                common.write_json(self.calls_path.parent / "checkpoint_before.json",
                                  {"completed_ids": ids, "taken_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                                   "note": "snapshot on restart after an unclean stop; state as saved before the interruption"})
                self.set_meta("checkpoint_before_written", "1")
                common.log("enrich", "resume_detected", self.log_path, completed=len(ids))
        elif self.meta("phase") is None:
            self.set_meta("phase", "initial")
        self.set_meta("run_active", "1")
        return self.meta("phase")

    def end(self):
        self.set_meta("run_active", "0")

    @property
    def client(self):
        if self._client is None:
            self._client = llm.client()
        return self._client

    # --- cache ---
    def apply_cache(self, scope_ids=None):
        """Fan cached results out to pending rows with identical text (no API call)."""
        rows = self.db.execute(
            "SELECT r.review_id, c.source_id, c.result_json FROM reviews r JOIN text_cache c"
            " ON c.text_sha=r.text_sha AND c.label_config=? WHERE r.status='pending'", (self.cfg,)).fetchall()
        n = 0
        self.db.execute("BEGIN")
        for rid, src, res in rows:
            if scope_ids is not None and rid not in scope_ids:
                continue
            self.db.execute("UPDATE reviews SET status='completed', cache_source_id=?, label_config=?, result_json=?,"
                            " completed_phase=?, completed_at=? WHERE review_id=?",
                            (None if src == rid else src, self.cfg, res, self.meta("phase"), _now(), rid))
            n += 1
        self.db.execute("COMMIT")
        return n

    # --- work selection ---
    def pending_texts(self, texts, scope_ids, limit):
        """Distinct pending texts in work order: [(representative_id, text, attempts)]."""
        q = ("SELECT review_id, text_sha, attempts FROM reviews WHERE status='pending'"
             " ORDER BY work_order IS NULL, work_order, review_id")
        out, seen_sha, inflight = [], set(), self.inflight_ids()
        for rid, tsha, att in self.db.execute(q):
            if scope_ids is not None and rid not in scope_ids:
                continue
            if tsha in seen_sha or rid in inflight:
                continue
            seen_sha.add(tsha)
            out.append((rid, texts[rid], att))
            if len(out) >= limit:
                break
        return out

    def inflight_ids(self):
        ids = set()
        for (rj,) in self.db.execute("SELECT requests_json FROM inflight WHERE role='enrich'"):
            for req in json.loads(rj).values():
                ids.update(req["review_ids"])
        return ids

    # --- one wave ---
    def build_requests(self, work, wave_tag):
        reqs, meta = [], {}
        retry = [w for w in work if w[2] >= 1]
        fresh = [w for w in work if w[2] == 0]
        # retries go in smaller requests so one bad item cannot sink 50 others again
        # Long reviews go in their own requests so the model never sees a run of short items
        # (which take q="") next to items that need a quote; pilot attempts 2-3 showed it copying "".
        short = [w for w in fresh if len(w[1]) <= SHORT_CHARS]
        long_ = [w for w in fresh if len(w[1]) > SHORT_CHARS]
        groups = [short[i:i + REVIEWS_PER_REQUEST] for i in range(0, len(short), REVIEWS_PER_REQUEST)]
        groups += [long_[i:i + REVIEWS_PER_REQUEST] for i in range(0, len(long_), REVIEWS_PER_REQUEST)]
        groups += [retry[i:i + 10] for i in range(0, len(retry), 10)]
        for gi, group in enumerate(groups):
            cid = f"{wave_tag}-{gi:04d}"
            payload = [{"id": f"r{j + 1}", "t": text, **({"qn": 1} if len(text) > SHORT_CHARS else {})}
                       for j, (_, text, _) in enumerate(group)]
            user = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
            max_tokens = 100 + OUT_TOKENS_PER_REVIEW * len(group) + sum(
                40 for _, t, _ in group if len(t) > SHORT_CHARS)
            params = llm.request_params(self.model, self.prompt, user, SCHEMA, max_tokens)
            reqs.append((cid, params))
            meta[cid] = {"review_ids": [rid for rid, _, _ in group],
                         "local": {f"r{j + 1}": rid for j, (rid, _, _) in enumerate(group)},
                         "max_tokens": max_tokens, "payload_chars": len(user),
                         "attempt": max(a for _, _, a in group) + 1}
        return reqs, meta

    def run_wave(self, texts, scope_ids, max_requests=REQUESTS_PER_WAVE):
        # Resume any batch submitted before an interruption instead of resubmitting it.
        row = self.db.execute("SELECT batch_id FROM inflight WHERE role='enrich' LIMIT 1").fetchone()
        if row:
            common.log("enrich", "reconcile_inflight_batch", self.log_path, batch_id=row[0])
            return self.collect(row[0])
        work = self.pending_texts(texts, scope_ids, max_requests * REVIEWS_PER_REQUEST)
        if not work:
            return 0
        wave_tag = f"{self.run_id}-w{int(time.time())}"
        reqs, meta = self.build_requests(work, wave_tag)
        reqs = reqs[:max_requests]
        # Reserve worst-case spend per request; admit only what fits under the cap.
        admitted, reserved = [], 0.0
        for cid, params in reqs:
            wc = llm.worst_case(self.model, self.tier, self.rates, len(self.prompt), meta[cid]["payload_chars"],
                                meta[cid]["max_tokens"])
            if self.ledger.spent() + self.ledger.reserved() + reserved + wc > self.ledger.cap:
                break
            admitted.append((cid, params))
            reserved += wc
        if not admitted:
            common.log("enrich", "stopped_at_cap", self.log_path, **self.ledger.summary())
            return -1
        meta = {cid: meta[cid] for cid, _ in admitted}
        key = f"enrich:{wave_tag}"
        if not self.ledger.try_reserve(key, reserved):
            common.log("enrich", "stopped_at_cap", self.log_path, **self.ledger.summary())
            return -1
        batch = llm.submit_batch(self.client, admitted)
        self.db.execute("INSERT INTO inflight VALUES (?,?,?,?,?,?)",
                        (batch.id, "enrich", self.meta("phase"), _now(), json.dumps({**meta, "_key": key}), reserved))
        common.log("enrich", "batch_submitted", self.log_path, batch_id=batch.id, requests=len(admitted),
                   reviews=sum(len(m["review_ids"]) for m in meta.values()), reserved_usd=round(reserved, 6),
                   phase=self.meta("phase"))
        return self.collect(batch.id)

    def collect(self, batch_id):
        phase_sub, submitted_at, rj, reserved = self.db.execute(
            "SELECT phase, submitted_at, requests_json, reserved_usd FROM inflight WHERE batch_id=?",
            (batch_id,)).fetchone()
        meta = json.loads(rj)
        key = meta.pop("_key")
        t0 = time.time()
        batch = llm.wait_batch(self.client, batch_id)
        ended_at = _now()
        results = {cid: (kind, obj) for cid, kind, obj in llm.batch_results(self.client, batch_id)}
        calls, charges, done = [], [], 0
        self.db.execute("BEGIN")
        for cid, m in meta.items():
            kind, obj = results.get(cid, ("missing", None))
            base = {"request_id": f"{batch_id}:{cid}", "batch_id": batch_id, "custom_id": cid, "run_id": self.run_id,
                    "role": "enrich", "review_ids": m["review_ids"], "model": self.model, "tier": self.tier,
                    "effort": "low", "thinking": "disabled", "phase": phase_sub, "label_config": self.cfg,
                    "attempt": m["attempt"], "max_tokens": m["max_tokens"], "submitted_at": submitted_at,
                    "ended_at": ended_at}
            if kind != "succeeded":
                calls.append({**base, "outcome": "failed", "error": f"{kind}:{getattr(obj, 'type', obj)}",
                              "input_tokens": 0, "output_tokens": 0, "usd": 0.0, "usage_note": "not billed per provider"})
                self._fail(m["review_ids"], f"batch_{kind}")
                continue
            items = llm.usage_items(obj.usage)
            usd = float(llm.cost(items, self.model, self.tier, self.rates))
            charges.append((base["request_id"], "enrich", usd))
            sent = {lid: self._text(rid) for lid, rid in m["local"].items()}
            if obj.stop_reason == "refusal":
                good, bad = {}, {lid: "refusal" for lid in sent}
            else:
                good, bad = parse_response(llm.message_text(obj), sent)
                if obj.stop_reason == "max_tokens":
                    bad.update({lid: "output_token_cap" for lid in sent if lid not in good})
            outcome = "succeeded" if good else "failed"
            common.append_jsonl(self.calls_path.with_name(self.calls_path.stem + "_raw_responses.jsonl"),
                                [{"request_id": base["request_id"], "local_ids": m["local"],
                                  "text": llm.message_text(obj)}])
            calls.append({**base, "outcome": outcome, "message_id": obj.id, "stop_reason": obj.stop_reason,
                          "input_tokens": items["input"], "output_tokens": items["output"],
                          "cache_read_input_tokens": items["cache_read"],
                          "cache_creation_input_tokens": items["cache_write_5m"] + items["cache_write_1h"],
                          "usage_items": items, "usd": round(usd, 8),
                          "valid_items": len(good), "invalid_items": len(bad),
                          "invalid_reasons": sorted(set(bad.values()))})
            for lid, fields in good.items():
                rid = m["local"][lid]
                self._complete(rid, fields, phase_sub)
                done += 1
            self._fail([m["local"][lid] for lid in bad], None, reasons=bad, local=m["local"])
        common.append_jsonl(self.calls_path, calls)
        self.db.execute("DELETE FROM inflight WHERE batch_id=?", (batch_id,))
        self.db.execute("COMMIT")
        self.ledger.settle(key, charges)
        common.log("enrich", "batch_committed", self.log_path, batch_id=batch_id, completed_reps=done,
                   wait_s=round(time.time() - t0, 1), usd=round(sum(c[2] for c in charges), 6),
                   **self.ledger.summary())
        return done

    def _text(self, rid):
        return self._texts[rid]

    def _complete(self, rid, fields, phase):
        res = json.dumps(fields, ensure_ascii=False, sort_keys=True)
        tsha = self.db.execute("SELECT text_sha FROM reviews WHERE review_id=?", (rid,)).fetchone()[0]
        self.db.execute("INSERT OR IGNORE INTO text_cache VALUES (?,?,?,?)", (tsha, self.cfg, rid, res))
        self.db.execute("UPDATE reviews SET status='completed', attempts=attempts+1, label_config=?, result_json=?,"
                        " cache_source_id=NULL, completed_phase=?, completed_at=? WHERE review_id=?",
                        (self.cfg, res, phase, _now(), rid))

    def _fail(self, rids, reason, reasons=None, local=None):
        inv = {v: k for k, v in (local or {}).items()}
        for rid in rids:
            why = reason or reasons[inv[rid]]
            att = self.db.execute("SELECT attempts FROM reviews WHERE review_id=?", (rid,)).fetchone()[0] + 1
            if att >= MAX_ATTEMPTS:
                self.db.execute("UPDATE reviews SET status='quarantined', attempts=?, reason=? WHERE review_id=?",
                                (att, f"enrich_failed:{why}", rid))
            else:
                self.db.execute("UPDATE reviews SET attempts=?, reason=? WHERE review_id=?", (att, f"retry:{why}", rid))

    def run(self, texts, scope_ids=None, stop_after_waves=None):
        """Enrich all pending in-scope texts. Returns final status counts."""
        self._texts = texts
        phase = self.begin()
        common.log("enrich", "start", self.log_path, phase=phase, label_config=self.cfg, **self.ledger.summary())
        waves = 0
        while True:
            hits = self.apply_cache(scope_ids)
            if hits:
                common.log("enrich", "cache_fanout", self.log_path, rows=hits)
            n = self.run_wave(texts, scope_ids)
            if n == 0 and not self.pending_texts(texts, scope_ids, 1):
                break
            if n < 0:
                break
            waves += 1
            if stop_after_waves and waves >= stop_after_waves:
                break
        self.apply_cache(scope_ids)
        self.end()
        counts = state.status_counts(self.db)
        common.log("enrich", "finished", self.log_path, **counts, **self.ledger.summary())
        return counts


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")
