"""Anthropic client wrapper: batch submit/poll, sync calls, usage -> cost.

Nothing here runs at import. A client is created only by paid commands (--paid).
"""
import csv
import json
import random
import time
from decimal import Decimal

from . import common

RATES_CSV = common.ROOT / "cost" / "rates.csv"
USAGE_ITEMS = ("input", "cache_write_5m", "cache_write_1h", "cache_read", "output")


def load_rates(path=RATES_CSV):
    rates = {}
    with open(path, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            rates[(r["model"], r["tier"], r["item"])] = Decimal(r["usd_per_mtok"]) / Decimal(1_000_000)
    return rates


def usage_items(usage):
    """Split provider usage into mutually exclusive billed items."""
    u = usage if isinstance(usage, dict) else usage.model_dump()
    cc = u.get("cache_creation") or {}
    w1h = cc.get("ephemeral_1h_input_tokens") or 0
    w5m = cc.get("ephemeral_5m_input_tokens")
    if w5m is None:
        w5m = (u.get("cache_creation_input_tokens") or 0) - w1h
    return {"input": u.get("input_tokens") or 0, "cache_write_5m": w5m, "cache_write_1h": w1h,
            "cache_read": u.get("cache_read_input_tokens") or 0, "output": u.get("output_tokens") or 0}


def cost(items, model, tier, rates):
    return sum(Decimal(items[k]) * rates[(model, tier, k)] for k in USAGE_ITEMS)


def worst_case(model, tier, rates, prompt_chars, payload_chars, max_tokens):
    """Upper bound for one request: every input token billed as a 1h cache write, ~2 chars/token."""
    in_tokens = (prompt_chars + payload_chars) // 2 + 200
    return float(in_tokens * rates[(model, tier, "cache_write_1h")] + max_tokens * rates[(model, tier, "output")])


def client():
    from dotenv import load_dotenv
    import anthropic
    load_dotenv(common.ROOT / ".env")
    return anthropic.Anthropic(max_retries=4)


def request_params(model, system_text, user_text, schema, max_tokens, effort="low"):
    return {
        "model": model,
        "max_tokens": max_tokens,
        "thinking": {"type": "disabled"},
        "output_config": {"effort": effort, "format": {"type": "json_schema", "schema": schema}},
        "system": [{"type": "text", "text": system_text, "cache_control": {"type": "ephemeral", "ttl": "1h"}}],
        "messages": [{"role": "user", "content": user_text}],
    }


def with_backoff(fn, attempts=6):
    import anthropic
    for i in range(attempts):
        try:
            return fn()
        except (anthropic.RateLimitError, anthropic.InternalServerError, anthropic.APIConnectionError) as e:
            if i == attempts - 1:
                raise
            wait = min(60, 2 ** i) + random.random()
            print(f"  transient {type(e).__name__}; retrying in {wait:.1f}s")
            time.sleep(wait)


def submit_batch(c, requests):
    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    from anthropic.types.messages.batch_create_params import Request
    reqs = [Request(custom_id=cid, params=MessageCreateParamsNonStreaming(**params)) for cid, params in requests]
    return with_backoff(lambda: c.messages.batches.create(requests=reqs))


def wait_batch(c, batch_id, poll=10, max_poll=60):
    while True:
        b = with_backoff(lambda: c.messages.batches.retrieve(batch_id))
        if b.processing_status == "ended":
            return b
        rc = b.request_counts
        print(f"  batch {batch_id}: {b.processing_status} processing={rc.processing} succeeded={rc.succeeded} errored={rc.errored}")
        time.sleep(poll)
        poll = min(max_poll, poll * 1.5)


def batch_results(c, batch_id):
    """Yield (custom_id, kind, message_or_error)."""
    for r in with_backoff(lambda: list(c.messages.batches.results(batch_id))):
        kind = r.result.type
        yield r.custom_id, kind, (r.result.message if kind == "succeeded" else getattr(r.result, "error", None))


def message_text(msg):
    return "".join(b.text for b in msg.content if b.type == "text")


def sync_call(c, params):
    t0 = time.time()
    msg = with_backoff(lambda: c.messages.create(**params))
    return msg, time.time() - t0
