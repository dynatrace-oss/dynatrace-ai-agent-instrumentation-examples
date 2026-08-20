"""Downstream 'appointments' service for the Strands OpenInference demo.

The agent's create_appointment tool issues GET /api/v1/random against this
service to fetch a random appointment title. Running it alongside the agent
turns that tool call into a real downstream span, so the trace spans two
services instead of failing with connection-refused.

Traces are exported to the same OTLP endpoint as the agent (the local OTel
Collector by default, or Dynatrace directly when run via run-openpipeline),
so the server span joins the agent's distributed trace via context
propagation from the incoming request headers.
"""
import os
import random

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

SERVICE_NAME = os.environ.get(
    "APPOINTMENTS_SERVICE_NAME", "aws-strands/openinference-appointments-service"
)

provider = TracerProvider(resource=Resource.create({"service.name": SERVICE_NAME}))
provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
trace.set_tracer_provider(provider)

APPOINTMENT_TITLES = [
    "Dentist appointment",
    "Team sync",
    "1:1 with manager",
    "Project kickoff",
    "Yoga class",
    "Coffee catch-up",
]

app = FastAPI()
FastAPIInstrumentor.instrument_app(app)


@app.get("/api/v1/random", response_class=PlainTextResponse)
def random_appointment_title() -> str:
    """Return a random appointment title for the agent to use."""
    return random.choice(APPOINTMENT_TITLES)
