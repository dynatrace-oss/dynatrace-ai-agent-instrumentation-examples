# E2E Tests — Local Setup

End-to-end tests that start each demo app, invoke it, and assert that the expected `gen_ai.*` spans appear in Dynatrace. Tests use the [DQL query API](https://docs.dynatrace.com/docs/discover-dynatrace/references/dynatrace-api/environment-api/query) to poll for spans.

## Prerequisites

| Tool | Version | Required for |
|------|---------|-------------|
| Go | 1.22+ | running tests |
| Python | 3.11+ | demo apps |
| uv | 0.11+ | Python dependency management in demo apps |
| Docker (or Colima) | any | apps that use a local OTel collector (e.g. `*/opentelemetry`) |
| Dynatrace tenant | — | all tests |
| Provider credentials | — | tests for the relevant provider (AWS, OpenAI, etc.) |

## Environment setup

Copy `.env.sample` to `.env` and fill in the values relevant to the tests you want to run:

```bash
cp .env.sample .env
```

### Always required

| Variable | Description |
|----------|-------------|
| `DT_ENDPOINT` | Classic tenant URL, e.g. `https://abc12345.live.dynatrace.com`. Used by the OTel collector and OneAgent installer. |
| `DT_APPS_ENDPOINT` | Platform/apps URL, e.g. `https://abc12345.apps.dynatrace.com`. Used by the DQL query client. |
| `DT_API_TOKEN` | OAuth token with scopes: `storage:spans:read`, `storage:buckets:read`, `storage:events:read`, `storage:metrics:read`, `storage:metrics:write`, `openpipeline:traces:ingest`, `openpipeline:logs:ingest`, `openpipeline:events:ingest`, `openpipeline:metrics:ingest` |
| `MAX_RUNS` | Number of LLM invocations per run. Set to `1` for local runs to avoid flooding Dynatrace with data. |
| `OTEL_SERVICE_NAME` | Service name stamped on OTel spans — must match the `service.name` filter in the test's DQL query. Conventionally set to `<sdk>/<instrumentation>` (e.g. `aws-bedrock/opentelemetry`). |

### Provider credentials

Set the credentials for the provider under test. Leave others blank.

| Provider | Variables |
|----------|-----------|
| AWS Bedrock | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION`, `BEDROCK_MODEL_ID` |
| OpenAI | `OPENAI_API_KEY` |
| Anthropic | `ANTHROPIC_API_KEY` |
| Mistral | `MISTRAL_API_KEY` |
| Cohere | `COHERE_API_KEY` |
| Groq | `GROQ_API_KEY` |

## Running a single test

Load the `.env` file, set `OTEL_SERVICE_NAME` to match the test, then run it:

```bash
cd test/e2e
export $(grep -v '^#' .env | xargs)

# example: aws-bedrock/opentelemetry (requires Docker/Colima for the OTel collector)
OTEL_SERVICE_NAME=aws-bedrock/opentelemetry go test ./... -run TestAWSBedrockOpenTelemetry -v -timeout 20m

# example: openai/oneagent (requires OneAgent installed)
OTEL_SERVICE_NAME=openai/oneagent go test ./... -run TestOpenAIOneAgent -v -timeout 20m
```

`OTEL_SERVICE_NAME` follows the `<sdk>/<instrumentation>` convention and must match the DQL filter written in the test function.

## What each test does

1. Installs the demo app's Python dependencies (`make install` in the app directory).
2. Starts the app (`make run`), passing through all environment variables.
3. Sends a request to trigger an LLM call (HTTP apps POST to `localhost:8000`; CLI apps emit telemetry autonomously).
4. Polls the Dynatrace DQL API until matching `gen_ai.*` spans appear (up to 3 minutes, polling every 15 seconds).
5. Fetches all spans in the same trace to build a complete attribute picture.
6. Writes an audit report to `test/e2e/reports/<sdk>-<instrumentation>.{json,md}` (gitignored).
7. Stops the app.

The test passes as long as at least one matching span is found. Missing required attributes are logged but do not fail the test — gaps are visible in the audit report verdict (`FAIL`/`PARTIAL`/`PASS`).

## Audit reports

After a test run, audit reports are written to `test/e2e/reports/`. They are gitignored — inspect them locally. In CI, reports are uploaded as GitHub Actions artifacts and written to the job summary.

Attribute profiles (`GenericProfile`, `BedrockProfile`, …) are defined in `audit_test.go` and mirror the contracts in `sdk-comparison-baseline.json`. To update profiles after a baseline change, run `/update-audit-profiles` in Claude Code.

## Instrumentation types

| Instrumentation | What it tests |
|----------------|---------------|
| `oneagent` | Dynatrace OneAgent auto-instrumentation (requires OneAgent on the runner) |
| `opentelemetry` | OpenTelemetry SDK + local OTel collector → Dynatrace (requires Docker) |
| `openinference` | OpenInference instrumentation via OTel collector |

## Troubleshooting

**Spans not appearing within 3 minutes**
- Check that `OTEL_SERVICE_NAME` matches the `service.name` filter in the test's DQL query.
- Confirm the app started successfully — errors appear in test output before the poll starts.
- For `*/opentelemetry`: confirm Docker/Colima is running; the OTel collector must be up for telemetry to reach Dynatrace.
- Verify `DT_API_TOKEN` has all required scopes.

**`required env var not set` panic**
- `.env` was not loaded. Run `export $(grep -v '^#' .env | xargs)` before `go test`.

**App runs in an infinite loop**
- Set `MAX_RUNS=1` in `.env`.

**Port 8000 already in use**
- A previous test run's app process is still running. Kill it: `lsof -ti:8000 | xargs kill -9`.
