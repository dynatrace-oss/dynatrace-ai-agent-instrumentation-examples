"""Fixture schema + loader.

A fixture case is an ordered list of `turns` (one span per turn). Single-turn
cases may use the `system`/`user`/`response` shorthand, which is normalized to a
one-turn conversation. The conversation id is a stable UUIDv5 of the case name
so the same conversation keeps the same id across runs.
"""

import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path

# Fixed namespace so UUIDv5(name) is stable across runs and machines.
_CONVERSATION_NAMESPACE = uuid.UUID("1b671a64-40d5-491e-99b0-da01ff1f3341")

DEFAULT_SERVICE_NAME = "dt-evals-fixtures"
DEFAULT_SYSTEM_PROMPT = "You are a helpful assistant."


@dataclass
class Turn:
    user: str
    response: str
    expect: str | None = None
    targets: list[str] = field(default_factory=list)


@dataclass
class Case:
    name: str
    turns: list[Turn]
    system: str = DEFAULT_SYSTEM_PROMPT
    targets: list[str] = field(default_factory=list)
    expect: str | None = None
    context: str | None = None
    reference: str | None = None
    model: str = "unknown"
    usage: dict | None = None

    @property
    def conversation_id(self) -> str:
        return str(uuid.uuid5(_CONVERSATION_NAMESPACE, self.name))


def normalize_case(raw: dict) -> Case:
    if "turns" in raw:
        turns = [
            Turn(
                user=t["user"],
                response=t["response"],
                expect=t.get("expect"),
                targets=t.get("targets", []),
            )
            for t in raw["turns"]
        ]
    else:
        turns = [Turn(user=raw["user"], response=raw["response"])]

    return Case(
        name=raw["name"],
        turns=turns,
        system=raw.get("system", DEFAULT_SYSTEM_PROMPT),
        targets=raw.get("targets", []),
        expect=raw.get("expect"),
        context=raw.get("context"),
        reference=raw.get("reference"),
        model=raw.get("model", "unknown"),
        usage=raw.get("usage"),
    )


def load_fixtures(path: str | Path) -> tuple[str, list[Case]]:
    """Return (service_name, cases) parsed from a fixtures JSON file."""
    data = json.loads(Path(path).read_text())
    service_name = data.get("service_name", DEFAULT_SERVICE_NAME)
    cases = [normalize_case(c) for c in data["cases"]]
    return service_name, cases
