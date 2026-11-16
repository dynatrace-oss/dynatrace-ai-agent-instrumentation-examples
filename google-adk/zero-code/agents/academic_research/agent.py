# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Academic_Research: Research advice, related literature finding, research area proposals, web knowledge access."""

import os

from google.adk.agents import LlmAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmRequest
from google.adk.tools.agent_tool import AgentTool
from google.genai import types

from . import prompt
from .sub_agents.academic_newresearch import academic_newresearch_agent
from .sub_agents.academic_websearch import academic_websearch_agent

MODEL = os.environ.get("MODEL", "gemini-3.1-flash-lite")


def _require_tool_call_first(
    callback_context: CallbackContext, llm_request: LlmRequest
) -> None:
    """Forces a tool call on the first model turn after each user message.

    Without this, the coordinator often answers from the model's own knowledge
    and never delegates to its sub-agents. Later turns stay on AUTO so the
    model can still write its final answer.
    """
    for content in reversed(llm_request.contents):
        parts = content.parts or []
        if any(p.function_response for p in parts):
            return None
        if content.role == "user" and any(p.text for p in parts):
            break
    llm_request.config = llm_request.config or types.GenerateContentConfig()
    llm_request.config.tool_config = types.ToolConfig(
        function_calling_config=types.FunctionCallingConfig(mode="ANY")
    )
    return None


academic_coordinator = LlmAgent(
    name="academic_coordinator",
    model=MODEL,
    description=(
        "analyzing seminal papers provided by the users, "
        "providing research advice, locating current papers "
        "relevant to the seminal paper, generating suggestions "
        "for new research directions, and accessing web resources "
        "to acquire knowledge"
    ),
    instruction=prompt.ACADEMIC_COORDINATOR_PROMPT,
    output_key="seminal_paper",
    before_model_callback=_require_tool_call_first,
    tools=[
        AgentTool(agent=academic_websearch_agent),
        AgentTool(agent=academic_newresearch_agent),
    ],
)

root_agent = academic_coordinator
