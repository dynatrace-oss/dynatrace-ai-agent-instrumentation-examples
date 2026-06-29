## Strands Agents

This example contains a demo of a Personal Assistant Agent built on top of [Strands Agents](https://strandsagents.com/).

![Trace View](../../assets/trace-view.png)

## Dynatrace Instrumentation

> [!TIP]
> For detailed setup instructions, configuration options, and advanced use cases, please refer to the [Get Started Docs](https://docs.dynatrace.com/docs/shortlink/ai-ml-get-started).

Strands Agents comes with [OpenTelemetry](https://opentelemetry.io/) support out-of-the-box.
We just need to register an [OpenTelemetry SDK](https://github.com/open-telemetry/opentelemetry-specification/blob/main/specification/overview.md#sdk) to send the data to Dynatrace.

We simplified this process, hiding all the complexity inside [dynatrace.py](./dynatrace.py).
For sending data to your Dynatrace tenant, configure the following environment variables:

- `OTEL_ENDPOINT` — your Dynatrace OTLP ingest URL, e.g. `https://<tenant>.live.dynatrace.com/api/v2/otlp`
- `DT_API_TOKEN` — Dynatrace API token with `openpipeline:traces:ingest` and `openpipeline:metrics:ingest` scopes

The token is read from `DT_API_TOKEN` (or from `/etc/secrets/dynatrace_otel` when running on a host with mounted secrets).

## How to use

### Setting your AWS keys

Follow the [Amazon Bedrock documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/security_iam_id-based-policy-examples-agent.html) to configure your AWS Role with the correct policies.
Afterwards, set your AWS credentials as environment variables:

```bash
export AWS_ACCESS_KEY_ID=your_access_key_id
export AWS_SECRET_ACCESS_KEY=your_secret_access_key
export AWS_DEFAULT_REGION=us-east-1
```

Ensure your account has access to the model `us.anthropic.claude-haiku-4-5-20251001-v1:0` used in this example. Refer to the
[Amazon Bedrock documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access-permissions.html) to enable model access.


### Run the app

`uv run main.py`
