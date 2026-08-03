"""Replay fixture cases through the instrumented fake model to emit spans.

Each turn is a separate `model.invoke()` — so a separate span / trace — sharing
the case's conversation id. Every turn resends the accumulated history
(system + prior user/assistant turns + current user), mirroring how a production
chatbot resends context on each request (SPEC.md §3.5).
"""

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from fixture_model import FixtureModel
from fixtures import Case
from tracing import reset_conversation, set_conversation


def ingest_case(case: Case) -> int:
    """Emit one span per turn of a single case. Returns the turn count."""
    model = FixtureModel(
        responses=[turn.response for turn in case.turns],
        model_name_str=case.model,
        usage=case.usage,
    )

    history: list = [SystemMessage(content=case.system)]
    token = set_conversation(case.conversation_id)
    try:
        for turn in case.turns:
            history.append(HumanMessage(content=turn.user))
            answer = model.invoke(history)
            history.append(AIMessage(content=answer.content))
    finally:
        reset_conversation(token)

    return len(case.turns)


def ingest_cases(cases: list[Case]) -> list[str]:
    """Emit spans for every case. Returns the case names emitted."""
    for case in cases:
        ingest_case(case)
    return [case.name for case in cases]
