package e2e

import (
	"testing"
)

func TestAWSBedrockAgentsOneAgent(t *testing.T) {
	startApp(t, "aws-bedrock-agents/oneagent")
	triggerAgent(t)
	triggerAgentGuardrail(t)

	// triggerAgent and triggerAgentGuardrail each produce their own trace.
	// sort + limit pins the baseline audit to the earlier (non-guardrail)
	// trace deterministically — otherwise which trace becomes the anchor is
	// unspecified, and the guardrail-blocked trace is missing several
	// baseline attributes (e.g. token usage), which would flip this audit's
	// verdict independent of any real regression.
	auditSpan(t, "aws-bedrock-agents", "oneagent", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "aws-bedrock-agents/oneagent"
| filter (gen_ai.provider.name == "aws_bedrock") and dt.openpipeline.source == "oneagent"
| filter isNotNull(gen_ai.request.model)
| filter isNotNull(dt.smartscape.service)
| filter isNull(span.status_code) or span.status_code != "error"
| sort start_time asc
| limit 1`)

	// The guardrail-triggering request is always sent last, so the latest
	// matching span is the one that actually tripped the guardrail.
	auditGuardrailSpan(t, "aws-bedrock-agents", "oneagent",
		`fetch spans, from: now()-10m
| filter service.name == "aws-bedrock-agents/oneagent"
| filter (gen_ai.provider.name == "aws_bedrock") and dt.openpipeline.source == "oneagent"
| filter isNotNull(gen_ai.request.model)
| filter isNotNull(dt.smartscape.service)
| sort start_time desc
| limit 1`)
}
