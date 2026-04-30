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
import requests

COLLECTOR_BASE_URL = "http://localhost:4318"

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
    BatchLogRecordProcessor(OTLPLogExporter(endpoint=f"{TRACELOOP_BASE_URL}/v1/logs"))
)
logging.getLogger().addHandler(OTLPLoggingHandler(logger_provider=_log_provider))

logging.info("Starting Bedrock Example Instrumetors...")

BedrockInstrumentor().instrument()
RequestsInstrumentor().instrument()
AsyncioInstrumentor().instrument()
BotocoreInstrumentor().instrument()


logging.info("Initializing traceloop...")
traceloop = Traceloop()
Traceloop.init(
    app_name="bedrock_example_app",
    disable_batch=True,
    should_enrich_metrics=True,
    api_endpoint=TRACELOOP_BASE_URL,
)

Traceloop.set_association_properties({
    "appid": "1234567890",
    "appname": "main",
    "assignmentgroup": "Dynatrace Sales Engineering",
    "ecosystem": "Observability Engineering",
})


@task("run_converse")
def run_converse(client_context):
    logging.info("Calling Converse API with Boto3...")
    response = client_context.converse(
        modelId="us.anthropic.claude-haiku-4-5-20251001-v1:0",
        messages=[
            {
                "role": "user",
                "content": [{"text": "Write a one-sentence bedtime story about a unicorn."}]
            }
        ]
    )
    print(response["output"]["message"]["content"][0]["text"])

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




@workflow("aws_bedrock_agent")
def run_workflow():
    logging.info("Starting the Workflow...")
    client = boto3.client("bedrock-runtime", region_name="us-east-1")

    run_converse(client)
    run_invoke(client)
    # run_call_with_service_tier()
    run_invoke_extra(client)

@agent("aws_bedrock_agent")
def run_agent():
    logging.info("Starting the Agent  ...")
    run_workflow()


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    count = 0
    while True:
        run_agent()
        count += 1
        sleep(5)
        if count > 60:
            exit(0)




