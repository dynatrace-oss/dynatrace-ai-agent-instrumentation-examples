package e2e

import (
	"testing"
)

func TestAnthropicOneAgent(t *testing.T) {
	startApp(t, "anthropic/oneagent")
	// Two calls in a row: the system prompt's cache_control block is byte-identical
	// across requests, so the first call only writes the Bedrock prompt cache and the
	// second reads from it (well within the 5-minute TTL). A single call would only
	// ever produce a cache WRITE, never a READ.
	triggerHaiku(t, true)
	triggerHaiku(t, true)

	auditSpan(t, "anthropic", "oneagent", AnthropicProfile,
		`fetch spans, from: now()-10m
| filter service.name == "anthropic/oneagent"
| filter (gen_ai.provider.name == "anthropic" or gen_ai.system == "anthropic") and dt.openpipeline.source == "oneagent"
| filter isNotNull(gen_ai.request.model)
| filter isNotNull(dt.smartscape.service)
| sort timestamp desc
| filter isNull(span.status_code) or span.status_code != "error"
| limit 1`)
}
