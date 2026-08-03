"""Replay fixture cases through the instrumented fake model to emit spans.

Each turn is a separate `model.invoke()` — so a separate span / trace — sharing
the case's conversation id. Every turn resends the accumulated history
(system + prior user/assistant turns + current user), mirroring how a production
chatbot resends context on each request (SPEC.md §3.5).
"""

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from fixture_model import FixtureModel
from fixtures import Case
from tracing import (
    GEN_AI_CONTEXT,
    GEN_AI_CONVERSATION_ID,
    GEN_AI_REFERENCE,
    reset_span_attributes,
    set_span_attributes,
)


def ingest_case(case: Case) -> int:
    """Emit one span per turn of a single case. Returns the turn count."""
    model = FixtureModel(
        responses=[turn.response for turn in case.turns],
        model_name_str=case.model,
        usage=case.usage,
    )

    # Every span of this case carries the conversation id and — where the
    # evaluator needs grounding — the fixture context / reference (which the
    # native instrumentation does not emit).
    attrs = {GEN_AI_CONVERSATION_ID: case.conversation_id}
    if case.context:
        attrs[GEN_AI_CONTEXT] = case.context
    if case.reference:
        attrs[GEN_AI_REFERENCE] = case.reference

    history: list = [SystemMessage(content=case.system)]
    token = set_span_attributes(attrs)
    try:
        for turn in case.turns:
            history.append(HumanMessage(content=turn.user))
            answer = model.invoke(history)
            history.append(AIMessage(content=answer.content))
    finally:
        reset_span_attributes(token)

    return len(case.turns)


def ingest_cases(cases: list[Case]) -> list[str]:
    """Emit spans for every case. Returns the case names emitted."""
    for case in cases:
        ingest_case(case)
    return [case.name for case in cases]
