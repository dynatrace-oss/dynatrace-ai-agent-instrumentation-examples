/**
 * telemetry.ts — OpenTelemetry bootstrap for Dynatrace OTLP export.
 *
 * Initializes the OTel NodeSDK with OTLP/HTTP protobuf exporters for
 * traces and metrics, configured for Dynatrace ingestion.
 *
 * Call initTelemetry() BEFORE any other imports that create spans/metrics.
 */

import { NodeSDK } from "@opentelemetry/sdk-node";
import { OTLPTraceExporter } from "@opentelemetry/exporter-trace-otlp-proto";
import { OTLPMetricExporter } from "@opentelemetry/exporter-metrics-otlp-proto";
import { PeriodicExportingMetricReader, AggregationTemporality } from "@opentelemetry/sdk-metrics";
import { BatchSpanProcessor } from "@opentelemetry/sdk-trace-base";
import { Resource } from "@opentelemetry/resources";
import { ATTR_SERVICE_NAME } from "@opentelemetry/semantic-conventions";
import { trace, metrics, type Tracer, type Meter } from "@opentelemetry/api";

let sdk: NodeSDK | null = null;

/**
 * Initialize OpenTelemetry with Dynatrace OTLP exporters.
 *
 * Requires environment variables:
 * - DYNATRACE_OTLP_URL: OTLP base path (e.g., https://abc123.live.dynatrace.com/api/v2/otlp)
 * - DYNATRACE_OTLP_TOKEN: Classic API token (dt0c01.*) with ingest scopes
 */
export function initTelemetry(): void {
  const otlpUrl = process.env.DYNATRACE_OTLP_URL;
  const otlpToken = process.env.DYNATRACE_OTLP_TOKEN;

  if (!otlpUrl || !otlpToken) {
    console.log("[telemetry] DYNATRACE_OTLP_URL or DYNATRACE_OTLP_TOKEN not set — telemetry disabled");
    return;
  }

  const serviceName = process.env.OTEL_SERVICE_NAME || "copilot-sdk-agent";
  const authHeader = `Api-Token ${otlpToken}`;

  const resource = new Resource({
    [ATTR_SERVICE_NAME]: serviceName,
  });

  // DYNATRACE_OTLP_URL should be the OTLP base path, e.g.:
  //   https://abc123.live.dynatrace.com/api/v2/otlp
  // See: https://docs.dynatrace.com/docs/ingest-from/opentelemetry/otlp-api
  const baseUrl = otlpUrl.replace(/\/+$/, ""); // strip trailing slashes

  const traceExporter = new OTLPTraceExporter({
    url: `${baseUrl}/v1/traces`,
    headers: { Authorization: authHeader },
  });

  const metricExporter = new OTLPMetricExporter({
    url: `${baseUrl}/v1/metrics`,
    headers: { Authorization: authHeader },
    // Dynatrace requires delta temporality
    temporalityPreference: AggregationTemporality.DELTA,
  });

  sdk = new NodeSDK({
    resource,
    spanProcessor: new BatchSpanProcessor(traceExporter),
    metricReader: new PeriodicExportingMetricReader({
      exporter: metricExporter,
      exportIntervalMillis: 60_000,
    }),
  });

  sdk.start();
  console.log(`[telemetry] Initialized — exporting to ${otlpUrl}`);
}

export async function shutdownTelemetry(): Promise<void> {
  if (sdk) {
    await sdk.shutdown();
    console.log("[telemetry] Shut down");
  }
}

export function getTracer(name: string): Tracer {
  return trace.getTracer(name);
}

export function getMeter(name: string): Meter {
  return metrics.getMeter(name);
}
