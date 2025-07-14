# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Academic_Research: Research advice, related literature finding, research area proposals, web knowledge access."""

from . import agent

import os
os.environ['TRACELOOP_TELEMETRY'] = "false"

def read_secret(secret: str):
    try:
        with open(f"/etc/secrets/{secret}", "r") as f:
            return f.read().rstrip()
    except Exception as e:
        print("No token was provided")
        print(e)
        return ""

from traceloop.sdk import Traceloop
token = read_secret("dynatrace_otel")
headers = {"Authorization": f"Api-Token {token}"}
Traceloop.init(
    app_name="adk-samples",
    api_endpoint="https://wkf10640.live.dynatrace.com/api/v2/otlp",
    disable_batch=True,
    headers=headers,
    should_enrich_metrics=True,
)