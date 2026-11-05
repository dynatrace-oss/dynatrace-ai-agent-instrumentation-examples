import { createServer, IncomingMessage, ServerResponse } from "node:http";
import OpenAI, { AzureOpenAI } from "openai";

const PORT = Number(process.env.PORT ?? 8000);
const MODEL = process.env.MODEL || "gpt-4o";

const client = process.env.OPENAI_API_VERSION
  ? new AzureOpenAI({
      endpoint: process.env.OPENAI_API_BASE,
      apiKey: process.env.OPENAI_API_KEY,
      apiVersion: process.env.OPENAI_API_VERSION,
    })
  : new OpenAI({
      baseURL: process.env.OPENAI_API_BASE || undefined,
      apiKey: process.env.OPENAI_API_KEY,
    });

async function haiku(topic: string): Promise<string> {
  const completion = await client.chat.completions.create({
    model: MODEL,
    messages: [
      { role: "system", content: "You are a haiku poet." },
      { role: "user", content: `Write a haiku about ${topic}.` },
    ],
    temperature: 1.0,
  });
  return completion.choices[0]?.message?.content ?? "";
}

function send(res: ServerResponse, status: number, body: unknown) {
  res.writeHead(status, { "Content-Type": "application/json" });
  res.end(JSON.stringify(body));
}

async function readJson(req: IncomingMessage): Promise<Record<string, unknown>> {
  let raw = "";
  for await (const chunk of req) raw += chunk;
  return raw ? JSON.parse(raw) : {};
}

createServer(async (req, res) => {
  if (req.method === "POST" && req.url === "/haiku") {
    try {
      const { topic } = await readJson(req);
      const text = await haiku(typeof topic === "string" && topic ? topic : "observability");
      send(res, 200, { haiku: text });
    } catch (err) {
      console.error(err);
      send(res, 500, { error: String(err) });
    }
    return;
  }
  if (req.method === "GET" && req.url === "/health") {
    send(res, 200, { status: "ok" });
    return;
  }
  send(res, 404, { error: "not found" });
}).listen(PORT, () => console.log(`Listening on http://localhost:${PORT}`));
