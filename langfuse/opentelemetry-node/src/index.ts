// IMPORTANT: initTelemetry() must run before any OTel API usage.
import { initTelemetry, shutdownTelemetry } from "./telemetry.js";

initTelemetry();

import { trace, SpanStatusCode } from "@opentelemetry/api";
import OpenAI, { AzureOpenAI } from "openai";

const tracer = trace.getTracer("langfuse");
const MODEL = process.env.MODEL ?? "gpt-4o-mini";
const TOPIC = process.env.TOPIC ?? "observability";

// Emit a span with the Langfuse 4.x OTel attribute schema (langfuse.observation.*).
// The OTel Collector (or Dynatrace OpenPipeline) transforms these to gen_ai.* attributes.
// Note: the Langfuse Node.js SDK does not yet support OTel export; this demo emits
// the attributes manually using @opentelemetry/api.
async function generateHaiku(topic: string): Promise<string> {
  const span = tracer.startSpan("generate-haiku");
  try {
    span.setAttribute("langfuse.observation.type", "generation");
    span.setAttribute("langfuse.observation.model.name", MODEL);

    const messages = [{ role: "user" as const, content: `Write a haiku about ${topic}.` }];
    span.setAttribute("langfuse.observation.input", JSON.stringify(messages));

    const openai = process.env.OPENAI_API_VERSION
      ? new AzureOpenAI({
          endpoint: process.env.OPENAI_API_BASE,
          apiKey: process.env.OPENAI_API_KEY,
          apiVersion: process.env.OPENAI_API_VERSION,
        })
      : new OpenAI({
          baseURL: process.env.OPENAI_API_BASE,
          apiKey: process.env.OPENAI_API_KEY,
        });

    const response = await openai.chat.completions.create({
      model: MODEL,
      messages,
      max_completion_tokens: 50,
    });

    const output = response.choices[0]?.message?.content ?? "";
    span.setAttribute("langfuse.observation.output", output);

    if (response.usage) {
      span.setAttribute(
        "langfuse.observation.usage_details",
        JSON.stringify({
          prompt_tokens: response.usage.prompt_tokens,
          completion_tokens: response.usage.completion_tokens,
          total_tokens: response.usage.total_tokens,
        }),
      );
    }

    span.setStatus({ code: SpanStatusCode.OK });
    return output;
  } catch (err) {
    span.setStatus({ code: SpanStatusCode.ERROR, message: String(err) });
    throw err;
  } finally {
    span.end();
  }
}

const result = await generateHaiku(TOPIC);
console.log(result);
await shutdownTelemetry();
