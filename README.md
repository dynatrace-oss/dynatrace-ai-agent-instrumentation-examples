# Dynatrace Agentic AI Instrumentation Examples

[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/dynatrace-oss/dynatrace-ai-agent-instrumentation-examples/badge)](https://scorecard.dev/viewer/?uri=github.com/dynatrace-oss/dynatrace-ai-agent-instrumentation-examples)

This project demonstrates how to instrument AI agents with Dynatrace to gain observability into Agentic AI workloads, including performance, cost, and runtime behavior.

By integrating Dynatrace with AI agents, developers can monitor agent execution, understand tool interactions, trace prompt and response flows, and analyze dependencies across distributed AI-driven systems.

Telemetry can be shipped directly via OneAgent or the OpenTelemetry (OTel) SDK, or routed through an **OTel Collector** — including the [Dynatrace Distribution of the OpenTelemetry Collector](https://docs.dynatrace.com/docs/extend-dynatrace/opentelemetry/collector) and [Dynatrace Bindplane Distribution of OpenTelemetry Collector](https://github.com/Dynatrace/dynatrace-bindplane-otel-collector).

## Key Features

### Runtime Observability for AI Agents

Monitor AI agent interactions, tool usage, service dependencies, performance metrics, token consumption, and cost drivers—providing end-to-end visibility into how AI agent workflows behave at runtime.

![Model Providers](assets/model-providers.png)

### Agent Execution Tracing and Debugging

Trace agent execution from the initial request through prompt flows, tool calls, and service interactions to the final response—enabling faster debugging and root cause analysis across complex agent workflows.

![Trace View](assets/trace-view.png)

### AI-Powered Workflow Insights

Use Dynatrace Intelligence to identify bottlenecks, optimize resource utilization, and understand how complex agent workflows behave across distributed services.

![Agents Topology](assets/agents-topology.png)

### LLM Evaluations

Evaluate AI agent responses at scale with built-in evaluation criteria—assess faithfulness, PII leakage, bias, context relevance, and user frustration across all prompts in your tenant.

![Evaluations](assets/evaluations.png)

### Fast Agent Instrumentation

Add Dynatrace instrumentation to AI agents in minutes using simple integration patterns and practical examples—bringing runtime observability directly into agent development workflows.

## Who This Repository Is For

This repository is designed for:

- Developers building AI-powered applications
- Platform and DevOps engineers operating AI systems
- AI practitioners working with agent frameworks

If you're building AI agents, copilots, chatbots, or autonomous systems, these examples will help you add observability to your agent workflows and gain deeper insight into how your AI systems operate in production.

## Coding Agent Observability

AI coding agents like Claude Code and OpenAI Codex CLI run autonomously in developer environments — writing, editing, and committing code on your behalf. Dynatrace gives engineering teams full visibility into how these agents operate across the organization, with zero code changes required. By capturing built-in OpenTelemetry signals, you can monitor token consumption, costs, session activity, and tool behavior in real time.

- **Cost & token tracking** — understand spend per model, per user, and per team
- **Engineering metrics** — lines of code added/removed, git commits, and pull requests created by AI
- **Tool observability** — trace every tool call, acceptance/rejection decision, and API error
- **Session-level attribution** — slice all data by `user.id`, `session.id`, or `organization.id`

See the **[AI Coding Agents](./ai-coding-agents/)** section for setup guides covering Antigravity, Claude Code, Cursor, GitHub Copilot in VS Code, Kiro, OpenAI Codex CLI, OpenClaw, OpenCode, and the GitHub Copilot SDK.

## Demos

### SDK + Instrumentation Demos

Monitor specific AI provider SDKs with Dynatrace.

| Provider | SDK version | OneAgent | OpenInference | OpenTelemetry |
|----------|-------------|----------|---------------|---------------|
| [AWS Bedrock](./aws-bedrock/) | `boto3` 1.43.121 <!-- renovate: datasource=pypi depName=boto3 --> | [✓](./aws-bedrock/oneagent/) | [✓](./aws-bedrock/openinference/) <img src="https://opentelemetry.io/img/logos/opentelemetry-logo-nav.png" width="16"> | [✓](./aws-bedrock/opentelemetry/) <img src="https://opentelemetry.io/img/logos/opentelemetry-logo-nav.png" width="16"> |
| [Anthropic](./anthropic/oneagent/) | `anthropic` 1.12.1 <!-- renovate: datasource=pypi depName=anthropic --> | [✓](./anthropic/oneagent/) | [✓](./anthropic/openinference/) <img src="https://opentelemetry.io/img/logos/opentelemetry-logo-nav.png" width="16"> | — |
| [Cohere](./cohere/oneagent/) | `cohere` 7.3.0 <!-- renovate: datasource=pypi depName=cohere --> | [✓\*](./cohere/oneagent/) | [✓](./cohere/openinference/) <img src="https://opentelemetry.io/img/logos/opentelemetry-logo-nav.png" width="16"> | — |
| [Gemini](./gemini/openinference/) | `google-genai` 2.33.0 <!-- renovate: datasource=pypi depName=google-genai --> | — | [✓](./gemini/openinference/) <img src="https://opentelemetry.io/img/logos/opentelemetry-logo-nav.png" width="16"> | — |
| [Groq](./groq/oneagent/) | `groq` 1.7.0 <!-- renovate: datasource=pypi depName=groq --> | [✓\*](./groq/oneagent/) | [✓](./groq/openinference/) <img src="https://opentelemetry.io/img/logos/opentelemetry-logo-nav.png" width="16"> | — |
| [Together AI](./together/openinference/) | `together` 2.41.0 <!-- renovate: datasource=pypi depName=together --> | — | [✓](./together/openinference/) <img src="https://opentelemetry.io/img/logos/opentelemetry-logo-nav.png" width="16"> | — |
| [Mistral](./mistral/) | `mistralai` 3.6.0 <!-- renovate: datasource=pypi depName=mistralai --> | [✓\*](./mistral/oneagent/) | [✓](./mistral/openinference/) <img src="https://opentelemetry.io/img/logos/opentelemetry-logo-nav.png" width="16"> | — |
| [Ollama](./ollama/oneagent/) | `ollama` 0.6.3 <!-- renovate: datasource=pypi depName=ollama --> | [✓\*](./ollama/oneagent/) | [✓](./ollama/openinference/) <img src="https://opentelemetry.io/img/logos/opentelemetry-logo-nav.png" width="16"> | — |
| [OpenAI](./openai/) | `openai` 3.26.0 <!-- renovate: datasource=pypi depName=openai --> | [✓](./openai/oneagent/) | [✓](./openai/openinference/) <img src="https://opentelemetry.io/img/logos/opentelemetry-logo-nav.png" width="16"> | [✓](./openai/opentelemetry/) |
| [vLLM](./vllm/openinference/) | `vllm` 0.31.0 <!-- renovate: datasource=pypi depName=vllm --> | — | [✓](./vllm/openinference/) | — |

\* Experimental sensor — prompt input and output capture not yet supported.  
<img src="https://opentelemetry.io/img/logos/opentelemetry-logo-nav.png" width="16"> Includes an [OTel Collector](https://opentelemetry.io/docs/collector/) configuration — compatible with the [Dynatrace Distribution of the OpenTelemetry Collector](https://docs.dynatrace.com/docs/extend-dynatrace/opentelemetry/collector) and [Dynatrace Bindplane Distribution of OpenTelemetry Collector](https://github.com/Dynatrace/dynatrace-bindplane-otel-collector).

### Agent Framework Demos

Monitor AI agent frameworks with Dynatrace.

| Framework | SDK version | OneAgent | OpenInference | OpenTelemetry |
|-----------|-------------|----------|---------------|---------------|
| [AWS Bedrock Agents](./aws-bedrock-agents/) | `boto3` 1.43.121 <!-- renovate: datasource=pypi depName=boto3 --> | [✓](./aws-bedrock-agents/oneagent/) | — | — |
| [AWS Bedrock AgentCore](./aws-bedrock-agentcore/oneagent-opentelemetry/) | `boto3` 1.43.121 <!-- renovate: datasource=pypi depName=boto3 --> | [✓](./aws-bedrock-agentcore/oneagent-opentelemetry/) | — | [✓](./aws-bedrock-agentcore/oneagent-opentelemetry/) |
| [AWS Strands Agents](./aws-strands/) | `strands-agents` 1.62.0 <!-- renovate: datasource=pypi depName=strands-agents --> | [✓](./aws-strands/oneagent/) | — | [✓](./aws-strands/opentelemetry/) <img src="https://opentelemetry.io/img/logos/opentelemetry-logo-nav.png" width="16"> |
| [CrewAI](./crewai/) | `crewai` 1.15.33 <!-- renovate: datasource=pypi depName=crewai --> | — | [✓](./crewai/openinference/) <img src="https://opentelemetry.io/img/logos/opentelemetry-logo-nav.png" width="16"> | [✓](./crewai/opentelemetry/) <img src="https://opentelemetry.io/img/logos/opentelemetry-logo-nav.png" width="16"> |
| [Google ADK](./google-adk/opentelemetry/) | `google-adk` 2.11.0 <!-- renovate: datasource=pypi depName=google-adk --> | — | [✓](./google-adk/openinference/) <img src="https://opentelemetry.io/img/logos/opentelemetry-logo-nav.png" width="16"> | [✓](./google-adk/opentelemetry/) <img src="https://opentelemetry.io/img/logos/opentelemetry-logo-nav.png" width="16"> / [✓ zero-code](./google-adk/zero-code/) <img src="https://opentelemetry.io/img/logos/opentelemetry-logo-nav.png" width="16"> |
| [Haystack](./haystack/) | `haystack-ai` 3.3.0 <!-- renovate: datasource=pypi depName=haystack-ai --> | [✓](./haystack/oneagent/) | [✓](./haystack/openinference/) <img src="https://opentelemetry.io/img/logos/opentelemetry-logo-nav.png" width="16"> | — |
| [LlamaIndex](./llamaindex/openinference/) | `llama-index-core` 0.14.25 <!-- renovate: datasource=pypi depName=llama-index-core --> | — | [✓](./llamaindex/openinference/) <img src="https://opentelemetry.io/img/logos/opentelemetry-logo-nav.png" width="16"> | — |
| [LangGraph](./langgraph/) | `langgraph` 1.2.18 <!-- renovate: datasource=pypi depName=langgraph --> | [✓](./langgraph/oneagent/) | [✓](./langgraph/openinference/) <img src="https://opentelemetry.io/img/logos/opentelemetry-logo-nav.png" width="16"> | [✓ OpenAI](./langgraph/opentelemetry/openai/) <img src="https://opentelemetry.io/img/logos/opentelemetry-logo-nav.png" width="16"> / [✓ Bedrock](./langgraph/opentelemetry/bedrock/) <img src="https://opentelemetry.io/img/logos/opentelemetry-logo-nav.png" width="16"> |
| [LiteLLM](./litellm/opentelemetry/) | `litellm` 1.106.6 <!-- renovate: datasource=pypi depName=litellm --> | — | — | [✓](./litellm/opentelemetry/) <img src="https://opentelemetry.io/img/logos/opentelemetry-logo-nav.png" width="16"> |
| [MCP (Model Context Protocol)](mcp/opentelemetry/) | `@modelcontextprotocol/sdk` 1.32.2 <!-- renovate: datasource=npm depName=@modelcontextprotocol/sdk --> | — | — | [✓](mcp/opentelemetry/) <img src="https://opentelemetry.io/img/logos/opentelemetry-logo-nav.png" width="16"> |
| [Microsoft Agent Framework](./microsoft-agent-framework/opentelemetry/) | `agent-framework` 1.23.0 <!-- renovate: datasource=pypi depName=agent-framework --> | — | — | [✓](./microsoft-agent-framework/opentelemetry/) <img src="https://opentelemetry.io/img/logos/opentelemetry-logo-nav.png" width="16"> |
| [n8n](./n8n/opentelemetry/) | `n8n` 2.41.7 <!-- renovate: datasource=docker depName=docker.n8n.io/n8nio/n8n --> | — | — | [✓](./n8n/opentelemetry/) <img src="https://opentelemetry.io/img/logos/opentelemetry-logo-nav.png" width="16"> |
| [OGX](./ogx/) | `ogx` 1.5.0 <!-- renovate: datasource=pypi depName=ogx --> | [✓](./ogx/oneagent/) | — | [✓](./ogx/opentelemetry/) |
| [OpenAI Agents SDK](./openai-agents/opentelemetry/) | `openai-agents` 0.23.1 <!-- renovate: datasource=pypi depName=openai-agents --> | — | [✓](./openai-agents/openinference/) <img src="https://opentelemetry.io/img/logos/opentelemetry-logo-nav.png" width="16"> | [✓](./openai-agents/opentelemetry/) <img src="https://opentelemetry.io/img/logos/opentelemetry-logo-nav.png" width="16"> |
| [Pydantic AI](./pydantic-ai/opentelemetry/) | `pydantic-ai` 2.54.0 <!-- renovate: datasource=pypi depName=pydantic-ai --> | — | — | [✓](./pydantic-ai/opentelemetry/) <img src="https://opentelemetry.io/img/logos/opentelemetry-logo-nav.png" width="16"> |
| [Real User Monitoring](./rum/opentelemetry/) | — | — | — | [✓](./rum/opentelemetry/) <img src="https://opentelemetry.io/img/logos/opentelemetry-logo-nav.png" width="16"> |

<img src="https://opentelemetry.io/img/logos/opentelemetry-logo-nav.png" width="16"> Includes an [OTel Collector](https://opentelemetry.io/docs/collector/) configuration — compatible with the [Dynatrace Distribution of the OpenTelemetry Collector](https://docs.dynatrace.com/docs/extend-dynatrace/opentelemetry/collector) and [Dynatrace Bindplane Distribution of OpenTelemetry Collector](https://github.com/Dynatrace/dynatrace-bindplane-otel-collector).

### AI Coding Agent Demos

Observe AI coding agents with zero code changes using built-in OpenTelemetry signals.

| Agent | SDK version | Path |
|-------|-------------|------|
| [Antigravity](./ai-coding-agents/antigravity/) | — | ai-coding-agents/antigravity |
| [Claude Code](./ai-coding-agents/claude-code/) | — | ai-coding-agents/claude-code |
| [Cursor](./ai-coding-agents/cursor/) | — | ai-coding-agents/cursor |
| [GitHub Copilot in VS Code](./ai-coding-agents/vscode-copilot/) | — | ai-coding-agents/vscode-copilot |
| [GitHub Copilot SDK](./ai-coding-agents/github-copilot-sdk/) | `@github/copilot-sdk` 1.0.28 <!-- renovate: datasource=npm depName=@github/copilot-sdk --> | ai-coding-agents/github-copilot-sdk |
| [Kiro](./ai-coding-agents/kiro/) | — | ai-coding-agents/kiro |
| [OpenAI Codex](./ai-coding-agents/openai-codex/) | — | ai-coding-agents/openai-codex |
| [OpenClaw](./ai-coding-agents/openclaw/) | — | ai-coding-agents/openclaw |
| [OpenClaw Observability Plugin](./ai-coding-agents/openclaw-observability-plugin/) | — | ai-coding-agents/openclaw-observability-plugin |
| [OpenCode](./ai-coding-agents/opencode/) | — | ai-coding-agents/opencode |

## Getting Started

Each demo follows the same interface:

```bash
cd <sdk>/<instrumentation>
make install   # install dependencies
make run       # start app on port 8000
make request   # send a test request (in a second terminal)
```

All demos expose `make help` for the full list of targets.

If you're using a framework that isn't listed here, don't worry! [You can explore the Dynatrace Hub for the full list of supported technologies.](https://www.dynatrace.com/hub/?filter=ai-ml-observability&internal_source=doc&internal_medium=link&internal_campaign=cross)
