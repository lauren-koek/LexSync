"""
OpenRouter API client.

Loads OPENROUTER_API_KEY and OPENROUTER_MODEL from .env.
Provides a thin wrapper around OpenRouter's OpenAI-compatible chat
completions and embeddings endpoints.

Usage:
    from llm import chat, stream_chat, embed, LLMClient

    # One-shot call
    reply = chat("Summarize this document: ...")

    # Streaming
    for chunk in stream_chat("Summarize this document: ..."):
        print(chunk, end="", flush=True)

    # Custom model or system prompt
    client = LLMClient(model="openai/gpt-4o")
    reply = client.chat("Hello", system="You are a legal analyst.")

    # Embeddings (defaults to OPENROUTER_EMBEDDING_MODEL, or
    # openai/text-embedding-3-small if unset)
    vector = embed("Section 12A. Mandatory audit logs.", dimensions=384)
"""

import json
import os
from collections.abc import Iterator

import requests
from dotenv import load_dotenv

load_dotenv()

_BASE_URL      = "https://openrouter.ai/api/v1"
_DEFAULT_MODEL = "deepseek/deepseek-v4-flash-0731"
# text-embedding-3-small supports OpenAI's `dimensions` param, which lets
# callers request a smaller vector (e.g. to match a fixed-width pgvector
# column) without switching models.
_DEFAULT_EMBEDDING_MODEL = "openai/text-embedding-3-small"


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


def _embedding_model() -> str:
    return os.environ.get("OPENROUTER_EMBEDDING_MODEL", "").strip() or _DEFAULT_EMBEDDING_MODEL


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

    def __init__(self, model: str | None = None, embedding_model: str | None = None) -> None:
        self.model = model  # None → read from OPENROUTER_MODEL env var at call time
        self.embedding_model = embedding_model  # None → read from OPENROUTER_EMBEDDING_MODEL

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {_api_key()}",
            "Content-Type": "application/json",
        }

    def _resolved_model(self) -> str:
        return self.model or _model()

    def _resolved_embedding_model(self) -> str:
        return self.embedding_model or _embedding_model()

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

    def embed(self, text: str, *, dimensions: int | None = None) -> list[float]:
        """Return an embedding vector for `text` via OpenRouter's
        OpenAI-compatible /embeddings endpoint.

        `dimensions` is passed straight through to the provider — OpenAI's
        v3 embedding models use it to truncate their native (larger)
        embedding to a requested size via Matryoshka representation
        learning, which is how a caller pins the vector to a fixed-width
        pgvector column without switching models. Omit it to get the
        model's native size. Raises on any failure (missing API key,
        network error, non-2xx response) rather than swallowing it —
        callers that want a fallback (e.g. an offline embedding) decide
        that for themselves.
        """
        payload: dict = {
            "model": self._resolved_embedding_model(),
            "input": text,
        }
        if dimensions is not None:
            payload["dimensions"] = dimensions

        resp = requests.post(
            f"{_BASE_URL}/embeddings",
            headers=self._headers(),
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["data"][0]["embedding"]


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


def embed(text: str, *, dimensions: int | None = None) -> list[float]:
    return _default_client.embed(text, dimensions=dimensions)
