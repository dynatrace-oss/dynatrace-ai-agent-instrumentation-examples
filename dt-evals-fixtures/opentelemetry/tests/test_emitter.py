"""Verify the emitter produces complete, deterministic multi-turn spans, using an
in-memory exporter (no Dynatrace tenant)."""

import json

import pytest
from opentelemetry import trace


@pytest.fixture
def exporter(span_exporter):
    return span_exporter


def _emit(exporter, case_dict):
    from fixtures import normalize_case
    from ingest import ingest_case

    exporter.clear()
    ingest_case(normalize_case(case_dict))
    trace.get_tracer_provider().force_flush()
    return exporter.get_finished_spans()


def test_multi_turn_emits_one_linked_span_per_turn(exporter):
    spans = _emit(
        exporter,
        {
            "name": "support-escalation-fail",
            "system": "You are a customer support agent.",
            "model": "gpt-4.1",
            "usage": {"input_tokens": 11, "output_tokens": 7},
            "turns": [
                {"user": "My order is late.", "response": "Can you share your order number?"},
                {"user": "12345. Told you TWICE.", "response": "Escalating now."},
            ],
        },
    )

    # One span per turn.
    assert len(spans) == 2

    conv_ids = {s.attributes.get("gen_ai.conversation.id") for s in spans}
    # Both turns share exactly one, non-empty conversation id.
    assert len(conv_ids) == 1
    assert next(iter(conv_ids))

    # Each turn is its own trace (separate invoke, no parent).
    assert len({s.context.trace_id for s in spans}) == 2

    for s in spans:
        assert s.attributes.get("gen_ai.request.model") == "gpt-4.1"
        assert s.attributes.get("gen_ai.usage.input_tokens") == 11
        assert s.attributes.get("gen_ai.usage.output_tokens") == 7

    # Turn 2's span carries the accumulated history: user -> assistant -> user.
    turn2 = spans[1]
    roles = [m["role"] for m in json.loads(turn2.attributes["gen_ai.input.messages"])]
    assert roles == ["user", "assistant", "user"]


def test_conversation_id_is_stable_uuid5_of_name():
    from fixtures import normalize_case

    a = normalize_case({"name": "case-x", "user": "hi", "response": "yo"})
    b = normalize_case({"name": "case-x", "user": "different", "response": "text"})
    assert a.conversation_id == b.conversation_id  # derived from name only
    assert len(a.conversation_id) == 36  # UUID string


def test_single_turn_shorthand_normalizes_to_one_turn(exporter):
    spans = _emit(
        exporter,
        {"name": "clean-geo", "user": "Capital of France?", "response": "Paris."},
    )
    assert len(spans) == 1
