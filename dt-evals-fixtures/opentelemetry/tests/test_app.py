"""The FastAPI app loads fixtures from FIXTURES_PATH and /ingest replays them."""

import importlib
import json

from opentelemetry import trace


def test_ingest_replays_fixtures_and_emits_spans(span_exporter, tmp_path, monkeypatch):
    fixtures = {
        "service_name": "svc-under-test",
        "cases": [
            {"name": "single", "user": "hi", "response": "yo"},
            {
                "name": "multi",
                "system": "s",
                "turns": [
                    {"user": "x", "response": "y"},
                    {"user": "z", "response": "w"},
                ],
            },
        ],
    }
    fpath = tmp_path / "fixtures.json"
    fpath.write_text(json.dumps(fixtures))
    monkeypatch.setenv("FIXTURES_PATH", str(fpath))

    import app as app_module

    importlib.reload(app_module)  # re-read fixtures from FIXTURES_PATH

    assert app_module.SERVICE_NAME == "svc-under-test"

    span_exporter.clear()
    result = app_module.ingest()
    trace.get_tracer_provider().force_flush()

    # One entry per case, span count sums each case's turns (1 + 2).
    assert result == {"ingested": 2, "cases": ["single", "multi"]}
    assert len(span_exporter.get_finished_spans()) == 3


def test_health_ok():
    import app as app_module

    assert app_module.health() == {"status": "ok"}
