#!/usr/bin/env bash
# Outputs oneagent-matrix and otelcol-matrix JSON arrays to GITHUB_OUTPUT.
#
# Inputs (environment variables):
#   EVENT       - github.event_name (pull_request | workflow_dispatch | schedule)
#   SUITE_INPUT - optional suite name from workflow_dispatch input
#   BASE_REF    - PR base branch (e.g. "main"), set only for pull_request events
set -euo pipefail

OA_ALL='[
  {"name":"aws-bedrock-oneagent","app_dir":"aws-bedrock/oneagent","test_file":"test/e2e/aws_bedrock_oneagent_test.go","test_run":"TestAWSBedrockOneAgent","otel_service_name":"aws-bedrock/oneagent"},
  {"name":"anthropic-oneagent","app_dir":"anthropic/oneagent","test_file":"test/e2e/anthropic_oneagent_test.go","test_run":"TestAnthropicOneAgent","otel_service_name":"anthropic/oneagent"},
  {"name":"openai-oneagent","app_dir":"openai/oneagent","test_file":"test/e2e/openai_oneagent_test.go","test_run":"TestOpenAIOneAgent","otel_service_name":"openai/oneagent"},
  {"name":"ollama-oneagent","app_dir":"ollama/oneagent","test_file":"test/e2e/ollama_test.go","test_run":"TestOllamaOneAgent","otel_service_name":"ollama/oneagent","ollama_model":"tinyllama"},
  {"name":"groq-oneagent","app_dir":"groq/oneagent","test_file":"test/e2e/groq_test.go","test_run":"TestGroqOneAgent","otel_service_name":"groq/oneagent","ollama_model":"tinyllama"},
  {"name":"cohere-oneagent","app_dir":"cohere/oneagent","test_file":"test/e2e/cohere_test.go","test_run":"TestCohereOneAgent","otel_service_name":"cohere/oneagent"}
]'

OC_ALL='[
  {"name":"aws-bedrock-opentelemetry","app_dir":"aws-bedrock/opentelemetry","test_file":"test/e2e/aws_bedrock_opentelemetry_test.go","test_run":"TestAWSBedrockOpenTelemetry","otel_service_name":"aws-bedrock/opentelemetry"},
  {"name":"aws-bedrock-openinference","app_dir":"aws-bedrock/openinference","test_file":"test/e2e/aws_bedrock_openinference_test.go","test_run":"TestAWSBedrockOpenInference","otel_service_name":"aws-bedrock/openinference"},
  {"name":"openai-openinference","app_dir":"openai/openinference","test_file":"test/e2e/openai_openinference_test.go","test_run":"TestOpenAIOpenInference","otel_service_name":"openai/openinference"},
  {"name":"langfuse-opentelemetry","app_dir":"langfuse/opentelemetry","test_file":"test/e2e/langfuse_opentelemetry_test.go","test_run":"TestLangfuseOpenTelemetry","otel_service_name":"langfuse"},
  {"name":"langfuse-opentelemetry-node","app_dir":"langfuse/opentelemetry-node","test_file":"test/e2e/langfuse_opentelemetry_node_test.go","test_run":"TestLangfuseOpenTelemetryNode","otel_service_name":"langfuse-node","needs_node":true},
  {"name":"langfuse-opentelemetry-openpipeline","app_dir":"langfuse/opentelemetry","test_file":"test/e2e/langfuse_opentelemetry_openpipeline_test.go","test_run":"TestLangfuseOpenTelemetryOpenPipeline","otel_service_name":"langfuse-openpipeline"},
  {"name":"pydantic-ai-opentelemetry","app_dir":"pydantic-ai/opentelemetry","test_file":"test/e2e/pydantic_ai_opentelemetry_test.go","test_run":"TestPydanticAIOpenTelemetry","otel_service_name":"pydantic-ai-music-agent"},
  {"name":"openai-agents-opentelemetry","app_dir":"openai-agents/opentelemetry","test_file":"test/e2e/openai_agents_opentelemetry_test.go","test_run":"TestOpenAIAgentsOpenTelemetry","otel_service_name":"openai-cs-agents"},
  {"name":"mcp-opentelemetry","app_dir":"mcp/opentelemetry","test_file":"test/e2e/mcp_opentelemetry_test.go","test_run":"TestMCPOpenTelemetry","otel_service_name":"mcp-agent-demo","node_version":"22"},
  {"name":"litellm-opentelemetry","app_dir":"litellm/opentelemetry","test_file":"test/e2e/litellm_opentelemetry_test.go","test_run":"TestLiteLLMOpenTelemetry","otel_service_name":"litellm-gateway"},
  {"name":"microsoft-agent-framework-opentelemetry","app_dir":"microsoft-agent-framework/opentelemetry","test_file":"test/e2e/microsoft_agent_framework_opentelemetry_test.go","test_run":"TestMicrosoftAgentFrameworkOpenTelemetry","otel_service_name":"microsoft-agent-framework"},
  {"name":"crewai-opentelemetry","app_dir":"crewai/opentelemetry","test_file":"test/e2e/crewai_opentelemetry_test.go","test_run":"TestCrewAIOpenTelemetry","otel_service_name":"crewai"},
  {"name":"google-adk-opentelemetry","app_dir":"google-adk/opentelemetry","test_file":"test/e2e/google_adk_opentelemetry_test.go","test_run":"TestGoogleADKOpenTelemetry","otel_service_name":"google-adk-samples","model":"gemini-3.1-flash-lite","needs_google":true}
]'

if [[ "$EVENT" == "pull_request" ]]; then
  # Fetch the tip of the base branch so we can diff against it.
  git fetch --depth=1 origin "$BASE_REF"
  CHANGED=$(git diff --name-only FETCH_HEAD HEAD)
  CHANGED_JSON=$(echo "$CHANGED" | jq -Rs 'split("\n") | map(select(length > 0))')

  # Changes to shared infrastructure trigger a full run:
  #   test/e2e/internal/   - DQL client and process manager used by every test
  #   test/e2e/fixture_*   - shared test helpers (suite setup, audit, triggers, …)
  #   test/e2e/go.mod|sum  - dependency changes affect every suite
  #   .github/ CI files    - changes to this script or the workflow itself
  INFRA_RE='^(test/e2e/internal/|test/e2e/fixture_|test/e2e/go\.(mod|sum)$|\.github/scripts/compute-e2e-matrix\.sh$)'
  if echo "$CHANGED" | grep -qE "$INFRA_RE"; then
    OA_MATRIX=$(echo "$OA_ALL" | jq -c .)
    OC_MATRIX=$(echo "$OC_ALL" | jq -c .)
  else
    # Run only suites whose app directory or test file was touched.
    # A new test file that isn't registered in OA_ALL/OC_ALL produces an empty
    # matrix — no tests run until the suite is explicitly added above.
    OA_MATRIX=$(echo "$OA_ALL" | jq -c --argjson changed "$CHANGED_JSON" '
      [.[] | . as $s | select(
        ($changed | any(startswith($s.app_dir + "/"))) or
        ($changed | any(. == $s.test_file))
      )]
    ')
    OC_MATRIX=$(echo "$OC_ALL" | jq -c --argjson changed "$CHANGED_JSON" '
      [.[] | . as $s | select(
        ($changed | any(startswith($s.app_dir + "/"))) or
        ($changed | any(. == $s.test_file))
      )]
    ')
  fi
elif [[ -n "${SUITE_INPUT:-}" ]]; then
  OA_MATRIX=$(echo "$OA_ALL" | jq --arg s "$SUITE_INPUT" '[.[] | select(.name == $s)]')
  OC_MATRIX=$(echo "$OC_ALL" | jq --arg s "$SUITE_INPUT" '[.[] | select(.name == $s)]')
else
  OA_MATRIX=$(echo "$OA_ALL" | jq -c .)
  OC_MATRIX=$(echo "$OC_ALL" | jq -c .)
fi

echo "oneagent-matrix=$(echo "$OA_MATRIX" | jq -c .)" >> "$GITHUB_OUTPUT"
echo "otelcol-matrix=$(echo "$OC_MATRIX" | jq -c .)" >> "$GITHUB_OUTPUT"
