"""Shared in-memory tracing setup.

Traceloop can only be initialized once per process, so a single session-scoped
exporter is shared across all tests (init_tracing is idempotent — first call
wins)."""

import pytest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)


@pytest.fixture(scope="session")
def span_exporter() -> InMemorySpanExporter:
    from tracing import init_tracing

    exp = InMemorySpanExporter()
    init_tracing("test-fixtures", exporter=exp)
    return exp
