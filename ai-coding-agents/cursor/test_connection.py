#!/usr/bin/env python3
"""Emit synthetic Cursor-shaped OTLP logs and metrics; does not instrument Cursor."""
import os, sys, time, uuid, urllib.error, urllib.request
from pathlib import Path
from dotenv import load_dotenv
from opentelemetry import metrics
from opentelemetry._logs import SeverityNumber, set_logger_provider
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource

load_dotenv(Path(__file__).parent / ".env")
token=os.getenv("DT_API_TOKEN",""); endpoint=os.getenv("DT_OTEL_ENDPOINT","").rstrip("/")
for suffix in ("/v1/logs","/v1/metrics","/v1/traces"):
    if endpoint.endswith(suffix): endpoint=endpoint[:-len(suffix)]
if not token or not endpoint:
    print("ERROR: Set DT_API_TOKEN and DT_OTEL_ENDPOINT in .env",file=sys.stderr); raise SystemExit(1)
headers={"Authorization":f"Api-Token {token}"}
def preflight(path):
    req=urllib.request.Request(endpoint+path,data=b"",headers={**headers,"Content-Type":"application/x-protobuf"},method="POST")
    try:
        with urllib.request.urlopen(req,timeout=15) as resp: print(f"Preflight {path}: HTTP {resp.status}"); return True
    except urllib.error.HTTPError as exc:
        if exc.code==400: print(f"Preflight {path}: reachable (expected HTTP 400 for empty payload)"); return True
        print(f"Preflight {path}: HTTP {exc.code}",file=sys.stderr)
    except urllib.error.URLError as exc: print(f"Preflight {path}: {exc.reason}",file=sys.stderr)
    return False
if not all(preflight(p) for p in ("/v1/logs","/v1/metrics")): raise SystemExit(1)
resource=Resource.create({"service.name":"cursor","cursor.team.id":"team-demo","cursor.user.id":"user-demo","cursor.surface":"cloud_agent","cursor.entrypoint":"editor"})
lp=LoggerProvider(resource=resource); lp.add_log_record_processor(BatchLogRecordProcessor(OTLPLogExporter(endpoint=endpoint+"/v1/logs",headers=headers))); set_logger_provider(lp)
otel_logger=lp.get_logger("cursor.telemetry.synthetic", "0.1.0")
os.environ["OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE"]="delta"
reader=PeriodicExportingMetricReader(OTLPMetricExporter(endpoint=endpoint+"/v1/metrics",headers=headers),export_interval_millis=3000)
mp=MeterProvider(resource=resource,metric_readers=[reader]); metrics.set_meter_provider(mp); meter=metrics.get_meter("cursor.telemetry","0.1.0")
tokens=meter.create_counter("cursor.token.usage",unit="{token}"); tools=meter.create_counter("cursor.tool.calls",unit="{call}"); cost=meter.create_counter("cursor.cost.usage",unit="USD")
conv="conv-demo-"+uuid.uuid4().hex[:8]; turn="turn-demo-"+uuid.uuid4().hex[:8]; usage="usage-demo-"+uuid.uuid4().hex[:8]; reqid="request-demo-"+uuid.uuid4().hex[:8]
def emit(name,body,**attrs):
    otel_logger.emit(
        severity_number=SeverityNumber.INFO,
        severity_text="INFO",
        body=body,
        attributes={"event.name":name,"cursor.event.id":"event-demo-"+uuid.uuid4().hex,**attrs},
        event_name=name,
    )
common={"cursor.conversation.id":conv,"cursor.request.id":reqid}
emit("cursor.api.request","api_request",**common,**{"cursor.usage_event.id":usage,"cursor.model.name":"claude-sonnet-demo","cursor.api.request.input_tokens":1200,"cursor.api.request.output_tokens":240,"cursor.api.request.cache_read_tokens":400,"cursor.api.request.cache_creation_tokens":80,"cursor.api.request.duration_ms":1820})
emit("cursor.skill.activated","skill_activated",**common,**{"cursor.skill.name":"repo-review"})
emit("cursor.hook.execution_complete","hook_execution_complete",**common,**{"cursor.hook.name":"afterFileEdit","cursor.hook.duration_ms":85,"cursor.hook.outcome":"success"})
emit("cursor.cloud_agent.setup","cloud_agent_setup",**common,**{"cursor.cloud_agent.status":"completed"})
emit("cursor.conversation.user_message","Create a safe example dashboard",**common,**{"cursor.conversation.turn.id":turn,"cursor.conversation.content_truncated":False})
emit("cursor.conversation.assistant_message","Created a synthetic dashboard example",**common,**{"cursor.conversation.turn.id":turn,"cursor.conversation.content_truncated":False})
for kind,value in (("input",1200),("output",240),("cache_read",400),("cache_creation",80)): tokens.add(value,{"cursor.token.type":kind,"cursor.model.name":"claude-sonnet-demo"})
tools.add(2,{"cursor.tool.kind":"builtin","cursor.tool.name":"read_file"}); cost.add(0.018,{"cursor.model.name":"claude-sonnet-demo"})
print("Flushing synthetic telemetry...")
time.sleep(5)
try:
    lp.force_flush(timeout_millis=10000)
    mp.force_flush(timeout_millis=10000)
finally:
    lp.shutdown()
    mp.shutdown()
print("Done.")
