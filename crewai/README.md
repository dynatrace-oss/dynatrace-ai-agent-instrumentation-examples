# CrewAI Observability with Dynatrace

This guide will explain how to gain Observability and monitor CrewAI using Dynatrace and OpenTelemetry.

CrewAI emits data which we will collect using the [Dynatrace OpenTelemetry collector](https://docs.dynatrace.com/docs/extend-dynatrace/opentelemetry/collector) and send into Dynatrace.

Broadly speaking this readme will follow the standard CrewAI documentation ([here](https://docs.crewai.com/en/installation) and here), with some adjustments to add the Observability pieces.

## Prerequisites

To follow this guide, you will need:

* [Python3 installed](https://www.python.org/downloads/)
* A Dynatrace environment ([sign up for a free trial](https://dt-url.net/trial))

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

