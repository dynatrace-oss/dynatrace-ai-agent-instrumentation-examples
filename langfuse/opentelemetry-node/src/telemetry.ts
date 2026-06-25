import { NodeSDK } from "@opentelemetry/sdk-node";
import { OTLPTraceExporter } from "@opentelemetry/exporter-trace-otlp-proto";
import { LangfuseSpanProcessor } from "@langfuse/otel";

let sdk: NodeSDK | null = null;

function parseHeaders(raw: string): Record<string, string> {
  const headers: Record<string, string> = {};
  for (const pair of raw.split(",")) {
    const idx = pair.indexOf("=");
    if (idx !== -1) {
      headers[pair.slice(0, idx).trim()] = pair.slice(idx + 1).trim();
    }
  }
  return headers;
}

// Must be called before any import that creates spans (including Langfuse).
// Reads OTEL_EXPORTER_OTLP_ENDPOINT and OTEL_EXPORTER_OTLP_HEADERS from env.
// OTEL_SERVICE_NAME is read automatically by NodeSDK to set service.name.
export function initTelemetry(): void {
  const endpoint = process.env.OTEL_EXPORTER_OTLP_ENDPOINT;
  if (!endpoint) {
    console.log("[telemetry] OTEL_EXPORTER_OTLP_ENDPOINT not set — telemetry disabled");
    return;
  }

  const exporter = new OTLPTraceExporter({
    url: `${endpoint}/v1/traces`,
    headers: parseHeaders(process.env.OTEL_EXPORTER_OTLP_HEADERS ?? ""),
  });

  sdk = new NodeSDK({
    spanProcessors: [new LangfuseSpanProcessor({ exporter })],
  });

  sdk.start();
  console.log(`[telemetry] Initialized — exporting to ${endpoint}`);
}

export async function shutdownTelemetry(): Promise<void> {
  if (sdk) {
    await sdk.shutdown();
    console.log("[telemetry] Shut down");
  }
}
