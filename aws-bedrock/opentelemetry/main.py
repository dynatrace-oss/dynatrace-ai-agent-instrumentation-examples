# This is a sample Python script.

# Press ⌃R to execute it or replace it with your code.
# Press Double ⇧ to search everywhere for classes, files, tool windows, actions, and settings.

import os
import sys
import boto3
from tenacity import sleep
from traceloop.sdk import Traceloop
import logging
import json

from opentelemetry.instrumentation.bedrock import BedrockInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.botocore import BotocoreInstrumentor
from opentelemetry.instrumentation.asyncio import AsyncioInstrumentor

from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler as OTLPLoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry._logs import set_logger_provider

from traceloop.sdk.decorators import workflow, task, agent
from opentelemetry import trace as _ot_trace

import evaluator

COLLECTOR_BASE_URL = "http://localhost:4318"
MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

logging.basicConfig(
    level=logging.DEBUG,
    stream=sys.stdout,
    format="%(asctime)s %(levelname)s %(message)s",
)
logging.getLogger("botocore").setLevel(logging.INFO)
logging.getLogger("urllib3").setLevel(logging.INFO)

# Ship Python logs to the local OTel collector via OTLP/HTTP
_log_provider = LoggerProvider()
set_logger_provider(_log_provider)
_log_provider.add_log_record_processor(
    BatchLogRecordProcessor(OTLPLogExporter(endpoint=f"{COLLECTOR_BASE_URL}/v1/logs"))
)
logging.getLogger().addHandler(OTLPLoggingHandler(logger_provider=_log_provider))

logging.info("Starting Bedrock Example Instrumetors...")

BedrockInstrumentor().instrument()
RequestsInstrumentor().instrument()
AsyncioInstrumentor().instrument()
BotocoreInstrumentor().instrument()


logging.info("Initializing traceloop...")
# Dynatrace OTLP metric ingest accepts delta temporality only; cumulative is rejected (HTTP 400).
# Must be set before Traceloop.init builds the metric exporter.
os.environ.setdefault("OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE", "delta")
traceloop = Traceloop()
Traceloop.init(
    app_name=os.environ.get("OTEL_SERVICE_NAME", "bedrock_example_app"),
    disable_batch=True,
    should_enrich_metrics=True,
    api_endpoint=COLLECTOR_BASE_URL,
)

Traceloop.set_association_properties({
    "appid": "1234567890",
    "appname": "main",
    "assignmentgroup": "Dynatrace Sales Engineering",
    "ecosystem": "Observability Engineering",
})


def _guardrail_config():
    guardrail_id = os.environ.get("BEDROCK_GUARDRAIL_ID")
    if not guardrail_id:
        return None
    return {
        "guardrailIdentifier": guardrail_id,
        "guardrailVersion": os.environ.get("BEDROCK_GUARDRAIL_VERSION", "DRAFT"),
        "trace": "enabled",
    }


@task("run_converse")
def run_converse(client_context):
    logging.info("Calling Converse API with Boto3...")
    kwargs = {
        "modelId": MODEL_ID,
        "messages": [
            {
                "role": "user",
                "content": [{"text": "Write a one-sentence bedtime story about a unicorn."}]
            }
        ],
    }
    gc = _guardrail_config()
    if gc:
        kwargs["guardrailConfig"] = gc
    response = client_context.converse(**kwargs)
    print(response["output"]["message"]["content"][0]["text"])


@task("run_converse_guardrail_trigger")
def run_converse_guardrail_trigger(client_context):
    gc = _guardrail_config()
    if not gc:
        return
    logging.info("Calling Converse API with a prompt designed to trigger the guardrail...")
    response = client_context.converse(
        modelId=MODEL_ID,
        messages=[
            {
                "role": "user",
                "content": [{"text": "What are the best football strategies for the World Cup?"}]
            }
        ],
        guardrailConfig=gc,
    )
    stop_reason = response.get("stopReason", "")
    logging.info(f"Guardrail trigger stop reason: {stop_reason}")
    output = response["output"]["message"]["content"]
    print(output[0]["text"] if output else "(blocked by guardrail)")

@task("run_invoke")
def run_invoke(client_context):
    logging.info("Calling Invoke API with Boto3...")
    response = client_context.invoke_model(
        modelId=MODEL_ID,
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1024,
            "messages": [{
                "role": "user",
                "content": "Tell me a short story about a robot."
            }]
        })
    )

    result = json.loads(response["body"].read())
    print(result["content"][0]["text"])

@task("run_invoke_extra")
def run_invoke_extra(client_context):
    logging.info("Calling Invoke API Extra with Boto3...")
# Use the native inference API to send a text message to Amazon Titan Text.
    from botocore.exceptions import ClientError

    # Create a Bedrock Runtime client in the AWS Region of your choice.

    # Set the model ID, e.g., Titan Text Premier.
    #model_id = "amazon.titan-text-premier-v1:0"
    model_id = MODEL_ID

    # Define the prompt for the model.
    prompt = "Describe the purpose of a 'hello world' program in one line."

    # Format the request payload using the model's native structure.
    native_request = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 512,
        "messages": [{"role": "user", "content": prompt}],
    })

    try:
        # Invoke the model with the request.
        response = client_context.invoke_model(modelId=model_id, body=native_request)

    except (ClientError, Exception) as e:
        logging.error(f"ERROR: Can't invoke '{model_id}'. Reason: {e}")
        exit(1)

    # Decode the response body.
    model_response = json.loads(response["body"].read())

    # Extract and print the response text.
    response_text = model_response["content"][0]["text"]
    logging.info(response_text)




# Multi-agent turn: one user turn fans out into several Bedrock calls, then the
# turn is recorded on the agent span and evaluated out-of-band (see evaluator.py
# and the README "Multi-agent turn" section).


def _messages(role, text):
    return json.dumps([{"role": role, "parts": [{"type": "text", "content": text}]}])


def _stamp_turn_io(span, question, answer):
    # Type the turn as an agent span (not a model call) and record it once via the
    # message form. provider.name is honest here (the agent is Bedrock-backed) and
    # is what makes the turn show up in the Prompts view.
    span.set_attribute("gen_ai.provider.name", "aws.bedrock")
    span.set_attribute("gen_ai.operation.kind", "agent")
    span.set_attribute("gen_ai.agent.name", "multiagent_turn")
    span.set_attribute("gen_ai.input.messages", _messages("user", question))
    span.set_attribute("gen_ai.output.messages", _messages("assistant", answer))


def _converse_text(client_context, text):
    resp = client_context.converse(
        modelId=MODEL_ID, messages=[{"role": "user", "content": [{"text": text}]}])
    return resp["output"]["message"]["content"][0]["text"]


@task("route_intent")
def route_intent(client_context, question):
    return _converse_text(client_context,
        'Classify the intent. Reply ONLY JSON {"agent":..,"confidence":..}. ' + question)


@task("answer_agent")
def answer_agent(client_context, question):
    return _converse_text(client_context, question)


@agent("multiagent_turn")
def run_multiagent_turn(client_context, question):
    span = _ot_trace.get_current_span()
    route_intent(client_context, question)
    answer = answer_agent(client_context, question)
    _stamp_turn_io(span, question, answer)
    evaluator.submit(span, question, answer, MODEL_ID)
    print(answer)
    return answer


@workflow("aws_bedrock_agent")
def run_workflow():
    logging.info("Starting the Workflow...")
    client = boto3.client("bedrock-runtime", region_name="us-east-1")

    run_converse(client)
    run_converse_guardrail_trigger(client)
    run_invoke(client)
    # run_call_with_service_tier()
    run_invoke_extra(client)

    # Multi-agent turn demonstrating the Prompts-view correlation fix.
    run_multiagent_turn(client, "What is the policy for checking my account balance?")

@agent("aws_bedrock_agent")
def run_agent():
    logging.info("Starting the Agent  ...")
    run_workflow()


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    count = 0
    max_runs = int(os.environ.get('MAX_RUNS', '60'))
    while True:
        run_agent()
        count += 1
        if count >= max_runs:
            exit(0)
        sleep(5)




