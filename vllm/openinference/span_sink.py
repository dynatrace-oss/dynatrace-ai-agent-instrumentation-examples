"""Minimal OTLP/HTTP trace receiver that counts spans per trace.

Accepts protobuf exports on POST /v1/traces, keeps per-trace span counts in
memory, and serves a summary on GET /stats. Reset with POST /reset.
"""

import os
from collections import Counter

from fastapi import FastAPI, Request, Response
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTraceServiceRequest,
    ExportTraceServiceResponse,
)

app = FastAPI()
spans_per_trace: Counter[str] = Counter()
span_names: Counter[str] = Counter()


@app.post("/v1/traces")
async def traces(request: Request) -> Response:
    msg = ExportTraceServiceRequest()
    msg.ParseFromString(await request.body())
    for rs in msg.resource_spans:
        for ss in rs.scope_spans:
            for span in ss.spans:
                spans_per_trace[span.trace_id.hex()] += 1
                span_names[span.name] += 1
    return Response(
        ExportTraceServiceResponse().SerializeToString(),
        media_type="application/x-protobuf",
    )


@app.get("/stats")
def stats() -> dict:
    traces = len(spans_per_trace)
    total = sum(spans_per_trace.values())
    return {
        "traces": traces,
        "spans": total,
        "spans_per_trace": round(total / traces, 2) if traces else 0,
        "span_names": dict(span_names),
    }


@app.post("/reset")
def reset() -> dict:
    spans_per_trace.clear()
    span_names.clear()
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("SINK_PORT", "14318")))
