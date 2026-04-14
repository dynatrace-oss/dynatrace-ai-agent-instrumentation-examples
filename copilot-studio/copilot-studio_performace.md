# Metrics You Can Pull from Microsoft for Copilot Studio → Dynatrace

## 1. Copilot Studio Analytics (Built-in)

Copilot Studio provides built-in analytics dashboards with metrics like:

| Metric | Description |
|---|---|
| **Total Sessions** | Number of bot conversations |
| **Engagement Rate** | % of sessions where the user interacted meaningfully |
| **Resolution Rate** | % of sessions resolved without human handoff |
| **Escalation Rate** | % of sessions escalated to a human agent |
| **Abandonment Rate** | % of sessions where the user left without resolution |
| **CSAT Score** | Customer satisfaction (if surveys are enabled) |
| **Topic Trigger Rate** | How often each topic/intent is triggered |
| **Session Outcomes** | Resolved, escalated, abandoned per topic |

> These are visible in the **Copilot Studio portal → Analytics tab**, but to get the raw data out, you need the methods below.

---

## 2. Dataverse / Power Platform APIs

Copilot Studio stores session and conversation data in **Dataverse**. You can query these tables:

| Dataverse Table | Contains |
|---|---|
| `ConversationTranscript` | Full conversation logs with timestamps |
| `bot` | Bot metadata |
| `botcomponent` | Topics, entities, actions |
| `ConversationStartedEvent` | Session start events |

### How to extract and send to Dynatrace:

```python
import requests
import time

# --- 1. Authenticate to Dataverse via OAuth2 ---
TENANT_ID = "<your-tenant-id>"
CLIENT_ID = "<your-app-registration-client-id>"
CLIENT_SECRET = "<your-client-secret>"
DATAVERSE_URL = "https://<your-org>.crm.dynamics.com"

token_url = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
token_resp = requests.post(token_url, data={
    "grant_type": "client_credentials",
    "client_id": CLIENT_ID,
    "client_secret": CLIENT_SECRET,
    "scope": f"{DATAVERSE_URL}/.default",
})
access_token = token_resp.json()["access_token"]

# --- 2. Query Copilot Studio session data from Dataverse ---
headers = {
    "Authorization": f"Bearer {access_token}",
    "OData-MaxVersion": "4.0",
    "OData-Version": "4.0",
    "Accept": "application/json",
}

# Example: Get conversation transcripts from the last 24 hours
query = (
    f"{DATAVERSE_URL}/api/data/v9.2/conversationtranscripts"
    f"?$filter=createdon ge {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(time.time() - 86400))}"
    f"&$orderby=createdon desc"
    f"&$top=1000"
)
resp = requests.get(query, headers=headers)
transcripts = resp.json().get("value", [])

# --- 3. Compute metrics ---
total_sessions = len(transcripts)
# Parse transcripts for resolution/escalation/abandonment as needed

# --- 4. Send to Dynatrace ---
DT_ENV_URL = "https://<your-env-id>.live.dynatrace.com"
DT_API_TOKEN = "<your-dynatrace-api-token>"

metric_lines = [
    f"copilot.studio.total_sessions {total_sessions}",
    # Add more computed metrics here:
    # f"copilot.studio.escalation_rate {escalation_rate}",
    # f"copilot.studio.resolution_rate {resolution_rate}",
]

dt_resp = requests.post(
    f"{DT_ENV_URL}/api/v2/metrics/ingest",
    headers={
        "Authorization": f"Api-Token {DT_API_TOKEN}",
        "Content-Type": "text/plain; charset=utf-8",
    },
    data="\n".join(metric_lines),
)
print(f"Dynatrace ingest: {dt_resp.status_code} - {dt_resp.text}")
```

---

## 3. Microsoft 365 & Copilot Usage Reports (Microsoft Graph API)

If you're tracking **Microsoft 365 Copilot** usage more broadly, Microsoft Graph exposes usage reports:

| Endpoint | Metrics |
|---|---|
| `GET /reports/getMicrosoft365CopilotUsageUserDetail` | Per-user Copilot activity (last activity date, product usage) |
| `GET /reports/getMicrosoft365CopilotUserCountSummary` | Aggregated enabled/active user counts |
| `GET /reports/getMicrosoft365CopilotUserCountTrend` | Active user trends over time |

> **Note:** These require **Reports.Read.All** permission in Microsoft Graph.

---

## 4. Azure Application Insights / Azure Monitor

If your Copilot Studio bot connects to **Azure Bot Service** or uses **custom connectors/Power Automate flows**:

| Source | Metrics Available |
|---|---|
| **Azure Bot Service** | Messages sent/received, latency, channel errors, active users |
| **Application Insights** | Custom telemetry, dependency call durations, exceptions, request traces |
| **Power Automate** | Flow run success/failure rates, duration, action-level telemetry |

### Export to Dynatrace:

- Use **Azure Monitor Metrics API** or **Log Analytics API** to query these metrics.
- Forward via the **Dynatrace Azure Monitor Integration** (native integration):
  - In Dynatrace: **Settings → Cloud and virtualization → Azure** → connect your Azure subscription.
  - Dynatrace will automatically pull Azure Monitor metrics for Bot Service, App Insights, etc.

---

## 5. Power Platform Admin Center – Telemetry & Analytics

The **Power Platform Admin Center** provides:

| Feature | What You Get |
|---|---|
| **Copilot Studio Analytics** | Session volumes, resolution rates, topic performance |
| **Environment-level telemetry** | API call counts, Dataverse storage, capacity usage |
| **Export to Application Insights** | Native integration to stream telemetry to Azure App Insights |

> **Key integration:** In the Power Platform Admin Center, you can enable **"Export to Application Insights"**, which streams Dataverse and Copilot Studio telemetry into App Insights → then forward to Dynatrace via the Azure Monitor integration.

---

## Recommended Architecture

```
┌─────────────────────┐
│  Copilot Studio      │
│  (Sessions, Topics)  │
└────────┬────────────┘
         │
    ┌────▼─────────────┐     ┌──────────────────────┐
    │  Dataverse        │────►│  Power Platform Admin │
    │  (Transcripts,    │     │  "Export to App       │
    │   Events)         │     │   Insights"           │
    └────┬─────────────┘     └────────┬─────────────┘
         │                            │
         │  Dataverse API             │
         ▼                            ▼
    ┌────────────────┐     ┌──────────────────────┐
    │ Custom Script   │     │ Azure App Insights    │
    │ (Python/PA flow)│     │ / Azure Monitor       │
    └────┬───────────┘     └────────┬─────────────┘
         │                          │
         │  Metrics Ingest API      │  Native Azure Integration
         ▼                          ▼
    ┌─────────────────────────────────────┐
    │          Dynatrace                   │
    │  (Dashboards, Alerts, SLOs)          │
    └──────────────────────────────────────┘
```

---

## Summary

| Source | Key Metrics | How to Get to Dynatrace |
|---|---|---|
| **Copilot Studio Analytics** | Sessions, resolution, escalation, CSAT | Dataverse API → custom script → Metrics Ingest |
| **Dataverse** | Conversation transcripts, events | Dataverse OData API → custom script |
| **Microsoft Graph** | M365 Copilot user activity & trends | Graph API → custom script → Metrics Ingest |
| **Azure Bot Service / App Insights** | Messages, latency, errors | Native Dynatrace Azure integration |
| **Power Platform Admin Center** | Export telemetry to App Insights | App Insights → Dynatrace Azure integration |

### Best Starting Point

Enable **"Export to Application Insights"** in the Power Platform Admin Center, then connect Azure Monitor to Dynatrace natively — this gets you the most data with the least custom code.
