# Instrumenting AWS Bedrock 

After iterating through several implmentations for AWS Bedrock.  This should be the correct implementation.  The key is in the __Instrumentor__

**All of these examples are using the Boto Client**.  No other SDK as of this post.



## APIS 
There are two primary APIs: 
Invoke and Converse 


# Imports 

```
from traceloop.sdk import Traceloop
from opentelemetry.instrumentation.bedrock import BedrockInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.botocore import BotocoreInstrumentor
from opentelemetry.instrumentation.asyncio import AsyncioInstrumentor

from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler as OTLPLoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry._logs import set_logger_provider

from traceloop.sdk.decorators import workflow, task, agent
```

## Sample Code 

```
logging.info("Starting Bedrock Example Instrumetors...")

BedrockInstrumentor().instrument()
RequestsInstrumentor().instrument()
AsyncioInstrumentor().instrument()
BotocoreInstrumentor().instrument()

logging.info("Initializing traceloop...")
traceloop = Traceloop()
Traceloop.init(
    app_name="bedrock_example_app",
    disable_batch=True,
    should_enrich_metrics=True,
    api_endpoint=TRACELOOP_BASE_URL,
)

Traceloop.set_association_properties({
    "appid": "1234567890",
    "appname": "main",
    "assignmentgroup": "Dynatrace Sales Engineering",
    "ecosystem": "Observability Engineering",
})
```

## Use Decorators Where Appropriate

from traceloop.sdk.decorators import workflow, task, agent

- Workflow
- Task 
- Agent


## Logging Setup
If you want to add Logs to your Traces : 

```

logging.basicConfig(
    level=logging.DEBUG,
    stream=sys.stdout,
    format="%(asctime)s %(levelname)s %(message)s",
)
logging.getLogger("botocore").setLevel(logging.INFO)
logging.getLogger("urllib3").setLevel(logging.INFO)

# Ship Python logs to the local OTel collector via OTLP/HTTP
_log_provider = LoggerProvider()
set_logger_provider(_log_provider)
_log_provider.add_log_record_processor(
    BatchLogRecordProcessor(OTLPLogExporter(endpoint=f"{TRACELOOP_BASE_URL}/v1/logs"))
)
logging.getLogger().addHandler(OTLPLoggingHandler(logger_provider=_log_provider))

```

## Examples 

![Image2](/image2.png "Dashboard") 

![Image1](/image1.png "Dashboard") 


