from dynatrace import init
init()

import ast
import operator
import os
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo
from opentelemetry import trace

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
        appointments_url = os.environ.get(
            "APPOINTMENTS_URL", "http://127.0.0.1:8081"
        )
        contents = http.request("GET", f"{appointments_url}/api/v1/random")
        if contents:
            new_title = contents.data.decode('utf-8')
        return f"Appointment {new_title} with at {location} in {date} created"


_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}


def _eval_arith(node):
    if isinstance(node, ast.Expression):
        return _eval_arith(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _eval_arith(node.operand)
        return value if isinstance(node.op, ast.UAdd) else -value
    if isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
        return _BINOPS[type(node.op)](_eval_arith(node.left), _eval_arith(node.right))
    raise ValueError("only basic arithmetic is supported")


@tool
def calculator(expression: str) -> str:
    """
    Evaluate a basic arithmetic expression.

    strands-agents-tools removed its calculator in 0.9.0. The replacement it
    suggests is a shell that runs arbitrary commands, so this demo keeps an
    allowlisted evaluator for the expressions the agent is asked to compute.

    Args:
        expression (str): An arithmetic expression such as '2+2'.

    Returns:
        str: The numeric result.
    """
    return str(_eval_arith(ast.parse(expression, mode="eval")))


@tool
def current_time(timezone_name: str = "UTC") -> str:
    """
    Get the current date and time in ISO 8601 format.

    Args:
        timezone_name (str): IANA timezone name such as 'UTC' or 'America/New_York'.

    Returns:
        str: Current datetime in ISO 8601 format.
    """
    return datetime.now(ZoneInfo(timezone_name)).isoformat()


TEMPERATURE = 0.7


def main():
    model = BedrockModel(
        temperature=TEMPERATURE,
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
        # Strands does not emit these on its spans itself.
        trace_attributes={
            "gen_ai.conversation.id": str(uuid.uuid4()),
            "gen_ai.request.temperature": TEMPERATURE,
        },
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
