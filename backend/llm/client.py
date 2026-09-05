"""
OpenRouter API client.

Loads OPENROUTER_API_KEY and OPENROUTER_MODEL from .env.
Provides a thin wrapper around OpenRouter's OpenAI-compatible chat completions endpoint.

Usage:
    from llm import chat, stream_chat, LLMClient

    # One-shot call
    reply = chat("Summarize this document: ...")

    # Streaming
    for chunk in stream_chat("Summarize this document: ..."):
        print(chunk, end="", flush=True)

    # Custom model or system prompt
    client = LLMClient(model="openai/gpt-4o")
    reply = client.chat("Hello", system="You are a legal analyst.")
"""

import json
import os
from collections.abc import Iterator

import requests
from dotenv import load_dotenv

load_dotenv()

_BASE_URL      = "https://openrouter.ai/api/v1"
_DEFAULT_MODEL = "deepseek/deepseek-v4-flash-0731"


def _api_key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        raise OSError(
            "OPENROUTER_API_KEY is not set. "
            "Add it to your .env file or export it as an environment variable."
        )
    return key


def _model() -> str:
    return os.environ.get("OPENROUTER_MODEL", "").strip() or _DEFAULT_MODEL


def _build_messages(
    prompt: str,
    system: str | None,
    history: list[dict] | None,
) -> list[dict]:
    messages: list[dict] = []
    if system:
        messages.append({"role": "system", "content": system})
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": prompt})
    return messages


class LLMClient:
    """Stateless OpenRouter client. Config is resolved from env vars at call time."""

    def __init__(self, model: str | None = None) -> None:
        self.model = model  # None → read from OPENROUTER_MODEL env var at call time

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {_api_key()}",
            "Content-Type": "application/json",
        }

    def _resolved_model(self) -> str:
        return self.model or _model()

    def chat(
        self,
        prompt: str,
        *,
        system: str | None = None,
        history: list[dict] | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.3,
    ) -> str:
        """Send a single prompt and return the full reply as a string."""
        payload = {
            "model": self._resolved_model(),
            "messages": _build_messages(prompt, system, history),
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        resp = requests.post(
            f"{_BASE_URL}/chat/completions",
            headers=self._headers(),
            json=payload,
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    def stream_chat(
        self,
        prompt: str,
        *,
        system: str | None = None,
        history: list[dict] | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.3,
    ) -> Iterator[str]:
        """Stream a reply token by token. Yields text chunks as they arrive."""
        payload = {
            "model": self._resolved_model(),
            "messages": _build_messages(prompt, system, history),
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }
        with requests.post(
            f"{_BASE_URL}/chat/completions",
            headers=self._headers(),
            json=payload,
            stream=True,
            timeout=120,
        ) as resp:
            resp.raise_for_status()
            for raw_line in resp.iter_lines():
                if not raw_line:
                    continue
                line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
                if not line.startswith("data: "):
                    continue
                data = line[len("data: "):]
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                    delta = chunk["choices"][0]["delta"].get("content")
                    if delta:
                        yield delta
                except (json.JSONDecodeError, KeyError):
                    continue


# ---------------------------------------------------------------------------
# Module-level convenience functions (use the default client from env vars)
# ---------------------------------------------------------------------------

_default_client = LLMClient()


def chat(
    prompt: str,
    *,
    system: str | None = None,
    history: list[dict] | None = None,
    max_tokens: int = 4096,
    temperature: float = 0.3,
) -> str:
    return _default_client.chat(
        prompt,
        system=system,
        history=history,
        max_tokens=max_tokens,
        temperature=temperature,
    )

def stream_chat(
    prompt: str,
    *,
    system: str | None = None,
    history: list[dict] | None = None,
    max_tokens: int = 4096,
    temperature: float = 0.3,
) -> Iterator[str]:
    return _default_client.stream_chat(
        prompt,
        system=system,
        history=history,
        max_tokens=max_tokens,
        temperature=temperature,
    )
