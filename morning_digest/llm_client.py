"""Minimal client for a local Lemonade server (OpenAI-compatible chat API).

Deliberately stdlib-only (urllib + json) -- Lemonade/llama.cpp-style servers
speak plain HTTP+JSON, so no SDK is needed.
"""
import json
import urllib.error
import urllib.request

from . import config


def chat(prompt: str, system: str = None, max_tokens: int = 300) -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": config.LEMONADE_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.3,
    }
    req = urllib.request.Request(
        f"{config.LEMONADE_BASE_URL}/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=config.LLM_TIMEOUT) as resp:
            data = json.loads(resp.read())
        return data["choices"][0]["message"]["content"].strip()
    except (urllib.error.URLError, KeyError, IndexError, json.JSONDecodeError, TimeoutError) as exc:
        return f"(local LLM unavailable: {exc})"


def available() -> bool:
    try:
        urllib.request.urlopen(f"{config.LEMONADE_BASE_URL}/v1/models", timeout=3)
        return True
    except Exception:
        return False
