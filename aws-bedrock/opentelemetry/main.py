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
import requests

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
        "modelId": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
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
        modelId="us.anthropic.claude-haiku-4-5-20251001-v1:0",
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
        modelId="us.anthropic.claude-haiku-4-5-20251001-v1:0",
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
    model_id = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

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




# ---------------------------------------------------------------------------
# Multi-agent turn: reproduces the "Prompts view mis-correlates input/output"
# scenario reported by customers instrumenting Bedrock agents with OpenLLMetry,
# and shows the two fixes.
#
# THE PROBLEM: a single user turn fans out into several Bedrock calls (router,
# answer agent, an eval/judge). OpenLLMetry stamps gen_ai.* on each *model call*
# span, but NOT on the traceloop @workflow/@agent span. The Prompts view pairs
# input->output per gen_ai span, so intermediate calls produce half-rows and no
# single span holds "user question -> final answer".
#
# FIX 1 (_stamp_turn_io): put the whole turn on the workflow span so exactly one
#        clean input->output record exists.
# FIX 2 (evaluate_answer): emit the judge result as a separate evaluation signal
#        instead of running it as a chat span that looks like a real reply.
# ---------------------------------------------------------------------------

def _stamp_turn_io(user_question, final_answer):
    """Stamp the whole user turn onto the current (workflow) span.

    Sets both attribute forms so the Prompts view has a canonical turn record:
      - flat form (gen_ai.prompt.N / gen_ai.completion.N) that current OpenLLMetry
        Bedrock spans already use and the Prompts view reads today;
      - message form (gen_ai.input.messages / gen_ai.output.messages) from the
        Dynatrace semantic dictionary.
    gen_ai.operation.name=chat is the dictionary-defined value for a chat turn.
    """
    span = _ot_trace.get_current_span()
    # The AI Observability app treats a span as a GenAI span only when
    # gen_ai.system OR gen_ai.provider.name is set (its DQL_AI_SPANS_FILTER).
    # The @workflow span has neither by default, so without these markers the
    # stamped turn record below would be filtered out of the Prompts view.
    span.set_attribute("gen_ai.system", "anthropic")
    span.set_attribute("gen_ai.provider.name", "anthropic")
    span.set_attribute("gen_ai.operation.name", "chat")
    # flat form (read by the Prompts view today)
    span.set_attribute("gen_ai.prompt.0.role", "user")
    span.set_attribute("gen_ai.prompt.0.content", user_question)
    span.set_attribute("gen_ai.completion.0.role", "assistant")
    span.set_attribute("gen_ai.completion.0.content", final_answer)
    # message form (semantic dictionary)
    span.set_attribute(
        "gen_ai.input.messages",
        json.dumps([{"role": "user",
                     "parts": [{"type": "text", "content": user_question}]}]),
    )
    span.set_attribute(
        "gen_ai.output.messages",
        json.dumps([{"role": "assistant",
                     "parts": [{"type": "text", "content": final_answer}]}]),
    )


@task("route_intent")
def route_intent(client_context, question):
    """Internal router call -> emits its own gen_ai span (NOT a user turn)."""
    resp = client_context.converse(
        modelId=MODEL_ID,
        messages=[{"role": "user", "content": [{
            "text": "You are an intent classifier. Reply ONLY with a JSON like "
                    '{"agent":"<name>","confidence":<0-1>}. Message: ' + question
        }]}],
    )
    return resp["output"]["message"]["content"][0]["text"]


@task("answer_agent")
def answer_agent(client_context, question):
    """Specialist agent call -> emits its own gen_ai span (NOT a user turn)."""
    resp = client_context.converse(
        modelId=MODEL_ID,
        messages=[{"role": "user", "content": [{"text": question}]}],
    )
    return resp["output"]["message"]["content"][0]["text"]


def _emit_evaluation_bizevent(payload):
    """Ingest the evaluation as a Dynatrace Business Event.

    Endpoint: POST {DT_ENDPOINT}/api/v2/bizevents/ingest (Content-Type
    application/json), token scope `bizevents.ingest`. Configure via env:
      DT_ENDPOINT   e.g. https://<env-id>.live.dynatrace.com
      DT_API_TOKEN  token with the bizevents.ingest scope
    If either is unset, we skip the REST call and fall back to an OTLP log so
    the default local-collector run still works.
    """
    dt_base = os.environ.get("DT_ENDPOINT", "").rstrip("/")
    dt_token = os.environ.get("DT_API_TOKEN", "")
    if not (dt_base and dt_token):
        return False
    resp = requests.post(
        f"{dt_base}/api/v2/bizevents/ingest",
        headers={
            "Authorization": f"Api-Token {dt_token}",
            "Content-Type": "application/json",
        },
        data=json.dumps(payload),
        timeout=10,
    )
    resp.raise_for_status()
    return True


def evaluate_answer(question, answer):
    """LLM-as-judge, emitted as an EVALUATION signal -- not a chat span.

    A judge implemented as a normal Bedrock converse call is indistinguishable
    from a user-facing reply and pollutes the Prompts/conversation view. The
    Dynatrace convention is a separate evaluation-result signal (a Business
    Event), so this is ingested via /api/v2/bizevents/ingest and lands on the
    AI Observability Evaluations page rather than in Prompts.

    The bizevent is correlated to the turn via trace_id/span_id. When DT_ENDPOINT
    / DT_API_TOKEN are not set, it falls back to an OTLP log for local testing.
    """
    # Deterministic stand-in verdict; swap for a real judge call if desired.
    passed = bool(answer and len(answer.strip()) > 0)

    ctx = _ot_trace.get_current_span().get_span_context()
    event = {
        "event.type": "gen_ai.evaluation",
        "event.provider": "aws-bedrock-opentelemetry-example",
        "gen_ai.operation.name": "chat",
        "gen_ai.request.model": MODEL_ID,
        "gen_ai.evaluation.name": "non_empty_answer",
        "gen_ai.evaluation.score": 1.0 if passed else 0.0,
        "gen_ai.evaluation.passed": passed,
        "gen_ai.evaluation.question": question,
        "gen_ai.evaluation.answer": answer,
        "trace_id": format(ctx.trace_id, "032x"),
        "span_id": format(ctx.span_id, "016x"),
    }

    try:
        if not _emit_evaluation_bizevent(event):
            logging.info("gen_ai.evaluation", extra=event)
    except Exception as e:
        logging.error(f"Failed to ingest evaluation bizevent: {e}")
        logging.info("gen_ai.evaluation", extra=event)
    return passed


@workflow("multiagent_turn")
def run_multiagent_turn(client_context, question):
    logging.info("Starting a multi-agent turn...")
    route_intent(client_context, question)          # internal call -> own gen_ai span
    answer = answer_agent(client_context, question)  # internal call -> own gen_ai span
    _stamp_turn_io(question, answer)                 # FIX 1: one correct turn record
    evaluate_answer(question, answer)                # FIX 2: eval as separate signal
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




