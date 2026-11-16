package e2e

import (
	"testing"
	"time"
)

// TestClaudeAgentSDKOneAgent needs the "Experimental Python GenAI Claude Agent SDK"
// OneAgent feature (1.349+) enabled on the tenant. The sensor emits one agent span
// per query() call and one child tool span per tool call.
func TestClaudeAgentSDKOneAgent(t *testing.T) {
	startApp(t, "claude-agent-sdk/oneagent")
	triggerHaiku(t, true)

	assertSpanExistsWithin(t, scopedDQL(`fetch spans, from: now()-10m
| filter service.name == "claude-agent-sdk/oneagent"
| filter dt.openpipeline.source == "oneagent"
| filter gen_ai.operation.kind == "tool"
| filter gen_ai.tool.name == "mcp__haiku__count_syllables"
| limit 1`), 5*time.Minute)

	auditSpan(t, "claude-agent-sdk", "oneagent", GenericProfile,
		`fetch spans, from: now()-10m
| filter service.name == "claude-agent-sdk/oneagent"
| filter dt.openpipeline.source == "oneagent"
| filter gen_ai.operation.kind == "agent"
| filter gen_ai.provider.name == "anthropic"
| filter isNotNull(gen_ai.response.model)
| filter isNotNull(dt.smartscape.service)
| filter isNull(span.status_code) or span.status_code != "error"
| sort timestamp desc
| limit 1`)
}
