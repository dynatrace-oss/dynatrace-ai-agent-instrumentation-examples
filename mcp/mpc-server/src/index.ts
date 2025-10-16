import { setupTracing } from './tracer.js';

// Initialize tracing before importing other modules
const tracer = setupTracing('weather-mcp-server');

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StreamableHTTPServerTransport } from '@modelcontextprotocol/sdk/server/streamableHttp.js';

import { z } from "zod";
import express from 'express';
import {propagation, ROOT_CONTEXT, context} from "@opentelemetry/api";


const server = new McpServer({
  name: "weather",
  version: "1.0.0",
  capabilities: {
    resources: {},
    tools: {},
  },
});


server.tool(
  "get_weather_forecast",
  "Get weather forecast for a location",
  {
    city: z.string().describe("The name of the city"),
  },
  async ({ city }) => {
    const span = tracer.startSpan("get_weather_forecast_tool", {
      attributes: {
        'tool.name': 'get_weather_forecast',
        'tool.city': city,
      },
    })
    const forecast: Record<string, string> = {
      "New York": "Sunny, high of 75°F (24°C), low of 55°F (13°C).",
      "Los Angeles": "Partly cloudy, high of 85°F (29°C), low of 65°F (18°C).",
      "Chicago": "Rainy, high of 70°F (21°C), low of 50°F (10°C).",
      "Houston": "Humid, high of 90°F (32°C), low of 70°F (21°C).",
    };
    const weather = forecast[city] ?? "Weather data not available.";
    const forecastText = `Forecast for ${city}:\n\n${weather}`;
    span.setAttribute('tool.result', weather);
    span.end();
    return {
      content: [
        {
          type: "text",
          text: forecastText,
        },
      ],
    };
  },
);

const app = express();
app.use(express.json());

app.post('/mcp', async (req, res) => {
  const headers = req.body?.params?._meta || {};
  const ctx = propagation.extract(ROOT_CONTEXT, headers);
  return context.with(ctx, () => {
    const name = req.body?.method || 'mcp_request';
    return tracer.startActiveSpan(name, {
      attributes: {
        'mcp.method': req.body?.method || '',
        'mcp.id': req.body?.id || '',
        'http.route': '/mcp',
        'http.method': 'POST',
        'http.client_ip': req.ip || '',
        'http.user_agent': headers['user-agent'] || '',
        'net.peer.ip': req.ip || '',
      }}, async (span) => {
      const transport = new StreamableHTTPServerTransport({
        sessionIdGenerator: undefined,
        enableJsonResponse: true
      });

      res.on('close', () => {
        span.end();
        transport.close();
      });

      await server.connect(transport);
      await transport.handleRequest(req, res, req.body);
    });
  });
});

const port = parseInt(process.env.PORT || '3000');
app.listen(port, () => {
  console.log(`Demo MCP Server running on http://localhost:${port}/mcp`);
}).on('error', error => {
  console.error('Server error:', error);
  process.exit(1);
});