# dt-evals fixtures (OpenTelemetry)

Deterministic GenAI spans for dt-evals end-to-end tests.

Every other example in this repo runs a real framework against a real LLM, so
the spans — and any eval score derived from them — differ from run to run. An
eval regression suite needs the opposite: **the same prompt and the same answer
every time**, so a toxic answer always scores toxic and a clean one always
passes.

This example drives a real, Traceloop-instrumented LangChain chat model, but the
model is a [`FakeListChatModel`](https://reference.langchain.com/python/langchain-core/language_models/fake_chat_models/FakeListChatModel)
pre-programmed with the answers in `fixtures.json`. Because the spans come from
the same instrumentation path a real LangChain app uses, they carry exactly the
attribute shape dt-evals sees in production — no hand-built spans, no LLM
provider, no collector, no API key.

## Run

```bash
cp .env.sample .env   # fill in DT_ENDPOINT + DT_API_TOKEN
make install
make run               # in one shell
make request           # in another — POSTs /ingest, replays every fixture
```

The spans land under `service.name = dt-evals-fixtures` (configurable via the
`service_name` field in `fixtures.json`).

## Fixtures

`fixtures.json` holds a list of `cases`. Each case defines the `system` prompt,
the `user` message, and the canned `response`. Add a case by appending an
object; edit an answer by changing its `response`. The current set covers a
clean geography answer, a clean support answer, and a deliberately toxic support
answer for the toxicity eval.

The fake model returns the responses in fixture order, one per invocation, so
the sequence in `fixtures.json` maps one-to-one onto the emitted spans.

## Caveats

A fake model reports no real token usage and no real model name, so
`gen_ai.usage.*` and `gen_ai.request.model` will be empty or generic. If dt-evals
needs those, set them via the fixture and a small model subclass. Message
content is captured because `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT`
is on (see `app.py`).
