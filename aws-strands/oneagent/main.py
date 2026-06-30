import os
from datetime import datetime, timezone
from boto3 import Session
from strands import Agent, tool
from strands.models import BedrockModel


@tool
def current_time(timezone_name: str = "UTC") -> str:
    """
    Get the current date and time in ISO 8601 format.

    Args:
        timezone_name (str): Timezone name (e.g. 'UTC', 'US/Eastern'). Defaults to UTC.

    Returns:
        str: Current datetime in ISO 8601 format.
    """
    return datetime.now(timezone.utc).isoformat()


@tool
def create_appointment(date: str, location: str, title: str) -> str:
    """
    Create a new personal appointment in the database.

    Args:
        date (str): Date and time of the appointment (format: YYYY-MM-DD HH:MM).
        location (str): Location of the appointment.
        title (str): Title of the appointment.

    Returns:
        str: Confirmation message with appointment details.
    """
    return f"Appointment '{title}' at {location} on {date} created"


def create_agent() -> Agent:
    model = BedrockModel(
        model_id=os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0"),
        boto_session=Session(
            region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
        ),
    )
    return Agent(
        model=model,
        system_prompt=(
            "You are a helpful personal assistant that specialises in managing appointments and calendars. "
            "You have access to appointment management tools, a calculator, and can check the current time "
            "to help organise schedules. Always provide the appointment id so that it can be updated if required."
        ),
        tools=[current_time, create_appointment],
    )


def run_agent(task: str) -> str:
    agent = create_agent()
    result = agent(task)
    return str(result)
