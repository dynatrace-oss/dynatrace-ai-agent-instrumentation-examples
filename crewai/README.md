# CrewAI Observability with Dynatrace

This guide will explain how to gain Observability and monitor CrewAI using Dynatrace and OpenTelemetry.

CrewAI emits data which we will collect using the [Dynatrace OpenTelemetry collector](https://docs.dynatrace.com/docs/extend-dynatrace/opentelemetry/collector) and send into Dynatrace.

Broadly speaking this readme will follow the standard CrewAI documentation ([here](https://docs.crewai.com/en/installation) and here), with some adjustments to add the Observability pieces.

## Prerequisites

To follow this guide, you will need:

* A Dynatrace environment ([sign up for a free trial](https://dt-url.net/trial))

## Clone repo & install CrewAI

```
git clone https://github.com/dynatrace-oss/dynatrace-ai-agent/instrumentation-examples
cd crewai
pip install -r requirements.txt
```
