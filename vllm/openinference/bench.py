"""Load generator for vLLM's OpenAI-compatible API.

Sends a fixed number of concurrent completions with a W3C traceparent header.
SAMPLE_RATIO sets the share of requests whose traceparent carries the sampled
flag, mimicking parent-based head sampling at the gateway. Prints output
tokens/s, mean latency, and the span counts seen by span_sink.py.
"""

import argparse
import asyncio
import json
import os
import random
import secrets
import time

import httpx


def traceparent(sampled: bool) -> str:
    return f"00-{secrets.token_hex(16)}-{secrets.token_hex(8)}-{'01' if sampled else '00'}"


async def one(client: httpx.AsyncClient, url: str, model: str, max_tokens: int, ratio: float):
    headers = {"traceparent": traceparent(random.random() < ratio)}
    body = {
        "model": model,
        "prompt": "Write a short story about observability.",
        "max_tokens": max_tokens,
        "min_tokens": max_tokens,
        "ignore_eos": True,
    }
    start = time.perf_counter()
    r = await client.post(f"{url}/v1/completions", json=body, headers=headers)
    r.raise_for_status()
    return r.json()["usage"]["completion_tokens"], time.perf_counter() - start


async def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--label", default="run")
    p.add_argument("--requests", type=int, default=int(os.getenv("REQUESTS", "64")))
    p.add_argument("--concurrency", type=int, default=int(os.getenv("CONCURRENCY", "8")))
    p.add_argument("--max-tokens", type=int, default=int(os.getenv("MAX_TOKENS", "64")))
    p.add_argument("--sample-ratio", type=float, default=float(os.getenv("SAMPLE_RATIO", "1.0")))
    args = p.parse_args()

    url = os.getenv("VLLM_URL", "http://localhost:8000")
    sink = os.getenv("SINK_URL", "http://localhost:14318")
    model = os.getenv("MODEL", "Qwen/Qwen2.5-0.5B-Instruct")

    async with httpx.AsyncClient(timeout=600) as client:
        await one(client, url, model, 8, 0.0)  # warm-up, never sampled
        await client.post(f"{sink}/reset")
        sem = asyncio.Semaphore(args.concurrency)

        async def bounded():
            async with sem:
                return await one(client, url, model, args.max_tokens, args.sample_ratio)

        start = time.perf_counter()
        results = await asyncio.gather(*(bounded() for _ in range(args.requests)))
        wall = time.perf_counter() - start
        await asyncio.sleep(7)  # let BatchSpanProcessor flush (5 s default delay)
        stats = (await client.get(f"{sink}/stats")).json()

    tokens = sum(t for t, _ in results)
    print(json.dumps({
        "label": args.label,
        "requests": args.requests,
        "concurrency": args.concurrency,
        "sample_ratio": args.sample_ratio,
        "output_tokens_per_s": round(tokens / wall, 1),
        "mean_latency_s": round(sum(l for _, l in results) / len(results), 3),
        **stats,
    }))


if __name__ == "__main__":
    asyncio.run(main())
