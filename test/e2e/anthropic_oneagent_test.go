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

	const baseFilter = `fetch spans, from: now()-10m
| filter service.name == "anthropic/oneagent"
| filter (gen_ai.provider.name == "anthropic" or gen_ai.system == "anthropic") and dt.openpipeline.source == "oneagent"
| filter isNotNull(gen_ai.request.model)
| filter isNotNull(dt.smartscape.service)
| filter isNull(span.status_code) or span.status_code != "error"
`
	// The write (call 1) and read (call 2) cache hits land on two different spans in
	// two different traces, so a single anchor query would only ever surface one of
	// gen_ai.usage.prompt_caching.write_tokens / .read_tokens. Anchor on each
	// independently and let auditSpanMerged combine both traces into one report.
	auditSpanMerged(t, "anthropic", "oneagent", AnthropicProfile, []string{
		baseFilter + `| filter isNotNull(gen_ai.usage.prompt_caching.write_tokens)
| sort timestamp desc
| limit 1`,
		baseFilter + `| filter isNotNull(gen_ai.usage.prompt_caching.read_tokens)
| sort timestamp desc
| limit 1`,
	})
}
