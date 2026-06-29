from dynatrace import init
init()

import os
from opentelemetry import trace
from strands_tools import calculator, current_time

from boto3 import Session
from strands import Agent, tool
from strands.models import BedrockModel

from opentelemetry.instrumentation.urllib3 import URLLib3Instrumentor
URLLib3Instrumentor().instrument()

import urllib3
http = urllib3.PoolManager()

otel_tracer = trace.get_tracer("strands-agents.tracer")


@tool
def create_appointment(date: str, location: str, title: str) -> str:
    """
    Create a new personal appointment in the database.

    Args:
        date (str): Date and time of the appointment (format: YYYY-MM-DD HH:MM).
        location (str): Location of the appointment.
        title (str): Title of the appointment.

    Returns:
        str: The ID of the newly created appointment.

    Raises:
        ValueError: If the date format is invalid.
    """
    with otel_tracer.start_as_current_span(name="appointment"):
        new_title = "Dentist appointment"
        contents = http.request("GET", "http://0.0.0.0:8081/api/v1/random")
        if contents:
            new_title = contents.data.decode('utf-8')
        return f"Appointment {new_title} with at {location} in {date} created"



def main():
    model = BedrockModel(
        model_id=os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0"),
        boto_session=Session(
            region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
        ),
    )
    system_prompt = """You are a helpful personal assistant that specializes in managing my appointments and calendar. 
You have access to appointment management tools, a calculator, and can check the current time to help me organize my schedule effectively. 
Always provide the appointment id so that I can update it if required"""
    agent = Agent(
        model=model,
        system_prompt=system_prompt,
        tools=[
            current_time,
            calculator,
            create_appointment,
        ],
    )
    results = agent("How much is 2+2?")
    print("=====")
    print(results)
    print(agent.messages)
    print(results.metrics)

    results = agent(
        "Book 'Agent fun' for tomorrow 3pm in NYC. This meeting will discuss all the fun things that an agent can do"
    )
    print("=====")
    print(results)
    print(agent.messages)
    print(results.metrics)


if __name__ == "__main__":
    with otel_tracer.start_as_current_span(name="/api", kind=trace.SpanKind.SERVER):
        main()
