import os

def read_secret(secret: str):
    try:
        with open(f"/etc/secrets/{secret}", "r") as f:
            return f.read().rstrip()
    except Exception as e:
        print("No token was provided")
        print(e)
        return ""

def init():
    os.environ['TRACELOOP_TELEMETRY'] = "false"
    os.environ["OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE"] = "delta"
    token = read_secret("dynatrace_otel")
    headers = {"Authorization": f"Api-Token {token}"}
    OTEL_ENDPOINT = os.environ.get(
        "OTEL_ENDPOINT", "https://wkf10640.live.dynatrace.com/api/v2/otlp" #manually configure your DT tenant here or a OTel collector endpoint
    )
    from traceloop.sdk import Traceloop
    token = read_secret("dynatrace_otel")
    headers = {"Authorization": f"Api-Token {token}"}
    Traceloop.init(
        app_name="agent-core-samples",
        api_endpoint=OTEL_ENDPOINT,
        disable_batch=True,
        headers=headers,
        should_enrich_metrics=True,
    )
    