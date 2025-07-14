import random

def read_secret(secret: str):
    try:
        with open(f"/etc/secrets/{secret}", "r") as f:
            return f.read().rstrip()
    except Exception as e:
        print("No token was provided")
        print(e)
        return ""

token = read_secret("otel_event")
headers = {"Authorization": f"Api-Token {token}"}
OTEL_ENDPOINT = "https://xbw95514.dev.dynatracelabs.com/api/v2/otlp/v1/traces"

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.resources import Resource
resource = Resource.create(
    {"service.name": "aws-agents-demo-random", "service.version": "0.4.14"}
)

provider = TracerProvider(resource=resource)
processor = SimpleSpanProcessor(
    OTLPSpanExporter(endpoint=f"{OTEL_ENDPOINT}", headers=headers)
)
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)
otel_tracer = trace.get_tracer("server-advisor.tracer")


from fastapi import FastAPI
import uvicorn

app = FastAPI()

from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
FastAPIInstrumentor.instrument_app(app)

@app.get("/api/v1/random")
def get_random():
    with otel_tracer.start_as_current_span(name="/api/v1/random") as span:
        v = random.randrange(0,100)
        span.set_attribute("rnd", v)
        return f"You get {v}"


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8081)