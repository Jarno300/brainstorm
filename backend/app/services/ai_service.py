"""
AI service — multi-provider LLM abstraction over direct HTTP calls.

Providers:
  - OpenAICompatibleProvider  → OpenAI, DeepSeek, and OpenAI-compatible APIs
  - AnthropicChatProvider     → Anthropic Messages API
  - OllamaProvider            → Ollama chat / generate APIs

No LangChain dependency — all providers use httpx directly.
"""

import json
import time
import logging
from dataclasses import dataclass
from typing import AsyncIterator, List, Optional, Protocol, Tuple

import httpx
from sqlalchemy.orm import Session

from app.config import (
    ANTHROPIC_API_KEY,
    ANTHROPIC_API_VERSION,
    ANTHROPIC_BASE_URL,
    CLASSIFICATION_MODEL,
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEFAULT_MODEL,
    OLLAMA_BASE_URL,
    OLLAMA_KEEP_ALIVE,
    OLLAMA_NUM_CTX,
    OLLAMA_NUM_PREDICT,
    OPENAI_API_KEY,
)
from app.models.provider_setting import ProviderSetting

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# Types
# ═══════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ResolvedModel:
    provider: str
    model_name: str


class ChatProvider(Protocol):
    """Interface for all chat providers.  Messages are dicts with role/content."""

    def invoke(self, messages: List[dict]) -> str: ...

    async def ainvoke(self, messages: List[dict]) -> str: ...

    async def astream(self, messages: List[dict]) -> AsyncIterator[str]: ...


# ═══════════════════════════════════════════════════════════════
# OpenAI-compatible provider (OpenAI, DeepSeek, any compatible API)
# ═══════════════════════════════════════════════════════════════

class OpenAICompatibleProvider:
    """Chat provider for OpenAI and OpenAI-compatible APIs (DeepSeek, etc.).

    Uses the /v1/chat/completions endpoint with streaming SSE support.
    """

    def __init__(
        self,
        model: str,
        api_key: str,
        base_url: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.max_tokens = max_tokens
        self.temperature = temperature

    def _build_payload(self, messages: List[dict], stream: bool = False) -> dict:
        return {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": stream,
        }

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _extract_content(self, response_json: dict) -> str:
        choices = response_json.get("choices", [])
        if choices:
            return choices[0].get("message", {}).get("content", "") or ""
        return ""

    def invoke(self, messages: List[dict]) -> str:
        response = httpx.post(
            f"{self.base_url}/v1/chat/completions",
            headers=self._headers(),
            json=self._build_payload(messages, stream=False),
            timeout=120,
        )
        response.raise_for_status()
        return self._extract_content(response.json())

    async def ainvoke(self, messages: List[dict]) -> str:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{self.base_url}/v1/chat/completions",
                headers=self._headers(),
                json=self._build_payload(messages, stream=False),
            )
            response.raise_for_status()
            return self._extract_content(response.json())

    async def astream(self, messages: List[dict]) -> AsyncIterator[str]:
        """Stream tokens from OpenAI-compatible chat completions SSE."""
        payload = self._build_payload(messages, stream=True)
        async with httpx.AsyncClient(timeout=300) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/v1/chat/completions",
                headers=self._headers(),
                json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[len("data: "):]
                    if not data.strip() or data.strip() == "[DONE]":
                        continue
                    try:
                        event = json.loads(data)
                        choices = event.get("choices", [])
                        if choices:
                            delta = choices[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                    except json.JSONDecodeError:
                        continue


# ═══════════════════════════════════════════════════════════════
# Anthropic provider
# ═══════════════════════════════════════════════════════════════

class AnthropicChatProvider:
    """Chat provider for the Anthropic Messages API.

    Messages are plain dicts with role/content keys.
    """

    def __init__(self, model: str, api_key: str, base_url: str, max_tokens: int = 4096):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.max_tokens = max_tokens

    def _build_payload(self, messages: List[dict], stream: bool = False) -> dict:
        system_parts = []
        anthropic_messages = []

        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")

            if role == "system":
                system_parts.append(content)
            elif role in ("user", "human"):
                anthropic_messages.append({"role": "user", "content": content})
            elif role in ("assistant", "ai"):
                anthropic_messages.append({"role": "assistant", "content": content})

        payload: dict = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": anthropic_messages,
        }
        if stream:
            payload["stream"] = True
        if system_parts:
            payload["system"] = "\n\n".join(system_parts)
        return payload

    @staticmethod
    def _extract_text(response_json: dict) -> str:
        parts = response_json.get("content", [])
        return "".join(
            part.get("text", "") for part in parts if part.get("type") == "text"
        )

    def _headers(self) -> dict:
        return {
            "x-api-key": self.api_key,
            "anthropic-version": ANTHROPIC_API_VERSION,
            "content-type": "application/json",
        }

    def invoke(self, messages: List[dict]) -> str:
        response = httpx.post(
            f"{self.base_url}/v1/messages",
            headers=self._headers(),
            json=self._build_payload(messages, stream=False),
            timeout=120,
        )
        response.raise_for_status()
        return self._extract_text(response.json())

    async def ainvoke(self, messages: List[dict]) -> str:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{self.base_url}/v1/messages",
                headers=self._headers(),
                json=self._build_payload(messages, stream=False),
            )
            response.raise_for_status()
            return self._extract_text(response.json())

    async def astream(self, messages: List[dict]) -> AsyncIterator[str]:
        """Stream tokens from Anthropic Messages API via SSE."""
        payload = self._build_payload(messages, stream=True)
        async with httpx.AsyncClient(timeout=300) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/v1/messages",
                headers=self._headers(),
                json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[len("data: "):]
                    if not data.strip():
                        continue
                    try:
                        event = json.loads(data)
                        if event.get("type") == "content_block_delta":
                            delta = event.get("delta", {})
                            if delta.get("type") == "text_delta":
                                yield delta.get("text", "")
                    except json.JSONDecodeError:
                        continue


# ═══════════════════════════════════════════════════════════════
# Ollama provider
# ═══════════════════════════════════════════════════════════════

class OllamaProvider:
    """Chat provider for Ollama's local chat API.

    Uses /api/chat for messages, /api/generate for structured JSON output.
    """

    def __init__(
        self,
        model: str,
        base_url: str,
        num_predict: int = 2048,
        num_ctx: int = 4096,
        keep_alive: str = "30m",
        temperature: float = 0.7,
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.num_predict = num_predict
        self.num_ctx = num_ctx
        self.keep_alive = keep_alive
        self.temperature = temperature

    def _options(self) -> dict:
        return {
            "temperature": self.temperature,
            "num_predict": self.num_predict,
            "num_ctx": self.num_ctx,
        }

    def _build_payload(self, messages: List[dict], stream: bool = False) -> dict:
        return {
            "model": self.model,
            "messages": messages,
            "stream": stream,
            "options": self._options(),
            "keep_alive": self.keep_alive,
        }

    def invoke(self, messages: List[dict]) -> str:
        response = httpx.post(
            f"{self.base_url}/api/chat",
            json=self._build_payload(messages, stream=False),
            timeout=300,
        )
        response.raise_for_status()
        return response.json().get("message", {}).get("content", "")

    async def ainvoke(self, messages: List[dict]) -> str:
        async with httpx.AsyncClient(timeout=300) as client:
            response = await client.post(
                f"{self.base_url}/api/chat",
                json=self._build_payload(messages, stream=False),
            )
            response.raise_for_status()
            return response.json().get("message", {}).get("content", "")

    async def astream(self, messages: List[dict]) -> AsyncIterator[str]:
        """Stream tokens from Ollama chat API.

        Each SSE line is a JSON object with {"message": {"content": "..."}, "done": false}.
        """
        payload = self._build_payload(messages, stream=True)
        async with httpx.AsyncClient(timeout=300) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/api/chat",
                json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        chunk = json.loads(line)
                        content = chunk.get("message", {}).get("content", "")
                        if content:
                            yield content
                    except json.JSONDecodeError:
                        continue


# ═══════════════════════════════════════════════════════════════
# Structured JSON generation (Ollama-specific path)
# ═══════════════════════════════════════════════════════════════

def _ollama_generate_json_sync(prompt: str, model_name: str) -> str:
    """Generate structured JSON from Ollama — tuned for speed on classification tasks."""
    t0 = time.perf_counter()
    prompt_chars = len(prompt)
    logger.debug("Ollama JSON gen start | model=%s prompt_chars=%d", model_name, prompt_chars)

    response = httpx.post(
        f"{OLLAMA_BASE_URL.rstrip('/')}/api/generate",
        json={
            "model": model_name,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.1,
                "num_predict": 512,
                "num_ctx": 4096,
            },
            "keep_alive": OLLAMA_KEEP_ALIVE,
        },
        timeout=120,
    )
    elapsed = time.perf_counter() - t0
    response.raise_for_status()
    payload = response.json()
    generated = payload.get("response", "")

    if not generated:
        raise ValueError("Ollama returned an empty structured response")

    logger.debug(
        "Ollama JSON gen done  | model=%s elapsed=%.2fs prompt_chars=%d response_chars=%d",
        model_name, elapsed, prompt_chars, len(generated),
    )
    return generated


# ═══════════════════════════════════════════════════════════════
# Model resolution
# ═══════════════════════════════════════════════════════════════

def normalize_model_name(model: str) -> str:
    return str(model or "").strip()


def resolve_model_spec(model: Optional[str] = None) -> ResolvedModel:
    normalized = normalize_model_name(model or DEFAULT_MODEL)
    if "/" in normalized:
        provider, model_name = normalized.split("/", 1)
        provider = provider.lower()
    else:
        provider, model_name = "ollama", normalized

    if provider not in {"ollama", "openai", "anthropic", "deepseek"}:
        provider, model_name = "ollama", normalized

    return ResolvedModel(provider=provider, model_name=model_name)


def get_chat_model(
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    max_tokens: int = 4096,
) -> ChatProvider:
    """Return a chat provider instance.

    Resolution order for credentials:
      1. Runtime overrides (api_key, base_url args) — highest priority
      2. ProviderSetting from database (see settings API)
      3. Environment variables
      4. Hardcoded defaults
    """
    resolved = resolve_model_spec(model)

    if resolved.provider == "ollama":
        return OllamaProvider(
            model=resolved.model_name,
            base_url=base_url or OLLAMA_BASE_URL,
            num_predict=OLLAMA_NUM_PREDICT,
            num_ctx=OLLAMA_NUM_CTX,
            keep_alive=OLLAMA_KEEP_ALIVE,
            temperature=0.7,
        )

    # DeepSeek — OpenAI-compatible API
    if resolved.provider == "deepseek":
        key = api_key or DEEPSEEK_API_KEY
        if not key:
            raise ValueError(
                "DeepSeek API key is not configured. "
                "Set DEEPSEEK_API_KEY in your environment or "
                "provide one via Settings → Add Model."
            )
        return OpenAICompatibleProvider(
            model=resolved.model_name,
            api_key=key,
            base_url=base_url or DEEPSEEK_BASE_URL,
            max_tokens=max_tokens,
        )

    if resolved.provider == "openai":
        key = api_key or OPENAI_API_KEY
        if not key:
            raise ValueError(
                "OpenAI API key is not configured. "
                "Set OPENAI_API_KEY in your environment or "
                "provide one via Settings → Add Model."
            )
        return OpenAICompatibleProvider(
            model=resolved.model_name,
            api_key=key,
            base_url=base_url or "https://api.openai.com",
            max_tokens=max_tokens,
        )

    # Anthropic
    key = api_key or ANTHROPIC_API_KEY
    if not key:
        raise ValueError(
            "Anthropic API key is not configured. "
            "Set ANTHROPIC_API_KEY in your environment or "
            "provide one via Settings → Add Model."
        )
    return AnthropicChatProvider(
        model=resolved.model_name,
        api_key=key,
        base_url=base_url or ANTHROPIC_BASE_URL,
        max_tokens=max_tokens,
    )


# ═══════════════════════════════════════════════════════════════
# Public API — same signatures, no LangChain dependency
# ═══════════════════════════════════════════════════════════════

async def chat_with_model(
    messages: List[dict],
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    max_tokens: int = 4096,
) -> str:
    """Send messages to the chat model and return the full response (async)."""
    provider = get_chat_model(model, api_key=api_key, base_url=base_url, max_tokens=max_tokens)
    return await provider.ainvoke(messages)


def chat_with_model_sync(
    messages: List[dict],
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    max_tokens: int = 4096,
) -> str:
    """Send messages to the chat model and return the full response (sync)."""
    t0 = time.perf_counter()
    resolved = resolve_model_spec(model)
    logger.debug(
        "Chat sync start | provider=%s model=%s msgs=%d",
        resolved.provider, resolved.model_name, len(messages),
    )
    provider = get_chat_model(model, api_key=api_key, base_url=base_url, max_tokens=max_tokens)
    result = provider.invoke(messages)
    elapsed = time.perf_counter() - t0
    logger.debug(
        "Chat sync done  | provider=%s model=%s elapsed=%.2fs response_chars=%d",
        resolved.provider, resolved.model_name, elapsed, len(result),
    )
    return result


async def stream_chat_with_model(
    messages: List[dict],
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    max_tokens: int = 4096,
) -> AsyncIterator[str]:
    """Stream tokens from the chat model as they are generated.

    Yields content chunks for all providers (OpenAI-compatible, Anthropic, Ollama).
    """
    t0 = time.perf_counter()
    resolved = resolve_model_spec(model)
    logger.debug(
        "Stream start | provider=%s model=%s msgs=%d",
        resolved.provider, resolved.model_name, len(messages),
    )
    provider = get_chat_model(model, api_key=api_key, base_url=base_url, max_tokens=max_tokens)

    token_count = 0
    total_chars = 0
    first_token = True

    async for token in provider.astream(messages):
        if first_token:
            ttfb = time.perf_counter() - t0
            logger.debug(
                "Stream TTFB  | provider=%s model=%s ttfb=%.2fs",
                resolved.provider, resolved.model_name, ttfb,
            )
            first_token = False
        token_count += 1
        total_chars += len(token)
        yield token

    elapsed = time.perf_counter() - t0
    logger.debug(
        "Stream done  | provider=%s model=%s elapsed=%.2fs tokens=%d chars=%d",
        resolved.provider, resolved.model_name, elapsed, token_count, total_chars,
    )


def generate_structured_json_sync(prompt: str, model: Optional[str] = None) -> str:
    """Generate structured output, optionally using a dedicated classification model.

    For Ollama, uses the /api/generate endpoint with format=json for reliability.
    For other providers, uses the standard chat completion API.
    """
    effective_model = model or CLASSIFICATION_MODEL or DEFAULT_MODEL
    resolved = resolve_model_spec(effective_model)

    if resolved.provider == "ollama":
        return _ollama_generate_json_sync(prompt, resolved.model_name)

    return chat_with_model_sync([{"role": "user", "content": prompt}], model=model)


# ═══════════════════════════════════════════════════════════════
# Credentials & model options
# ═══════════════════════════════════════════════════════════════

def resolve_credentials(
    db: Session,
    model: str,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """Resolve API key and base URL for a model.

    Resolution order: explicit args → ProviderSetting in DB → env var / default.
    """
    resolved = resolve_model_spec(model)
    if not api_key or not base_url:
        db_setting = db.query(ProviderSetting).filter(
            ProviderSetting.provider == resolved.provider
        ).first()
        if db_setting:
            if not api_key and db_setting.api_key:
                api_key = db_setting.api_key
            if not base_url and db_setting.base_url:
                base_url = db_setting.base_url
    return api_key, base_url


def get_model_options() -> List[Tuple[str, str]]:
    return [
        ("deepseek/deepseek-chat", "DeepSeek · DeepSeek-Chat"),
        ("deepseek/deepseek-reasoner", "DeepSeek · DeepSeek-Reasoner"),
        ("ollama/llama3.2:1b", "Ollama · llama3.2:1b"),
        ("openai/gpt-4o-mini", "OpenAI · gpt-4o-mini"),
        ("anthropic/claude-3-5-sonnet-latest", "Anthropic · claude-3-5-sonnet-latest"),
    ]
