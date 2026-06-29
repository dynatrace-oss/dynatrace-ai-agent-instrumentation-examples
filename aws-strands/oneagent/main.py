import os
from boto3 import Session
from strands import Agent
from strands.models import BedrockModel


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
        system_prompt="You are a haiku poet. Write a haiku (5-7-5 syllables) about the given topic. Reply with only the haiku, no extra text.",
    )


def write_haiku(topic: str) -> str:
    agent = create_agent()
    result = agent(f"Write a haiku about: {topic}")
    return str(result)
