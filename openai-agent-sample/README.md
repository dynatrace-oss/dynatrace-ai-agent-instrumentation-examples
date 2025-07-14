## OpenAI Agent SDK


This example contains a demo of a Customer Service Agent interface built on top of the [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/). The original example code can be found in the [openai-cs-agents-demo](https://github.com/openai/openai-cs-agents-demo) GitHub repo.

TODO: add DT screenshot

## Dynatrace Instrumentation

PR: https://github.com/traceloop/openllmetry/pull/2966
Got merged, check again


## How to use

### Setting your OpenAI API key

You can set your OpenAI API key in your environment variables by running the following command in your terminal:

```bash
export OPENAI_API_KEY=your_api_key
```

You can also follow [these instructions](https://platform.openai.com/docs/libraries#create-and-export-an-api-key) to set your OpenAI key at a global level.

Alternatively, you can set the `OPENAI_API_KEY` environment variable in an `.env` file at the root of the `python-backend` folder. You will need to install the `python-dotenv` package to load the environment variables from the `.env` file.

### Install dependencies

Install the dependencies for the backend by running the following commands:

```bash
cd python-backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

For the UI, you can run:

```bash
cd ui
npm install
```

### Run the app

From the `ui` folder, run:

```bash
npm run dev
```

The frontend will be available at: [http://localhost:3000](http://localhost:3000)

This command will also start the backend.

![Demo Screenshot](screenshot.jpg)