## Amazon Bedrock AgentCore

This example contains a demo of a Personal Assistant Agent built on top of [Bedrock AgentCore Agents](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html).

![Trace View](../../assets/trace-view.png)

## Dynatrace Instrumentation

> [!TIP]
> For detailed setup instructions, configuration options, and advanced use cases, please refer to the [Get Started Docs](https://docs.dynatrace.com/docs/shortlink/ai-ml-get-started).

Bedrock AgentCore comes with [Observability](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability.html) support out-of-the-box.
Dynatrace OneAgent automatically instruments the underlying AWS Bedrock API calls without any code changes required.

## How to use

### Setting your AWS keys

Follow the [Amazon Bedrock AgentCore documentation](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-permissions.html) to configure your AWS Role with the correct policies.
Afterwards, set your AWS credentials in environment variables:

```bash
export AWS_ACCESS_KEY_ID=your_api_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_DEFAULT_REGION=us-east-1
```

Ensure your account has access to the model `us.anthropic.claude-haiku-4-5-20251001-v1:0` used in this example. Refer to the
[Amazon Bedrock documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access-permissions.html) to enable model access.
You can change the model by setting the `BEDROCK_MODEL_ID` environment variable.

### Run the app

```bash
make install
make run
```

The agent is available at `http://localhost:8000/agent`. Send a POST request with a `task` field:

```bash
make request
```
