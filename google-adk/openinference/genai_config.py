"""Shared model settings and the system-instructions span callback for all agents."""

import json

from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmRequest
from google.genai.types import GenerateContentConfig
from opentelemetry import trace

# OpenInference records this config as llm.invocation_parameters, which its native
# semconv mode maps to gen_ai.request.temperature.
GENERATE_CONTENT_CONFIG = GenerateContentConfig(temperature=0.7)


def record_system_instructions(
    callback_context: CallbackContext, llm_request: LlmRequest
) -> None:
    """Set gen_ai.system_instructions on the LLM span from the agent instruction.

    OpenInference maps the system instruction only into the input messages, not into
    gen_ai.system_instructions. ADK runs before_model_callback inside the LLM span.
    """
    instruction = llm_request.config.system_instruction if llm_request.config else None
    if isinstance(instruction, str) and instruction:
        trace.get_current_span().set_attribute(
            "gen_ai.system_instructions",
            json.dumps([{"type": "text", "content": instruction}], ensure_ascii=False),
        )
    return None
