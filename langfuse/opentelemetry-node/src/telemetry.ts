import { NodeSDK } from "@opentelemetry/sdk-node";
import { OTLPTraceExporter } from "@opentelemetry/exporter-trace-otlp-proto";
import { BatchSpanProcessor } from "@opentelemetry/sdk-trace-base";

let sdk: NodeSDK | null = null;

// Must be called before any import that creates spans (including Langfuse).
// Reads OTEL_EXPORTER_OTLP_ENDPOINT and OTEL_EXPORTER_OTLP_HEADERS from env.
// OTEL_SERVICE_NAME is read automatically by NodeSDK to set service.name.
export function initTelemetry(): void {
  const endpoint = process.env.OTEL_EXPORTER_OTLP_ENDPOINT;
  if (!endpoint) {
    console.log("[telemetry] OTEL_EXPORTER_OTLP_ENDPOINT not set — telemetry disabled");
    return;
  }

  sdk = new NodeSDK({
    spanProcessor: new BatchSpanProcessor(new OTLPTraceExporter()),
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
