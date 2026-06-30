#!/usr/bin/env bash
# Outputs oneagent-matrix and otelcol-matrix JSON arrays to GITHUB_OUTPUT.
#
# Inputs (environment variables):
#   EVENT          - github.event_name (pull_request | workflow_dispatch | schedule)
#   SUITE_INPUT    - optional suite name from workflow_dispatch input
#   CHANGED_SUITES - JSON array of matched suite names from dorny/paths-filter (PR only)
set -euo pipefail

OA_ALL='[
  {"name":"aws-bedrock-oneagent","app_dir":"aws-bedrock/oneagent","test_run":"TestAWSBedrockOneAgent","otel_service_name":"aws-bedrock/oneagent"},
  {"name":"anthropic-oneagent","app_dir":"anthropic/oneagent","test_run":"TestAnthropicOneAgent","otel_service_name":"anthropic/oneagent"},
  {"name":"openai-oneagent","app_dir":"openai/oneagent","test_run":"TestOpenAIOneAgent","otel_service_name":"openai/oneagent"},
  {"name":"ollama-oneagent","app_dir":"ollama/oneagent","test_run":"TestOllamaOneAgent","otel_service_name":"ollama/oneagent","ollama_model":"tinyllama"},
  {"name":"groq-oneagent","app_dir":"groq/oneagent","test_run":"TestGroqOneAgent","otel_service_name":"groq/oneagent","ollama_model":"tinyllama"},
  {"name":"cohere-oneagent","app_dir":"cohere/oneagent","test_run":"TestCohereOneAgent","otel_service_name":"cohere/oneagent"},
  {"name":"aws-strands-oneagent","app_dir":"aws-strands/oneagent","test_run":"TestAWSStrandsOneAgent","otel_service_name":"aws-strands/oneagent"}
]'

OC_ALL='[
  {"name":"aws-bedrock-opentelemetry","app_dir":"aws-bedrock/opentelemetry","test_run":"TestAWSBedrockOpenTelemetry","otel_service_name":"aws-bedrock/opentelemetry"},
  {"name":"aws-bedrock-openinference","app_dir":"aws-bedrock/openinference","test_run":"TestAWSBedrockOpenInference","otel_service_name":"aws-bedrock/openinference"},
  {"name":"openai-openinference","app_dir":"openai/openinference","test_run":"TestOpenAIOpenInference","otel_service_name":"openai/openinference"},
  {"name":"langfuse-opentelemetry","app_dir":"langfuse/opentelemetry","test_run":"TestLangfuseOpenTelemetry","otel_service_name":"langfuse"},
  {"name":"langfuse-opentelemetry-node","app_dir":"langfuse/opentelemetry-node","test_run":"TestLangfuseOpenTelemetryNode","otel_service_name":"langfuse-node","needs_node":true},
  {"name":"langfuse-opentelemetry-openpipeline","app_dir":"langfuse/opentelemetry","test_run":"TestLangfuseOpenTelemetryOpenPipeline","otel_service_name":"langfuse-openpipeline"},
  {"name":"pydantic-ai-opentelemetry","app_dir":"pydantic-ai/opentelemetry","test_run":"TestPydanticAIOpenTelemetry","otel_service_name":"pydantic-ai-music-agent"},
  {"name":"openai-agents-opentelemetry","app_dir":"openai-agents/opentelemetry","test_run":"TestOpenAIAgentsOpenTelemetry","otel_service_name":"openai-cs-agents"},
  {"name":"mcp-opentelemetry","app_dir":"mcp/opentelemetry","test_run":"TestMCPOpenTelemetry","otel_service_name":"mcp-agent-demo","node_version":"22"},
  {"name":"litellm-opentelemetry","app_dir":"litellm/opentelemetry","test_run":"TestLiteLLMOpenTelemetry","otel_service_name":"litellm-gateway"},
  {"name":"microsoft-agent-framework-opentelemetry","app_dir":"microsoft-agent-framework/opentelemetry","test_run":"TestMicrosoftAgentFrameworkOpenTelemetry","otel_service_name":"microsoft-agent-framework"},
  {"name":"crewai-opentelemetry","app_dir":"crewai/opentelemetry","test_run":"TestCrewAIOpenTelemetry","otel_service_name":"crewai"},
  {"name":"aws-strands-opentelemetry","app_dir":"aws-strands/opentelemetry","test_run":"TestAWSStrandsOpenTelemetry","otel_service_name":"aws-strands/opentelemetry"},
  {"name":"aws-strands-opentelemetry-openpipeline","app_dir":"aws-strands/opentelemetry","test_run":"TestAWSStrandsOpenTelemetryOpenPipeline","otel_service_name":"aws-strands/opentelemetry-openpipeline"}
]'

if [[ "$EVENT" == "pull_request" ]]; then
  OA_MATRIX=$(echo "$OA_ALL" | jq --argjson changed "$CHANGED_SUITES" '[.[] | select(.name as $n | $changed | index($n) != null)]')
  OC_MATRIX=$(echo "$OC_ALL" | jq --argjson changed "$CHANGED_SUITES" '[.[] | select(.name as $n | $changed | index($n) != null)]')
elif [[ -n "${SUITE_INPUT:-}" ]]; then
  OA_MATRIX=$(echo "$OA_ALL" | jq --arg s "$SUITE_INPUT" '[.[] | select(.name == $s)]')
  OC_MATRIX=$(echo "$OC_ALL" | jq --arg s "$SUITE_INPUT" '[.[] | select(.name == $s)]')
else
  OA_MATRIX=$(echo "$OA_ALL" | jq -c .)
  OC_MATRIX=$(echo "$OC_ALL" | jq -c .)
fi

echo "oneagent-matrix=$(echo "$OA_MATRIX" | jq -c .)" >> "$GITHUB_OUTPUT"
echo "otelcol-matrix=$(echo "$OC_MATRIX" | jq -c .)" >> "$GITHUB_OUTPUT"
