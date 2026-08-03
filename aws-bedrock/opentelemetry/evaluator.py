"""Out-of-band evaluation for the multi-agent turn.

Runs off the request path in a background worker and emits a
`gen_ai.evaluation.result` Business Event per turn, correlated to the turn by
`trace_id` / `span_id`. The verdict is a stand-in that always passes; a real
deployment would run an actual judge (LLM-as-judge or a metric). Static event
fields live in `evaluation_bizevent.json`. See the README ("Multi-agent turn").
"""
import atexit
import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor

import requests

with open(os.path.join(os.path.dirname(__file__), "evaluation_bizevent.json")) as _f:
    _FIELDS = json.load(_f)

_POOL = ThreadPoolExecutor(max_workers=2)
atexit.register(lambda: _POOL.shutdown(wait=True))


def submit(span, question, answer, model):
    """Queue an evaluation for the turn and return immediately."""
    ctx = span.get_span_context()
    _POOL.submit(_run, question, answer, model,
                 format(ctx.trace_id, "032x"), format(ctx.span_id, "016x"))


def _run(question, answer, model, trace_id, span_id):
    event = dict(_FIELDS)
    event.update({
        "trace_id": trace_id,
        "span_id": span_id,
        "gen_ai.evaluation.score.value": 1.0,
        "gen_ai.evaluation.score.label": "pass",
        "gen_ai.evaluation.explanation": "Stand-in evaluator: always passes.",
        "gen_ai.evaluation.input.question": question,
        "gen_ai.evaluation.input.answer": answer,
        "gen_ai.request.model": model,
    })
    _ingest(event)


def _ingest(event):
    # POST to {DT_ENDPOINT}/api/v2/bizevents/ingest (token scope bizevents.ingest);
    # fall back to an OTLP log when unset so the local collector run still works.
    base = os.environ.get("DT_ENDPOINT", "").rstrip("/")
    token = os.environ.get("DT_API_TOKEN", "")
    if not (base and token):
        logging.info("gen_ai.evaluation", extra=event)
        return
    try:
        requests.post(f"{base}/api/v2/bizevents/ingest",
                      headers={"Authorization": f"Api-Token {token}", "Content-Type": "application/json"},
                      data=json.dumps(event), timeout=10).raise_for_status()
    except Exception as e:
        logging.error(f"eval bizevent ingest failed: {e}")
        logging.info("gen_ai.evaluation", extra=event)
