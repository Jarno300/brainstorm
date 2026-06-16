import json
import time
import logging
from dataclasses import dataclass
from typing import AsyncIterator, List, Optional, Protocol, Tuple

import httpx
from langchain_community.chat_models import ChatOllama
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
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


@dataclass(frozen=True)
class ResolvedModel:
    provider: str
    model_name: str


class ChatProvider(Protocol):
    async def ainvoke(self, messages: List):
        ...

    def invoke(self, messages: List):
        ...


class AnthropicResponse:
    def __init__(self, content: str):
        self.content = content


class AnthropicChatProvider:
    def __init__(self, model: str, api_key: str, base_url: str, max_tokens: int = 4096):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.max_tokens = max_tokens

    def _build_payload(self, messages: List) -> dict:
        system_parts = []
        anthropic_messages = []

        for message in messages:
            role = getattr(message, "type", None) or message.get("role")
            content = getattr(message, "content", None) if not isinstance(message, dict) else message.get("content")
            if role == "system":
                system_parts.append(content)
                continue

            if role in {"human", "user"}:
                anthropic_messages.append({"role": "user", "content": content})
                continue

            if role in {"ai", "assistant"}:
                anthropic_messages.append({"role": "assistant", "content": content})
                continue

            if role not in {"user", "assistant"}:
                continue

        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": anthropic_messages,
        }
        if system_parts:
            payload["system"] = "\n\n".join(system_parts)
        return payload

    def _extract_text(self, response_json: dict) -> str:
        parts = response_json.get("content", [])
        return "".join(part.get("text", "") for part in parts if part.get("type") == "text")

    def invoke(self, messages: List[dict]):
        response = httpx.post(
            f"{self.base_url}/v1/messages",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": ANTHROPIC_API_VERSION,
                "content-type": "application/json",
            },
            json=self._build_payload(messages),
            timeout=120,
        )
        response.raise_for_status()
        return AnthropicResponse(self._extract_text(response.json()))

    async def ainvoke(self, messages: List[dict]):
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{self.base_url}/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": ANTHROPIC_API_VERSION,
                    "content-type": "application/json",
                },
                json=self._build_payload(messages),
            )
            response.raise_for_status()
            return AnthropicResponse(self._extract_text(response.json()))

    async def astream(self, messages: List[dict]) -> AsyncIterator[str]:
        """Stream tokens from Anthropic Messages API via SSE."""
        payload = self._build_payload(messages)
        payload["stream"] = True
        async with httpx.AsyncClient(timeout=300) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": ANTHROPIC_API_VERSION,
                    "content-type": "application/json",
                },
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


def _ollama_generate_json_sync(prompt: str, model_name: str) -> str:
    """Generate structured JSON from Ollama — tuned for speed on classification."""
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
                "num_predict": 512,       # classification responses are short
                "num_ctx": 4096,           # enough for the prompt + response
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
    logger.debug("Ollama JSON gen done  | model=%s elapsed=%.2fs prompt_chars=%d response_chars=%d",
                 model_name, elapsed, prompt_chars, len(generated))
    return generated


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
):
    """Return a chat provider instance.

    Resolution order for credentials:
      1. Runtime overrides (api_key, base_url args) — highest priority
      2. ProviderSetting from database (see settings API)
      3. Environment variables
      4. Hardcoded defaults

    max_tokens is used by Anthropic (required) and optionally by OpenAI.
    For Ollama, OLLAMA_NUM_PREDICT env var controls the default.
    """
    resolved = resolve_model_spec(model)

    if resolved.provider == "ollama":
        return ChatOllama(
            model=resolved.model_name,
            base_url=base_url or OLLAMA_BASE_URL,
            temperature=0.7,
            num_predict=OLLAMA_NUM_PREDICT,
            num_ctx=OLLAMA_NUM_CTX,
            keep_alive=OLLAMA_KEEP_ALIVE,
        )

    # DeepSeek — OpenAI-compatible API, uses ChatOpenAI with custom base URL
    if resolved.provider == "deepseek":
        key = api_key or DEEPSEEK_API_KEY
        if not key:
            raise ValueError(
                "DeepSeek API key is not configured. "
                "Set DEEPSEEK_API_KEY in your environment or "
                "provide one via Settings → Add Model."
            )
        return ChatOpenAI(
            model=resolved.model_name,
            api_key=key,
            base_url=base_url or DEEPSEEK_BASE_URL,
            temperature=0.7,
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
        kwargs = {"model": resolved.model_name, "api_key": key, "temperature": 0.7, "max_tokens": max_tokens}
        if base_url:
            kwargs["base_url"] = base_url
        return ChatOpenAI(**kwargs)

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


def convert_messages_to_langchain(messages: List[dict]) -> List:
    lc_messages = []
    for msg in messages:
        if msg["role"] == "user":
            lc_messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            lc_messages.append(AIMessage(content=msg["content"]))
        elif msg["role"] == "system":
            lc_messages.append(SystemMessage(content=msg["content"]))
    return lc_messages


async def chat_with_model(
    messages: List[dict],
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    max_tokens: int = 4096,
) -> str:
    chat_model = get_chat_model(model, api_key=api_key, base_url=base_url, max_tokens=max_tokens)
    lc_messages = convert_messages_to_langchain(messages)
    response = await chat_model.ainvoke(lc_messages)
    return response.content


def chat_with_model_sync(
    messages: List[dict],
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    max_tokens: int = 4096,
) -> str:
    t0 = time.perf_counter()
    resolved = resolve_model_spec(model)
    logger.debug("Chat sync start | provider=%s model=%s msgs=%d",
                 resolved.provider, resolved.model_name, len(messages))
    chat_model = get_chat_model(model, api_key=api_key, base_url=base_url, max_tokens=max_tokens)
    lc_messages = convert_messages_to_langchain(messages)
    response = chat_model.invoke(lc_messages)
    elapsed = time.perf_counter() - t0
    resp_len = len(response.content) if hasattr(response, 'content') else 0
    logger.debug("Chat sync done  | provider=%s model=%s elapsed=%.2fs response_chars=%d",
                 resolved.provider, resolved.model_name, elapsed, resp_len)
    return response.content


async def stream_chat_with_model(
    messages: List[dict],
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    max_tokens: int = 4096,
) -> AsyncIterator[str]:
    """Stream tokens from the chat model as they are generated.

    Yields content chunks for all providers:
    - Ollama / OpenAI / DeepSeek: uses LangChain astream()
    - Anthropic: uses custom SSE streaming
    """
    t0 = time.perf_counter()
    resolved = resolve_model_spec(model)
    logger.debug("Stream start | provider=%s model=%s msgs=%d",
                 resolved.provider, resolved.model_name, len(messages))
    chat_model = get_chat_model(model, api_key=api_key, base_url=base_url, max_tokens=max_tokens)
    lc_messages = convert_messages_to_langchain(messages)
    token_count = 0
    first_token = True

    # Anthropic uses its own streaming implementation
    if isinstance(chat_model, AnthropicChatProvider):
        async for token in chat_model.astream(lc_messages):
            if first_token:
                ttfb = time.perf_counter() - t0
                logger.debug("Stream TTFB  | provider=%s model=%s ttfb=%.2fs",
                             resolved.provider, resolved.model_name, ttfb)
                first_token = False
            token_count += 1
            yield token
        elapsed = time.perf_counter() - t0
        logger.debug("Stream done  | provider=%s model=%s elapsed=%.2fs tokens=%d chars=%d",
                     resolved.provider, resolved.model_name, elapsed, token_count, sum(1 for _ in ""))
        return

    # LangChain providers (Ollama, OpenAI) support astream() natively
    total_chars = 0
    async for chunk in chat_model.astream(lc_messages):
        content = chunk.content if hasattr(chunk, "content") else ""
        if content:
            if first_token:
                ttfb = time.perf_counter() - t0
                logger.debug("Stream TTFB  | provider=%s model=%s ttfb=%.2fs",
                             resolved.provider, resolved.model_name, ttfb)
                first_token = False
            token_count += 1
            total_chars += len(content)
            yield content
    elapsed = time.perf_counter() - t0
    logger.debug("Stream done  | provider=%s model=%s elapsed=%.2fs tokens=%d chars=%d",
                 resolved.provider, resolved.model_name, elapsed, token_count, total_chars)


def generate_structured_json_sync(prompt: str, model: Optional[str] = None) -> str:
    """Generate structured output, optionally using a dedicated classification model."""
    effective_model = model or CLASSIFICATION_MODEL or DEFAULT_MODEL
    resolved = resolve_model_spec(effective_model)

    if resolved.provider == "ollama":
        return _ollama_generate_json_sync(prompt, resolved.model_name)

    return chat_with_model_sync([{"role": "user", "content": prompt}], model=model)


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
