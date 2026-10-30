SHELL            := /bin/bash
-include .env
export

PORT             ?= 8000
SINK_PORT        ?= 14318
MODEL            ?= Qwen/Qwen2.5-0.5B-Instruct
VLLM_IMAGE       ?= vllm/vllm-openai-cpu:v0.32.0
VLLM_CONTAINER   ?= vllm-otel
# off | traced | detailed | dt (export vLLM spans to Dynatrace)
MODE             ?= traced
SAMPLE_RATIO     ?= 1.0
# Optional vLLM-side traceidratio sampler, independent of the caller's decision
VLLM_SAMPLE_RATIO ?=

DT_ENDPOINT      ?=
DT_API_TOKEN     ?=
# Api-Token for classic API tokens, Bearer for platform tokens
DT_AUTH_SCHEME   ?= Api-Token
# Passed to the container by name only, so make never prints the token
export OTEL_EXPORTER_OTLP_TRACES_HEADERS = Authorization=$(DT_AUTH_SCHEME)%20$(DT_API_TOKEN)

TRACE_ARGS_off      :=
TRACE_ARGS_traced   := --otlp-traces-endpoint http://host.docker.internal:$(SINK_PORT)/v1/traces
TRACE_ARGS_detailed := $(TRACE_ARGS_traced) --collect-detailed-traces all
TRACE_ARGS_dt       := --otlp-traces-endpoint $(DT_ENDPOINT)/api/v2/otlp/v1/traces

.PHONY: install run sink stop request bench compare e2e help

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install Python dependencies for the sink and benchmark
	uv sync

run: stop ## Start vLLM (CPU image) on port $(PORT); MODE=off|traced|detailed|dt
	docker run -d --name $(VLLM_CONTAINER) -p $(PORT):8000 --shm-size 1g \
	  -e VLLM_CPU_KVCACHE_SPACE=2 \
	  -e OTEL_EXPORTER_OTLP_TRACES_PROTOCOL=http/protobuf \
	  -e OTEL_SERVICE_NAME=vllm -e OTEL_RESOURCE_ATTRIBUTES \
	  $(if $(filter dt,$(MODE)),-e OTEL_EXPORTER_OTLP_TRACES_HEADERS) \
	  $(if $(VLLM_SAMPLE_RATIO),-e OTEL_TRACES_SAMPLER=traceidratio -e OTEL_TRACES_SAMPLER_ARG=$(VLLM_SAMPLE_RATIO)) \
	  -v vllm-hf-cache:/root/.cache/huggingface \
	  $(VLLM_IMAGE) --model $(MODEL) --max-model-len 2048 --enforce-eager $(TRACE_ARGS_$(MODE))
	@until curl -sf http://localhost:$(PORT)/health >/dev/null; do \
	  [ "$$(docker inspect -f {{.State.Running}} $(VLLM_CONTAINER))" = true ] || { docker logs $(VLLM_CONTAINER); exit 1; }; \
	  sleep 3; done; echo "vLLM ready (MODE=$(MODE))"

sink: ## Run the OTLP span-counting sink on port $(SINK_PORT)
	SINK_PORT=$(SINK_PORT) uv run python span_sink.py

stop: ## Stop and remove the vLLM container
	-@docker rm -f $(VLLM_CONTAINER) >/dev/null 2>&1

request: ## POST one completion to localhost:$(PORT)
	curl -s http://localhost:$(PORT)/v1/completions \
	  -H 'Content-Type: application/json' \
	  -H "traceparent: 00-$$(openssl rand -hex 16)-$$(openssl rand -hex 8)-01" \
	  -d '{"model":"$(MODEL)","prompt":"Write a haiku about e2e test","max_tokens":32}' | python3 -m json.tool

bench: ## Benchmark the running vLLM; SAMPLE_RATIO sets the sampled share of traceparents
	uv run python bench.py --label $(MODE)-$(SAMPLE_RATIO)$(if $(VLLM_SAMPLE_RATIO),-vllm$(VLLM_SAMPLE_RATIO)) --sample-ratio $(SAMPLE_RATIO)

compare: ## Run off / traced / caller 10% / vLLM 10% / detailed back to back (needs `make sink` running)
	@$(MAKE) -s run MODE=off      && $(MAKE) -s bench MODE=off
	@$(MAKE) -s run MODE=traced   && $(MAKE) -s bench MODE=traced && $(MAKE) -s bench MODE=traced SAMPLE_RATIO=0.1
	@$(MAKE) -s run MODE=traced VLLM_SAMPLE_RATIO=0.1 && $(MAKE) -s bench MODE=traced VLLM_SAMPLE_RATIO=0.1
	@$(MAKE) -s run MODE=detailed && $(MAKE) -s bench MODE=detailed
	@$(MAKE) -s stop

E2E_RUNS ?= 20
E2E_SAMPLE_RATIO ?= 0.25

e2e: ## Run vLLM sampled at E2E_SAMPLE_RATIO exporting to Dynatrace, then E2E_RUNS client calls (needs DT_ENDPOINT, DT_API_TOKEN)
	@$(MAKE) -s run MODE=dt VLLM_SAMPLE_RATIO=$(E2E_SAMPLE_RATIO)
	MAX_RUNS=$(E2E_RUNS) uv run python client.py
