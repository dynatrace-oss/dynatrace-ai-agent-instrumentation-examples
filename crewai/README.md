# CrewAI Observability with Dynatrace

This guide will explain how to gain Observability and monitor CrewAI using Dynatrace and OpenTelemetry.

CrewAI emits data which we will collect using the [Dynatrace OpenTelemetry collector](https://docs.dynatrace.com/docs/extend-dynatrace/opentelemetry/collector) and send into Dynatrace.

Broadly speaking this readme will follow the standard CrewAI documentation ([here](https://docs.crewai.com/en/installation) and [here](https://docs.crewai.com/en/quickstart)), with some adjustments to add the Observability pieces.

## Prerequisites

To follow this guide, you will need:

* [Python3 installed](https://www.python.org/downloads/)
* A Dynatrace environment ([sign up for a free trial](https://dt-url.net/trial))
* [Download the Dynatrace collector binary and add it to your PATH](https://github.com/Dynatrace/dynatrace-otel-collector/releases)

## Clone repo & setup environment

```
git clone https://github.com/dynatrace-oss/dynatrace-ai-agent/instrumentation-examples
cd crewai
```

(optional) Create a new virtual environment:

```
python -m venv .
Scripts/activate.bat
```

Install CrewAI:

```
pip install -r requirements.txt
```

## Explore collector configuration

<img width="1125" height="211" alt="image" src="https://github.com/user-attachments/assets/bb8a7d52-ae3b-4d47-aa49-b12819307e76" />

During this tutorial, we will configure CrewAI to send telemetry to the collector. The collector will be process this telemetry then send it onwards into Dynatrace.

Let's quickly understand and start up the collector.

Open [collector.config.yaml](collector.config.yaml) and notice that the collector (not yet running) is configured to capture two data types: `metrics` and `traces`. Both data types will be received into the collector using the `otlp` receiver (`otlp` means `OpenTelemetry Protocol`).

* `traces` will not be processed in any way and will be sent out from the collector simultaneously to two places: `debug` (the collector's console output) and Dynatrace.

* `metrics` will also be received via OTLP and any metrics in the `cumulative` format will be transformed to `delta` (Dynatrace supports `delta`, not `cumulative`). The metrics will also be sent to both `debug` and Dynatrace.

Notice the two environment variables that need to be set: `DT_ENDPOINT` and `DT_API_TOKEN`. Let's configure these now.

### Create Dynatrace API token

In Dynatrace, press `ctrl + k` and search for `Access Tokens`. Create a new API token with these permissions:

* `metrics.ingest`
* `logs.ingest`

### Format Dynatrace URL

Look at your Dynatrace environment URL. It should start with `https://` then a random string like `abc12345`.

Take that random value and build a URL with this syntax: `https://ID_HERE.live.dynatrace.com`

For example: `https://abc12345.live.dynatrace.com`

This is your `DT_ENDPOINT` value.

### Set Dynatrace environment variables

Set these details as environment variables:

```
export DT_ENDPOINT=https://abc12345.live.dynatrace.com
export DT_API_TOKEN=dt0c01.****.*****
```

### Start the collector

Start the collector and leave it running:

```
"c:\path\to\dynatrace-otel-collector.exe" --config=collector.config.yaml
```

## Create a crew

Create a new "crew" called "latest-ai-development".
When prompted, choose OpenAI and enter `testkey123` when prompted for an API key (we will change this later):

```
crewai create crew latest-ai-development
cd latest_ai_development
```

## About Crews

Without wanting to anthropomorphise, it is conceptually helpful to imagine a "crew" as a "team" of people. Just like a well formed team of humans, each "person" (or agent) has its own role, knowledge and specialities. The crew also has a set of "tasks" that it must perform to achieve an outcome. The "crew" (or team) works together to achieve this goal. Crucially, the agents "hand-off" work between themselves when they need input from the others. This is a crucial difference from a static, predefined workflow where we (the actual humans) would predefine the "handoff points".

## Explore your Crew

The commands above will have created a new folder called `latest-ai-development` with lots of file inside that folder.

Take a look at `src/latest-ai-development/config/agents.yaml`. This file defines the agents (or "personas") you have available on your crew and what they can "do".

The items in curly brackets are variables, passed in at runtime (meaning your `researcher` agent can be a "Senior Data Researcher" for any topic).

Close that file an open `src/latest-ai-development/config/tasks.yaml`. This file defines the tasks that must be completed with a corresponding `agent` assigned to each task (much like a human team would have individuals assigned to each task). Again, the items in curly brackets are variables.
