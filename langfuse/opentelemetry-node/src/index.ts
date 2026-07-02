// IMPORTANT: initTelemetry() must run before any OTel API usage.
import { initTelemetry, shutdownTelemetry } from "./telemetry.js";

initTelemetry();

import OpenAI, { AzureOpenAI } from "openai";
import { observeOpenAI } from "@langfuse/openai";
import { startActiveObservation, propagateAttributes } from "@langfuse/tracing";

const MODEL = process.env.MODEL ?? "gpt-5.4-mini";
const TOPIC = process.env.TOPIC ?? "observability";
const TEMPERATURE = 1;
const SESSION_ID = process.env.LANGFUSE_SESSION_ID ?? "demo-session";

function createOpenAIClient(): OpenAI {
  return process.env.OPENAI_API_VERSION
    ? new AzureOpenAI({
        endpoint: process.env.OPENAI_API_BASE,
        apiKey: process.env.OPENAI_API_KEY,
        apiVersion: process.env.OPENAI_API_VERSION,
      })
    : new OpenAI({
        baseURL: process.env.OPENAI_API_BASE,
        apiKey: process.env.OPENAI_API_KEY,
      });
}

async function generateHaiku(topic: string): Promise<string> {
  // propagateAttributes sets session.id in OTel baggage so all child spans inherit it.
  return propagateAttributes({ sessionId: SESSION_ID }, () =>
    startActiveObservation("generate-haiku", async () => {
      // observeOpenAI wraps the client and emits a generation span with
      // model, temperature, input/output messages, and token usage automatically.
      const openai = observeOpenAI(createOpenAIClient(), {
        generationName: "chat-completion",
      });

      const response = await openai.chat.completions.create({
        model: MODEL,
        messages: [{ role: "user", content: `Write a haiku about ${topic}.` }],
        max_completion_tokens: 50,
        temperature: TEMPERATURE,
      });

      return response.choices[0]?.message?.content ?? "";
    }),
  );
}

const result = await generateHaiku(TOPIC);
console.log(result);
await shutdownTelemetry();
