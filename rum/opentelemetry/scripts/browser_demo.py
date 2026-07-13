#!/usr/bin/env python3
"""
Simulates a real user session so the full RUM + OTel story appears in
Dynatrace Experience Vitals. The Dynatrace RUM JS tag (loaded by the page)
injects W3C traceparent headers into every fetch, linking browser user-action
spans to backend OTel spans — exactly what a real user's browser would do.
"""
import asyncio
import os
import sys

from playwright.async_api import async_playwright

PORT = os.getenv("PORT", "8000")
BASE_URL = f"http://localhost:{PORT}"

QUESTIONS = [
    "Who invented jazz and where did it originate?",
    "What made Led Zeppelin so revolutionary?",
    "Who was Beethoven and what is his greatest legacy?",
    "What is bebop and who were its pioneers?",
    "How did Jimi Hendrix change the electric guitar?",
    "Tell me about Bach's influence on Western music",
]


async def main():
    async with async_playwright() as p:
        headless = os.getenv("CI", "").lower() in ("true", "1")
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context()
        page = await context.new_page()

        print(f"Opening {BASE_URL} ...")
        await page.goto(BASE_URL, wait_until="networkidle")

        conv_id = await page.evaluate("() => sessionStorage.getItem('conversationId')")
        rum_active = await page.evaluate("() => typeof dtrum !== 'undefined'")

        print(f"\nConversation ID : {conv_id}")
        print(f"DQL filter      : fetch spans | filter gen_ai.conversation.id == \"{conv_id}\"")
        print(f"Dynatrace RUM   : {'active ✓' if rum_active else 'NOT detected — set DT_RUM_SCRIPT in .env'}\n")

        if not rum_active:
            print("Warning: without RUM the session will not appear in Experience Vitals.", file=sys.stderr)

        for i, question in enumerate(QUESTIONS, 1):
            print(f"[{i}/{len(QUESTIONS)}] {question[:70]} ...")

            chip = page.locator(".chip", has_text=question)
            if await chip.count() > 0:
                await chip.first.click()
            else:
                await page.fill("#questionInput", question)
                await page.click("#sendBtn")

            # Wait for the loading indicator to disappear (LLM response received)
            await page.wait_for_selector(".loading-block", state="hidden", timeout=120_000)
            print(f"         ✓ response received")

            await asyncio.sleep(2)

        print(f"\nAll questions answered. Spans are being exported to Dynatrace.")
        print(f"In DQL:  fetch spans | filter gen_ai.conversation.id == \"{conv_id}\"")

        # Give the OTel batch exporter time to flush before we close
        await asyncio.sleep(5)
        await browser.close()


asyncio.run(main())
