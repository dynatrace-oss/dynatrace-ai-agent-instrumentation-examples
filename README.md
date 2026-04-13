# Dynatrace Agentic AI Instrumentation Examples

This project demonstrates how to instrument AI agents with Dynatrace to gain observability into Agentic AI workloads, including performance, cost, and runtime behavior.

By integrating Dynatrace with AI agents, developers can monitor agent execution, understand tool interactions, trace prompt and response flows, and analyze dependencies across distributed AI-driven systems.

## Key Features

### Runtime Observability for AI Agents

Monitor AI agent interactions, tool usage, service dependencies, performance metrics, token consumption, and cost drivers—providing end-to-end visibility into how AI agent workflows behave at runtime.

### Agent Execution Tracing and Debugging

Trace agent execution from the initial request through prompt flows, tool calls, and service interactions to the final response—enabling faster debugging and root cause analysis across complex agent workflows.

### AI-Powered Workflow Insights

Use Dynatrace Intelligence to identify bottlenecks, optimize resource utilization, and understand how complex agent workflows behave across distributed services.

### Fast Agent Instrumentation

Add Dynatrace instrumentation to AI agents in minutes using simple integration patterns and practical examples—bringing runtime observability directly into agent development workflows.

![Tracing](/mcp/dynatrace.png)

## Who This Repository Is For

This repository is designed for:

- Developers building AI-powered applications
- Platform and DevOps engineers operating AI systems
- AI practitioners working with agent frameworks

If you’re building AI agents, copilots, chatbots, or autonomous systems, these examples will help you add observability to your agent workflows and gain deeper insight into how your AI systems operate in production.

## Coding Agent Observability

AI coding agents like Claude Code and OpenAI Codex CLI run autonomously in developer environments — writing, editing, and committing code on your behalf. Dynatrace gives engineering teams full visibility into how these agents operate across the organization, with zero code changes required. By capturing built-in OpenTelemetry signals, you can monitor token consumption, costs, session activity, and tool behavior in real time.

- **Cost & token tracking** — understand spend per model, per user, and per team
- **Engineering metrics** — lines of code added/removed, git commits, and pull requests created by AI
- **Tool observability** — trace every tool call, acceptance/rejection decision, and API error
- **Session-level attribution** — slice all data by `user.id`, `session.id`, or `organization.id`

See the **[AI Coding Agents](./ai-coding-agents/)** section for setup guides covering Claude Code, OpenAI Codex CLI, OpenClaw, and the GitHub Copilot SDK.

## Supported Frameworks

This repository includes examples and guidance for integrating Dynatrace with the following AI Agent building frameworks and libraries:

- [Google Agent Development Kit (ADK)](./google-adk-sample/)
- [AWS Strands Agents](./aws-agent-sample/)
- [OpenAI Agents SDK](./openai-agent-sample/)
- [MCP - Model Context Protocol](./mcp/)
- [AI Coding Agents](./ai-coding-agents/) — Claude Code, OpenAI Codex CLI, OpenClaw, GitHub Copilot SDK

![MCP Agentic AI](/mcp/architecture.png)

If you’re using a framework that isn’t listed here, don’t worry! [You can explore the Dynatrace Hub for the full list of supported technologies.](https://www.dynatrace.com/hub/?filter=ai-ml-observability&internal_source=doc&internal_medium=link&internal_campaign=cross)
