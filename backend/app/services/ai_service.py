import json
from dataclasses import dataclass
from typing import List, Optional, Protocol, Tuple

import httpx
from langchain_community.chat_models import ChatOllama
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from app.config import (
    ANTHROPIC_API_KEY,
    ANTHROPIC_BASE_URL,
    DEFAULT_MODEL,
    OPENAI_API_KEY,
    OLLAMA_BASE_URL,
)


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
    def __init__(self, model: str, api_key: str, base_url: str):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

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
            "max_tokens": 1024,
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
                "anthropic-version": "2023-06-01",
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
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json=self._build_payload(messages),
            )
            response.raise_for_status()
            return AnthropicResponse(self._extract_text(response.json()))


def _ollama_generate_json_sync(prompt: str, model_name: str) -> str:
    response = httpx.post(
        f"{OLLAMA_BASE_URL.rstrip('/')}/api/generate",
        json={
            "model": model_name,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.2,
            },
        },
        timeout=120,
    )
    response.raise_for_status()
    payload = response.json()
    generated = payload.get("response", "")
    if not generated:
        raise ValueError("Ollama returned an empty structured response")
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

    if provider not in {"ollama", "openai", "anthropic"}:
        provider, model_name = "ollama", normalized

    return ResolvedModel(provider=provider, model_name=model_name)


def get_chat_model(
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
):
    """Return a chat provider instance.

    Resolution order for credentials:
      1. Runtime overrides (api_key, base_url args) — highest priority
      2. ProviderSetting from database (see settings API)
      3. Environment variables
      4. Hardcoded defaults
    """
    resolved = resolve_model_spec(model)

    if resolved.provider == "ollama":
        return ChatOllama(
            model=resolved.model_name,
            base_url=base_url or OLLAMA_BASE_URL,
            temperature=0.7,
        )

    if resolved.provider == "openai":
        key = api_key or OPENAI_API_KEY
        if not key:
            raise ValueError(
                "OpenAI API key is not configured. "
                "Set OPENAI_API_KEY in your environment or "
                "provide one via Settings → Add Model."
            )
        kwargs = {"model": resolved.model_name, "api_key": key, "temperature": 0.7}
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
) -> str:
    chat_model = get_chat_model(model, api_key=api_key, base_url=base_url)
    lc_messages = convert_messages_to_langchain(messages)
    response = await chat_model.ainvoke(lc_messages)
    return response.content


def chat_with_model_sync(
    messages: List[dict],
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
) -> str:
    chat_model = get_chat_model(model, api_key=api_key, base_url=base_url)
    lc_messages = convert_messages_to_langchain(messages)
    response = chat_model.invoke(lc_messages)
    return response.content


def generate_structured_json_sync(prompt: str, model: Optional[str] = None) -> str:
    resolved = resolve_model_spec(model)

    if resolved.provider == "ollama":
        return _ollama_generate_json_sync(prompt, resolved.model_name)

    return chat_with_model_sync([{"role": "user", "content": prompt}], model=model)


def get_model_options() -> List[Tuple[str, str]]:
    return [
        ("ollama/llama3.2:1b", "Ollama · llama3.2:1b"),
        ("openai/gpt-4o-mini", "OpenAI · gpt-4o-mini"),
        ("anthropic/claude-3-5-sonnet-latest", "Anthropic · claude-3-5-sonnet-latest"),
    ]
