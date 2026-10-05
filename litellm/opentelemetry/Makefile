SHELL            := /bin/bash
-include .env
export

PORT                 ?= 8000
COLLECTOR_BASE_URL   ?= localhost:4317

DT_ENDPOINT          ?= https://your-tenant.live.dynatrace.com
DT_API_TOKEN         ?= dt0c01.*****

override COLLECTOR_IMAGE     := ghcr.io/dynatrace/dynatrace-otel-collector/dynatrace-otel-collector:0.57.0
override COLLECTOR_CONTAINER := otel-collector

SUBDIRS := fastapi-instrumentation litellm-gateway-with-instrumentation
TARGET ?= all  # set TARGET=fastapi-instrumentation to act on single subdir

.PHONY: help install run stop request all $(SUBDIRS)

help:
	@echo "Usage: make <target> [TARGET=<subdir>]"
	@echo "Targets:"
	@echo "  install     Install deps for both or TARGET"
	@echo "  run         Run both or TARGET"
	@echo "  stop        Stop both or TARGET"
	@echo "  request     Run request(s) against both or TARGET"

install:
ifeq ($(TARGET),all)
	@for d in $(SUBDIRS); do echo "==> make -C $$d install"; make -C $$d install || true; done
else
	@echo "==> make -C $(TARGET) install"; make -C $(TARGET) install
endif

run:
ifeq ($(TARGET),all)
	@for d in $(SUBDIRS); do echo "==> make -C $$d run &"; (cd $$d && nohup make run >/dev/null 2>&1 &) ; done
	@sleep 1
else
	@echo "==> make -C $(TARGET) run"; make -C $(TARGET) run
endif

stop:
ifeq ($(TARGET),all)
	@for d in $(SUBDIRS); do echo "==> make -C $$d stop"; make -C $$d stop || true; done
else
	@echo "==> make -C $(TARGET) stop"; make -C $(TARGET) stop
endif

request:
ifeq ($(TARGET),all)
	@for d in $(SUBDIRS); do echo "==> make -C $$d request"; make -C $$d request || true; done
else
	@echo "==> make -C $(TARGET) request"; make -C $(TARGET) request
endif