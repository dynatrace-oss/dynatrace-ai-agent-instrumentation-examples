// Loaded with `node --require` so the OpenAI module is patched before the app imports it.
import { NodeSDK } from "@opentelemetry/sdk-node";
import { OTLPTraceExporter } from "@opentelemetry/exporter-trace-otlp-proto";
import { OpenAIInstrumentation } from "@arizeai/openinference-instrumentation-openai";

// OTLP endpoint is read from OTEL_EXPORTER_OTLP_ENDPOINT (defaults to http://localhost:4318).
const sdk = new NodeSDK({
  serviceName: process.env.OTEL_SERVICE_NAME ?? "openai/openinference/node",
  traceExporter: new OTLPTraceExporter(),
  instrumentations: [new OpenAIInstrumentation()],
});

sdk.start();

const shutdown = () => {
  sdk.shutdown().finally(() => process.exit(0));
};
process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);
