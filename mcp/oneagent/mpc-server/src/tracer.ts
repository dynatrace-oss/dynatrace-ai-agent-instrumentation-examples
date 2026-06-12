import {
  trace,
} from '@opentelemetry/api';
import {
  AlwaysOnSampler,
  SimpleSpanProcessor,
} from '@opentelemetry/sdk-trace-base';
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-proto';
import { resourceFromAttributes } from '@opentelemetry/resources';
import {
  ATTR_SERVICE_NAME,
} from '@opentelemetry/semantic-conventions';
import fs from 'fs';
import { NodeSDK } from '@opentelemetry/sdk-node';

export const setupTracing = (serviceName: string) => {

  const api = fs.readFileSync('/etc/secrets/dynatrace_otel').toString().trim();
  const otel_endpoint = process.env.OTEL_ENDPOINT;
  const otlp_url = otel_endpoint?.endsWith("/v1/traces") ? otel_endpoint : otel_endpoint + "/v1/traces";
  const exporter = new OTLPTraceExporter({
    url: otlp_url,
    headers: {
      'Authorization': `Api-Token ${api}`
    }
  });

  const sdk = new NodeSDK({
    resource: resourceFromAttributes({
      [ATTR_SERVICE_NAME]: serviceName,
    }),
    spanProcessors: [new SimpleSpanProcessor(exporter)],
    traceExporter: exporter,
    sampler: new AlwaysOnSampler(),
    instrumentations: [],
  });
  sdk.start();


  return trace.getTracer(serviceName);
};
