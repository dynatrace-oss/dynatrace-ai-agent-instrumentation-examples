# Tracking Performance of Copilot Studio & Sending Results to Dynatrace

Here's a comprehensive approach to monitor the performance of **Microsoft Copilot Studio** (https://copilotstudio.microsoft.com/) and integrate the results with **Dynatrace**:

---

## 1. Synthetic Monitoring with Dynatrace

Dynatrace has built-in **Synthetic Monitoring** that can directly track the availability and performance of external web applications like Copilot Studio:

- **HTTP Monitors**: Create synthetic HTTP monitors that periodically ping the Copilot Studio endpoints and measure response time, availability, and status codes.
- **Browser Monitors**: Record a clickpath (login → navigate → perform actions) to simulate real user interactions and measure load times, rendering, and errors.

### Setup in Dynatrace:

1. Go to **Synthetic** → **Create a synthetic monitor**
2. Choose **HTTP monitor** or **Browser monitor**
3. Set the URL to `https://copilotstudio.microsoft.com/` (and any specific API endpoints you use)
4. Configure frequency, locations, and alerting thresholds

---

## 2. Real User Monitoring (RUM) via Dynatrace RUM JavaScript

If you have a custom front-end or portal that embeds/interacts with Copilot Studio:

- Inject the **Dynatrace RUM (OneAgent) JavaScript snippet** into your web pages.
- This captures real user performance metrics (page load, XHR calls to Copilot Studio APIs, JS errors, etc.).

---

## 3. API-Level Performance Tracking

If you interact with Copilot Studio via its **APIs** (e.g., Direct Line API, Power Platform connectors):

- **Dynatrace OneAgent** on your application servers will automatically trace outbound HTTP calls to Copilot Studio APIs and report latency, error rates, and throughput.
- Use **Request Attributes** and **Calculated Service Metrics** in Dynatrace to tag and filter Copilot Studio traffic specifically.

---

## 4. Custom Metrics via Dynatrace API (for Custom Checks)

If you write a custom script (e.g., Python, PowerShell) to measure Copilot Studio performance, you can push results to Dynatrace:

```python
import requests
import time

# --- 1. Measure Copilot Studio response time ---
url = "https://copilotstudio.microsoft.com/"
start = time.time()
response = requests.get(url, timeout=30)
elapsed_ms = (time.time() - start) * 1000
status_code = response.status_code

# --- 2. Send metrics to Dynatrace via Metrics Ingest API ---
DYNATRACE_ENV_URL = "https://<your-environment-id>.live.dynatrace.com"
API_TOKEN = "<your-dynatrace-api-token>"  # Requires 'metrics.ingest' scope

metric_lines = [
    f"copilot.studio.response_time,url={url} {elapsed_ms}",
    f"copilot.studio.status_code,url={url} {status_code}",
]

ingest_url = f"{DYNATRACE_ENV_URL}/api/v2/metrics/ingest"
headers = {
    "Authorization": f"Api-Token {API_TOKEN}",
    "Content-Type": "text/plain; charset=utf-8",
}

resp = requests.post(ingest_url, headers=headers, data="\n".join(metric_lines))
print(f"Dynatrace ingest status: {resp.status_code} - {resp.text}")
```

> Run this on a schedule (e.g., cron, Azure Function, GitHub Actions) to collect periodic data.

---

## 5. Dynatrace Dashboard & Alerting

Once data flows in:

| Feature | How to Use |
|---|---|
| **Dashboards** | Create tiles for response time trends, availability %, and error rates for Copilot Studio |
| **Metric Events** | Set alerts if response time exceeds a threshold (e.g., >3s) or availability drops |
| **SLOs** | Define Service Level Objectives (e.g., 99.9% availability) tied to your Copilot Studio monitors |

---

## Summary of Options

| Method | Best For | Effort |
|---|---|---|
| **Dynatrace Synthetic HTTP Monitor** | Basic availability & response time | Low |
| **Dynatrace Browser Monitor** | Full user-journey simulation | Medium |
| **OneAgent on your app servers** | API call tracing from your backend | Low (if OneAgent is deployed) |
| **Custom script + Metrics Ingest API** | Fully custom checks & metrics | Medium |
| **RUM JavaScript** | Real user experience in your portal | Low–Medium |

**Recommended starting point:** Use **Dynatrace Synthetic HTTP Monitoring** for quick, no-code setup, then layer in custom metrics or browser monitors as needed for deeper insight.
