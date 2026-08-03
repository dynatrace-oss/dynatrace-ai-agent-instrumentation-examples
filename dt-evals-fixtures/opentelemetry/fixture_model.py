"""A fake chat model that reports a fixed model name and token usage.

A plain `FakeListChatModel` leaves `gen_ai.request.model` as "unknown" and emits
no `gen_ai.usage.*`, because the instrumentation reads both from the
`ChatResult.llm_output` dict on `on_llm_end` (verified, SPEC.md §3.4/§3.6).
Populating `llm_output` here makes the emitted spans carry the fixture-driven
model and usage. A span processor cannot do this — the instrumentation overwrites
the model name on `on_llm_end`.
"""

from typing import Any, Optional

from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.outputs import ChatResult


class FixtureModel(FakeListChatModel):
    """FakeListChatModel whose responses carry a fixed model name + token usage."""

    # Named to avoid colliding with any base-class field.
    model_name_str: str = "unknown"
    usage: Optional[dict] = None

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        result = super()._generate(messages, stop, run_manager, **kwargs)
        llm_output: dict[str, Any] = {"model_name": self.model_name_str}
        if self.usage:
            input_tokens = self.usage.get("input_tokens", 0)
            output_tokens = self.usage.get("output_tokens", 0)
            llm_output["token_usage"] = {
                "prompt_tokens": input_tokens,
                "completion_tokens": output_tokens,
                "total_tokens": self.usage.get(
                    "total_tokens", input_tokens + output_tokens
                ),
            }
        result.llm_output = llm_output
        return result
